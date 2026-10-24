#!/usr/bin/env python3
"""deploy-workflow-copy.py — deploy a migration copy to n8n and VERIFY it before any drill (MIGRATION-PLAN §3r).

Why the copy is not deployed as generated: scripts/build-workflow-copy.py builds it from the SANITIZED export,
so every node outside the data layer carries placeholders (a Telegram chat id, credential ids). Deployed as is,
such a copy cannot do what its original does: at D3b its owner alerts all went undelivered. So a copy is
deployed as THE LIVE ORIGINAL plus only the generated copy's data-layer delta: the spec's data nodes (with the
real Postgres credential swapped in), the real trigger's test path, and a declared temporary trigger.

After the write it runs these checks, and exits non-zero if any is red, so no drill starts on a broken copy:
  0. swapped: every spec data node is a Postgres node on a real credential, the trigger is on its test path,
     and the declared temporary trigger exists (so the original itself, or an unswapped copy, cannot pass).
     Separately, run() fails unless the copy reads back INACTIVE (live only; the selftest does not cover it);
  1. placeholders: the live copy holds no REPLACE_WITH_* / XXXX-id token that the live original does not hold;
  2. scripts/diff-workflow-copy.py, live original vs live copy (test phase): only the data nodes, the test path
     and the temporary trigger differ;
  3. scripts/check-content-parity.py's own check_live_not_sanitised (the "LIVE IS SANITISED" check), run on the
     live copy against the generated copy.
The copy is created INACTIVE and this tool never activates anything. It prints names, counts and the copy's
workflow id; never a credential, a host or a secret.

Usage (env: N8N_API_KEY, CF_ACCESS_CLIENT_ID/SECRET; N8N_HOST or CLAUDE.local.md):
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID [--update COPY_ID]
      (--update, --verify, --turnstile, --turnstile-swapped and --swap refuse the original's id and any target that
       is active or not named as the spec; they are exclusive, one target per run)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --verify COPY_ID
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --turnstile off|on COPY_ID
      (the Turnstile window on an INACTIVE copy in the TEST phase: one literal in its Load Config; 'off' checks that
       nothing else differs, 'on' runs the full verify. The check runs on the patched content BEFORE the write (red:
       no write) and again on the live copy after it. Settings the spec allowlists are never sent, on any write.)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --turnstile-swapped off|on COPY_ID
      (the same window on an INACTIVE copy in the SWAP phase, i.e. after --swap: trigger on the original's live path,
       no temporary trigger. Judged by swap_check instead of verify: 'off' with the one literal put back in memory,
       'on' as is; before the write and again after it.
       *Why a separate flag and not phase detection:* a swapped copy is the PRODUCTION holder, so lowering its gate is
       a production act. The operator names the phase, the check measures it, and the run proceeds only when both
       agree; a copy that is not in the named phase is refused before any write, in either direction.
       *ORDER guard (ruling 2026-10-24), 'off' and 'on' alike, before the content check and before any write:* the
       swap must be DECLARED, i.e. scripts/check-exports-parity.sh's ROLES (read through scripts/pair_roles.py, the one
       parser) holds a line for exactly this original and this copy with LIVE = copy; and the original must read back
       INACTIVE from n8n. A swapped-shaped copy is not yet a production holder: it becomes one when the swap is declared
       in a commit and the original is parked, and only then is lowering its gate a legitimate production act rather
       than a window opened on a workflow nobody has handed production to. The test-phase --turnstile reads neither:
       there the original is active and ROLES says original, and that is correct.)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --swap COPY_ID
      (D6b's cutover write, MIGRATION-PLAN §3a/§3t: refused unless the original AND the copy both read back
       INACTIVE. The copy's trigger moves to the original's live path and its temporary trigger is removed; the
       swap-phase checks run on that content BEFORE the write and again on the live copy after it. It never
       activates anything: the operator's next step does, one workflow at a time.)
  python3 scripts/deploy-workflow-copy.py --selftest      (offline: the checks on simulated live workflows)
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


BUILD = _module('scripts/build-workflow-copy.py', 'build_workflow_copy')   # import-safe: an offline sibling, itself guarded
DIFF = _module('scripts/diff-workflow-copy.py', 'diff_workflow_copy')      # import-safe: an offline sibling, itself guarded


# ── the three checks (pure: no network) ──────────────────────────────────────────────────────────────────────
def check_placeholders(live_orig, live_copy):
    extra = set(PLACEHOLDER.findall(json.dumps(live_copy))) - set(PLACEHOLDER.findall(json.dumps(live_orig)))
    return [f'placeholder in the live copy that the live original does not hold: {p}' for p in sorted(extra)]


def check_diff(live_orig, live_copy, spec):
    return DIFF.compare(live_orig, live_copy, set(spec['nodes']), phase='test',
                        temp_trigger=(spec.get('temp_trigger') or {}).get('name'),
                        trigger=(spec.get('trigger') or {}).get('node'),
                        settings_allow=spec.get('settings_allow', {}))


def check_not_sanitised(live_copy, generated):
    ccp = _module('scripts/check-content-parity.py', 'check_content_parity')
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            ccp.check_live_not_sanitised(live_copy, generated)
    except SystemExit as e:
        if e.code:
            return ['check-content-parity: ' + ' '.join(out.getvalue().split())[:300]]
    return []


def check_swapped(live_copy, spec):
    """The copy must actually BE a copy: every spec data node is a Postgres node on a real (non-placeholder)
    credential, the trigger sits on the spec's test path, and a declared temporary trigger exists. Without this,
    the original itself (or an unswapped copy) passed the three checks above (pre-push audit, 2026-10-20)."""
    errs, N = [], {n['name']: n for n in live_copy['nodes']}
    for name in spec['nodes']:
        n = N.get(name) or {}
        cred = ((n.get('credentials') or {}).get('postgres') or {}).get('id', '')
        if n.get('type') != 'n8n-nodes-base.postgres' or not cred or PLACEHOLDER.search(cred):
            errs.append(f"data node '{name}' is not a Postgres node on a real credential")
    trig = spec.get('trigger')
    if trig and (N.get(trig['node']) or {}).get('parameters', {}).get('path') != trig['test_path']:
        errs.append(f"trigger '{trig['node']}' is not on the spec's test path")
    temp = spec.get('temp_trigger')
    if temp and temp['name'] not in N:
        errs.append(f"the declared temporary trigger '{temp['name']}' is missing")
    return errs


def verify(live_orig, live_copy, generated, spec):
    errs = check_swapped(live_copy, spec) + check_placeholders(live_orig, live_copy) \
        + check_diff(live_orig, live_copy, spec) + check_not_sanitised(live_copy, generated)
    return errs


def assemble(generated, live_orig, spec, pg_credential):
    """The live original + the generated copy's data-layer delta. Nothing else comes from the generated copy."""
    LO = {n['name']: n for n in live_orig['nodes']}
    data, trig, temp = set(spec['nodes']), spec.get('trigger') or {}, spec.get('temp_trigger') or {}
    nodes = []
    for g in generated['nodes']:
        if g['name'] in data:
            n = _copy.deepcopy(g)
            n['credentials'] = {'postgres': dict(pg_credential)}
        elif g['name'] == temp.get('name'):
            n = _copy.deepcopy(g)
        else:
            n = _copy.deepcopy(LO[g['name']])
            if g['name'] == trig.get('node'):
                n['parameters']['path'] = trig['test_path']
        if n['type'] == 'n8n-nodes-base.webhook':
            n['webhookId'] = str(uuid.uuid4())
        nodes.append(n)
    # Keys the spec allowlists as ABSENT are never sent: the guard now reds a copy that carries one (D4-1), and
    # sending Main's `availableInMCP: true` would create the copy exactly as exposed as Main.
    allow = spec.get('settings_allow') or {}
    settings = {k: v for k, v in (live_orig.get('settings') or generated.get('settings') or {}).items() if k not in allow}
    return {'name': generated['name'], 'nodes': nodes, 'connections': generated['connections'], 'settings': settings}


