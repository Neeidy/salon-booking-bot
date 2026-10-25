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
The EDIT phase (7-F1, ruling 2026-10-25) is the same comparison turned into a per-edit ALLOWLIST for an engine edit
after the cutover: COMMITTED copy export vs the edited (staged) export. Only the --allow nodes may differ, and in them
only `parameters` and `alwaysOutputData` (an engine edit changes code, SQL and that one flag; type, typeVersion,
credentials, onError, disabled and every other key stay); a trigger can never be in an edit's --allow. Everything
else is red exactly as in the swap phase: a node added or removed, any other node changed, the connections, the
settings (strict), pinData. The temporary-trigger and test-path exceptions do not exist in this phase.
Two exceptions exist, and only in the TEST phase:
  · --temp-trigger NAME: a declared temporary webhook trigger (Q13's only test route for schedule-
    triggered copies) may exist, together with the edges that leave it, and those edges must be exactly
    what a real trigger of the original feeds (so a drill cannot enter past a kill-switch or a guard). In
    the SWAP phase its presence is a failure: it must be gone before the copy goes live;
  · --trigger NAME: the copy's real trigger may sit on a TEST path (parameters.path). In the SWAP phase the
    path must equal the original's.

Usage: python3 scripts/diff-workflow-copy.py ORIGINAL COPY --allow "Node A" "Node B" … \\
           [--phase test|swap] [--temp-trigger NAME] [--trigger NAME]
       python3 scripts/diff-workflow-copy.py COMMITTED_COPY_EXPORT STAGED_EXPORT --allow "Node A" … --phase edit
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
ALLOWED_ON_EDITED_NODE = {'parameters', 'alwaysOutputData'}   # the EDIT phase: code, SQL, and the flag item (2) removes


