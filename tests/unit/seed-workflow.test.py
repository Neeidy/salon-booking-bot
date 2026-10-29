#!/usr/bin/env python3
"""scripts/seed-workflow.py, offline: a stand-in for the n8n public API, Cloudflare Access at the edge and the seed
webhooks on 127.0.0.1 (loopback only, remote-operator.md). The tool's real curl layer runs against it. No database is
touched: what the statements DO is proven on their text (every write carries its guard in its own WHERE, no input
reaches the SQL text) and, for the clean-up, by evaluating its WHERE clauses on fixture rows.

What it proves: `up` and every action refuse to seed when the edge does not refuse a token-less request (and `up`
removes the workflow again); an action never goes through a live workflow that is not the committed build; the
statements are constants, guarded per table, never name bot_metrics; the clean-up takes the mig-p7 rows and the run-d11
dashboard markers and nothing else; `clean-p74` (7-4 B) takes the p74 window's rows and the G5 lead and nothing else; inserts send explicit created_at and unique, prefixed, shape-valid fake event ids.
Public demo (2026-10-29): the pd- actions write and clean only under their OWN prefix (`widget:w-pd-`, `pd-`), and
`clean` and `clean-pd` each leave the other's rows alone (both directions on fixture rows); a pd lead carries no name
and no phone.
7-2 R4: appt-insert's customer_name and lead-insert (name, phone, prefixed message) carry their values — unicode
included — in the body only, every payload key is named in its statement's recordset, INSERT and SELECT lists (a
dropped column would insert NULL and exit 0), and an option another action takes is refused, never swallowed.

Run: python3 tests/unit/seed-workflow.test.py   (SEED_WORKFLOW=<path> runs it against another copy of the script —
a mutant — with every import still resolving to this repo)
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
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLE_GUARD = {   # table → the guard its every write must carry, as a regex over the DML's own text
    'conversations': r"sender_key'?\)?\s+LIKE\s+'widget:w-mig-p7-%'",
    'appointments': r"sender_key'?\)?\s+LIKE\s+'widget:w-mig-p7-%'",
    'processed_messages': r"message_id\s+LIKE\s+'mig-p7-%'",
    'leads': r"message\s+LIKE\s+'mig-p7%'",
}
P74_GUARD = {     # clean-p74 only: the rows the 7-4 A window left, under that run's own prefixes
    'conversations': r"sender_key\s+LIKE\s+'widget:w-p74-%'",
    'appointments': r"sender_key\s+LIKE\s+'widget:w-p74-%'",
    'processed_messages': r"message_id\s+LIKE\s+'p74-%'\s+AND\s+sender_key\s+LIKE\s+'widget:w-p74-%'",
    'leads': r"message\s+=\s+'My name is Alex, please call me back'\s+AND\s+source\s+=\s+'widget'\s+AND\s+"
             r"created_at\s+>=\s+'2026-10-27T20:06:00Z'\s+AND\s+created_at\s+<=\s+'2026-10-27T20:10:00Z'",
}


PD_GUARD = {      # the public demo's actions (pd-lead-insert, pd-conv-insert, clean-pd): their own prefix only
    'conversations': r"sender_key'?\)?\s+LIKE\s+'widget:w-pd-%'",
    'leads': r"message\s+LIKE\s+'pd-%'",
}
PD_ACTIONS = ('pd-lead-insert', 'pd-conv-insert', 'clean-pd')


def load_script():
    path = os.environ.get('SEED_WORKFLOW', os.path.join(ROOT, 'scripts', 'seed-workflow.py'))
    spec = importlib.util.spec_from_file_location('seed_workflow_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = ROOT
    mod.EDGE_WAIT_S = 0
    mod.ACTIVATE_WAIT_S = 0
    return mod


# ── a tiny evaluator for the clean-ups' WHERE clauses: col LIKE/=/<>/>=/<= 'lit', AND, OR, NOT, parentheses ────────
# (>= and <= compare text: the fixtures hold created_at in the statement's own ISO-UTC form, so text order = time order)
TOK = re.compile(r"\s*('(?:[^']|'')*'|\(|\)|<>|>=|<=|=|[A-Za-z_][A-Za-z_0-9.]*)")


def _tokens(s):
    out, i = [], 0
    while i < len(s):
        m = TOK.match(s, i)
        if not m:
            if s[i:].strip():
                raise ValueError(f'cannot tokenise: {s[i:i + 30]!r}')
            break
        out.append(m.group(1))
        i = m.end()
    return out


def _like(v, pat):
    rx = ''.join('.*' if c == '%' else '.' if c == '_' else re.escape(c) for c in pat)
    return v is not None and re.fullmatch(rx, v, re.S) is not None


def evaluate(pred, row):
    toks = _tokens(pred)
    pos = [0]

    def peek():
        return toks[pos[0]].upper() if pos[0] < len(toks) else None

    def take():
        pos[0] += 1
        return toks[pos[0] - 1]

    def expr():
        v = term()
        while peek() == 'OR':
            take()
            v = term() or v
        return v

    def term():
        v = factor()
        while peek() == 'AND':
            take()
            v = factor() and v
        return v

    def factor():
        if peek() == 'NOT':
            take()
            return not factor()
        if peek() == '(':
            take()
            v = expr()
            assert take() == ')'
            return v
        col, op, lit = take(), take().upper(), take()
        assert lit.startswith("'"), f'only literals on the right: {lit}'
        val, lit = row.get(col), lit[1:-1].replace("''", "'")
        return {'LIKE': lambda: _like(val, lit), '=': lambda: val == lit, '<>': lambda: val is not None and val != lit,
                '>=': lambda: val is not None and val >= lit, '<=': lambda: val is not None and val <= lit}[op]()
    v = expr()
    assert pos[0] == len(toks), f'trailing tokens: {toks[pos[0]:]}'
    return v


class World:
    def __init__(self, edge_refuses=True):
        self.edge_refuses = edge_refuses
        self.wf = {}                  # id → workflow as created
        self.execs = {}
        self.hits = []                # (action, with_token, body)
        self.creates = []
        self.next = 0
        self.guard_refuses = False
        self.lock = threading.Lock()


def make_handler(world, mod):
    prefix = mod.PATH_PREFIX

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body, extra=None):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def body(self):
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}')

        def do_GET(self):
            with world.lock:
                if self.path.startswith('/api/v1/workflows?'):
                    return self.reply(200, {'data': [{'id': k, 'name': w['name'], 'active': w['active']} for k, w in world.wf.items()]})
                if self.path == '/api/v1/credentials':
                    return self.reply(200, {'data': [{'id': 'Cred01', 'name': 'Postgres account', 'type': 'postgres'},
                                                     {'id': 'Cred02', 'name': 'Telegram', 'type': 'telegramApi'}]})
                if self.path.startswith('/api/v1/executions?'):
                    wid = re.search(r'workflowId=([A-Za-z0-9]+)', self.path).group(1)
                    return self.reply(200, {'data': [{} for _ in range(world.execs.get(wid, 0))]})
                m = re.fullmatch(r'/api/v1/workflows/([A-Za-z0-9]+)', self.path)
                if m and m.group(1) in world.wf:
                    return self.reply(200, dict(world.wf[m.group(1)], id=m.group(1)))
                return self.reply(404, {'message': 'not found'})

        def do_DELETE(self):
            with world.lock:
                m = re.fullmatch(r'/api/v1/workflows/([A-Za-z0-9]+)', self.path)
                if m and world.wf.pop(m.group(1), None) is not None:
                    return self.reply(200, {})
                return self.reply(404, {})

        def do_POST(self):
            body = self.body()
            with world.lock:
                if self.path == '/api/v1/workflows':
                    world.next += 1
                    wid = f'S{world.next}'
                    world.wf[wid] = dict(copy.deepcopy(body), active=False)
                    world.creates.append(copy.deepcopy(body))
                    return self.reply(200, {'id': wid})
                m = re.fullmatch(r'/api/v1/workflows/([A-Za-z0-9]+)/(activate|deactivate)', self.path)
                if m and m.group(1) in world.wf:
                    world.wf[m.group(1)]['active'] = m.group(2) == 'activate'
                    return self.reply(200, {})
                if self.path.startswith('/webhook/' + prefix):
                    action = self.path[len('/webhook/' + prefix):]
                    token = bool(self.headers.get('CF-Access-Client-Id'))
                    world.hits.append((action, token, body))
                    if not token and world.edge_refuses:      # Cloudflare Access: refused at the edge, no execution
                        return self.reply(403, {'error': 'forbidden'}, {'cf-access-domain': 'edge.invalid'})
                    holder = [k for k, w in world.wf.items() if w['active']]
                    if not holder:
                        return self.reply(404, {'message': 'not registered'})
                    world.execs[holder[0]] = world.execs.get(holder[0], 0) + 1
                    p = body.get('p') or {}
                    n = len(p.get('rows') or [])
                    canned = {'appt-insert': {'inserted': 0 if world.guard_refuses else n, 'sent': n},
                              'pm-insert': {'inserted': 0 if world.guard_refuses else n, 'sent': n},
                              'lead-insert': {'inserted': 0 if world.guard_refuses else n, 'sent': n},
                              'conv-insert': {'inserted': 1}, 'conv-update': {'updated': 1},
                              'appt-update': {'updated': 1, 'candidates': 1}, 'appt-delete': {'deleted': 1, 'candidates': 1},
                              'clean': {'conversations': 0, 'appointments': 0, 'processed_messages': 0, 'leads': 0},
                              'clean-p74': {'conversations': 0, 'appointments': 0, 'processed_messages': 0, 'leads': 0},
                              'pd-lead-insert': {'inserted': 0 if world.guard_refuses else n, 'sent': n},
                              'pd-conv-insert': {'inserted': 1}, 'clean-pd': {'conversations': 0, 'leads': 0}}
                    return self.reply(200, canned.get(action, {'message': 'unknown'}))
                return self.reply(404, {'message': 'not found'})
    return H


def run(mod, world, argv):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), make_handler(world, mod))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = {'N8N_API_URL': f'http://127.0.0.1:{srv.server_address[1]}', 'N8N_API_KEY': 'fake-test-key', 'N8N_HOST': 'host.invalid',
           'CF_ACCESS_CLIENT_ID': 'fake-id', 'CF_ACCESS_CLIENT_SECRET': 'fake-secret',
           'CF_OWNER_ACCESS_CLIENT_ID': 'fake-owner-id', 'CF_OWNER_ACCESS_CLIENT_SECRET': 'fake-owner-secret'}
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            rc = mod.main(['seed-workflow.py', *argv])
    finally:
        srv.shutdown()
        srv.server_close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return rc, out.getvalue()


def main():
    mod = load_script()
    ok = True

    def case(label, good, detail=''):
        nonlocal ok
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}" + ('' if good or not detail else f'\n    {detail}'))

    # ── the statements, on their text ────────────────────────────────────────────────────────────────────────
    dml = re.compile(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+salon\.(\w+)(.*?)\bRETURNING\b', re.S)
    n_dml = 0
    for action, q in mod.SQL.items():
        segs = dml.findall(q)
        case(f'{action}: holds at least one write', bool(segs))
        guards = PD_GUARD if action in PD_ACTIONS else P74_GUARD if action == 'clean-p74' else TABLE_GUARD
        for verb, table, seg in segs:
            n_dml += 1
            case(f'{action}: {verb.split()[0]} on salon.{table} is a table this tool may write', table in guards)
            case(f'{action}: {verb.split()[0]} on salon.{table} carries its guard in its own clause',
                 table in guards and re.search(guards[table], seg) is not None, seg[:200])
        tables = set(re.findall(r'\bsalon\.(\w+)', q))
        case(f'{action}: names only the four drill tables ({sorted(tables)})', tables <= set(TABLE_GUARD))
        case(f'{action}: no brace / n8n expression / format marker, and $1 is its only placeholder',
             not re.search(r'[{}]|%s|%\(|\$[2-9]', q))
    case(f'{n_dml} writes checked across {len(mod.SQL)} statements (a zero would prove nothing)', n_dml >= len(mod.SQL))
    case('no statement names bot_metrics', not any('bot_metrics' in q for q in mod.SQL.values()))

    clean = mod.SQL['clean']
    preds = dict((t, p) for t, p in re.findall(r'DELETE FROM salon\.(\w+) WHERE (.*?) RETURNING', clean, re.S))
    case('clean: one DELETE per drill table', set(preds) == set(TABLE_GUARD))
    rows = {
        'conversations': [({'sender_key': 'widget:w-mig-p7-r5-1'}, True), ({'sender_key': 'widget:w-mig-d6-h1'}, False),
                          ({'sender_key': 'widget:w-real-session'}, False), ({'sender_key': 'whatsapp:+490000000001'}, False),
                          ({'sender_key': 'widget:w-mig-p7'}, False)],
        'appointments': [({'sender_key': 'widget:w-mig-p7-r8-2'}, True), ({'sender_key': 'widget:w-mig-p70x'}, False),
                         ({'sender_key': 'widget:w-customer'}, False)],
        'processed_messages': [({'message_id': 'mig-p7-123-1', 'sender_key': 'widget:w-mig-p7-a', 'channel': 'widget'}, True),
                               ({'message_id': 'd11-1729', 'sender_key': 'owner:dashboard', 'channel': 'owner'}, True),
                               ({'message_id': 'd11-1729', 'sender_key': 'widget:w-x', 'channel': 'widget'}, False),
                               ({'message_id': 'd11-1729', 'sender_key': 'owner:dashboard', 'channel': 'widget'}, False),
                               ({'message_id': 'mig-d6-9', 'sender_key': 'widget:w-mig-d6-a', 'channel': 'widget'}, False),
                               ({'message_id': 'wamid.real', 'sender_key': 'whatsapp:+490000000001', 'channel': 'whatsapp'}, False)],
        'leads': [({'message': 'mig-p7 lead drill'}, True), ({'message': 'mig-d6 lead'}, False), ({'message': 'Do you do colour?'}, False)],
    }
    for table, cases in rows.items():
        for row, want in cases:
            try:
                got = evaluate(preds.get(table, "x = 'never'"), row)
            except (AssertionError, ValueError, IndexError) as e:
                got = f'unparsable ({e})'
            case(f"clean on {table}: {json.dumps(row)} → {'deleted' if got is True else 'kept' if got is False else got}"
                 f"{'' if got == want else ' (WRONG)'}", got == want)

    p74 = dict((t, p) for t, p in re.findall(r'DELETE FROM salon\.(\w+) WHERE (.*?) RETURNING', mod.SQL['clean-p74'], re.S))
    case('clean-p74: one DELETE per drill table', set(p74) == set(P74_GUARD))
    g5 = 'My name is Alex, please call me back'
    rows74 = {
        'conversations': [({'sender_key': 'widget:w-p74-run0-g5'}, True), ({'sender_key': 'widget:w-mig-p7-r5-1'}, False),
                          ({'sender_key': 'widget:w-p74'}, False), ({'sender_key': 'widget:w-p740-x'}, False),
                          ({'sender_key': 'widget:w-real-session'}, False)],
        'appointments': [({'sender_key': 'widget:w-p74-run0-g1'}, True), ({'sender_key': 'widget:w-customer'}, False)],
        'processed_messages': [({'message_id': 'p74-run0-g1', 'sender_key': 'widget:w-p74-run0-g1'}, True),
                               ({'message_id': 'p74-run0-g1', 'sender_key': 'whatsapp:+490000000001'}, False),
                               ({'message_id': 'wamid.real', 'sender_key': 'widget:w-p74-run0-g1'}, False),
                               ({'message_id': 'mig-p7-1', 'sender_key': 'widget:w-mig-p7-a'}, False)],
        'leads': [({'message': g5, 'source': 'widget', 'created_at': '2026-10-27T20:06:55Z'}, True),
                  ({'message': g5, 'source': 'widget', 'created_at': '2026-10-27T20:05:59Z'}, False),
                  ({'message': g5, 'source': 'widget', 'created_at': '2026-10-27T20:10:01Z'}, False),
                  ({'message': g5, 'source': 'whatsapp', 'created_at': '2026-10-27T20:07:00Z'}, False),
                  ({'message': 'Please call me back', 'source': 'widget', 'created_at': '2026-10-27T20:07:00Z'}, False),
                  ({'message': 'mig-p7 lead drill', 'source': 'widget', 'created_at': '2026-10-27T20:07:00Z'}, False)],
    }
    for table, cases in rows74.items():
        for row, want in cases:
            try:
                got = evaluate(p74.get(table, "x = 'never'"), row)
            except (AssertionError, ValueError, IndexError) as e:
                got = f'unparsable ({e})'
            case(f"clean-p74 on {table}: {json.dumps(row)} → {'deleted' if got is True else 'kept' if got is False else got}"
                 f"{'' if got == want else ' (WRONG)'}", got == want)

    pd = dict((t, p) for t, p in re.findall(r'DELETE FROM salon\.(\w+) WHERE (.*?) RETURNING', mod.SQL['clean-pd'], re.S))
    case('clean-pd: one DELETE per pd table (conversations, leads)', set(pd) == set(PD_GUARD))
    rows_pd = {
        'conversations': [({'sender_key': 'widget:w-pd-r2-19'}, True), ({'sender_key': 'widget:w-mig-p7-r5-1'}, False),
                          ({'sender_key': 'widget:w-pd'}, False), ({'sender_key': 'widget:w-pdx-1'}, False),
                          ({'sender_key': 'widget:w-real-session'}, False), ({'sender_key': 'whatsapp:+490000000001'}, False)],
        'leads': [({'message': 'pd-13 back-dated'}, True), ({'message': 'mig-p7 lead drill'}, False),
                  ({'message': 'pdq real text'}, False), ({'message': 'Please call me back'}, False)],
    }
    for table, cases in rows_pd.items():
        for row, want in cases:
            try:
                got = evaluate(pd.get(table, "x = 'never'"), row)
            except (AssertionError, ValueError, IndexError) as e:
                got = f'unparsable ({e})'
            case(f"clean-pd on {table}: {json.dumps(row)} → {'deleted' if got is True else 'kept' if got is False else got}"
                 f"{'' if got == want else ' (WRONG)'}", got == want)
    for table, row in (('conversations', {'sender_key': 'widget:w-pd-r2-19'}), ('leads', {'message': 'pd-13 back-dated'})):
        case(f'clean leaves a pd row in {table} alone (the other direction)', evaluate(preds.get(table, "x = 'never'"), row) is False)

    # ── payloads: explicit created_at, unique prefixed shape-valid gids, refusals before any call ─────────────
    gids = set()
    for _ in range(200):
        p = mod.payload('appt-insert', {'session': 'w-mig-p7-u', 'start': '2030-01-07T13:00:00Z', 'created_at': '2030-01-01T09:00:00Z'})
        gids.add(p['rows'][0]['gcal_event_id'])
    case('200 fake gids: all unique, all prefixed, all pass /^[0-9a-v]{5,1024}$/',
         len(gids) == 200 and all(g.startswith('migp7') and re.fullmatch(r'[0-9a-v]{5,1024}', g) for g in gids))
    row = mod.payload('appt-insert', {'session': 'w-mig-p7-u', 'start': '2030-01-07T13:00:00Z', 'created_at': '2030-01-01T09:00:00+01:00'})['rows'][0]
    case('appt-insert carries the EXPLICIT created_at it was given (UTC)', row['created_at'] == '2030-01-01T08:00:00.000Z')
    blank = mod.payload('appt-insert', {'session': 'w-mig-p7-u', 'start': '2030-01-07T13:00:00Z', 'created_at': '2030-01-01T09:00:00Z',
                                        'gid': 'blank'})['rows'][0]['gcal_event_id']
    case("--gid blank (row #9) is whitespace only and FAILS the shape check, as the row intends",
         blank.strip() == '' and not re.fullmatch(r'[0-9a-v]{5,1024}', blank.strip()))

    # ── live flows against the stand-in ──────────────────────────────────────────────────────────────────────
    w = World()
    rc, out = run(mod, w, ['up'])
    created = w.creates[0] if w.creates else {'nodes': []}
    queries = {n['name']: n['parameters'].get('query') for n in created['nodes'] if n['type'] == 'n8n-nodes-base.postgres'}
    case('up: created, activated, every path refused at the edge → exit 0',
         rc == 0 and len(w.wf) == 1 and next(iter(w.wf.values()))['active'] and out.count('REFUSED AT EDGE') == len(mod.SQL), out[-300:])
    case('up: the created workflow holds exactly the committed statements',
         queries == {f'SQL {a}': q for a, q in mod.SQL.items()})
    case('up: no request ever carried the owner token (only token-less edge probes)', all(not t for _, t, _ in w.hits))

    hostile = "w-mig-p7-x' OR 1=1 --"
    before = len(w.hits)
    rc, out = run(mod, w, ['conv-update', '--session', hostile, '--stage', 'booked'])
    case('a hostile session is refused BEFORE any request (no hit, exit 1)', rc == 1 and len(w.hits) == before, out[-200:])
    rc, out = run(mod, w, ['conv-update', '--session', 'w-mig-p7-r12-1', '--turn-count', '6', '--confirm-turn', '5', '--bind-target'])
    sent = [h for h in w.hits if h[1]]
    case('conv-update: edge-checked, then ONE token hit with the values in the body only → exit 0',
         rc == 0 and len(sent) == 1 and sent[0][0] == 'conv-update'
         and sent[0][2] == {'p': {'sender_key': 'widget:w-mig-p7-r12-1', 'bind_target': True, 'turn_count': 6,
                                  'confirm_turn': '5', 'set': ['turn_count', 'confirm_turn']}}, out[-300:])
    case('the input values never appear in any statement of the live workflow',
         not any(v in json.dumps(w.creates) for v in ('w-mig-p7-r12-1', hostile)))
    rc, out = run(mod, w, ['appt-insert', '--session', 'w-mig-p7-r5-1', '--start', '2030-01-07T13:00:00Z',
                           '--created-at', '2030-01-07T08:00:00Z', '--calendar-id', 'cal-fixture'])
    last = [h for h in w.hits if h[1]][-1]
    case('appt-insert: one row, explicit created_at, prefixed fake gid → exit 0',
         rc == 0 and last[0] == 'appt-insert' and last[2]['p']['rows'][0]['created_at'] == '2030-01-07T08:00:00.000Z'
         and last[2]['p']['rows'][0]['gcal_event_id'].startswith('migp7'), out[-300:])
    case('the calendar id and the gid are never printed', 'cal-fixture' not in out and 'migp7' not in out)
    # 7-2 R4: synthetic names and phones for the export check — the values travel in the body only, never printed
    rc, out = run(mod, w, ['appt-insert', '--session', 'w-mig-p7-r4-1', '--start', '2030-01-07T13:00:00Z',
                           '--created-at', '2030-01-07T08:00:00Z', '--customer-name', 'Mila 0660 1234567'])
    last = [h for h in w.hits if h[1]][-1]
    case('appt-insert --customer-name: the name travels in the row, never printed → exit 0',
         rc == 0 and last[2]['p']['rows'][0].get('customer_name') == 'Mila 0660 1234567' and '1234567' not in out, out[-200:])
    rc, out = run(mod, w, ['lead-insert', '--message', 'mig-p7-r4 synthetic', '--created-at', '2030-01-07T08:00:00Z',
                           '--name', 'Noor 0660 1234567', '--phone', '+43 660 1234567'])
    last = [h for h in w.hits if h[1]][-1]
    case('lead-insert: one row (name, phone, prefixed message, explicit created_at), never printed → exit 0',
         rc == 0 and last[0] == 'lead-insert' and last[2]['p']['rows'][0] == {'name': 'Noor 0660 1234567', 'phone': '+43 660 1234567',
         'source': 'widget', 'message': 'mig-p7-r4 synthetic', 'created_at': '2030-01-07T08:00:00.000Z'} and '1234567' not in out, out[-200:])
    # M1: each payload key of the two inserts is in the recordset definition, the INSERT column list and the SELECT list
    # (review R4: a set comparison could not see `name, phone` swapped in one list — the ORDER is compared too)
    for action, opt in (('appt-insert', {'session': 'w-mig-p7-u', 'start': '2030-01-07T13:00:00Z', 'created_at': '2030-01-01T09:00:00Z',
                                         'customer_name': 'x'}),
                        ('lead-insert', {'message': 'mig-p7 x', 'created_at': '2030-01-01T09:00:00Z', 'name': 'x', 'phone': 'y'}),
                        ('pm-insert', {'session': 'w-mig-p7-u', 'message_id': 'mig-p7-x', 'created_at': '2030-01-01T09:00:00Z'}),
                        ('pd-lead-insert', {'message': 'pd-x', 'created_at': '2030-01-01T09:00:00Z'})):
        q = mod.SQL[action]
        rec = re.search(r'AS x\((.*?)\)\)', q, re.S).group(1)
        cols = re.search(r'INSERT INTO salon\.\w+ \((.*?)\) SELECT (.*?) FROM r', q, re.S)
        recs = {c.strip().split()[0] for c in rec.split(',')}
        ins, sel = ([c.strip() for c in g.split(',')] for g in cols.groups())
        keys = set(mod.payload(action, opt)['rows'][0])
        case(f'{action}: every payload key is in the recordset, and the INSERT and SELECT lists are the same columns in the same order',
             keys <= recs and keys == set(ins) and ins == sel,
             f'missing {sorted(keys - (recs & set(ins)))} · INSERT {ins} · SELECT {sel}')
    # L4: the value class the live check uses travels unchanged
    uni = 'Noor \u0660\u0666\u0666\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667 Q 0\u200b6\u200b6\u200b0 1234567\nzz'
    row = mod.payload('lead-insert', {'message': 'mig-p7 u', 'created_at': '2030-01-01T09:00:00Z', 'name': uni})['rows'][0]
    case('lead-insert carries Arabic-Indic digits, U+200B and a line break unchanged', row['name'] == uni)
    for label, argv in (('lead-insert --customer-name', ['lead-insert', '--message', 'mig-p7 x', '--created-at', '2030-01-07T08:00:00Z',
                                                         '--customer-name', 'X']),
                        ('appt-insert --name', ['appt-insert', '--session', 'w-mig-p7-r5-1', '--start', '2030-01-07T13:00:00Z',
                                                '--created-at', '2030-01-07T08:00:00Z', '--name', 'Y'])):
        before = len(w.hits)
        rc, out = run(mod, w, argv)
        case(f'{label}: an option of another action is REFUSED before any request (exit 2), never swallowed',
             rc == 2 and len(w.hits) == before, out[-200:])
    # public demo: a pd lead is synthetic (no name, no phone, whatever is offered) and a pd conversation is a handoff
    rc, out = run(mod, w, ['pd-lead-insert', '--message', 'pd-13 back-dated', '--created-at', '2026-09-01T08:00:00Z'])
    last = [h for h in w.hits if h[1]][-1]
    case('pd-lead-insert: one row, no name and no phone, the explicit created_at → exit 0',
         rc == 0 and last[0] == 'pd-lead-insert' and last[2]['p']['rows'] == [{'name': None, 'phone': None, 'source': 'widget',
         'message': 'pd-13 back-dated', 'created_at': '2026-09-01T08:00:00.000Z'}], out[-200:])
    rc, out = run(mod, w, ['pd-conv-insert', '--session', 'w-pd-r2-19', '--turn-count', '3'])
    last = [h for h in w.hits if h[1]][-1]
    case('pd-conv-insert: one handoff conversation under the pd prefix → exit 0',
         rc == 0 and last[0] == 'pd-conv-insert' and last[2]['p'] == {'sender_key': 'widget:w-pd-r2-19', 'turn_count': 3}, out[-200:])
    case("pd-lead-insert refuses a name or a phone IN SQL too, in both its check and its insert (a direct POST cannot add one)",
         mod.SQL['pd-lead-insert'].count('name IS NULL AND') == 2 and mod.SQL['pd-lead-insert'].count('phone IS NULL') == 2)
    case("pd-conv-insert's statement fixes stage and last_intent to 'handoff' (no input reaches them)",
         "'handoff', (p.j ->> 'turn_count')::int, 'handoff'" in mod.SQL['pd-conv-insert'])
    for label, argv in (('pd-lead-insert --phone', ['pd-lead-insert', '--message', 'pd-x', '--created-at', '2026-09-01T08:00:00Z',
                                                    '--phone', '+43 660 0000000']),
                        ('pd-lead-insert --name', ['pd-lead-insert', '--message', 'pd-x', '--created-at', '2026-09-01T08:00:00Z',
                                                   '--name', 'Noor']),
                        ('pd-conv-insert --stage', ['pd-conv-insert', '--session', 'w-pd-a', '--turn-count', '1', '--stage', 'booked'])):
        before = len(w.hits)
        rc, out = run(mod, w, argv)
        case(f'{label}: refused before any request (exit 2), never swallowed', rc == 2 and len(w.hits) == before, out[-200:])
    for label, argv in (('pd-lead-insert, a message outside the pd prefix', ['pd-lead-insert', '--message', 'mig-p7 x',
                                                                             '--created-at', '2026-09-01T08:00:00Z']),
                        ('pd-conv-insert, a session outside the pd prefix', ['pd-conv-insert', '--session', 'w-mig-p7-a', '--turn-count', '1']),
                        ('conv-insert, a pd session', ['conv-insert', '--session', 'w-pd-a', '--stage', 'new', '--turn-count', '0'])):
        before = len(w.hits)
        rc, out = run(mod, w, argv)
        case(f'{label}: refused BEFORE any request (no hit, exit 1)', rc == 1 and len(w.hits) == before, out[-200:])
    before = len(w.hits)
    rc, out = run(mod, w, ['lead-insert', '--message', 'a real customer', '--created-at', '2030-01-07T08:00:00Z'])
    case('lead-insert with a message outside the prefix is refused BEFORE any request (no hit, exit 1)',
         rc == 1 and len(w.hits) == before, out[-200:])
    w.guard_refuses = True
    rc, out = run(mod, w, ['lead-insert', '--message', 'mig-p7-r4 x', '--created-at', '2030-01-07T08:00:00Z'])
    case('lead-insert: a guard refusal in SQL (inserted 0 of 1) is RED, not OK (exit 1)', rc == 1 and 'RED' in out, out[-200:])
    rc, out = run(mod, w, ['appt-insert', '--session', 'w-mig-p7-r5-1', '--start', '2030-01-07T13:00:00Z',
                           '--created-at', '2030-01-07T08:00:00Z'])
    case('a guard refusal in SQL (inserted 0 of 1) is RED, not OK (exit 1)', rc == 1 and 'RED' in out, out[-200:])
    w.guard_refuses = False

    wid = next(iter(w.wf))
    w.wf[wid]['nodes'][1]['parameters']['query'] = w.wf[wid]['nodes'][1]['parameters']['query'].replace("LIKE 'widget:w-mig-p7-%'", "LIKE '%'")
    before = len([h for h in w.hits if h[1]])
    rc, out = run(mod, w, ['clean'])
    case('an action through a live workflow that is NOT the committed build is refused, no token hit',
         rc == 1 and 'not the committed build' in out and len([h for h in w.hits if h[1]]) == before, out[-200:])
    w.wf[wid]['nodes'] = copy.deepcopy(w.creates[0]['nodes'])

    w.edge_refuses = False
    before = len([h for h in w.hits if h[1]])
    rc, out = run(mod, w, ['clean'])
    case('edge NOT refusing a token-less request → the action refuses to seed, no token hit',
         rc == 1 and 'edge check RED' in out and len([h for h in w.hits if h[1]]) == before, out[-200:])
    w.edge_refuses = True
    rc, out = run(mod, w, ['down'])
    case('down: deactivated, deleted, GET answers 404 → exit 0', rc == 0 and not w.wf and '[404]' in out, out[-200:])

    w2 = World(edge_refuses=False)
    rc, out = run(mod, w2, ['up'])
    case('up with an OPEN edge: refused, the workflow removed again, no token hit',
         rc == 1 and not w2.wf and len(w2.creates) == 1 and all(not t for _, t, _ in w2.hits), out[-300:])

    print('seed-workflow:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
