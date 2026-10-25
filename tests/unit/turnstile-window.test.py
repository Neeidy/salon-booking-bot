#!/usr/bin/env python3
"""scripts/turnstile-window.py, offline: a stand-in for the n8n public API AND the webhook on 127.0.0.1 (loopback
only, remote-operator.md), and a fake deploy helper that flips the copy's Turnstile literal through that stand-in.
The window's own HTTP layer (the real curl) and its precheck run for real against it; the precheck's prediction uses
the REAL deploy helper's pure checks on workflows built from the committed exports (as the helper's own selftest does).

What it proves: the window closes and restores in `finally` when the command fails, times out, cannot start, is
interrupted (KeyboardInterrupt) or the process gets SIGTERM; it refuses to open (nothing touched, no helper call) when
ROLES declares the original, the original is active, the literal is not true, or a dummy token is not 403; and it
NEVER re-activates a copy whose draft literal is not true (SAFETY exit 3), even when the helper fails half-way.

Run: python3 tests/unit/turnstile-window.test.py   (TURNSTILE_WINDOW=<path> runs it against another copy of the
script — a mutant — with every import still resolving to this repo)
"""
import contextlib
import copy
import http.server
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRIG = 'Receive Inbound Message'
LIT = re.compile(r'turnstile\s*:\s*\{\s*enabled\s*:\s*(true|false)\s*\}')

FAKE_HELPER = r'''
import json, os, sys, urllib.request
base = os.environ['N8N_API_URL']
i = sys.argv.index('--turnstile-swapped')
state, wid = sys.argv[i + 1], sys.argv[i + 2]
mode = os.environ.get('FAKE_HELPER_MODE', 'ok')
def post(path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json'})
    try:
        return urllib.request.urlopen(req, timeout=10).status
    except urllib.error.HTTPError as e:
        return e.code
post('/__test/helper-call', {'state': state})
if mode == 'refuse-' + state:
    print(f'TURNSTILE {state.upper()} REFUSED before any write (fake)')
    sys.exit(1)
code = post('/__test/literal', {'wid': wid, 'value': 'false' if state == 'off' else 'true'})
if code != 200:
    print(f'fake helper: write refused [{code}]')
    sys.exit(1)
if mode == 'write-then-fail-' + state:
    print(f'TURNSTILE {state.upper()} CHECK FAILED after the write (fake)')
    sys.exit(1)
print(f'turnstile {state} on the copy (swap phase) · fake helper OK')
'''


