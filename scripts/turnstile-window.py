#!/usr/bin/env python3
"""turnstile-window.py — the Turnstile window on the SWAPPED Main copy, as one committed script.

Why it exists (PHASE-7-PLAN, re-entry ruling, premise 3): the regression suite drives Main with curl and a dummy
Turnstile token, so it can only run while Main's gate is lowered. After the cutover Main's production holder is its
COPY, and lowering that copy's gate is a production act. The D6b smoke ran it from a scratchpad driver; this is the
same sequence, committed, so the next window is the reviewed one and not a re-typed one.

ORDER — every live step is read back, and nothing below runs on import or with --selftest:
  PRE  (read-only; any red → exit 2, nothing touched):
       · ROLES (scripts/check-exports-parity.sh, read through scripts/pair_roles.py — one parser) has the pair for the
         spec's original, and it declares the COPY live; the deploy helper's own order guard (check_swap_declared)
         agrees, with the original read back INACTIVE;
       · the copy is ACTIVE, named as the spec, and is the ONE active holder of the original's production path
         (pair_roles.holder); its PUBLISHED trigger is on that path;
       · its published AND draft Load Config hold exactly one Turnstile literal, and it reads true;
       · the deploy helper's pure --turnstile-swapped checks ('off' and 'on', swap phase) are GREEN on the live
         content, so the helper will not refuse half-way through an opened window;
       · a dummy token to the production path answers 403 turnstile_failed, executed by the copy, none by the original.
  OPEN : deactivate the copy → `deploy-workflow-copy.py <spec> --original-id O --turnstile-swapped off C` → activate.
  RUN  : the caller's command, under a hard timeout (its whole process group is stopped at the limit).
  CLOSE (in `finally`, also on a failed/timed-out/raising command, Ctrl-C or SIGTERM/SIGHUP; the close itself ignores
        those signals, so a second Ctrl-C cannot leave the gate half-restored):
       deactivate the copy → read the DRAFT literal → `--turnstile-swapped on` ONLY if it reads false → re-activate
       ONLY if the draft literal then reads true → measure both ways: published literal true AND a dummy token 403.
       ⚠ The gate is restored here, BEFORE anything else: this script never activates the original. Once the original
       is active again the helper's order guard refuses 'on', and a parked copy would keep a lowered literal — so if
       you roll back after a SAFETY exit, restore the literal first (this script's close, or the helper's 'on' while the
       original is still inactive) and only then re-activate the original.
  Prints the window's open/close UTC and its duration. Never prints a host, a key, a token or a full workflow id.

Exit: 0 command green and Turnstile restored · 1 command failed or timed out, Turnstile restored ·
      2 refused before anything was touched (a precheck red, or usage) · 3 SAFETY: Turnstile NOT proven restored.

Usage (env: N8N_API_KEY, CF_ACCESS_CLIENT_ID/SECRET; N8N_HOST or CLAUDE.local.md's N8N_HOST line):
  python3 scripts/turnstile-window.py [--spec db/copies/main.json] [--timeout SECONDS] -- COMMAND [ARG ...]
  python3 scripts/turnstile-window.py [--spec db/copies/main.json] --precheck-only
  python3 scripts/turnstile-window.py --selftest          (offline: no network call, asserted)
"""
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SPEC = 'db/copies/main.json'
ROLES_FILE = None          # None = pair_roles' default, the committed check-exports-parity.sh (tests point it at a fixture)
HELPER = None              # None = ROOT/scripts/deploy-workflow-copy.py (tests point it at a fake)
DUMMY_TOKEN = 'XXXX.DUMMY.TOKEN.XXXX'   # Cloudflare's documented always-fail test token: not a secret
PROBE_WAIT_S = 5           # an execution appears in the API a few seconds after the webhook answers
ACTIVATE_WAIT_S = 3        # a webhook registers a moment after activation
DEFAULT_TIMEOUT_S = 420
MAX_TIMEOUT_S = 1500
HELPER_TIMEOUT_S = 300


