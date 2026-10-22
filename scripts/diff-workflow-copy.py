#!/usr/bin/env python3
"""diff-workflow-copy.py — a migration copy may differ from its original ONLY in its data layer
(docs/MIGRATION-PLAN.md §4.1, rulings Q2 and Q13).

The migration swaps each Airtable node for a Postgres node IN PLACE: same node name, same connections, so
every `$('Load State')` reference and every error branch survives untouched. That is the only reason
"no new bug" can be proven mechanically, and this tool is the proof. Given an original and its copy, it
FAILS when:
  · a node is added or removed (a renamed data node counts as both);
  · a node OUTSIDE --allow differs in anything but its id/position/webhookId;
  · an --allow node differs in anything other than type, typeVersion, parameters or credentials
    (its onError and alwaysOutputData must stay exactly as they were: they ARE the error branches);
  · the connection graph differs;
  · the workflow settings differ. Offline (two committed files) this is strict equality. In live mode (the
    deploy helper passes the copy spec's `settings_allow`) a key the spec allowlists may be ABSENT on the copy,
    and nothing else (scripts/settings_parity.py; MIGRATION-PLAN §3r, settings-parity).
Two exceptions exist, and only in the TEST phase:
  · --temp-trigger NAME: a declared temporary webhook trigger (Q13's only test route for schedule-
    triggered copies) may exist, together with the edges that leave it, and those edges must be exactly
    what a real trigger of the original feeds (so a drill cannot enter past a kill-switch or a guard). In
    the SWAP phase its presence is a failure: it must be gone before the copy goes live;
  · --trigger NAME: the copy's real trigger may sit on a TEST path (parameters.path). In the SWAP phase the
    path must equal the original's.

Usage: python3 scripts/diff-workflow-copy.py ORIGINAL COPY --allow "Node A" "Node B" … \\
           [--phase test|swap] [--temp-trigger NAME] [--trigger NAME]
       python3 scripts/diff-workflow-copy.py --selftest      (positive control, built from a committed export)
"""
import argparse
import copy as _copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORED = {'id', 'position', 'webhookId'}            # n8n assigns these per workflow; never behaviour
ALLOWED_ON_DATA_NODE = {'type', 'typeVersion', 'parameters', 'credentials'}


def _settings_parity():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'settings_parity', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings_parity.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def canon(o):
    return json.dumps(o, sort_keys=True)


def strip(node, drop=()):
    return {k: v for k, v in node.items() if k not in IGNORED and k not in drop}


def compare(orig, cp, allow, phase='swap', temp_trigger=None, trigger=None, settings_allow=None):
    errs = []
    O = {n['name']: n for n in orig['nodes']}
    C = {n['name']: n for n in cp['nodes']}
    added, removed = set(C) - set(O), set(O) - set(C)
    if temp_trigger and temp_trigger in added:
        if phase == 'test':
            added.discard(temp_trigger)
        else:
            errs.append(f"temporary trigger '{temp_trigger}' is still present in the SWAP phase")
            added.discard(temp_trigger)
    errs += [f"node added: '{n}'" for n in sorted(added)]
    errs += [f"node removed: '{n}'" for n in sorted(removed)]
    for name in sorted(set(O) & set(C)):
        o, c = O[name], C[name]
        if name in allow:
            if o.get('type') not in ('n8n-nodes-base.airtable', 'n8n-nodes-base.postgres'):
                errs.append(f"'{name}' is in --allow but is not a data-layer node in the original ({o.get('type')})")
                continue
            if o.get('type') != c.get('type') and not (o.get('type') == 'n8n-nodes-base.airtable'
                                                        and c.get('type') == 'n8n-nodes-base.postgres'):
                errs.append(f"data node '{name}': type {o.get('type')} -> {c.get('type')} (only airtable -> postgres is a data-layer swap)")
            for k in sorted((set(o) | set(c)) - IGNORED - ALLOWED_ON_DATA_NODE):
                if canon(o.get(k)) != canon(c.get(k)):
                    errs.append(f"data node '{name}': '{k}' changed (only type/typeVersion/parameters/credentials may)")
            continue
        so, sc = strip(o), strip(c)
        if name == trigger and phase == 'test':
            so = _copy.deepcopy(so); sc = _copy.deepcopy(sc)
            so.get('parameters', {}).pop('path', None); sc.get('parameters', {}).pop('path', None)
        if canon(so) != canon(sc):
            keys = sorted(k for k in set(so) | set(sc) if canon(so.get(k)) != canon(sc.get(k)))
            errs.append(f"node outside the data layer changed: '{name}' ({', '.join(keys)})")
    oc = _copy.deepcopy(orig.get('connections', {}))
    cc = _copy.deepcopy(cp.get('connections', {}))
    if temp_trigger and phase == 'test' and temp_trigger in C:
        # A temporary trigger stands in for the real one, so it must feed EXACTLY what a real trigger of the
        # original feeds. Otherwise it could enter the flow past a kill-switch, a concurrency guard or a
        # signature check, and the drill would test a path production never takes (found at D3c, 2026-10-20:
        # a temp trigger wired past Reminders' kill-switch passed this tool).
        real = [canon(oc.get(n['name'], {})) for n in orig['nodes']
                if n.get('type') == 'n8n-nodes-base.webhook' or str(n.get('type', '')).endswith('Trigger')]
        if canon(cc.get(temp_trigger, {})) not in real:
            errs.append(f"temporary trigger '{temp_trigger}' does not feed what a real trigger of the original feeds")
    if temp_trigger and phase == 'test':
        cc.pop(temp_trigger, None)
    if canon(oc) != canon(cc):
        diff = sorted(k for k in set(oc) | set(cc) if canon(oc.get(k)) != canon(cc.get(k)))
        errs.append(f"connections differ (from: {', '.join(diff)})")
    if settings_allow is None:              # offline: two committed files, strict equality
        if canon(orig.get('settings')) != canon(cp.get('settings')):
            errs.append('workflow settings differ')
    else:                                   # live (deploy helper): the copy spec's allowlist, absences only
        errs += _settings_parity().copy_vs_original(orig.get('settings'), cp.get('settings'), settings_allow)
    if cp.get('pinData'):
        errs.append('the copy carries pinData (pinned data changes what a node returns)')
    return errs


