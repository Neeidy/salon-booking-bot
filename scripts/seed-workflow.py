#!/usr/bin/env python3
"""seed-workflow.py — the COMMITTED seed tool for the regression's setup-heavy rows (PHASE-7-PLAN, re-entry ruling,
premise 7): it replaces "inject/edit a row by hand" (the Airtable-era setups) with fixed, prefix-guarded statements.

Claude holds only `salon_ro` (ruling Q6), so a test row cannot be written to Postgres directly. This tool builds a
temporary n8n workflow (the S2 pattern of the migration's seed scripts): one Access-covered webhook per action, each
feeding ONE fixed Postgres statement on the app credential. Creating, activating, hitting and deleting it are edits
and executions of a workflow that uses a database credential: each `up`, action and `down` is gated (⚠ ONAY,
irreversible-actions.md) and is run through its webhook, never as a manual execution (ruling Q13).

The statements (SQL below, printed by --print-sql) — what makes them safe is IN the SQL, not in this Python:
  · every statement is a constant: no table name, column name or SQL text comes from input. Input reaches Postgres
    only as ONE jsonb value through the node's Query Parameters (`$1`), and the guard is applied to that value;
  · every write is prefix-guarded in its own WHERE clause:
      conversations / appointments  sender_key LIKE 'widget:w-mig-p7-%'
      processed_messages            message_id LIKE 'mig-p7-%'  (the clean-up also takes the run-d11 dashboard
                                    markers: message_id LIKE 'd11-%' AND sender_key = 'owner:dashboard' AND channel = 'owner')
      leads                         message LIKE 'mig-p7%'
  · a fake event id must be prefixed AND pass Validate Cancel Target's shape check (/^[0-9a-v]{5,1024}$/):
    'migp7' + random base32hex digits; the one exception is the deliberately broken whitespace id of row #9;
  · inserts are all-or-nothing (one row failing the guard inserts none) and take an EXPLICIT created_at;
  · an update/delete of an appointment acts only when the session has exactly ONE booked row;
  · the month's bot_metrics row is never named by any statement: after the cutover it is the production spend meter.
Before ANY hit, the action's path is edge-checked: no token → 403 + a Cloudflare Access header + zero new
executions. A red edge check refuses to seed (and `up` tears the workflow down again).

Usage (env: N8N_API_KEY, CF_ACCESS_CLIENT_ID/SECRET for the API, CF_OWNER_ACCESS_CLIENT_ID/SECRET for the
webhooks; N8N_HOST or CLAUDE.local.md's N8N_HOST line). SESSION is a widget sessionId, e.g. w-mig-p7-r5-<run>:
  python3 scripts/seed-workflow.py up        create INACTIVE → activate → edge-check every path (red: deactivate+delete)
  python3 scripts/seed-workflow.py appt-insert --session S --start ISO [--minutes 30] --created-at ISO
                                   [--gid valid|blank] [--calendar-id VALUE] [--service Haircut] [--status booked]
                                   [--customer-name TEXT]
  python3 scripts/seed-workflow.py lead-insert --message mig-p7… --created-at ISO [--name TEXT] [--phone TEXT]
                                   [--source widget]      (7-2 R4: synthetic names/phones for the export check)
  python3 scripts/seed-workflow.py conv-insert --session S --stage STAGE --turn-count N [--confirm-turn T]
                                   [--bind-target] [--last-intent I]
  python3 scripts/seed-workflow.py conv-update --session S [--stage STAGE] [--turn-count N]
                                   [--confirm-turn T | --confirm-turn-null] [--bind-target]
  python3 scripts/seed-workflow.py appt-update --session S [--blank-calendar-id] [--fake-gid]
  python3 scripts/seed-workflow.py appt-delete --session S
  python3 scripts/seed-workflow.py pm-insert --session S --message-id mig-p7-… --created-at ISO
  python3 scripts/seed-workflow.py clean     the prefix-guarded clean-up of every p7 drill row (and the d11 markers)
  python3 scripts/seed-workflow.py down      deactivate → delete → GET answers 404
  python3 scripts/seed-workflow.py --print-sql | --selftest       (offline; the selftest asserts it made no call)
  (--bind-target sets cancel_target_id to the session's ONE booked appointment, found in SQL: no record id travels.)
Exit: 0 done · 1 refused or red (nothing seeded unless the output says so) · 2 usage.
"""
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'MIG SEED — P7'
PATH_PREFIX = 'owner-mig-p7-'
SESSION_RE = re.compile(r'^w-mig-p7-[a-z0-9][a-z0-9-]{0,60}$')
MESSAGE_RE = re.compile(r'^mig-p7-[A-Za-z0-9][A-Za-z0-9-]{0,80}$')
STAGES = ('new', 'collecting', 'ready', 'confirming', 'booked', 'cancel_confirming', 'cancelled',
          'reschedule_confirming', 'handoff')        # = the CHECK in db/schema/001_init.sql
