#!/usr/bin/env python3
"""build-workflow-copy.py — generate a migration copy OFFLINE from a committed original (MIGRATION-PLAN §3r).

A copy differs from its original only in its data layer (§2, §4.1). Writing that by hand invites exactly the
drift the mechanical diff exists to catch, so the copy is generated instead:
  · from the COMMITTED sanitized export of the original (never from live);
  · each data node named in the copy spec (db/copies/<workflow>.json) becomes a Postgres `executeQuery` node
    in place: same name, same connections, and its onError / alwaysOutputData / executeOnce untouched;
  · its SQL comes from the spec, where `@@shape(table)@@` / `@@shape(table:col,col)@@` expand to the Airtable
    record projection built from db/shape-spec.json, the one source the contract runner reads too;
  · its parameters become ONE array expression (`={{ [ … ] }}`), the only form check-sql-params accepts;
  · the real trigger may move to a test path, and a declared temporary webhook trigger may be added (Q13).
The output carries the credential PLACEHOLDER, like every committed export; deploying it is a separate,
gated step that swaps in the real credential id.

Usage: python3 scripts/build-workflow-copy.py db/copies/<workflow>.json [-o OUT.json]
       python3 scripts/build-workflow-copy.py --selftest   (every spec: diff-workflow-copy test phase green,
                                                            check-sql-params green; refused: a non-data
                                                            node, a test or temporary-trigger path outside
                                                            owner-mig-, a "trigger" that is not a webhook)
"""
import copy as _copy
import glob
import importlib.util
import json
import os
import re
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PG_TYPE, PG_VERSION = 'n8n-nodes-base.postgres', 2.6
PG_CREDENTIAL = {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}}
SHAPE = re.compile(r'@@shape\((\w+)(?::([\w,]+))?\)@@')
# Every test path sits under the Access application's owner-* scope (spike S6). The temporary trigger skips the
# workflow's own signature check and Purge deletes, so Access is its ONLY layer: a path outside the prefix is
# refused here, before anything can be deployed (pre-push audit, 2026-10-20).
TEST_PATH = re.compile(r'^owner-mig-[a-z0-9-]+$')


def load(rel):
    return json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))


def projection(spec, table, only=None):
    cols = spec['tables'][table]
    if only:
        want = only.split(',')
        missing = [w for w in want if w not in [c[0] for c in cols]]
        if missing:
            raise ValueError(f'@@shape({table}:…)@@ names unknown field(s) {missing}')
        cols = [c for c in cols if c[0] in want]
    pairs = ', '.join(f"'{c[0]}', " + spec['kinds'][c[1]].replace('{c}', c[2] if len(c) > 2 else c[0]) for c in cols)
    return f'id, salon.at_ts(created_at) AS "createdTime", jsonb_strip_nulls(jsonb_build_object({pairs})) AS fields'


