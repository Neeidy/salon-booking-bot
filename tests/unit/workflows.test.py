#!/usr/bin/env python3
"""scripts/workflows.py — the one list of production workflows since D6c (2026-10-27) — and check-active-set.py, which
applies its active-set rule to the live instance. Offline: the parser runs on fixture files in a temporary directory,
check-active-set against a stand-in for the n8n API on 127.0.0.1 (loopback only, remote-operator.md).
Every refusal is a case that only that refusal can turn red.

Run: python3 tests/unit/workflows.test.py   (WORKFLOWS_SRC / ACTIVE_SET=<path> run it against another copy of the module / script)
"""
import http.server, importlib.util, json, os, subprocess, sys, tempfile, threading, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.environ.get('WORKFLOWS_SRC', os.path.join(ROOT, 'scripts', 'workflows.py'))
_s = importlib.util.spec_from_file_location('workflows', SRC)
W = importlib.util.module_from_spec(_s); _s.loader.exec_module(W)

TMP = tempfile.mkdtemp(prefix='wftest-')
SPECS = os.path.join(TMP, 'copies'); os.makedirs(SPECS)
for k in ('main', 'purge'):
    open(os.path.join(SPECS, f'{k}.json'), 'w').write('{}')
GOOD = ['"AAAA1111:n8n/workflow.main.sanitized.json"', '"BBBB2222:n8n/workflow.purge.sanitized.json"']
_n = [0]


def sh(lines, extra=''):
    _n[0] += 1
    p = os.path.join(TMP, f'w{_n[0]}.sh')
    open(p, 'w').write(extra + 'WORKFLOWS=(\n' + ''.join(f'  {l}\n' for l in lines) + ')\n')
    return p


def load(lines, extra=''):
    try:
        return W.load(sh(lines, extra), SPECS)
    except ValueError as e:
        return f'refused: {e}'


ok = True


def case(label, good, detail=''):
    global ok
    ok = ok and good
    print(f"{'✓' if good else '✗'} {label}" + (f': {detail}' if detail else ''))


got = load(GOOD)
case('load: two well-formed lines', got == {'AAAA1111': 'n8n/workflow.main.sanitized.json', 'BBBB2222': 'n8n/workflow.purge.sanitized.json'}, str(got)[:90])
got = load([GOOD[0] + '   # a comment', '', GOOD[1]])
case('load: comments and blank lines are skipped', isinstance(got, dict) and len(got) == 2, str(got)[:90])
for label, lines, extra, needle in (
        ('a PAIRS block still declared', GOOD, 'PAIRS=(\n)\n', 'PAIRS or ROLES'),
        ('a ROLES block still declared', GOOD, 'ROLES=(\n)\n', 'PAIRS or ROLES'),
        ('a malformed line (no export)', ['"AAAA1111"', GOOD[1]], '', 'malformed'),
        ('a malformed line (a copy export name)', ['"AAAA1111:n8n/workflow.main.copy.sanitized.json"'], '', 'malformed'),
        ('an id with a character outside letters/digits', ['"AAA-1111:n8n/workflow.main.sanitized.json"'], '', 'malformed'),
        ('an id twice', [GOOD[0], '"AAAA1111:n8n/workflow.purge.sanitized.json"'], '', 'id twice'),
        ('an export twice', [GOOD[0], '"CCCC3333:n8n/workflow.main.sanitized.json"'], '', 'export twice'),
        ('a workflow with no spec file', [GOOD[0], '"DDDD4444:n8n/workflow.reminders.sanitized.json"'], '', 'no spec'),
        ('an empty list', [], '', 'empty')):
    got = load(lines, extra)
    case(f'load refuses {label}', isinstance(got, str) and needle in got, str(got)[:110])
case('load: the real check-exports-parity.sh parses (five workflows)', len(W.load()) == 5)

L = {'AAAA1111': 'n8n/workflow.main.sanitized.json', 'BBBB2222': 'n8n/workflow.purge.sanitized.json'}
case('key_of: the export path names the key', W.key_of('n8n/workflow.owner-actions.sanitized.json') == 'owner-actions')
for bad in ('n8n/workflow.main.copy.sanitized.json', 'n8n/staged/workflow.main.sanitized.json', 'workflow.main.sanitized.json'):
    try:
        W.key_of(bad); r = 'accepted'
    except ValueError:
        r = 'refused'
    case(f'key_of refuses {bad}', r == 'refused')
case('id_for: the listed id for a key', W.id_for(L, 'purge') == 'BBBB2222')
for label, wl in (('a key nobody lists', L), ('a key listed twice', dict(L, CCCC3333='n8n/workflow.purge.sanitized.json'))):
    try:
        W.id_for(wl, 'purge' if 'twice' in label else 'reminders'); r = 'accepted'
    except ValueError as e:
        r = str(e)
    case(f'id_for refuses {label}', 'exactly one' in r, r[:90])