# ── the Turnstile window on a COPY (MIGRATION-PLAN §4.5, D4 plan §6) ─────────────────────────────────────────
# The copy carries Main's Turnstile gate, so drills with a dummy token need it lowered ON THE COPY ONLY. The change
# is ONE literal in the copy's Load Config; nothing else may move, and the copy must be inactive while it is
# written (a PUT to an active workflow publishes at once). Restoring it must leave the copy verify-green again.
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


def turnstile_check(live_orig, live_copy, generated, spec, state, phase='test'):
    """Before AND after a window write. 'on': the phase's full check (the copy is a plain copy of that phase again).
    'off': the copy with that ONE literal put back in memory must pass the phase's full check, so nothing else can
    ride along with the lowered gate. (A second, textual comparison of the two Load Configs was written first; its
    mutant survived, because this check already reds every other difference, so it was removed rather than kept as a
    check that measures nothing.)
    `phase` picks the check: 'test' = verify() (trigger on the test path, temporary trigger present), 'swap' =
    swap_check() (trigger on the original's live path, no temporary trigger). Each reds the other phase's copy."""
    check = {'test': verify, 'swap': swap_check}[phase]
    if state == 'on':
        return check(live_orig, live_copy, generated, spec)
    try:
        restored = turnstile_patch(live_copy, 'on')
    except ValueError as e:
        return [f'turnstile off: {e}']
    return check(live_orig, restored, generated, spec)


ROLES_FILE = None   # None = pair_roles' own default, the committed check-exports-parity.sh; the selftest points it at a fixture


def check_swap_declared(original_id, copy_id, original_active):
    """--turnstile-swapped's ORDER guard (ruling 2026-10-24): the reason the window is refused, or None.
    (1) the swap is DECLARED: a ROLES line for exactly this pair, LIVE = copy; (2) the original is PARKED: read back
    inactive. ROLES is read through pair_roles, so there is one parser; a declaration it cannot read declares nothing."""
    try:
        _, roles = _module('scripts/pair_roles.py', 'pair_roles').load(ROLES_FILE)
    except (ValueError, OSError) as e:
        return f'ROLES does not read, so nothing is declared ({e})'
    role = next((r for r in roles if r['orig'] == original_id and r['copy'] == copy_id), None)
    if role is None:
        return 'ROLES has no line for this original and this copy, so the swap is not declared'
    if role['live'] != 'copy':
        return f"ROLES declares the {role['live']} live, so the swap is not declared (flip the pair to copy first)"
    if original_active is not False:
        return 'the original is not INACTIVE; park it first (§3a), its copy is not the production holder yet'
    return None