def build(copy_spec):
    shape = load('db/shape-spec.json')
    wf = _copy.deepcopy(load(copy_spec['original']))
    nodes = {n['name']: n for n in wf['nodes']}
    for name, d in copy_spec['nodes'].items():
        n = nodes.get(name)
        if n is None:
            raise ValueError(f"spec names '{name}', which is not in the original")
        if n['type'] != 'n8n-nodes-base.airtable':
            raise ValueError(f"spec names '{name}', which is a {n['type']}, not a data-layer (Airtable) node")
        query = SHAPE.sub(lambda m: projection(shape, m.group(1), m.group(2)), d['query'])
        options = {}
        if d.get('params'):
            options['queryReplacement'] = '={{ [' + ', '.join(d['params']) + '] }}'
        if d.get('batching', 'single') != 'single':
            options['queryBatching'] = d['batching']
        n['type'], n['typeVersion'] = PG_TYPE, PG_VERSION
        n['parameters'] = {'operation': 'executeQuery', 'query': query, 'options': options}
        n['credentials'] = _copy.deepcopy(PG_CREDENTIAL)
    wf['name'] = copy_spec['name']
    trig = copy_spec.get('trigger')
    if trig:
        if nodes.get(trig['node'], {}).get('type') != 'n8n-nodes-base.webhook':
            raise ValueError(f"trigger '{trig['node']}' is not a webhook node in the original")
        if not TEST_PATH.match(trig['test_path']):
            raise ValueError(f"test path '{trig['test_path']}' is outside the Access-covered owner-mig- prefix")
        nodes[trig['node']]['parameters']['path'] = trig['test_path']
    temp = copy_spec.get('temp_trigger')
    if temp:
        if not TEST_PATH.match(temp['path']):
            raise ValueError(f"temporary trigger path '{temp['path']}' is outside the Access-covered owner-mig- prefix")
        if temp['name'] in nodes:
            raise ValueError(f"temporary trigger name '{temp['name']}' already exists in the original")
        target = nodes[temp['connect_to']]
        wf['nodes'].append({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'mig-temp-trigger:' + copy_spec['name'])),
                            'name': temp['name'], 'type': 'n8n-nodes-base.webhook', 'typeVersion': 2.1,
                            'position': [target['position'][0] - 220, target['position'][1] + 200],
                            'parameters': {'httpMethod': 'POST', 'path': temp['path'], 'responseMode': 'onReceived',
                                           'options': {}}})
        wf['connections'][temp['name']] = {'main': [[{'node': temp['connect_to'], 'type': 'main', 'index': 0}]]}
    return wf


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def selftest():
    diff = _module('scripts/diff-workflow-copy.py', 'diff_workflow_copy')
    sqlp = _module('scripts/check-sql-params.py', 'check_sql_params')
    specs = sorted(glob.glob(os.path.join(ROOT, 'db', 'copies', '*.json')))
    assert specs, 'no copy specs found under db/copies/'
    ok = True
    for f in specs:
        cs = json.load(open(f, encoding='utf-8'))
        cp = build(cs)
        errs = diff.compare(load(cs['original']), cp, set(cs['nodes']), phase='test',
                            temp_trigger=(cs.get('temp_trigger') or {}).get('name'),
                            trigger=(cs.get('trigger') or {}).get('node'))
        pg = [n for n in cp['nodes'] if n['type'] == PG_TYPE]
        sq = [e for n in pg for e in sqlp.check_node(n)]
        good = not errs and not sq and len(pg) == len(cs['nodes'])
        ok = ok and good
        print(f"{'✓' if good else '✗'} {os.path.basename(f)}: {len(pg)} Postgres node(s) · diff (test phase) "
              f"{'green' if not errs else errs} · check-sql-params {'green' if not sq else sq}")
    base = json.load(open(specs[0], encoding='utf-8'))
    orig = load(base['original'])
    other = next(n['name'] for n in orig['nodes'] if n['type'] not in ('n8n-nodes-base.airtable', 'n8n-nodes-base.stickyNote', 'n8n-nodes-base.webhook'))
    first_webhook = next(n['name'] for n in orig['nodes'] if n['type'] == 'n8n-nodes-base.webhook')
    negatives = {
        'a spec naming a non-data node': lambda s: s.update(nodes={other: {'query': 'SELECT 1'}}),
        'a test path outside owner-mig-': lambda s: s.update(trigger={'node': first_webhook, 'test_path': 'not-owner-open'}),
        'a temporary trigger path outside owner-mig-': lambda s: s.update(temp_trigger={'name': 'Temporary Test Trigger', 'path': 'mig-open', 'connect_to': other}),
        'a "trigger" that is not a webhook node': lambda s: s.update(trigger={'node': other, 'test_path': 'owner-mig-x'}),
    }
    for label, mutate in negatives.items():
        bad = _copy.deepcopy(base); mutate(bad)
        try:
            build(bad)
            print(f'✗ {label} was NOT refused')
            ok = False
        except ValueError as e:
            print(f'✓ {label} is refused: {e}')
    print('build-workflow-copy selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2
    wf = build(json.load(open(argv[1], encoding='utf-8')))
    out = json.dumps(wf, indent=2, ensure_ascii=False) + '\n'
    if '-o' in argv:
        open(argv[argv.index('-o') + 1], 'w', encoding='utf-8').write(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
