#!/usr/bin/env python3
"""check-content-parity.py's two workflow rules since D6c (2026-10-27, the copy↔original pairing ended):
  · check_listed: the id must be the one WORKFLOWS (check-exports-parity.sh) lists for the export — exit 1 when it is
    another workflow's id, exit 2 when the path is not a workflow export at all;
  · check_published_matches_draft: a listed workflow is a production role, so an INACTIVE one is RED (exit 1); an active
    one whose published graph cannot be seen is "could not measure" (exit 2).
Runs the guard's own functions, and then the whole guard end to end against a stand-in for the n8n API on 127.0.0.1
(its success path once printed a name D6c had removed, which no function-level case reaches). No network, no credentials.

Run: python3 tests/unit/content-parity-inactive.test.py   (GUARD=<path> runs it against another copy of the guard)
"""
import contextlib, importlib.util, io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD = os.environ.get('GUARD', os.path.join(ROOT, 'scripts', 'check-content-parity.py'))
argv, sys.argv = sys.argv, ['x', os.path.join(ROOT, 'n8n', 'workflow.drill-state.sanitized.json')]
spec = importlib.util.spec_from_file_location('ccp', GUARD); m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass
sys.argv = argv
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import workflows  # noqa: E402

listed = workflows.load()
by_key = {workflows.key_of(e): w for w, e in listed.items()}
DS, MAIN = by_key['drill-state'], by_key['main']
EXP = lambda k: os.path.join(ROOT, 'n8n', f'workflow.{k}.sanitized.json')


def run(fn, *a):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn(*a)
        return 'pass'
    except SystemExit as e:
        return f'exit {e.code}'


nodes = [{'name': 'A', 'type': 'n8n-nodes-base.code', 'parameters': {'jsCode': '1'}}]
CASES = [
    ('listed: the id WORKFLOWS lists for the export', (m.check_listed, DS, EXP('drill-state')), 'pass'),
    ("listed: another listed workflow's id on this export", (m.check_listed, MAIN, EXP('drill-state')), 'exit 1'),
    ('listed: an id nobody lists', (m.check_listed, 'Zzzzzzzzzzzzzzzz', EXP('drill-state')), 'exit 1'),
    ('listed: a path that is not a workflow export', (m.check_listed, DS, os.path.join(ROOT, 'db', 'copies', 'main.json')), 'exit 2'),
    ('an inactive listed workflow', (m.check_published_matches_draft, {'active': False, 'nodes': []}), 'exit 1'),
    ('an inactive workflow that still shows a published graph',
     (m.check_published_matches_draft, {'active': False, 'nodes': nodes, 'activeVersion': {'nodes': nodes}}), 'exit 1'),
    ('an active workflow with no visible published graph', (m.check_published_matches_draft, {'active': True, 'nodes': nodes}), 'exit 2'),
    ('an active workflow whose published graph equals the draft',
     (m.check_published_matches_draft, {'active': True, 'nodes': nodes, 'activeVersion': {'nodes': nodes}}), 'pass'),
]
ok = True
for label, (fn, *a), want in CASES:
    got = run(fn, *a)
    ok = ok and got == want
    print(f"{'✓' if got == want else '✗'} {label}: expected {want}, got {got}")

# END TO END: the guard as a process, against live workflows simulated from the committed exports (every placeholder
# replaced by a real-looking value, as the deploy helper's own simulation does). Main carries binaryMode live, which its
# spec allowlists; the same live value on Drill State, which allowlists nothing, is drift.
import http.server, json, subprocess, threading  # noqa: E402
_hs = importlib.util.spec_from_file_location('dwc', os.path.join(ROOT, 'scripts', 'deploy-workflow-copy.py'))
H = importlib.util.module_from_spec(_hs); _hs.loader.exec_module(H)
LIVE = {}


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        w = LIVE[self.path.rsplit('/', 1)[-1]]
        raw = json.dumps(dict(w, activeVersion={'nodes': w['nodes'], 'connections': w['connections']})).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)


srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
env = {k: v for k, v in os.environ.items() if k not in ('N8N_WORKFLOW_ID', 'SANITIZED_PATH', 'CF_ACCESS_CLIENT_ID', 'CF_ACCESS_CLIENT_SECRET')}
env.update(N8N_API_URL=f'http://127.0.0.1:{srv.server_address[1]}', N8N_API_KEY='fake-test-key')
for label, key, extra, want_rc, want_out in (
        ('end to end: Main, binaryMode "separate" live (allowlisted)', 'main', {'binaryMode': 'separate'}, 0, "except the allowlisted live-only key(s) ['binaryMode']"),
        ('end to end: Main, binaryMode "combined" live', 'main', {'binaryMode': 'combined'}, 1, "allowlisted live only as exactly 'separate'"),
        ('end to end: Drill State, settings equal', 'drill-state', {}, 0, 'settings parity OK'),
        ('end to end: Drill State, binaryMode live (not allowlisted there)', 'drill-state', {'binaryMode': 'separate'}, 1, "'binaryMode' is live but not")):
    comm = json.load(open(EXP(key), encoding='utf-8'))
    live = H._simulated_live(comm, keep=m.EXEMPT)
    live.update(active=True, settings=dict(comm.get('settings') or {}, **extra))
    wid = by_key[key]
    LIVE.clear(); LIVE[wid] = live
    r = subprocess.run([sys.executable, GUARD, EXP(key)], cwd=ROOT, env=dict(env, N8N_WORKFLOW_ID=wid), capture_output=True,
                       text=True, timeout=60, stdin=subprocess.DEVNULL)
    good = r.returncode == want_rc and want_out in r.stdout
    ok = ok and good
    CASES.append(label)
    print(f"{'✓' if good else '✗'} {label}: exit {r.returncode}" + ('' if good else f" · {r.stdout.strip()[-200:]} {r.stderr.strip()[-200:]}"))
srv.shutdown()
print('content-parity workflow rules:', 'OK' if ok else 'FAILED', f'({len(CASES)} cases)')
sys.exit(0 if ok else 1)