EDGE_WAIT_S = 4
ACTIVATE_WAIT_S = 3
PARAM = '={{ [ JSON.stringify($json.body.p) ] }}'     # ONE jsonb value; the array form check-sql-params requires

# The guards, named once so the tests can look for them; the SQL below spells them out literally (no formatting).
GUARD_SENDER = "sender_key LIKE 'widget:w-mig-p7-%'"
GUARD_MESSAGE = "message_id LIKE 'mig-p7-%'"
GUARD_D11 = "(message_id LIKE 'd11-%' AND sender_key = 'owner:dashboard' AND channel = 'owner')"
GUARD_LEAD = "message LIKE 'mig-p7%'"

SQL = {
    'appt-insert': (
        "WITH r AS (SELECT * FROM jsonb_to_recordset($1::jsonb -> 'rows') AS x(sender_key text, service text, "
        "start_utc timestamptz, end_utc timestamptz, gcal_event_id text, calendar_id text, channel text, status text, "
        "created_at timestamptz, customer_name text)), "
        "ok AS (SELECT NOT EXISTS (SELECT 1 FROM r AS q WHERE NOT coalesce(q.sender_key LIKE 'widget:w-mig-p7-%' "
        "AND q.created_at IS NOT NULL AND ((q.gcal_event_id LIKE 'migp7%' AND q.gcal_event_id !~ '[^0-9a-v]' "
        "AND length(q.gcal_event_id) BETWEEN 13 AND 64) OR (q.gcal_event_id !~ '[^ ]' "
        "AND length(q.gcal_event_id) BETWEEN 3 AND 8)), false)) AS all_ok), "
        "ins AS (INSERT INTO salon.appointments (sender_key, service, start_utc, end_utc, gcal_event_id, calendar_id, "
        "channel, status, created_at, customer_name) SELECT sender_key, service, start_utc, end_utc, gcal_event_id, "
        "calendar_id, channel, status, created_at, customer_name FROM r, ok WHERE ok.all_ok "
        "AND sender_key LIKE 'widget:w-mig-p7-%' "
        "AND created_at IS NOT NULL RETURNING 1) "
        "SELECT (SELECT count(*) FROM ins)::int AS inserted, (SELECT count(*) FROM r)::int AS sent"),
    'conv-insert': (
        "WITH p AS (SELECT $1::jsonb AS j), "
        "t AS (SELECT a.id FROM salon.appointments AS a, p WHERE a.sender_key = p.j ->> 'sender_key' "
        "AND a.sender_key LIKE 'widget:w-mig-p7-%' AND a.status = 'booked'), "
        "ins AS (INSERT INTO salon.conversations (sender_key, stage, turn_count, confirm_turn, cancel_target_id, "
        "last_intent, created_at, last_updated) SELECT p.j ->> 'sender_key', p.j ->> 'stage', "
        "(p.j ->> 'turn_count')::int, p.j ->> 'confirm_turn', "
        "CASE WHEN (p.j -> 'bind_target') = 'true'::jsonb THEN (SELECT id FROM t) END, p.j ->> 'last_intent', "
        "now(), now() FROM p WHERE (p.j ->> 'sender_key') LIKE 'widget:w-mig-p7-%' "
        "AND ((p.j -> 'bind_target') <> 'true'::jsonb OR (SELECT count(*) FROM t) = 1) RETURNING 1) "
        "SELECT (SELECT count(*) FROM ins)::int AS inserted"),
    'conv-update': (
        "WITH p AS (SELECT $1::jsonb AS j), "
        "t AS (SELECT a.id FROM salon.appointments AS a, p WHERE a.sender_key = p.j ->> 'sender_key' "
        "AND a.sender_key LIKE 'widget:w-mig-p7-%' AND a.status = 'booked'), "
        "up AS (UPDATE salon.conversations AS c SET "
        "stage = CASE WHEN (p.j -> 'set') @> '\"stage\"' THEN p.j ->> 'stage' ELSE c.stage END, "
        "turn_count = CASE WHEN (p.j -> 'set') @> '\"turn_count\"' THEN (p.j ->> 'turn_count')::int ELSE c.turn_count END, "
        "confirm_turn = CASE WHEN (p.j -> 'set') @> '\"confirm_turn\"' THEN p.j ->> 'confirm_turn' ELSE c.confirm_turn END, "
        "cancel_target_id = CASE WHEN (p.j -> 'bind_target') = 'true'::jsonb THEN (SELECT id FROM t) "
        "ELSE c.cancel_target_id END "
        "FROM p WHERE c.sender_key = p.j ->> 'sender_key' AND c.sender_key LIKE 'widget:w-mig-p7-%' "
        "AND ((p.j -> 'bind_target') <> 'true'::jsonb OR (SELECT count(*) FROM t) = 1) RETURNING 1) "
        "SELECT (SELECT count(*) FROM up)::int AS updated"),
    'appt-update': (
        "WITH p AS (SELECT $1::jsonb AS j), "
        "t AS (SELECT a.id FROM salon.appointments AS a, p WHERE a.sender_key = p.j ->> 'sender_key' "
        "AND a.sender_key LIKE 'widget:w-mig-p7-%' AND a.status = 'booked'), "
        "up AS (UPDATE salon.appointments AS a SET "
        "calendar_id = CASE WHEN (p.j -> 'set') @> '\"calendar_id\"' THEN '' ELSE a.calendar_id END, "
        "gcal_event_id = CASE WHEN (p.j -> 'set') @> '\"gcal_event_id\"' THEN p.j ->> 'gcal_event_id' "
        "ELSE a.gcal_event_id END "
        "FROM p WHERE a.id IN (SELECT id FROM t) AND a.sender_key LIKE 'widget:w-mig-p7-%' "
        "AND (SELECT count(*) FROM t) = 1 AND (NOT ((p.j -> 'set') @> '\"gcal_event_id\"') "
        "OR ((p.j ->> 'gcal_event_id') LIKE 'migp7%' AND (p.j ->> 'gcal_event_id') !~ '[^0-9a-v]' "
        "AND length(p.j ->> 'gcal_event_id') BETWEEN 13 AND 64)) RETURNING 1) "
        "SELECT (SELECT count(*) FROM up)::int AS updated, (SELECT count(*) FROM t)::int AS candidates"),
    'appt-delete': (
        "WITH p AS (SELECT $1::jsonb AS j), "
        "t AS (SELECT a.id FROM salon.appointments AS a, p WHERE a.sender_key = p.j ->> 'sender_key' "
        "AND a.sender_key LIKE 'widget:w-mig-p7-%' AND a.status = 'booked'), "
        "d AS (DELETE FROM salon.appointments AS a WHERE a.id IN (SELECT id FROM t) "
        "AND a.sender_key LIKE 'widget:w-mig-p7-%' AND (SELECT count(*) FROM t) = 1 RETURNING 1) "
        "SELECT (SELECT count(*) FROM d)::int AS deleted, (SELECT count(*) FROM t)::int AS candidates"),
    'pm-insert': (
        "WITH r AS (SELECT * FROM jsonb_to_recordset($1::jsonb -> 'rows') AS x(message_id text, sender_key text, "
        "channel text, created_at timestamptz)), "
        "ok AS (SELECT NOT EXISTS (SELECT 1 FROM r AS q WHERE NOT coalesce(q.message_id LIKE 'mig-p7-%' "
        "AND q.sender_key LIKE 'widget:w-mig-p7-%' AND q.created_at IS NOT NULL, false)) AS all_ok), "
        "ins AS (INSERT INTO salon.processed_messages (message_id, sender_key, channel, created_at) "
        "SELECT message_id, sender_key, channel, created_at FROM r, ok WHERE ok.all_ok "
        "AND message_id LIKE 'mig-p7-%' AND sender_key LIKE 'widget:w-mig-p7-%' AND created_at IS NOT NULL RETURNING 1) "
        "SELECT (SELECT count(*) FROM ins)::int AS inserted, (SELECT count(*) FROM r)::int AS sent"),
    'lead-insert': (
        "WITH r AS (SELECT * FROM jsonb_to_recordset($1::jsonb -> 'rows') AS x(name text, phone text, source text, "
        "message text, created_at timestamptz)), "
        "ok AS (SELECT NOT EXISTS (SELECT 1 FROM r AS q WHERE NOT coalesce(q.message LIKE 'mig-p7%' "
        "AND q.created_at IS NOT NULL, false)) AS all_ok), "
        "ins AS (INSERT INTO salon.leads (name, phone, source, message, created_at) SELECT name, phone, source, message, "
        "created_at FROM r, ok WHERE ok.all_ok AND message LIKE 'mig-p7%' AND created_at IS NOT NULL RETURNING 1) "
        "SELECT (SELECT count(*) FROM ins)::int AS inserted, (SELECT count(*) FROM r)::int AS sent"),
    'clean': (
        "WITH c AS (DELETE FROM salon.conversations WHERE sender_key LIKE 'widget:w-mig-p7-%' RETURNING 1), "
        "a AS (DELETE FROM salon.appointments WHERE sender_key LIKE 'widget:w-mig-p7-%' RETURNING 1), "
        "p AS (DELETE FROM salon.processed_messages WHERE message_id LIKE 'mig-p7-%' OR (message_id LIKE 'd11-%' "
        "AND sender_key = 'owner:dashboard' AND channel = 'owner') RETURNING 1), "
        "l AS (DELETE FROM salon.leads WHERE message LIKE 'mig-p7%' RETURNING 1) "
        "SELECT (SELECT count(*) FROM c)::int AS conversations, (SELECT count(*) FROM a)::int AS appointments, "
        "(SELECT count(*) FROM p)::int AS processed_messages, (SELECT count(*) FROM l)::int AS leads"),
}
EXPECT = {      # the response keys each action must return (ints), and the rule that makes it green
    'appt-insert': ('inserted', 'sent'), 'pm-insert': ('inserted', 'sent'), 'lead-insert': ('inserted', 'sent'),
    'conv-insert': ('inserted',),
    'conv-update': ('updated',), 'appt-update': ('updated', 'candidates'), 'appt-delete': ('deleted', 'candidates'),
    'clean': ('conversations', 'appointments', 'processed_messages', 'leads'),
}