def _is_trigger(node):
    t = str(node.get('type', ''))
    return t == 'n8n-nodes-base.webhook' or t.endswith('Trigger')


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
    if phase == 'edit':
        settings_allow = None   # strict settings: the live-mode absence allowlist is a migration exception (the test-phase
                                # trigger exceptions are keyed on phase == 'test' and cannot apply here)
        errs += [f"'{n}' is in --allow but is not a node of the committed export" for n in sorted(set(allow) - set(O))]
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
        if name in allow and phase == 'edit':
            if _is_trigger(o) or _is_trigger(c):
                errs.append(f"'{name}' is a trigger: an engine edit never changes a trigger")
            for k in sorted((set(o) | set(c)) - IGNORED - ALLOWED_ON_EDITED_NODE):
                if canon(o.get(k)) != canon(c.get(k)):
                    errs.append(f"edited node '{name}': '{k}' changed (only parameters/alwaysOutputData may)")
            continue
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
            where = 'the edit allowlist' if phase == 'edit' else 'the data layer'
            errs.append(f"node outside {where} changed: '{name}' ({', '.join(keys)})")
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

    # EDIT phase (7-F1): built from the Main copy export, which carries a Load Config Turnstile literal and a webhook
    # trigger. The edit allowlist is one Code node.
    mexp = json.load(open(os.path.join(ROOT, 'n8n', 'workflow.main.copy.sanitized.json')))
    mtrig = [n['name'] for n in mexp['nodes'] if n['type'] == 'n8n-nodes-base.webhook'][0]
    medit = 'Build Owner Alert'
    mother = [n['name'] for n in mexp['nodes'] if n['type'] == 'n8n-nodes-base.code' and n['name'] not in (medit, 'Load Config')][0]
    mpg = [n['name'] for n in mexp['nodes'] if n['type'] == 'n8n-nodes-base.postgres'][0]

    def edited():
        e = _copy.deepcopy(mexp)
        node(e, medit)['parameters']['jsCode'] += '\n// the engine edit'
        return e
    ecases = []                                                # (label, edited export, allow, expect_pass)
    ecases.append(('edit: only the allowed Code node changed', edited(), {medit}, True))
    m = edited(); node(m, mpg)['alwaysOutputData'] = not node(m, mpg).get('alwaysOutputData', False)
    m2 = _copy.deepcopy(m); node(m2, mpg)['parameters']['query'] = 'SELECT 1'
    ecases.append(("edit: an allowed Postgres node's SQL and alwaysOutputData changed", m2, {medit, mpg}, True))
    m = edited(); node(m, mother)['parameters']['jsCode'] += '\n// not allowed'
    ecases.append(('edit: a NON-allowed node changed', m, {medit}, False))
    m = edited(); src_e = next(k for k, v in m['connections'].items() if v.get('main') and v['main'][0])
    m['connections'][src_e]['main'][0] = m['connections'][src_e]['main'][0][:-1] + [{'node': medit, 'type': 'main', 'index': 0}]
    ecases.append(('edit: an edge rewired', m, {medit}, False))
    m = edited(); lc = node(m, 'Load Config')['parameters']
    lc['jsCode'] = lc['jsCode'].replace('enabled: true', 'enabled: false', 1)
    ecases.append(('edit: the Turnstile literal changed in Load Config', m, {medit}, False))
    m = edited(); node(m, mtrig)['parameters']['path'] = 'owner-mig-somewhere-else'
    ecases.append(('edit: the trigger path changed', m, {medit}, False))
    m = edited(); node(m, mtrig)['parameters']['path'] = 'owner-mig-somewhere-else'
    ecases.append(('edit: the trigger smuggled into --allow', m, {medit, mtrig}, False))
    m = edited(); node(m, medit)['onError'] = 'continueErrorOutput'
    ecases.append(("edit: an allowed node's onError changed", m, {medit}, False))
    m = edited(); node(m, mpg)['credentials'] = {'postgres': {'id': 'REPLACE_WITH_OTHER', 'name': 'x'}}
    ecases.append(("edit: an allowed node's credentials changed", m, {medit, mpg}, False))
    m = edited(); node(m, medit)['type'] = 'n8n-nodes-base.function'
    ecases.append(("edit: an allowed node's type changed", m, {medit}, False))
    m = edited(); m['nodes'].append({'name': 'Temporary Test Trigger', 'type': 'n8n-nodes-base.webhook', 'typeVersion': 2,
                                     'parameters': {'path': 'owner-mig-x'}})
    ecases.append(('edit: a temporary trigger added (no test-phase exception)', m, {medit}, False))
    m = edited(); m['settings'] = dict(m.get('settings') or {}, executionTimeout=999)
    ecases.append(('edit: settings changed', m, {medit}, False))
    m = edited(); m['settings'] = {k: v for k, v in (m.get('settings') or {}).items() if k != 'executionOrder'}
    ecases.append(('edit: a settings key dropped, even with a live-mode allowlist passed', m, {medit}, False))
    ecases.append(('edit: an --allow name the export does not have', edited(), {medit, 'No Such Node'}, False))
    # The only trigger type in the tool's scope is the SCHEDULE trigger (Purge, Reminders): prove the rule on it too.
    pexp = json.load(open(os.path.join(ROOT, 'n8n', 'workflow.purge.copy.sanitized.json')))
    ptrig = [n['name'] for n in pexp['nodes'] if str(n['type']).endswith('Trigger')][0]
    m = _copy.deepcopy(pexp); node(m, ptrig)['parameters']['rule'] = {'interval': [{'field': 'minutes'}]}
    pcase = ('edit: a schedule trigger smuggled into --allow and re-timed', m, {ptrig}, False)

    ok = True
    perrs = compare(pexp, pcase[1], pcase[2], 'edit')
    ok &= bool(perrs)
    print(f"{'✓' if perrs else '✗'} {pcase[0]}: {'RED — ' + perrs[0] if perrs else 'pass'}")
    for label, e, allow, expect_pass in ecases:
        errs = compare(mexp, e, allow, 'edit', temp_trigger='Temporary Test Trigger', trigger=mtrig,
                       settings_allow={'executionOrder': {'covers': 'absent', 'ruling': 'selftest'}})
        good = (not errs) == expect_pass
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    for label, cp, phase, expect_pass, kw in cases:
        kw = dict(kw); allow = set(data) | ({kw.pop('allow_extra')} if 'allow_extra' in kw else set())
        o = dict(orig, settings=kw.pop('_orig_settings')) if '_orig_settings' in kw else orig
        errs = compare(o, cp, allow, phase, **kw)
        good = (not errs) == expect_pass
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    print('diff-workflow-copy selftest:', 'OK' if ok else 'FAILED',
          f'({len(cases)} cases built from {os.path.basename(src)}, {len(ecases) + 1} edit-phase cases from the Main and Purge copy exports)')
    return 0 if ok else 1


def main():
    if sys.argv[1:2] == ['--selftest']:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument('original'); ap.add_argument('copy')
    ap.add_argument('--allow', nargs='+', required=True)
    ap.add_argument('--phase', choices=['test', 'swap', 'edit'], default='swap')
    ap.add_argument('--temp-trigger'); ap.add_argument('--trigger')
    a = ap.parse_args()
    errs = compare(json.load(open(a.original)), json.load(open(a.copy)), set(a.allow), a.phase, a.temp_trigger, a.trigger)
    if errs:
        print('diff-workflow-copy: FAILED')
        for e in errs:
            print('  - ' + e)
        return 1
    what = 'allowed node(s) may' if a.phase == 'edit' else 'data-layer node(s)'
    print(f'diff-workflow-copy: OK — only the {len(a.allow)} {what} differ ({a.phase} phase)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