# ── the SWAP (D6b, MIGRATION-PLAN §3a, §3t) ─────────────────────────────────────────────────────────────────
# §3a: deactivate the original → put the copy on the production path → activate the copy → measure. This is the
# middle step only. Its content comes from the LIVE copy (already verified, real credentials, Load Config as live),
# with exactly two changes: the trigger takes the ORIGINAL's live path (read, never hard-coded), and the declared
# temporary trigger is removed (Q13: it must be gone at the swap, proven by the diff tool's swap phase).
def swap_patch(live_copy, live_orig, spec):
    out = _copy.deepcopy(live_copy)
    trig, temp = spec.get('trigger') or {}, (spec.get('temp_trigger') or {}).get('name')
    if trig:
        prod = next(n for n in live_orig['nodes'] if n['name'] == trig['node'])['parameters']['path']
        next(n for n in out['nodes'] if n['name'] == trig['node'])['parameters']['path'] = prod
    if temp:
        out['nodes'] = [n for n in out['nodes'] if n['name'] != temp]
        (out.get('connections') or {}).pop(temp, None)
    out['settings'] = {k: v for k, v in (out.get('settings') or {}).items() if k not in (spec.get('settings_allow') or {})}
    return out


def swap_check(live_orig, live_copy, generated, spec):
    """The swap phase: only the data nodes may differ from the original (the trigger on the original's path, no
    temporary trigger: the diff tool's swap phase reds both), each data node a Postgres node on a REAL credential
    (the diff tool allows a data node's credentials to change, so it cannot see a placeholder there), and no
    placeholder the original lacks (the diff tool also allows a data node's PARAMETERS to change).
    *Declared:* verify()'s not-sanitised check was in this list first and its mutant SURVIVED: in the swap phase every
    non-data node must equal the live original, so a sanitised copy is already red in the diff. It was removed rather
    than kept as a check that measures nothing (the same call as the Turnstile window's textual comparison).
    `generated` stays in the signature so the swap and verify checks are called alike."""
    errs, N = [], {n['name']: n for n in live_copy['nodes']}
    for name in spec['nodes']:
        n = N.get(name) or {}
        cred = ((n.get('credentials') or {}).get('postgres') or {}).get('id', '')
        if n.get('type') != 'n8n-nodes-base.postgres' or not cred or PLACEHOLDER.search(cred):
            errs.append(f"data node '{name}' is not a Postgres node on a real credential")
    errs += check_placeholders(live_orig, live_copy)
    errs += DIFF.compare(live_orig, live_copy, set(spec['nodes']), phase='swap',
                         temp_trigger=(spec.get('temp_trigger') or {}).get('name'),
                         trigger=(spec.get('trigger') or {}).get('node'),
                         settings_allow=spec.get('settings_allow', {}))
    return errs


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


def _pg_credential():
    st, d = api('GET', '/credentials')
    pg = [c for c in (d.get('data') or []) if c.get('type') == 'postgres'] if st == 200 else []
    if len(pg) != 1:
        sys.exit(f'deploy-workflow-copy: expected exactly one postgres credential, found {len(pg)}')
    return {'id': pg[0]['id'], 'name': pg[0]['name']}