class Refused(Exception):
    pass


# ── the workflow (pure) ──────────────────────────────────────────────────────────────────────────────────────
def build(credential):
    """The seed workflow: per action, an Access-covered webhook → ONE Postgres node holding the constant SQL."""
    nodes, con = [], {}
    for i, (action, query) in enumerate(SQL.items()):
        w = {'name': f'Trigger {action}', 'type': 'n8n-nodes-base.webhook', 'typeVersion': 2,
             'webhookId': str(uuid.uuid4()), 'position': [0, i * 200],
             'parameters': {'httpMethod': 'POST', 'path': PATH_PREFIX + action, 'responseMode': 'lastNode',
                            'options': {}}}
        p = {'name': f'SQL {action}', 'type': 'n8n-nodes-base.postgres', 'typeVersion': 2.6, 'position': [260, i * 200],
             'parameters': {'operation': 'executeQuery', 'query': query,
                            'options': {'queryReplacement': PARAM} if '$1' in query else {}},   # 'clean' takes no input
             'credentials': {'postgres': dict(credential)}, 'onError': 'continueRegularOutput'}
        nodes += [w, p]
        con[w['name']] = {'main': [[{'node': p['name'], 'type': 'main', 'index': 0}]]}
    return {'name': NAME, 'nodes': nodes, 'connections': con, 'settings': {'executionOrder': 'v1'}}


