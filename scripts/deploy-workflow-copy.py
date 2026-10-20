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
      (--update and --verify refuse the original's id and any target that is active or not named as the spec)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --verify COPY_ID
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


BUILD = _module('scripts/build-workflow-copy.py', 'build_workflow_copy')
DIFF = _module('scripts/diff-workflow-copy.py', 'diff_workflow_copy')


# ── the three checks (pure: no network) ──────────────────────────────────────────────────────────────────────
def check_placeholders(live_orig, live_copy):
    extra = set(PLACEHOLDER.findall(json.dumps(live_copy))) - set(PLACEHOLDER.findall(json.dumps(live_orig)))
    return [f'placeholder in the live copy that the live original does not hold: {p}' for p in sorted(extra)]


def check_diff(live_orig, live_copy, spec):
    return DIFF.compare(live_orig, live_copy, set(spec['nodes']), phase='test',
                        temp_trigger=(spec.get('temp_trigger') or {}).get('name'),
                        trigger=(spec.get('trigger') or {}).get('node'))


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
    return {'name': generated['name'], 'nodes': nodes, 'connections': generated['connections'],
            'settings': live_orig.get('settings') or generated.get('settings') or {}}


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


def run(spec_path, original_id, update=None, verify_only=None):
    spec = json.load(open(spec_path, encoding='utf-8'))
    generated = BUILD.build(spec)
    live_orig = _workflow(original_id)
    target = verify_only or update
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
        cases = [('clean copy', clean, True), (f"placeholder in a non-data node ('{other}')", placeholder_copy, False),
                 (f"non-data node changed ('{other}')", drifted, False),
                 ('a data node still carrying the credential placeholder', data_ph, False),
                 ('the ORIGINAL itself passed as the copy', _copy.deepcopy(live_orig), False),
                 ("a placeholder inside a data node's parameters", data_param_ph, False)]
        if PLACEHOLDER.search(json.dumps([n for n in generated['nodes'] if n['name'] not in spec['nodes']])):
            cases.append(('the generated (sanitized) copy deployed whole', sanitized_whole, False))
        for label, live_copy, want_green in cases:
            errs = verify(live_orig, live_copy, generated, spec)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
    print('deploy-workflow-copy selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    if len(argv) < 2 or '--original-id' not in argv:
        print(__doc__)
        return 2
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    return run(argv[1], opt('--original-id'), update=opt('--update'), verify_only=opt('--verify'))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