def selftest():
    src = os.path.join(ROOT, 'n8n', 'workflow.drill-state.sanitized.json')
    orig = json.load(open(src))
    data = [n['name'] for n in orig['nodes'] if n['type'] == 'n8n-nodes-base.airtable']
    trig = [n['name'] for n in orig['nodes'] if n['type'] == 'n8n-nodes-base.webhook'][0]
    assert data, 'the source export has no Airtable node to swap'

    def swapped():
        cp = _copy.deepcopy(orig)
        for n in cp['nodes']:
            n['id'] = 'copy-' + n['name']                      # a copy gets new ids: must not matter
            if n['name'] in data:
                n['type'], n['typeVersion'] = 'n8n-nodes-base.postgres', 2.6
                n['parameters'] = {'operation': 'executeQuery', 'query': 'SELECT 1', 'options': {}}
                n['credentials'] = {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Salon Postgres'}}
        return cp

    def node(cp, name):
        return [n for n in cp['nodes'] if n['name'] == name][0]

    def with_temp(cp):
        cp['nodes'].append({'name': 'TEMP Test Trigger', 'type': 'n8n-nodes-base.webhook', 'typeVersion': 2,
                            'parameters': {'path': 'owner-test-x', 'httpMethod': 'POST'}})
        cp['connections']['TEMP Test Trigger'] = _copy.deepcopy(orig['connections'][trig])   # feeds what the real trigger feeds
        return cp

    other = [n['name'] for n in orig['nodes'] if n['name'] not in data and n['type'] == 'n8n-nodes-base.code'][0]
    cases = []                                                 # (label, copy, phase, expect_pass, kwargs)
    cases.append(('clean data-layer swap', swapped(), 'swap', True, {}))
    m = swapped(); node(m, other)['parameters']['jsCode'] += '\n// drift'
    cases.append(('a node outside the data layer changed', m, 'swap', False, {}))
    m = swapped(); src_node = data[0]; m['connections'][src_node]['main'][0] = []
    cases.append(('a connection changed', m, 'swap', False, {}))
    m = swapped(); node(m, data[0])['name'] = data[0] + ' (pg)'
    cases.append(('a data node renamed', m, 'swap', False, {}))
    m = swapped(); node(m, data[0])['onError'] = 'stopWorkflow'
    cases.append(("a data node's onError changed", m, 'swap', False, {}))
    m = swapped(); node(m, data[0])['alwaysOutputData'] = not node(m, data[0]).get('alwaysOutputData', False)
    cases.append(("a data node's alwaysOutputData changed", m, 'swap', False, {}))
    cases.append(('declared temp trigger, TEST phase', with_temp(swapped()), 'test', True, {'temp_trigger': 'TEMP Test Trigger'}))
    cases.append(('declared temp trigger, SWAP phase', with_temp(swapped()), 'swap', False, {'temp_trigger': 'TEMP Test Trigger'}))
    cases.append(('UNdeclared extra trigger, TEST phase', with_temp(swapped()), 'test', False, {}))
    m = swapped(); node(m, trig)['parameters']['path'] = 'owner-drill-state-pg-test'
    cases.append(('trigger on a test path, TEST phase', m, 'test', True, {'trigger': trig}))
    m2 = _copy.deepcopy(m)
    cases.append(('trigger still on the test path, SWAP phase', m2, 'swap', False, {'trigger': trig}))
    m = swapped(); m['nodes'].append({'name': 'Stray Node', 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'parameters': {}})
    cases.append(('an extra node with NO connections', m, 'swap', False, {}))   # only the "added" check sees it
    m = swapped(); m['nodes'] = [n for n in m['nodes'] if n['type'] != 'n8n-nodes-base.stickyNote']
    cases.append(('a node with NO connections deleted', m, 'swap', False, {}))   # only the "removed" check sees it
    m = with_temp(swapped()); m['connections'].pop('TEMP Test Trigger')
    cases.append(('edge-less temp trigger left in, SWAP phase', m, 'swap', False, {'temp_trigger': 'TEMP Test Trigger'}))
    m = with_temp(swapped()); m['connections']['TEMP Test Trigger'] = {'main': [[{'node': data[0], 'type': 'main', 'index': 0}]]}
    cases.append(('temp trigger wired past the real entry (straight to a data node), TEST phase', m, 'test', False, {'temp_trigger': 'TEMP Test Trigger'}))
    m = swapped(); node(m, data[0])['type'] = 'n8n-nodes-base.code'; node(m, data[0])['parameters'] = {'jsCode': 'return []'}
    cases.append(('a data node turned into a Code node', m, 'swap', False, {}))
    m = swapped(); node(m, other)['parameters']['jsCode'] = 'return [$input.first()];'
    cases.append(('a NON-data node smuggled into --allow and rewritten', m, 'swap', False, {'allow_extra': other}))
    m = swapped(); m['pinData'] = {data[0]: [{'json': {'id': 'recAAAAAAAAAAAAAA'}}]}
    cases.append(('the copy carries pinData', m, 'swap', False, {}))
    m = swapped(); m['settings'] = dict(m.get('settings') or {}, executionOrder='v0')
    cases.append(('workflow settings changed', m, 'swap', False, {}))
    o2 = dict(orig.get('settings') or {}, binaryMode='separate')
    AB = {'binaryMode': {'covers': 'absent', 'ruling': 'selftest'}}
    m = swapped(); m['settings'] = {k: v for k, v in o2.items() if k != 'binaryMode'}
    cases.append(('settings: allowlisted key absent on the copy (live mode)', m, 'swap', True, {'settings_allow': AB, '_orig_settings': o2}))
    m = swapped(); m['settings'] = dict(o2, binaryMode='combined')
    cases.append(('settings: allowlisted key with a DIFFERENT value (live mode)', m, 'swap', False, {'settings_allow': AB, '_orig_settings': o2}))
    m = swapped(); m['settings'] = {k: v for k, v in o2.items() if k != 'binaryMode'}
    cases.append(('settings: key absent and NOT allowlisted (live mode)', m, 'swap', False, {'settings_allow': {}, '_orig_settings': o2}))

    ok = True
    for label, cp, phase, expect_pass, kw in cases:
        kw = dict(kw); allow = set(data) | ({kw.pop('allow_extra')} if 'allow_extra' in kw else set())
        o = dict(orig, settings=kw.pop('_orig_settings')) if '_orig_settings' in kw else orig
        errs = compare(o, cp, allow, phase, **kw)
        good = (not errs) == expect_pass
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    print('diff-workflow-copy selftest:', 'OK' if ok else 'FAILED', f'({len(cases)} cases, built from {os.path.basename(src)})')
    return 0 if ok else 1


def main():
    if sys.argv[1:2] == ['--selftest']:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument('original'); ap.add_argument('copy')
    ap.add_argument('--allow', nargs='+', required=True)
    ap.add_argument('--phase', choices=['test', 'swap'], default='swap')
    ap.add_argument('--temp-trigger'); ap.add_argument('--trigger')
    a = ap.parse_args()
    errs = compare(json.load(open(a.original)), json.load(open(a.copy)), set(a.allow), a.phase, a.temp_trigger, a.trigger)
    if errs:
        print('diff-workflow-copy: FAILED')
        for e in errs:
            print('  - ' + e)
        return 1
    print(f'diff-workflow-copy: OK — only the {len(a.allow)} data-layer node(s) differ ({a.phase} phase)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