def drift(live_nodes):
    """Differences between the live seed workflow and build(): a hit goes only through the committed statements."""
    errs, L = [], {n.get('name'): n for n in live_nodes or []}
    want = build({'id': '-', 'name': '-'})
    for n in want['nodes']:
        got = L.get(n['name'])
        if not got or got.get('type') != n['type']:
            errs.append(f"node '{n['name']}' missing or of another type")
            continue
        gp, wp = got.get('parameters') or {}, n['parameters']
        if n['type'] == 'n8n-nodes-base.postgres':
            if gp.get('query') != wp['query'] or (gp.get('options') or {}) != wp['options'] \
                    or gp.get('operation') != 'executeQuery':
                errs.append(f"node '{n['name']}' does not hold the committed statement")
        elif gp.get('path') != wp['path']:
            errs.append(f"node '{n['name']}' is not on its committed path")
    extra = set(L) - {n['name'] for n in want['nodes']}
    if extra:
        errs.append(f'nodes the committed build does not have: {sorted(extra)}')
    return errs


# ── the payloads (pure): validated here so a bad value never leaves this machine ─────────────────────────────
def _iso(s, label):
    try:
        d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        raise Refused(f'{label} is not an ISO timestamp: {s!r}')
    if d.tzinfo is None:
        raise Refused(f'{label} needs an explicit offset (Z or +hh:mm): {s!r}')
    return d.astimezone(timezone.utc)