on = lambda wid, active=True, **kw: dict(id=wid, active=active, **kw)
for label, inst, want in (
        ('every listed active, an unlisted INACTIVE one passes', [on('AAAA1111'), on('BBBB2222'), on('SCRATCH1', False)], []),
        ('a listed workflow inactive', [on('AAAA1111'), on('BBBB2222', False)], ['INACTIVE']),
        ('a listed workflow n8n does not list (archived)', [on('AAAA1111')], ['does not list']),
        ('an unlisted ACTIVE workflow (a second holder nobody reviews)', [on('AAAA1111'), on('BBBB2222'), on('ORIG0001')], ['not listed']),
        ('active given as the string "true" is not active', [on('AAAA1111'), on('BBBB2222', 'true')], ['INACTIVE'])):
    errs = W.judge_active(L, inst)
    good = (not errs) if not want else (len(errs) == len(want) and all(w in e for w, e in zip(want, errs)))
    case(f'judge_active: {label}', good, '; '.join(errs)[:120] or 'green')

hook = lambda path: [{'type': 'n8n-nodes-base.webhook', 'parameters': {'path': path}}]
for label, inst, want in (
        ('one listed active holder', [on('AAAA1111', nodes=hook('p')), on('BBBB2222', nodes=hook('q'))], ('AAAA1111', L['AAAA1111'])),
        ('an inactive second holder does not count', [on('AAAA1111', nodes=hook('p')), on('ORIG0001', False, nodes=hook('p'))], ('AAAA1111', L['AAAA1111'])),
        ('two active holders', [on('AAAA1111', nodes=hook('p')), on('ORIG0001', nodes=hook('p'))], 'exactly one'),
        ('no holder', [on('AAAA1111', nodes=hook('q'))], 'exactly one'),
        ('the one holder is unlisted', [on('ORIG0001', nodes=hook('p'))], 'not listed'),
        ('a schedule trigger is not a webhook holder', [on('AAAA1111', nodes=[{'type': 'n8n-nodes-base.scheduleTrigger', 'parameters': {'path': 'p'}}])], 'exactly one')):
    try:
        got = W.holder(inst, 'p', L)
    except Exception as e:   # any other exception is a failed case with its type shown, never a crash of the suite
        got = str(e) if isinstance(e, ValueError) else f'{type(e).__name__}: {e}'
    case(f'holder: {label}', got == want if isinstance(want, tuple) else (isinstance(got, str) and want in got), str(got)[:90])

# check-active-set.py end to end: the real WORKFLOWS, a paginated listing, the three exits.
real = W.load()
PAGES = []


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        # read the query as a server does: an UNencoded '+' arrives as a space, so a base64 cursor must be sent encoded
        c = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('cursor', ['0'])[0]
        i = int(c) if c.isdigit() else {'1+x==': 1}.get(c)
        if i is None:
            self.send_response(400); self.end_headers(); return
        page = PAGES[i] if i < len(PAGES) else {'data': []}
        if isinstance(page, int):                    # an HTTP error status for this page
            self.send_response(page); self.end_headers(); return
        raw = json.dumps(page).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)


srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
env = {k: v for k, v in os.environ.items() if k not in ('N8N_API_URL', 'N8N_API_KEY', 'CF_ACCESS_CLIENT_ID', 'CF_ACCESS_CLIENT_SECRET')}
api = dict(N8N_API_URL=f'http://127.0.0.1:{srv.server_address[1]}', N8N_API_KEY='fake-test-key')
ids = list(real)
listed_on = [on(w) for w in ids]
for label, pages, e, want_rc, needle in (
        ('all listed active, an archived original inactive', [{'data': listed_on + [on('Orig000000000001', False)]}], api, 0, 'none active'),
        ('the listing on two pages, a listed one only on the second', [{'data': listed_on[:2], 'nextCursor': '1'}, {'data': listed_on[2:]}], api, 0, 'all active'),
        ('an unlisted active workflow on the second page', [{'data': listed_on, 'nextCursor': '1'}, {'data': [on('Orig000000000001')]}], api, 1, 'not listed'),
        ('a listed workflow inactive', [{'data': [on(ids[0], False)] + listed_on[1:]}], api, 1, 'INACTIVE'),
        ('a cursor carrying "+" and "=" (sent encoded)', [{'data': listed_on[:2], 'nextCursor': '1+x=='}, {'data': listed_on[2:]}], api, 0, 'all active'),
        ('the listing answers 500', [500], api, 2, 'did not read'),
        ('the second page answers 403', [{'data': listed_on, 'nextCursor': '1'}, 403], api, 2, 'did not read'),
        ('a listing that never ends', [{'data': listed_on, 'nextCursor': str(i + 1)} for i in range(25)], api, 2, 'did not end'),
        ('no credentials', [{'data': listed_on}], {}, 2, 'NOT MEASURED')):
    PAGES[:] = pages
    r = subprocess.run([sys.executable, os.environ.get('ACTIVE_SET', os.path.join(ROOT, 'scripts', 'check-active-set.py'))], cwd=ROOT, env=dict(env, **e),
                       capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    case(f'check-active-set: {label} → exit {want_rc}', r.returncode == want_rc and needle in r.stdout,
         f'exit {r.returncode} · {r.stdout.strip().splitlines()[-1][:100] if r.stdout.strip() else r.stderr.strip()[-100:]}')
srv.shutdown()
print('workflows test:', 'OK' if ok else 'FAILED')
sys.exit(0 if ok else 1)
