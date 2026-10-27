#!/usr/bin/env python3
"""deploy-workflow-copy.py — the shared library for a live n8n workflow judged by its committed export, and the ONE
write it still makes itself: lowering or restoring the Main workflow's Turnstile literal for a window.

Since D6c (2026-10-27) each production workflow has one id and one committed export, listed together in
scripts/check-exports-parity.sh's WORKFLOWS (parsed by scripts/workflows.py); its spec db/copies/<key>.json holds only
the settings a live workflow may carry beyond its export. The migration's build / verify / swap modes, the
copy↔original comparison and the disabled --engine-edit / --restore path are gone; their history is in
docs/MIGRATION-PLAN.md and docs/PHASE-7-PLAN.md. Engine edits go through scripts/workflow-step.py, which imports this
module for: content_drift, fill_by_path, committed_export, the Turnstile literal helpers, api / _read / _draft and
check_not_sanitised.

  python3 scripts/deploy-workflow-copy.py db/copies/<key>.json --turnstile-swapped off|on WORKFLOW_ID
      The Turnstile window's write (called by scripts/turnstile-window.py, which deactivates the workflow first and
      re-activates it after). Refused before any write unless WORKFLOW_ID is the id WORKFLOWS lists for <key>, it reads
      back INACTIVE (a PUT to an active workflow publishes at once) and it is named exactly as its committed export.
      window_check judges the body against the committed export at HEAD BEFORE the write (red → no write) and the
      read-back AFTER it: 'on' with post_cutover_check as is; 'off' with the one literal put back in memory, so that
      literal is the only thing that may differ. post_cutover_check: every webhook trigger on the committed export's
      path and none the export lacks (no temporary trigger), the Turnstile literal ON in both, the content and
      connections equal (content_drift), the settings equal except what the spec allowlists
      (settings_parity.committed_vs_live), no placeholder the live workflow lacks, nothing sanitised. The body keeps
      the live settings as they are. Exit 0 written and proven · 1 red before or after the write · SystemExit refused.
  python3 scripts/deploy-workflow-copy.py --selftest      (offline: no network call, asserted)

It prints names, counts and shortened ids; never a credential, a host or a secret.
"""
import contextlib
import copy as _copy
import glob
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER = re.compile(r'REPLACE_WITH_[A-Z0-9_]+|\b(?:app|tbl)X{14}\b')
WORKFLOWS_FILE = None      # None = workflows' default, the committed check-exports-parity.sh (the selftest points it at a fixture)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [path]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return mod


DIFF = _module('scripts/diff-workflow-copy.py', 'diff_workflow_copy')      # import-safe: an offline sibling, itself guarded


def _workflows():
    """scripts/workflows.py, loaded once: the one parser of WORKFLOWS."""
    if 'wf' not in _MODS:
        _MODS['wf'] = _module('scripts/workflows.py', 'workflows')
    return _MODS['wf']


def check_placeholders(ref, cand, ref_name='the live workflow before the write'):
    extra = set(PLACEHOLDER.findall(json.dumps(cand))) - set(PLACEHOLDER.findall(json.dumps(ref)))
    return [f'placeholder in the candidate that {ref_name} does not hold: {p}' for p in sorted(extra)]


_MODS = {}


def _ccp():
    """scripts/check-content-parity.py, loaded once: its sanitise checks, mask and projection are the one truth."""
    if 'ccp' not in _MODS:
        _MODS['ccp'] = _module('scripts/check-content-parity.py', 'check_content_parity')
    return _MODS['ccp']


def _settings_parity():
    if 'sp' not in _MODS:
        _MODS['sp'] = _module('scripts/settings_parity.py', 'settings_parity')
    return _MODS['sp']


def check_not_sanitised(live_copy, generated):
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            _ccp().check_live_not_sanitised(live_copy, generated)
    except SystemExit as e:
        if e.code:
            return ['check-content-parity: ' + ' '.join(out.getvalue().split())[:300]]
    return []


# ── the Turnstile literal: ONE `turnstile: { enabled: … }` in Load Config, the only thing a window changes ─────
TS_NODE = 'Load Config'
TS_LITERAL = re.compile(r'turnstile\s*:\s*\{\s*enabled\s*:\s*(true|false)\s*\}')


def turnstile_patch(wf, state):
    """Return a copy of wf with the one Turnstile literal set to `state` ('off' or 'on'). Refuses (ValueError)
    unless Load Config holds exactly ONE such literal and it is currently in the opposite state."""
    want, have = ('false', 'true') if state == 'off' else ('true', 'false')
    out = _copy.deepcopy(wf)
    node = next((n for n in out['nodes'] if n['name'] == TS_NODE), None)
    code = ((node or {}).get('parameters') or {}).get('jsCode', '')
    found = TS_LITERAL.findall(code)
    if len(found) != 1:
        raise ValueError(f"'{TS_NODE}' holds {len(found)} Turnstile literal(s), not exactly one — refused")
    if found[0] != have:
        raise ValueError(f'the Turnstile literal is already {found[0]!r}, so turning it {state} changes nothing — refused')
    node['parameters']['jsCode'] = TS_LITERAL.sub(lambda m: m.group(0).replace(have, want), code, count=1)
    return out