def _sender(session):
    if not SESSION_RE.match(session or ''):
        raise Refused(f'session must match {SESSION_RE.pattern}')
    return 'widget:' + session


def fake_gid():
    """Unique, prefixed, and shape-valid for Validate Cancel Target: 'migp7' + 16 base32hex digits."""
    return 'migp7' + secrets.token_hex(8)


def _text(opt, key, flag, cap):
    v = opt.get(key)
    if v is not None and (not isinstance(v, str) or len(v) > cap):
        raise Refused(f'{flag} is text of at most {cap} characters')
    return v


def payload(action, opt):
    if action == 'clean':
        return None
    if action == 'lead-insert':     # a lead has no session: its guard is the message prefix (the clean-up's own)
        msg = opt.get('message') or ''
        if not msg.startswith('mig-p7') or len(msg) > 200:
            raise Refused("--message must start with 'mig-p7' (the leads guard) and be at most 200 characters")
        source = opt.get('source') or 'widget'
        if source not in ('whatsapp', 'widget', 'instagram'):
            raise Refused('--source must be whatsapp|widget|instagram (the table CHECK)')
        created = _iso(opt.get('created_at'), '--created-at')
        return {'rows': [{'name': _text(opt, 'name', '--name', 120), 'phone': _text(opt, 'phone', '--phone', 60),
                          'source': source, 'message': msg, 'created_at': created.strftime('%Y-%m-%dT%H:%M:%S.000Z')}]}
    sk = _sender(opt.get('session'))
    if action == 'appt-insert':
        start = _iso(opt.get('start'), '--start')
        created = _iso(opt.get('created_at'), '--created-at')
        minutes = int(opt.get('minutes') or 30)
        kind = opt.get('gid') or 'valid'
        if kind not in ('valid', 'blank') or not 5 <= minutes <= 240:
            raise Refused('--gid must be valid|blank and --minutes 5..240')
        status = opt.get('status') or 'booked'
        if status not in ('booked', 'cancelled'):
            raise Refused('--status must be booked|cancelled')
        row = {'sender_key': sk, 'service': opt.get('service') or 'Haircut',
               'start_utc': start.strftime('%Y-%m-%dT%H:%M:%SZ'),
               'end_utc': (start + timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'gcal_event_id': fake_gid() if kind == 'valid' else '   ',
               'calendar_id': opt.get('calendar_id') or '', 'channel': 'widget', 'status': status,
               'created_at': created.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
               'customer_name': _text(opt, 'customer_name', '--customer-name', 120)}
        return {'rows': [row]}
    if action == 'pm-insert':
        if not MESSAGE_RE.match(opt.get('message_id') or ''):
            raise Refused(f'--message-id must match {MESSAGE_RE.pattern}')
        created = _iso(opt.get('created_at'), '--created-at')
        return {'rows': [{'message_id': opt['message_id'], 'sender_key': sk, 'channel': 'widget',
                          'created_at': created.strftime('%Y-%m-%dT%H:%M:%S.000Z')}]}
    if action in ('appt-delete',):
        return {'sender_key': sk}
    if action == 'appt-update':
        sets = [k for k, flag in (('calendar_id', 'blank_calendar_id'), ('gcal_event_id', 'fake_gid')) if opt.get(flag)]
        if not sets:
            raise Refused('appt-update needs --blank-calendar-id and/or --fake-gid')
        p = {'sender_key': sk, 'set': sets}
        if 'gcal_event_id' in sets:
            p['gcal_event_id'] = fake_gid()
        return p
    if action in ('conv-insert', 'conv-update'):
        p, sets = {'sender_key': sk, 'bind_target': bool(opt.get('bind_target'))}, []
        if opt.get('stage') is not None:
            if opt['stage'] not in STAGES:
                raise Refused(f'--stage must be one of {", ".join(STAGES)} (the table CHECK)')
            p['stage'] = opt['stage']; sets.append('stage')
        if opt.get('turn_count') is not None:
            if not re.fullmatch(r'[0-9]{1,4}', str(opt['turn_count'])):
                raise Refused('--turn-count is an integer 0..9999 (turn_count is integer NOT NULL: no null)')
            p['turn_count'] = int(opt['turn_count']); sets.append('turn_count')
        if opt.get('confirm_turn_null'):
            p['confirm_turn'] = None; sets.append('confirm_turn')
        elif opt.get('confirm_turn') is not None:
            p['confirm_turn'] = str(opt['confirm_turn'])[:12]; sets.append('confirm_turn')
        if action == 'conv-insert':
            if 'stage' not in p or 'turn_count' not in p:
                raise Refused('conv-insert needs --stage and --turn-count')
            if opt.get('last_intent'):
                p['last_intent'] = str(opt['last_intent'])[:40]
        else:
            if not sets and not p['bind_target']:
                raise Refused('conv-update needs at least one field to set')
            p['set'] = sets
        return p
    raise Refused(f'unknown action {action}')


def judge(action, p, body):
    """Errors for an action's response, or [] when it did exactly what was asked."""
    keys = EXPECT[action]
    if not isinstance(body, dict) or any(not isinstance(body.get(k), int) for k in keys):
        return [f'unexpected response (a SQL error or a wrong path): {str(body)[:160]}']
    if action in ('appt-insert', 'pm-insert', 'lead-insert'):
        return [] if body['inserted'] == body['sent'] == len(p['rows']) else \
            [f"inserted {body['inserted']} of {body['sent']} (the guard refused; all-or-nothing, so none)"]
    if action == 'conv-insert':
        return [] if body['inserted'] == 1 else ['no row inserted (guard, or --bind-target found no single booked row)']
    if action == 'conv-update':
        return [] if body['updated'] == 1 else [f"updated {body['updated']} rows (expected exactly 1)"]
    if action in ('appt-update', 'appt-delete'):
        n = body['updated' if action == 'appt-update' else 'deleted']
        return [] if n == 1 else [f"acted on {n} rows; the session has {body['candidates']} booked (exactly 1 required)"]
    return []


# ── HTTP: the real curl; secrets in a 0600 header file, never on argv ──────────────────────────────────────────
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
    tmp = []
    try:
        fd, hpath = tempfile.mkstemp(suffix='.hdr'); tmp.append(hpath)
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


def hook(action, body, token):
    """POST to an action's path. token=False sends NO credential at all: the edge must refuse that."""
    hdr = {'Content-Type': 'application/json'}
    if token:
        hdr.update({'CF-Access-Client-Id': os.environ.get('CF_OWNER_ACCESS_CLIENT_ID', ''),
                    'CF-Access-Client-Secret': os.environ.get('CF_OWNER_ACCESS_CLIENT_SECRET', '')})
    return curl('POST', f'{_base()}/webhook/{PATH_PREFIX}{action}', hdr, body)


# ── live steps ───────────────────────────────────────────────────────────────────────────────────────────────
def find_seed():
    """The ONE workflow named NAME (no state file: nothing with an id is ever written)."""
    st, d = api('GET', '/workflows?limit=250')
    if st != 200 or not isinstance(d, dict):
        raise Refused(f'GET workflows answered {st}')
    hits = [w for w in d.get('data') or [] if w.get('name') == NAME]
    if len(hits) > 1:
        raise Refused(f"{len(hits)} workflows are named '{NAME}' (exactly one may be)")
    return hits[0] if hits else None


def wf_get(wid):
    st, d = api('GET', f'/workflows/{wid}')
    if st != 200 or not isinstance(d, dict):
        raise Refused(f'GET seed workflow answered {st}')
    return d


def exec_count(wid):
    st, d = api('GET', f'/executions?workflowId={wid}&limit=100')
    if st != 200 or not isinstance(d, dict):
        raise Refused(f'GET executions answered {st}')
    return len(d.get('data') or [])


def edge_refused(wid, action):
    """S6's signals: no token → 403, a Cloudflare Access header on that response, and no execution created."""
    c0 = exec_count(wid)
    st, _, names = hook(action, {'probe': 1}, token=False)
    access = any(n.startswith('cf-access') for n in names)
    time.sleep(EDGE_WAIT_S)
    c1 = exec_count(wid)
    ok = st == 403 and access and c1 == c0
    print(f"  edge {PATH_PREFIX}{action}: no token → {st} · Access header {access} · executions {c0}→{c1} · "
          f"{'REFUSED AT EDGE' if ok else 'NOT PROVEN'}")
    return ok


def _credential():
    st, d = api('GET', '/credentials')
    pg = [c for c in (d.get('data') or []) if c.get('type') == 'postgres'] if st == 200 and isinstance(d, dict) else []
    if len(pg) != 1:
        raise Refused(f'expected exactly one postgres credential, found {len(pg)}')
    return {'id': pg[0]['id'], 'name': pg[0]['name']}


def remove(wid):
    api('POST', f'/workflows/{wid}/deactivate')
    st, _ = api('DELETE', f'/workflows/{wid}')
    gst, _ = api('GET', f'/workflows/{wid}')
    print(f'  seed workflow delete [{st}] · GET afterwards [{gst}]')
    return gst == 404


def cmd_up():
    if find_seed():
        raise Refused(f"a workflow named '{NAME}' already exists: run `down` first")
    st, d = api('POST', '/workflows', build(_credential()))
    wid = d.get('id') if isinstance(d, dict) else None
    if st != 200 or not wid:
        raise Refused(f'create answered {st}')
    if wf_get(wid).get('active') is not False:
        remove(wid)
        raise Refused('the new seed workflow did not read back INACTIVE')
    print(f'  created ({len(SQL)} actions) · inactive')
    ast, _ = api('POST', f'/workflows/{wid}/activate')
    active = wf_get(wid).get('active') is True
    print(f'  activate [{ast}] · read back active {active}')
    time.sleep(ACTIVATE_WAIT_S)
    if not active or not all([edge_refused(wid, a) for a in SQL]):
        remove(wid)
        raise Refused('edge check RED (or not active): the seed workflow was removed, nothing can be seeded')
    print('up: GREEN — every path refused at the edge without a token')
    return 0


def cmd_action(action, opt):
    p = payload(action, opt)                    # offline validation first: a refused value never travels
    w = find_seed()
    if not w:
        raise Refused(f"no workflow named '{NAME}': run `up` first")
    live = wf_get(w['id'])
    if live.get('active') is not True:
        raise Refused('the seed workflow is not active')
    errs = drift(live.get('nodes'))
    if errs:
        raise Refused('the live seed workflow is not the committed build: ' + '; '.join(errs[:3]))
    if not edge_refused(w['id'], action):
        raise Refused('edge check RED: not seeding')
    st, body, _ = hook(action, {'p': p} if p is not None else {}, token=True)
    errs = [f'webhook answered {st}'] if st != 200 else judge(action, p, body)
    if errs:
        print(f'{action}: RED — ' + '; '.join(errs))
        return 1
    print(f"{action}: OK · {json.dumps({k: body[k] for k in EXPECT[action]})}")
    return 0


def cmd_down():
    w = find_seed()
    if not w:
        print(f"down: no workflow named '{NAME}' — nothing to remove")
        return 0
    return 0 if remove(w['id']) else 1


# ── offline ──────────────────────────────────────────────────────────────────────────────────────────────────
def selftest():
    global api, hook
    real, calls = (api, hook), []
    api = lambda *a, **k: calls.append(a) or (599, {}, [])
    hook = lambda *a, **k: calls.append(a) or (599, {}, [])
    ok = True

    def case(label, good):
        nonlocal ok
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}")
    try:
        wf = build({'id': 'Cred01', 'name': 'Postgres account'})
        case('build: one webhook + one Postgres node per action, no drift against itself', not drift(wf['nodes'])
             and len(wf['nodes']) == 2 * len(SQL))
        case('no statement holds a brace, an n8n expression or a format marker',
             not any(c in q for q in SQL.values() for c in ('{', '}', '%s', '%(')))
        case('no statement names bot_metrics', not any('bot_metrics' in q for q in SQL.values()))
        for bad, opt in (('a session outside the prefix', {'session': 'w-real-1', 'start': '2030-01-01T10:00:00Z',
                                                            'created_at': '2030-01-01T09:00:00Z'}),
                         ('a quote in the session', {'session': "w-mig-p7-x'--", 'stage': 'new', 'turn_count': 0}),
                         ('a stage outside the CHECK', {'session': 'w-mig-p7-a', 'stage': 'gone', 'turn_count': 0}),
                         ('a null turn_count', {'session': 'w-mig-p7-a', 'stage': 'new', 'turn_count': 'null'}),
                         ('a naive created_at', {'session': 'w-mig-p7-a', 'start': '2030-01-01T10:00:00Z',
                                                 'created_at': '2030-01-01T09:00:00'})):
            action = 'appt-insert' if 'start' in opt else 'conv-insert'
            try:
                payload(action, opt)
                case(f'{action} refuses {bad}: NOT refused', False)
            except Refused as e:
                case(f'{action} refuses {bad} ({str(e)[:60]})', True)
        for bad, opt in (('a message outside the prefix', {'message': 'real lead', 'created_at': '2030-01-01T09:00:00Z'}),
                         ('a source outside the CHECK', {'message': 'mig-p7 x', 'source': 'sms', 'created_at': '2030-01-01T09:00:00Z'})):
            try:
                payload('lead-insert', opt)
                case(f'lead-insert refuses {bad}: NOT refused', False)
            except Refused as e:
                case(f'lead-insert refuses {bad} ({str(e)[:60]})', True)
        g = payload('appt-insert', {'session': 'w-mig-p7-a', 'start': '2030-01-01T10:00:00Z',
                                    'created_at': '2030-01-01T09:00:00Z'})['rows'][0]['gcal_event_id']
        case('a fake gid is prefixed and passes /^[0-9a-v]{5,1024}$/', g.startswith('migp7')
             and re.fullmatch(r'[0-9a-v]{5,1024}', g) is not None)
    finally:
        api, hook = real
    case(f'no network call during the selftest ({len(calls)})', not calls)
    print('seed-workflow selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


FLAGS = {'--session': 'session', '--start': 'start', '--minutes': 'minutes', '--created-at': 'created_at',
         '--gid': 'gid', '--calendar-id': 'calendar_id', '--service': 'service', '--status': 'status',
         '--stage': 'stage', '--turn-count': 'turn_count', '--confirm-turn': 'confirm_turn',
         '--last-intent': 'last_intent', '--message-id': 'message_id', '--customer-name': 'customer_name',
         '--name': 'name', '--phone': 'phone', '--message': 'message', '--source': 'source'}
SWITCHES = {'--bind-target': 'bind_target', '--confirm-turn-null': 'confirm_turn_null',
            '--blank-calendar-id': 'blank_calendar_id', '--fake-gid': 'fake_gid'}


def main(argv):
    args = argv[1:]
    if args[:1] == ['--selftest']:
        return selftest()
    if args[:1] == ['--print-sql']:
        for a, q in SQL.items():
            print(f'-- {a}\n{q};\n')
        return 0
    if not args or args[0] not in set(SQL) | {'up', 'down'}:
        print(__doc__)
        return 2
    action, rest, opt = args[0], args[1:], {}
    while rest:
        a = rest.pop(0)
        if a in SWITCHES:
            opt[SWITCHES[a]] = True
        elif a in FLAGS and rest:
            opt[FLAGS[a]] = rest.pop(0)
        else:
            print(f'seed-workflow: unknown or incomplete option {a!r}')
            return 2
    try:
        if action == 'up':
            return cmd_up()
        if action == 'down':
            return cmd_down()
        return cmd_action(action, opt)
    except Refused as e:
        print(f'{action}: REFUSED — {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
