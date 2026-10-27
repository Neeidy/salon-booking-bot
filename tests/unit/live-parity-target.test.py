#!/usr/bin/env python3
"""check-live-parity.py's TARGET (MIGRATION-PLAN §3t, decision 9; unpaired at D6c, 2026-10-27): with no workflow id
given, it compares the ONE active workflow listening on `barber-inbound`, which must be listed in WORKFLOWS
(scripts/workflows.py), against that workflow's own committed export. Offline: a stand-in for the n8n public API on
127.0.0.1 (loopback only, remote-operator.md) serves the workflow list and each workflow's published graph, built from
the committed exports.

Run: python3 tests/unit/live-parity-target.test.py   (LIVE_PARITY=<path> runs it against another copy of the script)
"""
import http.server, json, os, subprocess, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.environ.get('LIVE_PARITY', os.path.join(ROOT, 'scripts', 'check-live-parity.py'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import workflows  # noqa: E402

listed = workflows.load()
M = workflows.id_for(listed, 'main')
X = 'Unlisted0000000X'              # an id WORKFLOWS does not list


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

MAIN_EXPORT = 'n8n/workflow.main.sanitized.json'
main_live = dict(active=True, **published(MAIN_EXPORT, 'barber-inbound'))
ok = True
for label, state, want_rc, want_out in (
        ('the listed Main is the one holder: compared with ITS export', {M: main_live}, 0, f'({M[:4]}…), compared with {MAIN_EXPORT}'),
        ('an unlisted active holder of barber-inbound: refused', {X: dict(main_live)}, 1, 'not listed in WORKFLOWS'),
        ('two active holders of barber-inbound: refused', {M: main_live, X: dict(main_live)}, 1, 'NO SINGLE PRODUCTION HOLDER'),
        ('no active holder: refused', {M: dict(main_live, active=False)}, 1, 'NO SINGLE PRODUCTION HOLDER'),
        ('an INACTIVE unlisted workflow on the path does not count', {M: main_live, X: dict(main_live, active=False)}, 0,
         f'({M[:4]}…), compared with {MAIN_EXPORT}')):
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