class Refused(Exception):
    """A precheck is red: the window is not opened and nothing has been touched."""


class Interrupted(BaseException):
    """SIGTERM/SIGHUP while the window is open: raised so that `finally` still closes it."""


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HELPER_MOD = None


def helper_module():
    """The deploy helper's OWN pure checks and its Turnstile literal regex: one rule, not a copy of it."""
    global _HELPER_MOD
    if _HELPER_MOD is None:
        _HELPER_MOD = _module('scripts/deploy-workflow-copy.py', 'deploy_workflow_copy')
    _HELPER_MOD.ROLES_FILE = ROLES_FILE
    return _HELPER_MOD


def short(wid):
    return (wid or '????')[:4] + '…'


def utc():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())


# ── HTTP: the real curl (urllib is refused at the edge); secrets in a 0600 header file, never on argv ─────────────
def _host():
    h = os.environ.get('N8N_HOST')
    if not h:
        try:
            src = open(os.path.join(ROOT, 'CLAUDE.local.md'), encoding='utf-8').read()
        except OSError:
            src = ''
        m = re.search(r'^N8N_HOST=\s*(\S+)', src, re.M)
        h = m.group(1) if m else None
    if not h:
        raise Refused('N8N_HOST is not set and CLAUDE.local.md has none')
    return h


def _base():
    return (os.environ.get('N8N_API_URL') or f'https://{_host()}').rstrip('/')


def curl(method, url, headers, body=None):
    """(status, parsed body, lower-cased response header names)."""
    tmp = []
    try:
        fd, hpath = tempfile.mkstemp(suffix='.hdr'); tmp.append(hpath)      # mkstemp: mode 0600
        with os.fdopen(fd, 'w') as f:
            f.write(''.join(f'{k}: {v}\n' for k, v in headers.items()))
        fd, opath = tempfile.mkstemp(suffix='.out'); os.close(fd); tmp.append(opath)
        fd, dpath = tempfile.mkstemp(suffix='.resp'); os.close(fd); tmp.append(dpath)
        args = ['curl', '-4', '-s', '-m', '60', '-X', method, '-o', opath, '-D', dpath, '-w', '%{http_code}',
                url, '-H', '@' + hpath]
        if body is not None:
            fd, bpath = tempfile.mkstemp(suffix='.json'); tmp.append(bpath)
            with os.fdopen(fd, 'w') as f:
                json.dump(body, f)
            args += ['--data-binary', '@' + bpath]
        code = subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
        raw = open(opath, encoding='utf-8', errors='replace').read()
        names = [l.split(':', 1)[0].strip().lower() for l in open(dpath, encoding='utf-8', errors='replace')
                 if ':' in l]
    finally:
        for p in tmp:
            os.unlink(p)
    try:
        status = int(code)
    except ValueError:
        status = 0
    try:
        return status, json.loads(raw), names
    except ValueError:
        return status, raw, names


def api(method, path, body=None):
    hdr = {'X-N8N-API-KEY': os.environ.get('N8N_API_KEY', ''), 'Content-Type': 'application/json',
           'CF-Access-Client-Id': os.environ.get('CF_ACCESS_CLIENT_ID', ''),
           'CF-Access-Client-Secret': os.environ.get('CF_ACCESS_CLIENT_SECRET', '')}
    st, d, _ = curl(method, f'{_base()}/api/v1{path}', hdr, body)
    return st, d


def webhook(path, body):
    """The PUBLIC production path: no API key and no Access token ever travel on it."""
    st, d, _ = curl('POST', f'{_base()}/webhook/{path}', {'Content-Type': 'application/json'}, body)
    return st, d


# ── reads ────────────────────────────────────────────────────────────────────────────────────────────────────
def wf_get(wid):
    st, d = api('GET', f'/workflows/{wid}')
    if st != 200 or not isinstance(d, dict):
        raise Refused(f'GET workflow {short(wid)} answered {st}')
    return d


