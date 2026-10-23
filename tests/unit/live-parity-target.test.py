#!/usr/bin/env python3
"""check-live-parity.py's TARGET (MIGRATION-PLAN §3t, decision 9): with no workflow id given, it compares the ONE active
workflow listening on `barber-inbound`, against THAT workflow's own PAIRS export — Main original before the cutover,
Main's copy after it. Offline: a stand-in for the n8n public API on 127.0.0.1 (loopback only, remote-operator.md)
serves the workflow list and each workflow's published graph, built from the committed exports.

Run: python3 tests/unit/live-parity-target.test.py   (LIVE_PARITY=<path> runs it against another copy of the script)
"""
import http.server, json, os, subprocess, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.environ.get('LIVE_PARITY', os.path.join(ROOT, 'scripts', 'check-live-parity.py'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import pair_roles  # noqa: E402

pairs, roles = pair_roles.load()
main_role = next(r for r in roles if pairs[r['orig']] == 'n8n/workflow.sanitized.json')
O, C = main_role['orig'], main_role['copy']


def published(export, path):
    wf = json.load(open(os.path.join(ROOT, export), encoding='utf-8'))
    nodes = json.loads(json.dumps(wf['nodes']))
    for n in nodes:
        if n['name'] == 'Receive Inbound Message':
            n['parameters']['path'] = path
    return {'nodes': nodes, 'connections': wf['connections']}


STATE = {}


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith('/api/v1/workflows?'):
            body = {'data': [dict(id=w, active=s['active'], nodes=s['nodes']) for w, s in STATE.items()]}
        else:
            wid = self.path.rsplit('/', 1)[-1]
            s = STATE[wid]
            body = {'id': wid, 'active': s['active'], 'nodes': s['nodes'], 'connections': s['connections'],
                    'activeVersion': {'nodes': s['nodes'], 'connections': s['connections']} if s['active'] else None}
        raw = json.dumps(body).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)


srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
api = f'http://127.0.0.1:{srv.server_address[1]}'

before = {O: dict(active=True, **published('n8n/workflow.sanitized.json', 'barber-inbound')),
          C: dict(active=False, **published('n8n/workflow.main.copy.sanitized.json', 'owner-mig-main'))}
after = {O: dict(active=False, **published('n8n/workflow.sanitized.json', 'barber-inbound')),
         C: dict(active=True, **published('n8n/workflow.main.copy.sanitized.json', 'barber-inbound'))}
both = {O: dict(before[O]), C: dict(after[C])}

ok = True
for label, state, want_rc, want_out in (
        ('before the cutover: Main original, against workflow.sanitized.json', before, 0, f'({O[:4]}…), compared with n8n/workflow.sanitized.json'),
        ("after the cutover: Main's copy, against ITS export", after, 0, f'({C[:4]}…), compared with n8n/workflow.main.copy.sanitized.json'),
        ('two active holders of barber-inbound: refused', both, 1, 'NO SINGLE PRODUCTION HOLDER')):
    STATE.clear(); STATE.update(json.loads(json.dumps(state)))
    env = {k: v for k, v in os.environ.items() if k not in ('N8N_WORKFLOW_ID', 'SANITIZED_PATH', 'CF_ACCESS_CLIENT_ID', 'CF_ACCESS_CLIENT_SECRET')}
    r = subprocess.run([sys.executable, SCRIPT], cwd=ROOT, env=dict(env, N8N_API_URL=api, N8N_API_KEY='fake-test-key'),
                       capture_output=True, text=True, timeout=60)
    good = r.returncode == want_rc and want_out in r.stdout
    ok = ok and good
    print(f"{'✓' if good else '✗'} {label}: exit {r.returncode}" + ('' if good else f" · {r.stdout.strip()[-160:]} {r.stderr.strip()[-160:]}"))
srv.shutdown()
print('live-parity target:', 'OK' if ok else 'FAILED')
sys.exit(0 if ok else 1)