def run(spec_path, original_id, update=None, verify_only=None, turnstile=None, swap=None, turnstile_swapped=None):
    # One target per run. With --turnstile beside --update/--verify the guards below checked ONE id and the PUT went
    # to the OTHER, unchecked: the production original's id would have taken the copy (pre-push audit, 2026-10-23).
    if sum(x is not None for x in (update, verify_only, turnstile, swap, turnstile_swapped)) > 1:
        sys.exit('deploy-workflow-copy: refused — --update, --verify, --turnstile, --turnstile-swapped and --swap are '
                 'exclusive (one target per run)')
    spec = json.load(open(spec_path, encoding='utf-8'))
    generated = BUILD.build(spec)
    live_orig, om = _workflow(original_id, meta=True)
    window = turnstile or turnstile_swapped
    target = verify_only or update or swap or (window or (None, None))[1]
    if target:
        if target == original_id:
            sys.exit('deploy-workflow-copy: refused — the copy id equals the original id')
        tw, m = _workflow(target, meta=True)
        if m['name'] != spec['name'] or m['active'] is not False:
            sys.exit(f"deploy-workflow-copy: refused — the target must be the INACTIVE workflow named '{spec['name']}'")
        T = {n['name']: n for n in tw['nodes']}
        if any((T.get(name) or {}).get('type') != 'n8n-nodes-base.postgres' for name in spec['nodes']):
            # Name and state can collide; an original's data nodes are Airtable, a copy's are Postgres.
            sys.exit('deploy-workflow-copy: refused — the target\'s data nodes are not Postgres, so it is not a copy')
    if swap:
        assert swap == target, 'the swap write must go to the id the guards above checked'
        if om['active'] is not False:
            # Two active workflows cannot hold one path (S1: the second activation is refused with 409), but the
            # copy is not activated here; the point is ORDER: §3a deactivates the original first, and this write is
            # only safe after that step has happened and been read back.
            sys.exit('deploy-workflow-copy: refused — the original is not INACTIVE; deactivate it first (§3a)')
        wf = swap_patch(tw, live_orig, spec)
        errs = swap_check(live_orig, wf, generated, spec)
        if errs:
            print('SWAP REFUSED before any write — the swap-phase content is not clean:')
            for e in errs:
                print('  - ' + e)
            return 1
        st, d = api('PUT', f'/workflows/{swap}', wf)
        if st != 200:
            sys.exit(f'deploy-workflow-copy: swap write failed [{st}]')
        live_copy, m = _workflow(swap, meta=True)
        errs = swap_check(live_orig, live_copy, generated, spec)
        if m['active'] is not False:
            errs.append('the copy is not inactive (read back from n8n)')
        if errs:
            print('SWAP CHECK FAILED after the write — do not activate this copy:')
            for e in errs:
                print('  - ' + e)
            return 1
        trig = (spec.get('trigger') or {}).get('node')
        print(f"swap written · swap phase green · {'trigger on the original' + chr(39) + 's live path' if trig else 'no webhook trigger moved'}"
              f" · temporary trigger absent · original and copy both inactive (nothing activated)")
        return 0
    if window:
        # The phase is NAMED by the flag and MEASURED by the check; a copy in the other phase is red before the write.
        phase = 'swap' if turnstile_swapped else 'test'
        state, wid = window
        assert wid == target, 'the Turnstile write must go to the id the guards above checked'
        if turnstile_swapped:
            # The ORDER guard: lowering a swapped copy's gate is a production act only once the swap is declared and
            # the original parked. Before the content check, so a refusal here never depends on what the copy holds.
            why = check_swap_declared(original_id, wid, om['active'])
            if why:
                sys.exit(f'deploy-workflow-copy: refused before any write — {why}')
        try:
            wf = turnstile_patch(tw, state)
        except ValueError as e:
            sys.exit(f'deploy-workflow-copy: {e}')
        wf['settings'] = {k: v for k, v in (wf.get('settings') or {}).items() if k not in (spec.get('settings_allow') or {})}
        # Check BEFORE the write. The first version PUT first and checked after, so a red copy (or a copy in the
        # wrong phase) was already written with its gate lowered by the time the check said so.
        errs = turnstile_check(live_orig, wf, generated, spec, state, phase)
        if errs:
            print(f'TURNSTILE {state.upper()} REFUSED before any write — the {phase}-phase content is not clean:')
            for e in errs:
                print('  - ' + e)
            return 1
        st, d = api('PUT', f'/workflows/{wid}', wf)
        if st != 200:
            sys.exit(f'deploy-workflow-copy: Turnstile write failed [{st}]')
        # And AFTER it, on what n8n actually holds: a 200 does not prove the write landed as sent.
        live_copy, m = _workflow(wid, meta=True)
        errs = turnstile_check(live_orig, live_copy, generated, spec, state, phase)
        if m['active'] is not False:
            errs.append('the copy is not inactive (read back from n8n)')
        if errs:
            print(f'TURNSTILE {state.upper()} CHECK FAILED after the write — no drill may start on this copy:')
            for e in errs:
                print('  - ' + e)
            return 1
        print(f"turnstile {state} on the copy ({phase} phase) · check OK before and after the write — "
              f"{'only the one literal differs' if state == 'off' else phase + '-phase check green'}"
              f" · active read back: {m['active']}")
        return 0
    if verify_only:
        wid = verify_only
    else:
        wf = assemble(generated, live_orig, spec, _pg_credential())
        if update:
            st, d = api('PUT', f'/workflows/{update}', wf)
            wid = update
        else:
            st, d = api('POST', '/workflows', wf)
            wid = d.get('id') if isinstance(d, dict) else None
        if st != 200 or not wid:
            sys.exit(f'deploy-workflow-copy: write failed [{st}]')
    live_copy, m = _workflow(wid, meta=True)
    if not verify_only:
        print(f"deployed '{wf['name']}' ({len(wf['nodes'])} nodes) as workflow {wid} · {'updated' if update else 'created'}"
              f" · active read back: {m['active']}")
    errs = verify(live_orig, live_copy, generated, spec)
    if m['active'] is not False:
        errs.append('the copy is not inactive (read back from n8n)')
    if errs:
        print('VERIFY FAILED — no drill may start on this copy:')
        for e in errs:
            print('  - ' + e)
        return 1
    print(f'verify OK — no new placeholder · only the {len(spec["nodes"])} data node(s), the test path and the '
          f'temporary trigger differ from the live original · not sanitised')
    return 0


# ── selftest: the checks on simulated live workflows, every spec ─────────────────────────────────────────────
def _simulated_live(sanitized):
    """A stand-in for the live original: every committed placeholder replaced by a real-looking value."""
    s = json.dumps(sanitized)
    for i, ph in enumerate(sorted(set(PLACEHOLDER.findall(s)))):
        s = s.replace(ph, f'Live{i:02d}Value{uuid.uuid5(uuid.NAMESPACE_URL, ph).hex[:8]}')
    return json.loads(s)