def draft(d):
    return {k: d.get(k) for k in ('name', 'nodes', 'connections', 'settings')}


def published_nodes(d):
    return (d.get('activeVersion') or {}).get('nodes') or []


def literal(nodes):
    X = helper_module()
    code = next((n for n in nodes or [] if n.get('name') == X.TS_NODE), {}).get('parameters', {}).get('jsCode', '')
    return X.TS_LITERAL.findall(code)


def trigger_path(nodes, name):
    return (next((n for n in nodes or [] if n.get('name') == name), {}).get('parameters') or {}).get('path')


def executions_since(wid, since):
    st, d = api('GET', f'/executions?workflowId={wid}&limit=100')
    if st != 200 or not isinstance(d, dict):
        raise Refused(f'GET executions {short(wid)} answered {st}')
    return sum(1 for e in d.get('data') or [] if (e.get('startedAt') or '') >= since)


def set_active(wid, on):
    st, _ = api('POST', f"/workflows/{wid}/{'activate' if on else 'deactivate'}")
    got = wf_get(wid).get('active') is True
    print(f"  {'activate' if on else 'deactivate'} copy {short(wid)}: [{st}] · read back active {got}")
    return got is on


def dummy_probe(path, o, c):
    """A dummy token to the production path: must be 403 turnstile_failed, run by the copy, none by the original."""
    since = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    t = int(time.time())
    st, body = webhook(path, {'channel': 'widget', 'sessionId': 'w-mig-p7-ts-probe', 'text': 'hi',
                              'messageId': f'mig-p7-ts-{t}', 'turnstileToken': DUMMY_TOKEN})
    err = body.get('error') if isinstance(body, dict) else None
    time.sleep(PROBE_WAIT_S)
    ec, eo = executions_since(c, since), executions_since(o, since)
    ok = st == 403 and err == 'turnstile_failed' and ec >= 1 and eo == 0
    print(f"  dummy token → {st} {err} · copy executions {ec} · original executions {eo} · {'OK' if ok else 'RED'}")
    return ok, st


# ── which pair: ROLES through pair_roles (one parser) ─────────────────────────────────────────────────────────
def resolve(spec):
    pr = _module('scripts/pair_roles.py', 'pair_roles')
    try:
        pairs, roles = pr.load(ROLES_FILE)
    except (ValueError, OSError) as e:
        raise Refused(f'ROLES does not read ({e})')
    hit = [r for r in roles if pairs.get(r['orig']) == spec['original']]
    if len(hit) != 1:
        raise Refused(f"{len(hit)} ROLES lines name the original export {spec['original']} (exactly one must)")
    return hit[0], pairs