def committed_export(path, rev='HEAD'):
    """The export as COMMITTED at `rev`, never the working tree: an uncommitted edit is not a reference. A revision
    must start with a letter or digit, so it can never be read by git as an option."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/~^@{}-]*', rev or ''):
        raise ValueError(f'{rev!r} is not a plain git revision')
    out = subprocess.run(['git', '-C', ROOT, 'show', f'{rev}:{path}'], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        raise ValueError(f'git show {rev}:{path} failed: ' + ' '.join(out.stderr.split())[:160])
    return json.loads(out.stdout)


def resolve_rev(rev):
    """The full commit hash `rev` names (so a printed revision cannot drift with HEAD)."""
    out = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--verify', '--quiet', f'{rev}^{{commit}}'], capture_output=True,
                         text=True, stdin=subprocess.DEVNULL)
    return out.stdout.strip() or rev


# Execution fields check-content-parity's projection does not compare (a gap it records itself). Compared HERE only:
# widening ccp's projection would change all ten parity runs, and that is a separate decision. Round B removes
# `alwaysOutputData` on Purge nodes, and without this neither the edit's diff nor its read-back could see it land.
EXEC_FLAGS = ('alwaysOutputData', 'executeOnce', 'retryOnFail')


def content_drift(live, committed, smap=None):
    """check-content-parity's own content_drift (its placeholder-only mask, executable node sets and projection; one
    truth), plus what
    a copy judged by its export needs beside it: per node the three execution flags (absent = False, n8n omits a
    default) and typeVersion (compared exactly; carried on one side only is a difference), the CONNECTIONS, which
    ccp's content half does not compare and an engine edit rewires, and the name. `smap={}` compares two LIVE bodies
    raw (the rollback read-back): a mask derived from two real bodies would map a changed credential onto the old one
    and hide it."""
    ccp = _ccp()
    smap = ccp.placeholder_smap(live, committed) if smap is None else smap
    errs = ccp.content_drift(live, committed, smap)
    L, C = ccp._executable(live), ccp._executable(committed)
    for nm in sorted(set(L) & set(C)):
        lv, cv = L[nm], C[nm]
        diff = [f'{k} (committed={bool(cv.get(k))!r} live={bool(lv.get(k))!r})' for k in EXEC_FLAGS
                if bool(lv.get(k)) != bool(cv.get(k))]
        if ('typeVersion' in lv) != ('typeVersion' in cv) or lv.get('typeVersion') != cv.get('typeVersion'):
            diff.append(f"typeVersion (committed={cv.get('typeVersion', 'absent')!r} live={lv.get('typeVersion', 'absent')!r})")
        if diff:
            errs.append(f"execution fields differ in '{nm}': {diff} (committed != live)")
    if json.dumps(live.get('connections') or {}, sort_keys=True) != json.dumps(committed.get('connections') or {}, sort_keys=True):
        errs.append('the connections differ (live copy != committed export)')
    if live.get('name') != committed.get('name'):
        errs.append('the workflow name differs (live copy != committed export)')
    return errs


def _ts_literal(wf):
    code = next((n for n in wf.get('nodes') or [] if n.get('name') == TS_NODE), {}).get('parameters', {}).get('jsCode', '')
    return TS_LITERAL.findall(code or '')


def _ts_shape_errs(wf, side):
    """A Load Config that mentions turnstile but does not hold EXACTLY one `turnstile: { enabled: … }` literal (e.g.
    `{ enabled: false, mode: "x" }`) would make every Turnstile check above see "no gate" and skip itself: red instead."""
    code = next((n for n in wf.get('nodes') or [] if n.get('name') == TS_NODE), {}).get('parameters', {}).get('jsCode', '') or ''
    if 'turnstile' in code.lower() and len(TS_LITERAL.findall(code)) != 1:
        return [f"the {side}'s {TS_NODE} mentions turnstile but holds {len(TS_LITERAL.findall(code))} exact Turnstile "
                'literal(s), not one: its gate cannot be judged']
    return []


# ── a live workflow judged by its committed export ───────────────────────────────────────────────────────────
def webhook_triggers(wf):
    """{node name: path} for every webhook trigger: what decides which requests reach the workflow."""
    return {n['name']: (n.get('parameters') or {}).get('path')
            for n in wf.get('nodes') or [] if n.get('type') == 'n8n-nodes-base.webhook'}


def post_cutover_check(cand, committed, spec, ref):
    """A live workflow, or a body about to become one, against its committed export. `ref` is the live workflow as it
    stands before the write (the source of "no placeholder the live workflow lacks"); `spec` its db/copies spec (the
    settings allowlist)."""
    errs = []
    want = webhook_triggers(committed)
    if len(want) > 1:
        errs.append(f'the committed export has {len(want)} webhook triggers, not at most one: no single production path')
    # A trigger off the export's path, or a webhook trigger the export lacks (a temporary one left in), is drift that
    # content_drift below already reds (parameters and node sets); a separate check for each was written first and
    # both mutants survived, so they were removed rather than kept as checks that measure nothing.
    # The content comparison below only proves cand == export; this proves the export's gate is UP. A committed export
    # carrying a lowered literal would otherwise go live green, and every later 'on' would restore it to off.
    errs += _ts_shape_errs(committed, 'committed export') + _ts_shape_errs(cand, 'candidate')
    lit_c, lit = _ts_literal(committed), _ts_literal(cand)
    if (lit_c or lit) and (lit_c != ['true'] or lit != ['true']):
        errs.append(f'the Turnstile literal is not ON (committed export {lit_c}, candidate {lit})')
    errs += content_drift(cand, committed)
    errs += _settings_parity().committed_vs_live(committed.get('settings'), cand.get('settings'),
                                                 (spec or {}).get('settings_allow') or None)
    errs += check_placeholders(ref, cand)
    errs += check_not_sanitised(cand, committed)
    return errs


def window_check(cand, committed, spec, state, ref):
    """--turnstile-swapped, before AND after its write. 'on': post_cutover_check as is. 'off': the candidate with its
    ONE Turnstile literal put back on in memory must pass it, so that literal is the only thing that may differ from
    the committed export."""
    if state == 'on':
        return post_cutover_check(cand, committed, spec, ref)
    try:
        restored = turnstile_patch(cand, 'on')
    except ValueError as e:
        return [f'turnstile off: {e}']
    return post_cutover_check(restored, committed, spec, ref)


def _path_seg(i, v):
    """A list element is addressed by its `name` when it has one (n8n's bodyParameters, assignments), so a parameter
    inserted before it does not shift the secret onto its neighbour; otherwise by index."""
    return f"[name={v['name']}]" if isinstance(v, dict) and isinstance(v.get('name'), str) else f'[{i}]'


def _strings(o, path=''):
    """(path, string) for every string leaf of a node, paths as _path_seg builds them."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, f'{path}/{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _strings(v, path + _path_seg(i, v))
    elif isinstance(o, str):
        yield path, o


def _set_at(node, path, value):
    """Set the string leaf at `path` (as _strings yields it) inside `node`."""
    parts = re.findall(r'/([^/\[]+)|\[name=([^\]]+)\]|\[(\d+)\]', path)
    cur, last = node, None
    for i, (key, name, idx) in enumerate(parts):
        nxt = cur[key] if key else (next(v for v in cur if isinstance(v, dict) and v.get('name') == name) if name else cur[int(idx)])
        if i == len(parts) - 1:
            last = (key, name, idx)
            break
        cur = nxt
    key, name, idx = last
    if key:
        cur[key] = value
    elif name:
        cur[next(j for j, v in enumerate(cur) if isinstance(v, dict) and v.get('name') == name)] = value
    else:
        cur[int(idx)] = value


def _shaped(v):
    return any(re.search(pat, v, re.I) for pat in _ccp().PLACEHOLDER_SHAPES)


def fill_by_path(live, committed, removable=()):
    """The PUT body for an engine edit (scripts/workflow-step.py put). THE RULE: an engine edit never changes a masked value — a credential, a
    chat id, the Turnstile secret, the calendar id are operator/credential operations, not engine edits. So every
    sanitize placeholder in the target export is replaced by the LIVE copy's value at the SAME path (node name + key
    path); a placeholder renamed in the export therefore changes nothing. A placeholder embedded in a longer string
    (the calendar id inside Load Config's code) is located in the live string by the text before it on its line,
    which must occur exactly once there. Refused (ValueError) when a placeholder has no live counterpart at its path
    (a new node needing a credential: an operator step) or the live value there is itself placeholder-shaped (except
    the exact token check-content-parity exempts as live by design). Also: every live node's webhookId kept by node
    name, and an export that renames or drops a node carrying one is refused — except a node named in `removable` (the
    approved delta's remove_nodes, passed by workflow-step put; ruling 2026-10-26, R3) that is NOT a trigger: n8n gives
    Telegram nodes a webhookId too, and the approved Owner Actions delta removes one. A trigger (diff-workflow-copy's own
    _is_trigger, the one definition: webhook, `…Trigger` and the legacy trigger types) is never removable here;
    settings: live, as they are."""
    ph_re = re.compile(r'REPLACE_WITH_[A-Za-z0-9_]+(?:@[A-Za-z0-9.\-]+)?|(?:app|tbl|viw|rec|fld)[A-Za-z0-9]*X{4,}[A-Za-z0-9]*')
    L = {n['name']: n for n in live['nodes']}
    nodes, missing = _copy.deepcopy(committed['nodes']), []
    for n in nodes:
        lstr = dict(_strings(L[n['name']])) if n['name'] in L else {}
        for path, val in list(_strings(n)):
            if not ph_re.search(val):
                continue
            where = f"'{n['name']}' {path}"
            lv = lstr.get(path)
            if lv is None:
                missing.append(f'{where}: no live value at this path')
                continue
            if ph_re.fullmatch(val):
                new, pieces = lv, [lv]
            else:
                new, pieces = val, []
                for m in ph_re.finditer(val):
                    before = val[:m.start()].rsplit('\n', 1)[-1].lstrip()
                    after = val[m.end():m.end() + 1]
                    start = lv.index(before) + len(before) if before and after and lv.count(before) == 1 else -1
                    end = lv.find(after, start) if start >= 0 else -1
                    if end < 0:
                        pieces = None
                        break
                    pieces.append(lv[start:end])
                    new = new.replace(m.group(0), lv[start:end], 1)
                if pieces is None:
                    missing.append(f'{where}: an embedded placeholder cannot be located in the live text')
                    continue
            if any(_shaped(v) and v not in _ccp().EXEMPT for v in pieces):
                missing.append(f'{where}: the live value is itself placeholder-shaped')
                continue
            _set_at(n, path, new)
    if missing:
        raise ValueError('an engine edit never changes a masked value, and these cannot be filled from the live copy '
                         '(an operator step): ' + '; '.join(missing[:4]))
    hooks = {n['name']: n['webhookId'] for n in live['nodes'] if n.get('webhookId')}
    rm = set(removable)
    droppable = {n['name'] for n in live['nodes'] if n['name'] in rm and not DIFF._is_trigger(n)}
    gone = sorted(set(hooks) - {n['name'] for n in nodes} - droppable)
    if gone:
        raise ValueError(f'the export renames or drops node(s) carrying a live webhookId: {gone}')
    for n in nodes:
        if n['name'] in hooks:
            n['webhookId'] = hooks[n['name']]
    return {'name': live['name'], 'nodes': nodes, 'connections': _copy.deepcopy(committed['connections']),
            'settings': _copy.deepcopy(live.get('settings') or {})}


# ── n8n API (the real curl: urllib is refused at the edge) ───────────────────────────────────────────────────
def _host():
    h = os.environ.get('N8N_HOST')
    if not h:
        m = re.search(r'^N8N_HOST=\s*(\S+)', open(os.path.join(ROOT, 'CLAUDE.local.md'), encoding='utf-8').read(), re.M)
        h = m.group(1) if m else None
    if not h:
        sys.exit('deploy-workflow-copy: N8N_HOST is not set and CLAUDE.local.md has none')
    return h


def api(method, path, body=None):
    hdr = {'X-N8N-API-KEY': os.environ['N8N_API_KEY'], 'Content-Type': 'application/json',
           'CF-Access-Client-Id': os.environ.get('CF_ACCESS_CLIENT_ID', ''),
           'CF-Access-Client-Secret': os.environ.get('CF_ACCESS_CLIENT_SECRET', '')}
    args = ['curl', '-4', '-s', '-m', '60', '-X', method, '-w', '\n%{http_code}', f'https://{_host()}/api/v1{path}']
    files = []
    try:
        # Secrets go in a 0600 header file, never on the command line (argv is readable by other local users).
        fd, hpath = tempfile.mkstemp(suffix='.hdr'); files.append(hpath)
        with os.fdopen(fd, 'w') as f:
            f.write(''.join(f'{k}: {v}\n' for k, v in hdr.items()))
        args += ['-H', '@' + hpath]
        if body is not None:
            fd, bpath = tempfile.mkstemp(suffix='.json'); files.append(bpath)
            with os.fdopen(fd, 'w') as f:
                json.dump(body, f)
            args += ['--data-binary', '@' + bpath]
        out = subprocess.run(args, capture_output=True, text=True).stdout
    finally:
        for p in files:
            os.unlink(p)
    raw, code = out.rsplit('\n', 1)
    try:
        return int(code), json.loads(raw)
    except ValueError:
        return int(code), raw


def _workflow(wid, meta=False):
    st, w = api('GET', f'/workflows/{wid}')
    if st != 200:
        sys.exit(f'deploy-workflow-copy: GET workflow failed [{st}]')
    wf = {k: w.get(k) for k in ('name', 'nodes', 'connections', 'settings')}
    return (wf, {'active': w.get('active'), 'name': w.get('name')}) if meta else wf


def _draft(d):
    return {k: d.get(k) for k in ('name', 'nodes', 'connections', 'settings')}


def _say(msg):
    """Every message while a copy is out of production (and in its recovery): output must never be what stops the
    recovery. On a hung-up terminal (SIGHUP after an ssh drop) print raises EIO, into a closed pipe EPIPE."""
    try:
        print(msg, flush=True)
    except (OSError, ValueError):
        pass


def _read(wid):
    """The full workflow, or None. Never sys.exit: inside an opened edit a failed read must reach the rollback."""
    st, d = api('GET', f'/workflows/{wid}')
    return d if st == 200 and isinstance(d, dict) else None


def _set_active(wid, on):
    st, _ = api('POST', f"/workflows/{wid}/{'activate' if on else 'deactivate'}")
    got = (_read(wid) or {}).get('active')
    _say(f"  {'activate' if on else 'deactivate'} the workflow: [{st}] · read back active {got}")
    return got is on


def _published_matches_draft(full):
    """check-content-parity's own published-vs-draft check, on an ACTIVE workflow; its errors as a list."""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            _ccp().check_published_matches_draft(full)
    except SystemExit as e:
        if e.code:
            return ['published vs draft: ' + ' '.join(out.getvalue().split())[:300]]
    return []


def turnstile_probe(path, wid):
    """The window script's own end-of-window measurement (dummy_probe): a dummy token to the production path must answer
    403 turnstile_failed, executed by `wid`, which must be the path's ONLY active holder. (ok, status)."""
    return _module('scripts/turnstile-window.py', 'turnstile_window').dummy_probe(path, wid)


def run(spec_path, state, wid):
    """--turnstile-swapped off|on WORKFLOW_ID: the module docstring has the rules."""
    key = os.path.splitext(os.path.basename(spec_path))[0]
    try:
        spec = json.load(open(spec_path, encoding='utf-8'))
        wfs = _workflows().load(WORKFLOWS_FILE)
        listed = _workflows().id_for(wfs, key)
    except (ValueError, OSError) as e:
        sys.exit(f'deploy-workflow-copy: refused before any write — {e}')
    if wid != listed:
        sys.exit(f"deploy-workflow-copy: refused before any write — {wid[:4]}… is not the workflow WORKFLOWS lists for '{key}'")
    try:
        committed = committed_export(wfs[wid])
    except (ValueError, OSError) as e:
        sys.exit(f'deploy-workflow-copy: refused before any write — no committed export to judge by ({e})')
    tw, m = _workflow(wid, meta=True)
    if m['name'] != committed.get('name') or m['active'] is not False:
        sys.exit(f"deploy-workflow-copy: refused before any write — the target must be the INACTIVE workflow named "
                 f"'{committed.get('name')}'")
    ref = _copy.deepcopy(tw)
    check = lambda wf: window_check(wf, committed, spec, state, ref)
    try:
        wf = turnstile_patch(tw, state)
    except ValueError as e:
        sys.exit(f'deploy-workflow-copy: {e}')
    # Check BEFORE the write: a red body is never written with its gate lowered.
    errs = check(wf)
    if errs:
        print(f'TURNSTILE {state.upper()} REFUSED before any write — the content is not clean against the committed export:')
        for e in errs:
            print('  - ' + e)
        return 1
    st, _ = api('PUT', f'/workflows/{wid}', wf)
    if st != 200:
        sys.exit(f'deploy-workflow-copy: Turnstile write failed [{st}]')
    # And AFTER it, on what n8n actually holds: a 200 does not prove the write landed as sent.
    live, m = _workflow(wid, meta=True)
    errs = check(live)
    if m['active'] is not False:
        errs.append('the workflow is not inactive (read back from n8n)')
    if errs:
        print(f'TURNSTILE {state.upper()} CHECK FAILED after the write — no drill may start on this workflow:')
        for e in errs:
            print('  - ' + e)
        return 1
    print(f"turnstile {state} on the workflow · check OK before and after the write — "
          f"{'only the one literal differs' if state == 'off' else 'equal'} from the committed export · "
          f"active read back: {m['active']}")
    return 0


# ── selftest: the checks on simulated live workflows, every spec ─────────────────────────────────────────────
def _simulated_live(sanitized, keep=()):
    """A stand-in for a live workflow: every committed placeholder replaced by a real-looking value, except `keep`."""
    s = json.dumps(sanitized)
    for i, ph in enumerate(sorted(set(PLACEHOLDER.findall(s)) - set(keep))):
        s = s.replace(ph, f'Live{i:02d}Value{uuid.uuid5(uuid.NAMESPACE_URL, ph).hex[:8]}')
    return json.loads(s)


def _simulated_live_copy(spec_file):
    """(the committed export, a stand-in for the live workflow built from it). Read from the WORKING TREE: in a clean
    check-all run that is HEAD, and before the commit that moves an export it is the file about to be committed."""
    x = os.path.splitext(os.path.basename(spec_file))[0]
    committed = json.load(open(os.path.join(ROOT, 'n8n', f'workflow.{x}.sanitized.json'), encoding='utf-8'))
    return committed, _simulated_live(committed, keep=_ccp().EXEMPT)   # what live holds as a placeholder by design


def selftest():
    ok = True

    def case(label, good, detail=''):
        nonlocal ok
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}" + ('' if good or not detail else f' — {detail}'))

    global api, committed_export, WORKFLOWS_FILE
    real_api, real_ce, real_wf = api, committed_export, WORKFLOWS_FILE
    stray, fixtures = [], []
    api = lambda *a, **k: stray.append(a) or (599, {})   # any call that is not a test's own fake is recorded: a failure
    committed_export = lambda path, rev='HEAD': json.load(open(os.path.join(ROOT, path), encoding='utf-8'))
    N_ = lambda w, name: next(n for n in w['nodes'] if n['name'] == name)
    try:
        specs = sorted(glob.glob(os.path.join(ROOT, 'db', 'copies', '*.json')))
        assert specs, 'no specs under db/copies/'
        # ── post_cutover_check / window_check / turnstile_patch, on every workflow ──
        for f in specs:
            spec, base = json.load(open(f, encoding='utf-8')), os.path.basename(f)
            committed, plive = _simulated_live_copy(f)
            trig = webhook_triggers(committed)
            other = next(n['name'] for n in plive['nodes'] if n['type'] not in
                         ('n8n-nodes-base.webhook', 'n8n-nodes-base.stickyNote', 'n8n-nodes-base.telegram'))

            def v(fn, w=plive):
                w = _copy.deepcopy(w)
                fn(w)
                return w
            pg = next((n['name'] for n in plive['nodes'] if (n.get('credentials') or {}).get('postgres')), None)
            pc = [('the live workflow equals its committed export', plive, committed, plive, True),
                  (f"a node ('{other}') differs from the export", v(lambda w: N_(w, other)['parameters'].__setitem__('_probe', 'changed')), committed, plive, False),
                  (f"a placeholder in a node ('{other}')", v(lambda w: N_(w, other)['parameters'].__setitem__('_probe', 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID')), committed, plive, False),
                  ('a node the export does not have', v(lambda w: w['nodes'].append(dict(_copy.deepcopy(N_(w, other)), name='Extra Node', id='extra'))), committed, plive, False),
                  ('one connection removed', v(lambda w: w['connections'].pop(sorted(w['connections'])[0])), committed, plive, False),
                  ('settings: executionOrder missing', v(lambda w: w['settings'].pop('executionOrder', None)), committed, plive, False),
                  ('a webhook trigger the export does not have (a temporary trigger)', v(lambda w: w['nodes'].append(
                      {'name': 'Temporary Test Trigger', 'type': 'n8n-nodes-base.webhook', 'parameters': {'path': 'temp'}, 'id': 'tmp'})), committed, plive, False),
                  (f"typeVersion differs on '{other}'", v(lambda w: N_(w, other).__setitem__('typeVersion', (N_(w, other).get('typeVersion') or 1) + 1)), committed, plive, False),
                  (f"typeVersion carried by the export only ('{other}')", v(lambda w: N_(w, other).pop('typeVersion', None)), committed, plive, False),
                  (f"executeOnce set on '{other}' live only", v(lambda w: N_(w, other).__setitem__('executeOnce', True)), committed, plive, False),
                  (f"retryOnFail set on '{other}' live only", v(lambda w: N_(w, other).__setitem__('retryOnFail', True)), committed, plive, False),
                  (f"executeOnce: false written out live, absent in the export ('{other}')", v(lambda w: N_(w, other).__setitem__('executeOnce', False)), committed, plive, True)]
            if pg:
                pc.append((f"a node ('{pg}') on the credential placeholder", v(lambda w: N_(w, pg).__setitem__(
                    'credentials', {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}})), committed, plive, False))
                dropped, kept = _copy.deepcopy(committed), v(lambda w: N_(w, pg).__setitem__('alwaysOutputData', True))
                N_(dropped, pg).pop('alwaysOutputData', None)
                pc.append((f"the export drops alwaysOutputData on '{pg}' while live keeps it", kept, dropped, kept, False))
            for name, path in trig.items():
                pc.append((f"trigger '{name}' moved off the production path", v(lambda w, name=name: N_(w, name)['parameters'].__setitem__('path', path + '-test')), committed, plive, False))
            tg = next((n['name'] for n in plive['nodes'] if n['type'] == 'n8n-nodes-base.telegram'), None)
            if tg:                                       # R1: a masked path whose COMMITTED value is not a placeholder is drift
                pc.append((f"R1 the export's chatId on '{tg}' is an expression, live holds the value", plive,
                           v(lambda w: N_(w, tg)['parameters'].__setitem__('chatId', '={{ $json.ownerChat }}'), committed), plive, False))
            for token in sorted(_ccp().EXEMPT):          # exempt from the shape scan, so only the "live lacks" check sees it
                if token in json.dumps(committed):
                    pc.append((f'brings back {token} where the live workflow holds a real value', plive, committed,
                               json.loads(json.dumps(plive).replace(token, 'LiveRealValue01')), False))
            for key, entry in (spec.get('settings_allow') or {}).items():
                val = entry['value']
                pc += [(f"settings: allowlisted '{key}' live as exactly {val!r}", v(lambda w: w['settings'].__setitem__(key, val)), committed, plive, True),
                       (f"settings: allowlisted '{key}' live with another value", v(lambda w: w['settings'].__setitem__(key, '__other__')), committed, plive, False),
                       (f"settings: allowlisted '{key}' live as True (type-strict)", v(lambda w: w['settings'].__setitem__(key, True)), committed, plive, False),
                       (f"settings: allowlisted '{key}' in the export AND live", v(lambda w: w['settings'].__setitem__(key, val)),
                        v(lambda w: w['settings'].__setitem__(key, val), committed), plive, False)]
            if trig:
                add2 = lambda w: w['nodes'].append(dict(_copy.deepcopy(N_(w, next(iter(trig)))), name='Second Trigger', id='t2'))
                two_live = v(add2)
                pc.append(('the committed export holds two webhook triggers (no single production path)', two_live, v(add2, committed), two_live, False))
            pc.append(('settings: a key nobody allowlisted, live only', v(lambda w: w['settings'].__setitem__('availableInMCP', True)), committed, plive, False))
            for label, cand, comm, ref, want in pc:
                errs = post_cutover_check(cand, comm, spec, ref)
                case(f'{base} · {label}', (not errs) == want, errs[0][:100] if errs else 'green')
            if _ts_literal(committed):
                errs = post_cutover_check(turnstile_patch(plive, 'off'), turnstile_patch(committed, 'off'), spec, plive)
                case(f'{base} · the committed export AND the live workflow both lowered: red', bool(errs))
                off = turnstile_patch(plive, 'off')
                rider = _copy.deepcopy(off)                 # a second literal lowered with it
                rn = N_(rider, TS_NODE)
                rn['parameters']['jsCode'] = rn['parameters']['jsCode'].replace('enabled: true', 'enabled: false', 1)
                ride2 = _copy.deepcopy(off)
                N_(ride2, other)['parameters']['_probe'] = 'changed'
                for label, wf, st_, want in (('window off: only the one literal changed', off, 'off', True),
                                             ('window off: a second literal changed with it', rider, 'off', False),
                                             (f"window off: another node ('{other}') changed with it", ride2, 'off', False),
                                             ('window on: restored', turnstile_patch(off, 'on'), 'on', True),
                                             ("window 'on' check while the literal is still off", off, 'on', False)):
                    errs = window_check(wf, committed, spec, st_, plive)
                    case(f'{base} · {label}', (not errs) == want, errs[0][:100] if errs else 'green')
                for label, wf, st_ in (('turnstile off twice', off, 'off'), ('turnstile on while already on', plive, 'on')):
                    try:
                        turnstile_patch(wf, st_)
                        case(f'{base} · {label}: refused', False, 'NOT refused')
                    except ValueError:
                        case(f'{base} · {label}: refused', True)
                two = _copy.deepcopy(plive)
                N_(two, TS_NODE)['parameters']['jsCode'] += '\n// turnstile: { enabled: true }'
                try:
                    turnstile_patch(two, 'off')
                    case(f'{base} · two Turnstile literals: refused', False, 'NOT refused')
                except ValueError:
                    case(f'{base} · two Turnstile literals: refused', True)
                shaped = _copy.deepcopy(committed)
                sn = N_(shaped, TS_NODE)
                sn['parameters']['jsCode'] = sn['parameters']['jsCode'].replace('turnstile: { enabled: true }', 'turnstile: { enabled: true, mode: "x" }', 1)
                errs = post_cutover_check(plive, shaped, spec, plive)
                case(f"{base} · the export's Turnstile literal has an extra key: red, not skipped", any('exact Turnstile' in e for e in errs))
        # ── fill_by_path, on the Main export (the engine-edit rule: a masked value is never changed by an edit) ──
        mpath = os.path.join(ROOT, 'db', 'copies', 'main.json')
        mspec = json.load(open(mpath, encoding='utf-8'))
        mcom, mlive = _simulated_live_copy(mpath)
        TG, TRIG = 'Send Owner Alert (Telegram)', next(iter(webhook_triggers(mcom)))
        body = fill_by_path(mlive, mcom)
        case('fill_by_path: an unchanged export fills back exactly the live values', not content_drift(body, _draft(mlive), smap={}))
        case('fill_by_path: the body carries the LIVE settings', body['settings'] == mlive.get('settings'))
        lh = _copy.deepcopy(mlive)
        N_(lh, TG)['webhookId'] = 'live-hook-1'
        N_(lh, TRIG)['webhookId'] = 'live-trigger-hook'
        ch = _copy.deepcopy(mcom)
        N_(ch, TG)['webhookId'] = 'export-hook-x'
        b = fill_by_path(lh, ch)
        case("R6 fill_by_path: a Telegram node's live webhookId is kept over the export's", N_(b, TG).get('webhookId') == 'live-hook-1')

        def refused(fn, needle):
            try:
                fn()
                return False, 'not refused'
            except ValueError as e:
                return needle in str(e), str(e)[:90]
        ren = _copy.deepcopy(mcom)
        N_(ren, TRIG)['name'] = 'Receive Inbound (renamed)'
        case('R6 fill_by_path: the export renames a node that carries a live webhookId: refused', *refused(lambda: fill_by_path(lh, ren), 'webhookId'))
        drop_tg = dict(_copy.deepcopy(mcom), nodes=[n for n in mcom['nodes'] if n['name'] != TG])
        try:
            b = fill_by_path(lh, drop_tg, removable=[TG])
            case('R3 fill_by_path: a non-trigger node in the approved removal drops its live webhookId', TG not in {n['name'] for n in b['nodes']})
        except ValueError as e:
            case('R3 fill_by_path: a non-trigger node in the approved removal drops its live webhookId', False, str(e)[:90])
        case('R3 fill_by_path: the same drop with no removable list: refused', *refused(lambda: fill_by_path(lh, drop_tg), 'webhookId'))
        drop_tr = dict(_copy.deepcopy(mcom), nodes=[n for n in mcom['nodes'] if n['name'] != TRIG])
        case('R3 fill_by_path: the trigger dropped, even when named removable: refused', *refused(lambda: fill_by_path(lh, drop_tr, removable=[TRIG]), 'webhookId'))
        pgs = [n['name'] for n in mlive['nodes'] if (n.get('credentials') or {}).get('postgres')]
        two_pg = _copy.deepcopy(mlive)
        N_(two_pg, pgs[0])['credentials']['postgres']['id'] = 'LiveOtherPostgres01'
        b = fill_by_path(two_pg, mcom)
        case('fill_by_path: two live credentials behind one placeholder — each path keeps its own',
             N_(b, pgs[0])['credentials']['postgres']['id'] == 'LiveOtherPostgres01'
             and N_(b, pgs[1])['credentials']['postgres']['id'] == N_(mlive, pgs[1])['credentials']['postgres']['id'])
        c_ren = _copy.deepcopy(mcom)
        N_(c_ren, TG)['parameters']['chatId'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID_V2'
        b = fill_by_path(mlive, c_ren)
        case('fill_by_path: a placeholder renamed in the export takes the live value at that path',
             N_(b, TG)['parameters']['chatId'] == N_(mlive, TG)['parameters']['chatId'])
        c_new = _copy.deepcopy(mcom)
        c_new['nodes'].append(dict(_copy.deepcopy(N_(mcom, pgs[0])), name='New Lookup', id='new-lookup'))
        case('fill_by_path: a new node that needs a credential: refused (an operator step)', *refused(lambda: fill_by_path(mlive, c_new), 'operator step'))
        # ── run(): --turnstile-swapped through a fake n8n, with a fixture WORKFLOWS (fake ids) ──
        with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as t:
            t.write('WORKFLOWS=(\n  "C1:n8n/workflow.main.sanitized.json"\n  "C3:n8n/workflow.purge.sanitized.json"\n)\n')
        fixtures.append(t.name)
        WORKFLOWS_FILE = t.name
        mname = mcom['name']
        m_off = turnstile_patch(mlive, 'off')
        m_dirty = _copy.deepcopy(mlive)
        N_(m_dirty, 'Normalize Inbound')['parameters']['_probe'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
        ppath = os.path.join(ROOT, 'db', 'copies', 'purge.json')
        for label, sp, wid, state, wf, active, name, mangle, want in (
                ('off on the listed, inactive, rightly named workflow', mpath, 'C1', 'off', mlive, False, mname, None, 'written'),
                ('on (restore)', mpath, 'C1', 'on', m_off, False, mname, None, 'written'),
                ('the target is ACTIVE', mpath, 'C1', 'off', mlive, True, mname, None, 'refused'),
                ('an id WORKFLOWS does not list', mpath, 'X9', 'off', mlive, False, mname, None, 'refused'),
                ('an id WORKFLOWS lists for another workflow (purge)', mpath, 'C3', 'off', mlive, False, mname, None, 'refused'),
                ('the target is named otherwise', mpath, 'C1', 'off', mlive, False, 'MIG COPY — Main', None, 'refused'),
                ('a workflow with no Turnstile literal (purge)', ppath, 'C3', 'off', _simulated_live_copy(ppath)[1], False,
                 _simulated_live_copy(ppath)[0]['name'], None, 'refused'),
                ('a placeholder in the body (pre-write check)', mpath, 'C1', 'off', m_dirty, False, mname, None, 'rc 1'),
                ('n8n keeps the old literal on write (post-write check)', mpath, 'C1', 'off', mlive, False, mname, 'keep', 'rc 1'),
                ('the workflow reads back ACTIVE after the write (post-write check)', mpath, 'C1', 'off', mlive, False, mname, 'activate', 'rc 1')):
            db, calls = {wid: dict(_copy.deepcopy(wf), active=active, name=name)}, []

            def fake(method, path, body=None, db=db, calls=calls, mangle=mangle):
                calls.append((method, path))
                w = db[path.rsplit('/', 1)[-1]]
                if method == 'PUT' and mangle != 'keep':      # 'keep': 200 and nothing stored
                    w.update(_copy.deepcopy({k: body[k] for k in ('nodes', 'connections', 'settings')}))
                    if mangle == 'activate':
                        w['active'] = True
                return 200, _copy.deepcopy(w)
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(sp, state, wid)
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit:
                got = 'refused'
            except Exception as e:                     # an escaped exception is a red case, never a crash of the selftest
                got = f'escaped {type(e).__name__}'
            puts = [c for c in calls if c[0] == 'PUT']
            good = got == want and (puts == [('PUT', f'/workflows/{wid}')] if (want == 'written' or mangle) else not puts)
            if want == 'written':
                good = good and _ts_literal(db[wid]) == (['false'] if state == 'off' else ['true'])
            case(f'--turnstile-swapped {state}, {label}: {got}', good, f'PUTs {puts}')
            api = lambda *a, **k: stray.append(a) or (599, {})
        # ── main(): usage, and the removed modes, refused before any call ──
        for argv in (['d', mpath], ['d', '--turnstile-swapped', 'off', 'C1', mpath], ['d', mpath, '--turnstile-swapped', 'off'],
                     ['d', mpath, '--turnstile-swapped', 'up', 'C1'], ['d', mpath, '--turnstile-swapped', 'off', 'C1/../x'],
                     ['d', mpath, '--original-id', 'O1', '--turnstile-swapped', 'off', 'C1'], ['d', mpath, '--update', 'C1'],
                     ['d', mpath, '--verify', 'C1'], ['d', mpath, '--swap', 'C1'], ['d', mpath, '--turnstile', 'off', 'C1'],
                     ['d', mpath, '--engine-edit', 'C1'], ['d', mpath, '--restore', 'C1']):
            n0 = len(stray)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(argv)
            case(f"argv '{' '.join(argv[1:]).replace(mpath, '<spec>')}': usage exit 2, no call", rc == 2 and len(stray) == n0, f'exit {rc}')
    finally:
        api, committed_export, WORKFLOWS_FILE = real_api, real_ce, real_wf
        for p in fixtures:
            os.unlink(p)
    case(f'no network call during the selftest ({len(stray)})', not stray)
    print('deploy-workflow-copy selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    args = argv[1:]
    if (len(args) != 4 or args[0].startswith('--') or args[1] != '--turnstile-swapped' or args[2] not in ('off', 'on')
            or not re.fullmatch(r'[A-Za-z0-9]+', args[3])):
        print('usage: deploy-workflow-copy.py db/copies/<key>.json --turnstile-swapped off|on WORKFLOW_ID  |  --selftest')
        return 2
    return run(args[0], args[2], args[3])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