def selftest():
    ok = True
    specs = sorted(glob.glob(os.path.join(ROOT, 'db', 'copies', '*.json')))
    assert specs, 'no copy specs under db/copies/'
    for f in specs:
        spec = json.load(open(f, encoding='utf-8'))
        generated = BUILD.build(spec)
        live_orig = _simulated_live(json.load(open(os.path.join(ROOT, spec['original']), encoding='utf-8')))
        clean = assemble(generated, live_orig, spec, {'id': 'LiveCredential01', 'name': 'Postgres account'})
        other = next(n['name'] for n in clean['nodes'] if n['name'] not in spec['nodes']
                     and n['type'] not in ('n8n-nodes-base.webhook', 'n8n-nodes-base.stickyNote'))
        placeholder_copy = _copy.deepcopy(clean)
        nd = next(n for n in placeholder_copy['nodes'] if n['name'] == other)
        nd['parameters']['_probe'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
        drifted = _copy.deepcopy(clean)
        next(n for n in drifted['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
        sanitized_whole = _copy.deepcopy(generated)          # what the first D3b deploy effectively was
        for n in sanitized_whole['nodes']:
            if n['name'] in spec['nodes']:
                n['credentials'] = {'postgres': {'id': 'LiveCredential01', 'name': 'Postgres account'}}
        data_param_ph = _copy.deepcopy(clean)                 # only the two placeholder checks can see this one:
        dn = next(n for n in data_param_ph['nodes'] if n['name'] in spec['nodes'])   # diff allows data-node parameters,
        dn['parameters']['query'] += ' -- REPLACE_WITH_SOMETHING'                    # swapped looks at the credential only
        data_ph = _copy.deepcopy(clean)                       # the diff tool allows a data node's credentials to change
        next(n for n in data_ph['nodes'] if n['name'] in spec['nodes'])['credentials'] = \
            {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}}
        no_order = _copy.deepcopy(clean)                     # a key the API might drop that NO ruling allows
        no_order['settings'] = {k: v for k, v in (no_order.get('settings') or {}).items() if k != 'executionOrder'}
        cases = [('clean copy', clean, True), ('settings: executionOrder missing on the copy', no_order, False), (f"placeholder in a non-data node ('{other}')", placeholder_copy, False),
                 (f"non-data node changed ('{other}')", drifted, False),
                 ('a data node still carrying the credential placeholder', data_ph, False),
                 ('the ORIGINAL itself passed as the copy', _copy.deepcopy(live_orig), False),
                 ("a placeholder inside a data node's parameters", data_param_ph, False)]
        for key in spec.get('settings_allow', {}):           # the clean copy is assemble()'s output, so it LACKS each key
            if key in (clean.get('settings') or {}):
                cases.append((f"assemble() sent the allowlisted '{key}'", clean, False))
            kept = _copy.deepcopy(clean)                       # what the helper produced before D4-1, if the original has it
            if key in (live_orig.get('settings') or {}):
                kept['settings'] = dict(kept.get('settings') or {}, **{key: live_orig['settings'][key]})
                cases.append((f"settings: allowlisted '{key}' kept with the original's value", kept, False))
            other_val = _copy.deepcopy(clean); other_val['settings'] = dict(other_val.get('settings') or {}, **{key: '__different__'})
            cases.append((f"settings: allowlisted '{key}' with a different value", other_val, False))
        lcode = next((n for n in live_orig['nodes'] if n['name'] == TS_NODE), {}).get('parameters', {}).get('jsCode', '')
        ts_cases = []
        if len(TS_LITERAL.findall(lcode)) == 1:               # the copies that carry a Turnstile gate (Main)
            off = turnstile_patch(clean, 'off')
            ts_cases.append(('turnstile off: only the one literal changed', off, 'off', True))
            rider = _copy.deepcopy(off)                        # something else slips in with the lowered gate
            rn = next(n for n in rider['nodes'] if n['name'] == TS_NODE)
            rn['parameters']['jsCode'] = rn['parameters']['jsCode'].replace('enabled: true', 'enabled: false', 1)
            ts_cases.append(('turnstile off: a second literal changed with it', rider, 'off', False))
            ride2 = _copy.deepcopy(off)
            next(n for n in ride2['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
            ts_cases.append((f"turnstile off: another node ('{other}') changed with it", ride2, 'off', False))
            ts_cases.append(('turnstile on: restored copy', turnstile_patch(off, 'on'), 'on', True))
            ts_cases.append(("turnstile 'on' check while the literal is still off", off, 'on', False))
            for label, wf, st_ in (('turnstile off twice', off, 'off'), ('turnstile on while already on', clean, 'on')):
                try:
                    turnstile_patch(wf, st_)
                    print(f'✗ {os.path.basename(f)} · {label}: NOT refused'); ok = False
                except ValueError as e:
                    print(f'✓ {os.path.basename(f)} · {label}: refused — {e}')
            two = _copy.deepcopy(clean)
            tn = next(n for n in two['nodes'] if n['name'] == TS_NODE)
            tn['parameters']['jsCode'] += '\n// turnstile: { enabled: true }'
            try:
                turnstile_patch(two, 'off')
                print(f'✗ {os.path.basename(f)} · two Turnstile literals: NOT refused'); ok = False
            except ValueError as e:
                print(f'✓ {os.path.basename(f)} · two Turnstile literals: refused — {e}')
        for label, wf, st_, want_green in ts_cases:
            errs = turnstile_check(live_orig, wf, generated, spec, st_)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        if PLACEHOLDER.search(json.dumps([n for n in generated['nodes'] if n['name'] not in spec['nodes']])):
            cases.append(('the generated (sanitized) copy deployed whole', sanitized_whole, False))
        # The SWAP (D6b): the clean deployed copy, patched for the swap, must be green in the swap phase, and every
        # way of getting the swap content wrong must be red.
        swapped = swap_patch(clean, live_orig, spec)
        sw_cases = [('swap: the clean copy, patched', swapped, True),
                    ('swap: the deployed copy NOT patched (test path / temporary trigger)', clean, not (spec.get('trigger') or spec.get('temp_trigger'))),
                    ('swap: the original itself passed as the copy', _copy.deepcopy(live_orig), False)]
        sw_other = _copy.deepcopy(swapped); next(n for n in sw_other['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
        sw_cases.append((f"swap: a non-data node changed ('{other}')", sw_other, False))
        sw_ph = _copy.deepcopy(swapped)
        next(n for n in sw_ph['nodes'] if n['name'] in spec['nodes'])['credentials'] = \
            {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}}
        sw_cases.append(('swap: a data node on the credential placeholder', sw_ph, False))
        sw_qph = _copy.deepcopy(swapped)                      # only the placeholder check can see this one
        next(n for n in sw_qph['nodes'] if n['name'] in spec['nodes'])['parameters']['query'] += ' -- REPLACE_WITH_SOMETHING'
        sw_cases.append(("swap: a placeholder inside a data node's parameters", sw_qph, False))
        if spec.get('temp_trigger') and spec['temp_trigger']['name'] in {n['name'] for n in clean['nodes']}:
            kept = _copy.deepcopy(swapped)
            kept['nodes'].append(next(n for n in clean['nodes'] if n['name'] == spec['temp_trigger']['name']))
            kept['connections'][spec['temp_trigger']['name']] = clean['connections'][spec['temp_trigger']['name']]
            sw_cases.append(('swap: the temporary trigger left in', kept, False))
        if spec.get('trigger'):
            stay = _copy.deepcopy(swapped)
            next(n for n in stay['nodes'] if n['name'] == spec['trigger']['node'])['parameters']['path'] = spec['trigger']['test_path']
            sw_cases.append(('swap: the trigger left on its test path', stay, False))
        if len(TS_LITERAL.findall(lcode)) == 1:
            sw_cases.append(('swap: the Turnstile literal still lowered', swap_patch(turnstile_patch(clean, 'off'), live_orig, spec), False))
            # The Turnstile window on the SWAPPED copy (D6b smoke): the swap-phase check, and each phase reds the other.
            sw_off = turnstile_patch(swapped, 'off')
            sw_rider = _copy.deepcopy(sw_off)
            rn = next(n for n in sw_rider['nodes'] if n['name'] == TS_NODE)
            rn['parameters']['jsCode'] = rn['parameters']['jsCode'].replace('enabled: true', 'enabled: false', 1)
            sw_ride2 = _copy.deepcopy(sw_off)
            next(n for n in sw_ride2['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
            tsw_cases = [('turnstile-swapped off: only the one literal changed', sw_off, 'off', True, 'swap'),
                         ('turnstile-swapped off: a second literal changed with it', sw_rider, 'off', False, 'swap'),
                         (f"turnstile-swapped off: another node ('{other}') changed with it", sw_ride2, 'off', False, 'swap'),
                         ('turnstile-swapped on: restored copy', turnstile_patch(sw_off, 'on'), 'on', True, 'swap'),
                         ("turnstile-swapped 'on' check while the literal is still off", sw_off, 'on', False, 'swap'),
                         ('turnstile-swapped off on the UNSWAPPED copy (wrong phase)', turnstile_patch(clean, 'off'), 'off', False, 'swap'),
                         ('turnstile (test phase) off on the SWAPPED copy (wrong phase)', sw_off, 'off', False, 'test'),
                         ('turnstile (test phase) on on the SWAPPED copy (wrong phase)', swapped, 'on', False, 'test')]
        else:
            tsw_cases = []
        for label, wf, st_, want_green, phase in tsw_cases:
            errs = turnstile_check(live_orig, wf, generated, spec, st_, phase)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        for label, wf, want_green in sw_cases:
            errs = swap_check(live_orig, wf, generated, spec)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        for label, live_copy, want_green in cases:
            errs = verify(live_orig, live_copy, generated, spec)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
    # The target selection in main()/run(): every pair of write modes is refused BEFORE any API call.
    global api, ROLES_FILE
    real_api, calls, real_roles, fixtures = api, [], ROLES_FILE, []
    api = lambda *a, **k: calls.append(a) or (599, {})

    def roles_fixture(line):
        """A check-exports-parity.sh-shaped file with fake ids, so no case depends on what the committed ROLES says."""
        pairs = (('O1', 'workflow'), ('O2', 'workflow.reminders'), ('C1', 'workflow.main.copy'), ('C2', 'workflow.reminders.copy'))
        with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as t:
            t.write('PAIRS=(\n' + ''.join(f'  "{i}:n8n/{p}.sanitized.json"\n' for i, p in pairs) + ')\n\n'
                    f'ROLES=(\n  "{line}"\n)\n')
        fixtures.append(t.name)
        return t.name
    try:
        for flags in (['--update', 'C1', '--turnstile', 'off', 'O1'], ['--verify', 'C1', '--turnstile', 'on', 'O1'],
                      ['--update', 'C1', '--verify', 'C1']):
            argv = ['deploy', specs[0], '--original-id', 'O1', *flags]
            try:
                rc = main(argv)
            except SystemExit:
                rc = 'SystemExit (main() did not refuse first)'
            try:
                run(specs[0], 'O1', **{'update': 'C1', 'turnstile': ('off', 'O1')}) if '--turnstile' in flags else None
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and not calls and ('--turnstile' not in flags or rrc == 'refused')
            ok = ok and good
            print(f"{'✓' if good else '✗'} {' '.join(f for f in flags if f.startswith('--'))} together: main() exit {rc}, run() {rrc if '--turnstile' in flags else '—'}, API calls {len(calls)}")
        for other_flag in (['--update', 'C1'], ['--verify', 'C1'], ['--turnstile', 'on', 'C1']):
            calls.clear()
            rc = main(['deploy', specs[0], '--original-id', 'O1', '--swap', 'C1', *other_flag])
            try:
                run(specs[0], 'O1', swap='C1', **({'update': 'C1'} if other_flag[0] == '--update' else {'verify_only': 'C1'} if other_flag[0] == '--verify' else {'turnstile': ('on', 'C1')}))
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and rrc == 'refused' and not calls
            ok = ok and good
            print(f"{'✓' if good else '✗'} --swap with {other_flag[0]}: main() exit {rc}, run() {rrc}, API calls {len(calls)}")
        for other_flag, kw in ((['--update', 'C1'], {'update': 'C1'}), (['--verify', 'C1'], {'verify_only': 'C1'}),
                               (['--swap', 'C1'], {'swap': 'C1'}), (['--turnstile', 'on', 'C1'], {'turnstile': ('on', 'C1')})):
            calls.clear()
            try:
                rc = main(['deploy', specs[0], '--original-id', 'O1', '--turnstile-swapped', 'off', 'C1', *other_flag])
            except SystemExit:
                rc = 'SystemExit (main() did not refuse first)'
            try:
                run(specs[0], 'O1', turnstile_swapped=('off', 'C1'), **kw)
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and rrc == 'refused' and not calls
            ok = ok and good
            print(f"{'✓' if good else '✗'} --turnstile-swapped with {other_flag[0]}: main() exit {rc}, run() {rrc}, API calls {len(calls)}")
        # --swap's ORDER guard, on a simulated instance: the original and the copy must both read back inactive,
        # and the one PUT goes to the copy's id. (Spec: Main; its copy simulated as the clean deployed copy.)
        mspec_path = os.path.join(ROOT, 'db', 'copies', 'main.json')
        mspec = json.load(open(mspec_path, encoding='utf-8'))
        mgen = BUILD.build(mspec)
        morig = _simulated_live(json.load(open(os.path.join(ROOT, mspec['original']), encoding='utf-8')))
        mcopy = assemble(mgen, morig, mspec, {'id': 'LiveCredential01', 'name': 'Postgres account'})
        dirty = _copy.deepcopy(mcopy)                     # a placeholder in a non-data node: refused BEFORE the PUT
        next(n for n in dirty['nodes'] if n['name'] == 'Normalize Inbound')['parameters']['_probe'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
        for label, o_active, c_active, want, copy_wf, drop in (
                ('original still ACTIVE', True, False, 'refused', mcopy, False),
                ('copy ACTIVE', False, True, 'refused', mcopy, False),
                ('both inactive', False, False, 'written', mcopy, False),
                ('the copy carries a placeholder (pre-write check)', False, False, 'rc 1', dirty, False),
                ('n8n drops the path change on write (post-write check)', False, False, 'rc 1', mcopy, True)):
            db = {'O1': dict(morig, active=o_active, name='Salon Booking Bot — Main'), 'C1': dict(copy_wf, active=c_active)}
            calls.clear()
            def fake(method, path, body=None, db=db, drop=drop):
                calls.append((method, path))
                wid = path.rsplit('/', 1)[-1]
                if method == 'PUT':
                    db[wid] = dict(_copy.deepcopy(body), active=db[wid]['active'], name=db[wid]['name'])
                    if drop:                                 # the API answers 200 but keeps the old trigger path
                        next(n for n in db[wid]['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path'] = mspec['trigger']['test_path']
                return 200, db[wid]
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(mspec_path, 'O1', swap='C1')
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit:
                got = 'refused'
            puts = [c for c in calls if c[0] == 'PUT']
            good = got == want and (puts == [('PUT', '/workflows/C1')] if (want == 'written' or drop) else not puts)
            if want == 'written':
                trig = next(n for n in db['C1']['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path']
                good = good and trig == next(n for n in morig['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path']
            ok = ok and good
            print(f"{'✓' if good else '✗'} --swap, {label}: {got} · PUTs {puts}")
            api = lambda *a, **k: calls.append(a) or (599, {})
        # The Turnstile window through run(), both phases (Main): checked BEFORE the write (red → no PUT) and again on
        # the read-back after it; an ACTIVE target is refused before anything. The original is inactive, as after --swap.
        msw = swap_patch(mcopy, morig, mspec)
        msw_off, mcopy_off = turnstile_patch(msw, 'off'), turnstile_patch(mcopy, 'off')
        TS, TT = 'turnstile_swapped', 'turnstile'
        ROLES_FILE = roles_fixture('O1:C1:copy')          # the swap declared, as the ORDER guard requires
        for label, mode, state, copy_wf, c_active, mangle, want in (
                ('swapped copy, off', TS, 'off', msw, False, None, 'written'),
                ('swapped copy, on (restored)', TS, 'on', msw_off, False, None, 'written'),
                ('swapped copy ACTIVE', TS, 'off', msw, True, None, 'refused'),
                ('swapped copy with a placeholder (pre-write check)', TS, 'off', swap_patch(dirty, morig, mspec), False, None, 'rc 1'),
                ('an UNSWAPPED copy (wrong phase, pre-write check)', TS, 'off', mcopy, False, None, 'rc 1'),
                ('n8n keeps the old literal on write (post-write check)', TS, 'off', msw, False, 'keep', 'rc 1'),
                ('the copy reads back ACTIVE after the write (post-write check)', TS, 'off', msw, False, 'activate', 'rc 1'),
                ('unswapped copy, off', TT, 'off', mcopy, False, None, 'written'),
                ('unswapped copy, on (restored)', TT, 'on', mcopy_off, False, None, 'written'),
                ('unswapped copy ACTIVE', TT, 'off', mcopy, True, None, 'refused'),
                ('unswapped copy with a placeholder (pre-write check)', TT, 'off', dirty, False, None, 'rc 1'),
                ('n8n keeps the old literal on write (post-write check)', TT, 'off', mcopy, False, 'keep', 'rc 1'),
                ('the SWAPPED copy (wrong phase, pre-write check)', TT, 'off', msw, False, None, 'rc 1')):
            db = {'O1': dict(morig, active=False, name='Salon Booking Bot — Main'), 'C1': dict(copy_wf, active=c_active)}
            calls.clear()
            def fake(method, path, body=None, db=db, mangle=mangle):
                calls.append((method, path))
                wid = path.rsplit('/', 1)[-1]
                if method == 'PUT' and mangle != 'keep':      # 'keep': the API answers 200 and stores nothing
                    db[wid] = dict(_copy.deepcopy(body), active=db[wid]['active'], name=db[wid]['name'])
                if method == 'PUT' and mangle == 'activate':
                    db[wid]['active'] = True
                return 200, db[wid]
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(mspec_path, 'O1', **{mode: (state, 'C1')})
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit:
                got = 'refused'
            puts = [c for c in calls if c[0] == 'PUT']
            wrote = want == 'written' or mangle is not None
            good = got == want and (puts == [('PUT', '/workflows/C1')] if wrote else not puts)
            if want == 'written':
                lit = TS_LITERAL.findall(next(n for n in db['C1']['nodes'] if n['name'] == TS_NODE)['parameters']['jsCode'])
                good = good and lit == (['false'] if state == 'off' else ['true'])
            ok = ok and good
            print(f"{'✓' if good else '✗'} --{mode.replace('_', '-')} {state}, {label}: {got} · PUTs {puts}")
            api = lambda *a, **k: calls.append(a) or (599, {})
        # --turnstile-swapped's ORDER guard (ruling 2026-10-24): refused, with no PUT, unless ROLES declares exactly this
        # pair with the copy live AND the original reads back inactive. The test-phase --turnstile reads neither, so it
        # writes with the original ACTIVE and ROLES saying original (the test phase as it really is) or silent.
        for label, mode, state, copy_wf, roles_line, o_active, want in (
                ('ROLES declares the copy, original inactive', TS, 'off', msw, 'O1:C1:copy', False, 'written'),
                ('ROLES still declares the original', TS, 'off', msw, 'O1:C1:original', False, 'refused'),
                ('ROLES still declares the original (restore)', TS, 'on', msw_off, 'O1:C1:original', False, 'refused'),
                ('ROLES has no line for this pair', TS, 'off', msw, 'O2:C2:copy', False, 'refused'),
                ('ROLES does not read (the pair written the wrong way round)', TS, 'off', msw, 'C1:O1:copy', False, 'refused'),
                ('the original still ACTIVE (ROLES declares the copy)', TS, 'off', msw, 'O1:C1:copy', True, 'refused'),
                ('the original still ACTIVE (restore)', TS, 'on', msw_off, 'O1:C1:copy', True, 'refused'),
                ('test phase: ROLES declares the original, original ACTIVE', TT, 'off', mcopy, 'O1:C1:original', True, 'written'),
                ('test phase: ROLES has no line for this pair', TT, 'off', mcopy, 'O2:C2:copy', True, 'written')):
            ROLES_FILE = roles_fixture(roles_line)
            db = {'O1': dict(morig, active=o_active, name='Salon Booking Bot — Main'), 'C1': dict(copy_wf, active=False)}
            calls.clear()
            def fake(method, path, body=None, db=db):
                calls.append((method, path))
                wid = path.rsplit('/', 1)[-1]
                if method == 'PUT':
                    db[wid] = dict(_copy.deepcopy(body), active=db[wid]['active'], name=db[wid]['name'])
                return 200, db[wid]
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(mspec_path, 'O1', **{mode: (state, 'C1')})
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit as e:
                got, why = 'refused', str(e.code)
            puts = [c for c in calls if c[0] == 'PUT']
            good = got == want and (puts == [('PUT', '/workflows/C1')] if want == 'written' else not puts)
            ok = ok and good
            print(f"{'✓' if good else '✗'} --{mode.replace('_', '-')} {state}, ORDER guard, {label}: {got}"
                  f"{' (' + why.split('— ', 1)[-1][:120] + ')' if got == 'refused' else ''} · PUTs {puts}")
            api = lambda *a, **k: calls.append(a) or (599, {})
    finally:
        api, ROLES_FILE = real_api, real_roles
        for p in fixtures:
            os.unlink(p)
    print('deploy-workflow-copy selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    if len(argv) < 2 or '--original-id' not in argv:
        print(__doc__)
        return 2
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    if sum(k in argv for k in ('--update', '--verify', '--turnstile', '--swap', '--turnstile-swapped')) > 1:
        print('deploy-workflow-copy: refused — --update, --verify, --turnstile, --turnstile-swapped and --swap are '
              'exclusive (one target per run)')
        return 2
    windows = {}
    for flag in ('--turnstile', '--turnstile-swapped'):
        if flag in argv:
            i = argv.index(flag)
            windows[flag] = tuple(argv[i + 1:i + 3])
            if len(windows[flag]) != 2 or windows[flag][0] not in ('off', 'on'):
                print(f'usage: … {flag} off|on COPY_ID')
                return 2
    return run(argv[1], opt('--original-id'), update=opt('--update'), verify_only=opt('--verify'),
               turnstile=windows.get('--turnstile'), swap=opt('--swap'), turnstile_swapped=windows.get('--turnstile-swapped'))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