def precheck(spec_path):
    spec = json.load(open(os.path.join(ROOT, spec_path), encoding='utf-8'))
    trig = (spec.get('trigger') or {}).get('node')
    if not trig:
        raise Refused('the spec names no webhook trigger, so there is no production path to open a window on')
    role, pairs = resolve(spec)
    o, c = role['orig'], role['copy']
    if role['live'] != 'copy':
        raise Refused(f"ROLES declares the {role['live']} live for {short(o)}/{short(c)}: the swap is not declared")
    print(f'  ✓ ROLES declares the copy live (pair {short(o)}/{short(c)})')
    od, cd = wf_get(o), wf_get(c)
    X = helper_module()
    why = X.check_swap_declared(o, c, od.get('active'))
    if why:
        raise Refused(f"the deploy helper's order guard refuses: {why}")
    print('  ✓ the original reads back INACTIVE (the helper\'s order guard agrees)')
    if cd.get('active') is not True or cd.get('name') != spec['name']:
        raise Refused(f"the copy must be the ACTIVE workflow named '{spec['name']}'")
    prod = trigger_path(od.get('nodes'), trig)
    st, listed = api('GET', '/workflows?limit=250')
    if st != 200 or not isinstance(listed, dict):
        raise Refused(f'GET workflows answered {st}')
    pr = _module('scripts/pair_roles.py', 'pair_roles')
    try:
        holder, _ = pr.holder(listed.get('data') or [], prod, pairs)
    except ValueError as e:
        raise Refused(f'production path: {e}')
    if holder != c or trigger_path(published_nodes(cd), trig) != prod:
        raise Refused("the copy is not the published holder of the original's production path")
    print(f"  ✓ the copy is ACTIVE, named as the spec, and the one published holder of the production path")
    pub, dr = literal(published_nodes(cd)), literal(cd.get('nodes'))
    if pub != ['true'] or dr != ['true']:
        raise Refused(f'the Turnstile literal is not true on the copy (published {pub}, draft {dr})')
    print('  ✓ published and draft Turnstile literal: true')
    try:
        gen = X.BUILD.build(spec)
        lo, lc = draft(od), draft(cd)
        off = X.turnstile_check(lo, X.turnstile_patch(lc, 'off'), gen, spec, 'off', 'swap')
        on = X.turnstile_check(lo, lc, gen, spec, 'on', 'swap')
    except (ValueError, KeyError, StopIteration) as e:
        off = on = [f'{type(e).__name__}: {e}']
    if off or on:
        raise Refused("the deploy helper's --turnstile-swapped checks are predicted RED on the live copy: "
                      + '; '.join((off + on)[:3]))
    print("  ✓ the helper's --turnstile-swapped off/on checks predicted GREEN on the live content")
    ok, _ = dummy_probe(prod, o, c)
    if not ok:
        raise Refused('the production path does not answer a dummy token 403 through the copy')
    return {'spec_path': spec_path, 'spec': spec, 'o': o, 'c': c, 'path': prod}


# ── the helper, run for real (the same binary the operator would type) ───────────────────────────────────────
def run_helper(ctx, state):
    path = HELPER or os.path.join(ROOT, 'scripts', 'deploy-workflow-copy.py')
    cmd = [sys.executable, path, ctx['spec_path'], '--original-id', ctx['o'], '--turnstile-swapped', state, ctx['c']]
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                             timeout=HELPER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f'  helper --turnstile-swapped {state}: TIMED OUT')
        return None
    for line in mask(out.stdout + out.stderr, ctx).strip().splitlines()[-12:]:
        print('  helper: ' + line)
    return out.returncode


def mask(text, ctx):
    for wid in (ctx.get('o'), ctx.get('c')):
        if wid:
            text = text.replace(wid, short(wid))
    try:
        text = text.replace(_host(), '<host>')
    except Refused:
        pass
    return text


# ── the caller's command, under a hard timeout ────────────────────────────────────────────────────────────────
def run_command(cmd, timeout):
    """Its exit code, or 'timeout'. The command gets its own session, so at the limit (or on any exception) its
    whole process group is stopped — by the group id of the child this function started, never by a name pattern."""
    p = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        return p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_group(p)
        return 'timeout'
    except BaseException:
        _stop_group(p)
        raise


def _stop_group(p):
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            return
        try:
            p.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


# ── open / close ─────────────────────────────────────────────────────────────────────────────────────────────
def open_window(ctx):
    """True when the copy is active with its gate lowered. False leaves the close to `finally`."""
    if not set_active(ctx['c'], False):
        print('  ✗ the copy did not deactivate: window not opened')
        return False
    rc = run_helper(ctx, 'off')
    if rc != 0:
        print(f'  ✗ helper --turnstile-swapped off exit {rc}: window not opened')
        return False
    if not set_active(ctx['c'], True):
        print('  ✗ the copy did not activate with Turnstile off')
        return False
    time.sleep(ACTIVATE_WAIT_S)
    return True