def load_script():
    path = os.environ.get('TURNSTILE_WINDOW', os.path.join(ROOT, 'scripts', 'turnstile-window.py'))
    spec = importlib.util.spec_from_file_location('turnstile_window_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = ROOT                 # imports resolve to THIS repo, wherever the script under test lives
    mod.PROBE_WAIT_S = 0
    mod.ACTIVATE_WAIT_S = 0
    return mod


def helper_module():
    spec = importlib.util.spec_from_file_location('dwc_for_fixtures', os.path.join(ROOT, 'scripts', 'deploy-workflow-copy.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class World:
    """The fake instance's state. Ids are fixture ids (O1/C1): no real workflow id is used or written."""

    def __init__(self, orig, copy_wf):
        self.wf = {'O1': dict(copy.deepcopy(orig), active=False, published=None),
                   'C1': dict(copy.deepcopy(copy_wf), active=True, published=copy.deepcopy(copy_wf['nodes']))}
        self.execs = {'O1': [], 'C1': []}
        self.log = []                # ('activate'|'deactivate'|'helper', id or state)
        self.force_dummy = {}        # probe number (1-based) → status the webhook answers instead
        self.probes = 0
        self.lock = threading.Lock()

    def literal(self, nodes):
        code = next((n for n in nodes or [] if n['name'] == 'Load Config'), {}).get('parameters', {}).get('jsCode', '')
        return LIT.findall(code)

    def set_literal(self, wid, value, published=False):
        for nodes in ([self.wf[wid]['nodes']] + ([self.wf[wid]['published']] if published else [])):
            n = next(n for n in nodes if n['name'] == 'Load Config')
            n['parameters']['jsCode'] = LIT.sub(f'turnstile: {{ enabled: {value} }}', n['parameters']['jsCode'], count=1)


def make_handler(world):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(raw)

        def body(self):
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}')

        def do_GET(self):
            with world.lock:
                if self.path.startswith('/api/v1/workflows?'):
                    return self.reply(200, {'data': [{'id': k, 'name': w['name'], 'active': w['active'], 'nodes': w['nodes']}
                                                     for k, w in world.wf.items()]})
                if self.path.startswith('/api/v1/executions?'):
                    wid = re.search(r'workflowId=([A-Za-z0-9]+)', self.path).group(1)
                    return self.reply(200, {'data': [{'startedAt': t} for t in world.execs.get(wid, [])]})
                m = re.fullmatch(r'/api/v1/workflows/([A-Za-z0-9]+)', self.path)
                if m and m.group(1) in world.wf:
                    w = world.wf[m.group(1)]
                    return self.reply(200, {'id': m.group(1), 'name': w['name'], 'active': w['active'], 'nodes': w['nodes'],
                                            'connections': w['connections'], 'settings': w.get('settings'),
                                            'activeVersion': {'nodes': w['published']} if w['published'] else None})
                return self.reply(404, {'message': 'not found'})

        def do_POST(self):
            body = self.body()
            with world.lock:
                m = re.fullmatch(r'/api/v1/workflows/([A-Za-z0-9]+)/(activate|deactivate)', self.path)
                if m:
                    w = world.wf[m.group(1)]
                    world.log.append((m.group(2), m.group(1)))
                    w['active'] = m.group(2) == 'activate'
                    if w['active']:
                        w['published'] = copy.deepcopy(w['nodes'])
                    return self.reply(200, {'id': m.group(1), 'active': w['active']})
                if self.path == '/__test/helper-call':
                    world.log.append(('helper', body['state']))
                    return self.reply(200, {})
                if self.path == '/__test/literal':
                    if world.wf[body['wid']]['active']:
                        return self.reply(409, {'message': 'active'})      # the real helper refuses an active target
                    world.set_literal(body['wid'], body['value'])
                    return self.reply(200, {})
                if self.path.startswith('/webhook/'):
                    path = self.path[len('/webhook/'):]
                    holder = [k for k, w in world.wf.items() if w['active'] and w['published'] and any(
                        n['name'] == TRIG and n['parameters'].get('path') == path for n in w['published'])]
                    if not holder:
                        return self.reply(404, {'message': 'webhook not registered'})
                    world.execs[holder[0]].append(time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()))
                    world.probes += 1
                    if world.probes in world.force_dummy:
                        return self.reply(world.force_dummy[world.probes], {'reply': 'forced'})
                    if body.get('turnstileToken') and world.literal(world.wf[holder[0]]['published']) == ['true']:
                        return self.reply(403, {'ok': False, 'error': 'turnstile_failed'})
                    return self.reply(200, {'reply': 'the brain answered'})
                return self.reply(404, {'message': 'not found'})
    return H


def roles_fixture(d, line):
    p = os.path.join(d, f'roles-{abs(hash(line))}.sh')
    with open(p, 'w') as f:
        f.write('PAIRS=(\n  "O1:n8n/workflow.sanitized.json"\n  "C1:n8n/workflow.main.copy.sanitized.json"\n)\n\n'
                f'ROLES=(\n  "{line}"\n)\n')
    return p


def main():
    X = helper_module()
    spec = json.load(open(os.path.join(ROOT, 'db', 'copies', 'main.json'), encoding='utf-8'))
    orig = X._simulated_live(json.load(open(os.path.join(ROOT, spec['original']), encoding='utf-8')))
    deployed = X.assemble(X.BUILD.build(spec), orig, spec, {'id': 'LiveCredential01', 'name': 'Postgres account'})
    swapped = X.swap_patch(deployed, orig, spec)
    orig = {k: orig.get(k) for k in ('name', 'nodes', 'connections', 'settings')}
    swapped = {k: swapped.get(k) for k in ('name', 'nodes', 'connections', 'settings')}

    tmp = tempfile.mkdtemp(prefix='tw-test-')
    fake_helper = os.path.join(tmp, 'fake_helper.py')
    open(fake_helper, 'w').write(FAKE_HELPER)
    roles_copy, roles_orig = roles_fixture(tmp, 'O1:C1:copy'), roles_fixture(tmp, 'O1:C1:original')

    pid = os.getpid()
    PY = sys.executable
    cases = [
        # label, command, timeout, setup(world, env) → roles file, want exit, want final copy (active, draft, published), want helper calls
        ('green: command exits 0', [PY, '-c', 'pass'], 60, {'text': 'predicted GREEN'}, 0, (True, ['true'], ['true']), ['off', 'on']),
        ('command FAILS (exit 1): closed and restored', [PY, '-c', 'import sys; sys.exit(1)'], 60, {}, 1,
         (True, ['true'], ['true']), ['off', 'on']),
        ('command TIMES OUT: its group stopped, closed and restored', [PY, '-c', 'import time; time.sleep(30)'], 1, {}, 1,
         (True, ['true'], ['true']), ['off', 'on']),
        ('command CANNOT START (raises FileNotFoundError): closed and restored', [os.path.join(tmp, 'no-such-binary')], 60,
         {}, 1, (True, ['true'], ['true']), ['off', 'on']),
        ('KeyboardInterrupt in the command step: closed and restored', None, 60, {'raise': KeyboardInterrupt}, 1,
         (True, ['true'], ['true']), ['off', 'on']),
        ('SIGTERM to the window process mid-command: closed and restored',
         [PY, '-c', f'import os, signal, time; os.kill({pid}, signal.SIGTERM); time.sleep(30)'], 60, {}, 1,
         (True, ['true'], ['true']), ['off', 'on']),
        ('REFUSED: ROLES declares the original live', [PY, '-c', 'pass'], 60, {'roles': roles_orig, 'text': 'ROLES declares the original live'}, 2,
         (True, ['true'], ['true']), []),
        ('REFUSED: the original is ACTIVE', [PY, '-c', 'pass'], 60, {'orig_active': True, 'text': "order guard refuses"}, 2, (True, ['true'], ['true']), []),
        ('REFUSED: the literal is not true (published and draft false)', [PY, '-c', 'pass'], 60, {'literal': 'false', 'text': 'Turnstile literal is not true'}, 2,
         (True, ['false'], ['false']), []),
        ('REFUSED: a dummy token is not 403 (200)', [PY, '-c', 'pass'], 60, {'force': {1: 200}, 'text': 'does not answer a dummy token 403'}, 2,
         (True, ['true'], ['true']), []),
        ("REFUSED: the copy drifted from the original (the helper's checks predicted RED)", [PY, '-c', 'pass'], 60,
         {'drift': True, 'text': 'predicted RED'}, 2, (True, ['true'], ['true']), []),
        ("helper 'on' REFUSES: never re-activated with a false draft literal (SAFETY)", [PY, '-c', 'pass'], 60,
         {'mode': 'refuse-on'}, 3, (False, ['false'], ['false']), ['off', 'on']),
        ("helper 'off' writes, then fails: command not run, 'on' restores", [PY, '-c', 'raise SystemExit(9)'], 60,
         {'mode': 'write-then-fail-off'}, 1, (True, ['true'], ['true']), ['off', 'on']),
        ("helper 'off' refuses before writing: nothing to restore, copy re-activated", [PY, '-c', 'raise SystemExit(9)'], 60,
         {'mode': 'refuse-off'}, 1, (True, ['true'], ['true']), ['off']),
        ('restored in the draft but the dummy token answers 200 after the close: copy stopped (SAFETY)', [PY, '-c', 'pass'],
         60, {'force': {2: 200}}, 3, (False, ['true'], ['true']), ['off', 'on']),
    ]
    ok = True
    for label, cmd, timeout, setup, want_rc, (want_active, want_draft, want_pub), want_helper in cases:
        world = World(orig, swapped)
        if setup.get('orig_active'):
            world.wf['O1']['active'], world.wf['O1']['published'] = True, copy.deepcopy(world.wf['O1']['nodes'])
        if setup.get('literal'):
            world.set_literal('C1', setup['literal'], published=True)
        if setup.get('drift'):
            for nodes in (world.wf['C1']['nodes'], world.wf['C1']['published']):
                next(n for n in nodes if n['name'] == 'Normalize Inbound')['parameters']['_probe'] = 'changed'
        world.force_dummy = setup.get('force', {})
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), make_handler(world))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        saved = {k: os.environ.get(k) for k in ('N8N_API_URL', 'N8N_API_KEY', 'N8N_HOST', 'FAKE_HELPER_MODE',
                                                 'CF_ACCESS_CLIENT_ID', 'CF_ACCESS_CLIENT_SECRET')}
        os.environ.update({'N8N_API_URL': f'http://127.0.0.1:{srv.server_address[1]}', 'N8N_API_KEY': 'fake-test-key',
                           'N8N_HOST': 'host.invalid', 'FAKE_HELPER_MODE': setup.get('mode', 'ok'),
                           'CF_ACCESS_CLIENT_ID': 'fake-id', 'CF_ACCESS_CLIENT_SECRET': 'fake-secret'})
        tw = load_script()
        tw.HELPER, tw.ROLES_FILE = fake_helper, setup.get('roles', roles_copy)
        if setup.get('raise'):
            exc = setup['raise']

            def boom(*_a, **_k):
                raise exc()
            tw.run_command = boom
        out = io.StringIO()
        t0 = time.time()
        try:
            with contextlib.redirect_stdout(out):
                rc = tw.main(['turnstile-window.py', '--timeout', str(timeout), '--', *(cmd or [PY, '-c', 'pass'])])
        except BaseException as e:      # a mutant may let an exception escape; that is a red case, not a crash
            rc = f'escaped {type(e).__name__}'
        took = time.time() - t0
        srv.shutdown()
        srv.server_close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        c = world.wf['C1']
        final = (c['active'], world.literal(c['nodes']), world.literal(c['published']))
        helper_calls = [s for a, s in world.log if a == 'helper']
        touched = [e for e in world.log if e[0] in ('activate', 'deactivate')]
        good = rc == want_rc and final == (want_active, want_draft, want_pub) and helper_calls == want_helper
        if want_rc == 2:
            good = good and not touched                                   # refused: nothing touched at all
        if 'refuse-on' == setup.get('mode'):
            # the ONLY activation is the window's opening one: the close never re-activates (the draft never read true)
            good = good and [e[0] for e in world.log if e[0] == 'activate'] == ['activate']
        if setup.get('text'):
            good = good and setup['text'] in out.getvalue()   # refused for THIS reason, not another
        if want_rc == 3:
            good = good and 'SAFETY' in out.getvalue()
        if 'TIMES OUT' in label:
            good = good and took < 25
        if want_rc in (0, 1, 3):
            good = good and 'WINDOW OPEN' in out.getvalue() and 'WINDOW CLOSED' in out.getvalue()
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}: exit {rc} · copy active {final[0]}, draft {final[1]}, published {final[2]}"
              f" · helper {helper_calls} · {len(touched)} (de)activations"
              + ('' if good else '\n    ' + '\n    '.join(out.getvalue().strip().splitlines()[-8:])))
    for p in (fake_helper, roles_copy, roles_orig):
        os.unlink(p)
    os.rmdir(tmp)
    print('turnstile-window:', 'OK' if ok else 'FAILED', f'({len(cases)} cases)')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