def close_decision(draft_before, rc_on, draft_after):
    """Pure: (run 'on'?, re-activate?). 'on' only on a draft that reads false; re-activation only on a draft that
    then reads exactly one literal, true, with a clean helper exit (or nothing to restore)."""
    run_on = draft_before == ['false']
    if run_on:
        reactivate = rc_on == 0 and draft_after == ['true']
    else:
        reactivate = draft_before == ['true']
    return run_on, reactivate


def close_window(ctx):
    """Always runs. Returns True only when Turnstile is MEASURED restored on an active copy."""
    c = ctx['c']
    try:
        set_active(c, False)
    except Refused as e:
        print(f'  ✗ deactivate during close failed: {e}')
    try:
        before = literal(wf_get(c).get('nodes'))
    except Refused as e:
        print(f'  ✗ the draft literal could not be read: {e}')
        return False
    rc_on, after = None, before
    run_on, _ = close_decision(before, None, None)
    if run_on:
        rc_on = run_helper(ctx, 'on')
        after = literal(wf_get(c).get('nodes'))
    else:
        print(f"  draft literal {before} before restoring: {'nothing to restore' if before == ['true'] else 'NOT ONE LITERAL'}")
    _, reactivate = close_decision(before, rc_on, after)
    if not reactivate:
        print(f'  ✗ Turnstile NOT restored (draft literal {after}, helper on exit {rc_on}) — the copy stays INACTIVE')
        return False
    if not set_active(c, True):
        print('  ✗ the copy did not re-activate after the restore')
        return False
    time.sleep(ACTIVATE_WAIT_S)
    pub = literal(published_nodes(wf_get(c)))
    ok, code = dummy_probe(ctx['path'], ctx['o'], c)
    if pub != ['true'] or code == 200:
        # The gate is demonstrably open on production: stop the copy rather than serve the brain without Turnstile.
        print(f'  ✗ published literal {pub}, dummy token {code}: the gate is OPEN — deactivating the copy')
        set_active(c, False)
        return False
    if not ok:
        print(f'  ✗ published literal true but the dummy token answered {code}: restore NOT proven (copy left active)')
        return False
    print('  ✓ restored: published literal true · dummy token 403')
    return True


def _raise_interrupted(signum, _frame):
    raise Interrupted(signal.Signals(signum).name)


def window(spec_path, cmd, timeout):
    try:
        ctx = precheck(spec_path)
    except Refused as e:
        print(f'REFUSED before anything was touched: {mask(str(e), {})}')
        return 2
    old = {s: signal.signal(s, _raise_interrupted) for s in (signal.SIGTERM, signal.SIGHUP)}
    t_open, result, restored = time.time(), None, False
    print(f'WINDOW OPEN {utc()} UTC · copy {short(ctx["c"])} · command timeout {timeout} s')
    try:
        if open_window(ctx):
            result = run_command(cmd, timeout)
            print(f'  command finished: {result}')
        else:
            result = 'not run'
    except BaseException as e:            # noqa: B902 — reported, then the window is closed below, then re-raised
        result = f'raised {type(e).__name__}'
        print(f'  command step raised {type(e).__name__}: {mask(str(e), ctx)[:160]}')
    finally:
        # The close is not interruptible: a second Ctrl-C/SIGTERM must not leave the gate half-restored. It is
        # bounded anyway: curl's 60 s per call and the helper's HELPER_TIMEOUT_S.
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            old.setdefault(s, signal.getsignal(s))
            signal.signal(s, signal.SIG_IGN)
        try:
            restored = close_window(ctx)
        except BaseException as e:        # the close must report even when a read fails half-way
            print(f'  ✗ close raised {type(e).__name__}: {mask(str(e), ctx)[:160]}')
            restored = False
        t_close = time.time()
        print(f'WINDOW CLOSED {utc()} UTC · {t_close - t_open:.0f} s · command: {result}')
        for s, h in old.items():
            signal.signal(s, h)
    if not restored:
        print('SAFETY: Turnstile is NOT proven restored on the Main copy. Restore the literal FIRST (re-run this '
              "script's close by hand: deploy-workflow-copy.py --turnstile-swapped on, with the original still "
              'inactive), and only then decide on any rollback. This script did not touch the original.')
        return 3
    return 0 if result == 0 else 1


# ── selftest: offline, and it proves it made no call ──────────────────────────────────────────────────────────
def selftest():
    global api, webhook, ROLES_FILE
    real = (api, webhook, ROLES_FILE)
    calls = []
    api = lambda *a, **k: calls.append(a) or (599, {})
    webhook = lambda *a, **k: calls.append(a) or (599, {})
    ok = True
    fixtures = []
    try:
        for before, rc_on, after, want in ((['false'], 0, ['true'], (True, True)),
                                           (['false'], 1, ['false'], (True, False)),
                                           (['false'], 0, ['false'], (True, False)),
                                           (['false'], None, ['true'], (True, False)),
                                           (['true'], None, ['true'], (False, True)),
                                           ([], None, [], (False, False)),
                                           (['true', 'true'], None, None, (False, False))):
            got = close_decision(before, rc_on, after)
            good = got == want
            ok = ok and good
            print(f"{'✓' if good else '✗'} close_decision(draft {before}, helper on {rc_on}, after {after}) → "
                  f"run on {got[0]}, re-activate {got[1]}")
        for line, want in (('O1:C1:copy', 'copy'), ('O1:C1:original', 'original')):
            with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as t:
                t.write('PAIRS=(\n  "O1:n8n/workflow.sanitized.json"\n  "C1:n8n/workflow.main.copy.sanitized.json"\n)\n\n'
                        f'ROLES=(\n  "{line}"\n)\n')
            fixtures.append(t.name)
            ROLES_FILE = t.name
            role, _ = resolve({'original': 'n8n/workflow.sanitized.json'})
            good = (role['orig'], role['copy'], role['live']) == ('O1', 'C1', want)
            ok = ok and good
            print(f"{'✓' if good else '✗'} resolve() through pair_roles: ROLES '{line}' → live {role['live']}")
        good = mask('wf O1 and C1 at x', {'o': 'O1', 'c': 'C1'}).count('…') == 2
        ok = ok and good
        print(f"{'✓' if good else '✗'} ids are cut to four characters in helper output")
    finally:
        api, webhook, ROLES_FILE = real
        for p in fixtures:
            os.unlink(p)
    good = not calls
    ok = ok and good
    print(f"{'✓' if good else '✗'} no network call during the selftest ({len(calls)})")
    print('turnstile-window selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    args = argv[1:]
    if args[:1] == ['--selftest']:
        return selftest()
    cmd = []
    if '--' in args:
        i = args.index('--')
        args, cmd = args[:i], args[i + 1:]
    spec_path, timeout, pre_only = DEFAULT_SPEC, DEFAULT_TIMEOUT_S, False
    while args:
        a = args.pop(0)
        if a == '--spec' and args:
            spec_path = args.pop(0)
        elif a == '--timeout' and args and args[0].isdigit():
            timeout = int(args.pop(0))
        elif a == '--precheck-only':
            pre_only = True
        else:
            print(__doc__)
            return 2
    if not 1 <= timeout <= MAX_TIMEOUT_S:
        print(f'turnstile-window: --timeout must be 1..{MAX_TIMEOUT_S} seconds')
        return 2
    if pre_only:
        try:
            precheck(spec_path)
        except Refused as e:
            print(f'REFUSED: {mask(str(e), {})}')
            return 2
        print('precheck GREEN — nothing was touched')
        return 0
    if not cmd:
        print('turnstile-window: no command after `--` (use --precheck-only to only measure)')
        return 2
    return window(spec_path, cmd, timeout)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
