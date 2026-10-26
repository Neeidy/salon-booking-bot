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
A DECLARED DELTA (7-2 Tur 2, rulings R-1a/DEAD, R-Q2) widens the edit phase by exactly what is named and nothing else,
and it exists only as a delta FILE (--delta-file F: allow + the four lists of DELTA_KEYS + an optional `settings` map;
load_delta_file, `_doc` ignored, any other key refused; mutually exclusive with --allow): add_nodes / remove_nodes (a
trigger can never be added or removed) and add_edges / remove_edges "SRC|OUT|DST|IN" (main connections). The committed
edge set minus the removed edges plus the added edges must EQUAL the staged edge set; an edge touching an added or
removed node exists on one side only, so it must be declared too; a declared item that is not actually there (a node
"added" that the committed export already has, an edge "removed" that never existed) is red, so a declaration cannot sit
unused beside the change it was meant to describe. An added node must be of an ADDABLE_TYPES type (logic and notes); a
repeated edge and an edge to a missing node are red; a touched source's non-main connections stay exact.
APPROVED DELTAS (ruling FIXED, Yigitcan 2026-10-26): this tool checks that a staged export matches a delta; WHICH deltas
may be applied at all is APPROVED_DELTAS below — the two reviewed 7-2 Tur 2 edits, by exact identity. workflow-step.py
refuses a delta file that is not exactly one of them (approved_errs), and tests/unit/staged-sanitised.test.py holds the
committed delta files to them. A new delta is a change to this list, reviewed as code.
DECLARED SETTINGS (ruling T-4): `settings` maps workflow-settings keys to exact JSON scalars (no object, array, null; not
empty); the staged settings must equal the committed settings updated with exactly that map, and `executionOrder` is
never declared (it is sibling order, i.e. behaviour). Without it, settings stay strictly equal. workflow-step put never
sends them: its `settings` command applies them as the last step.
GATE (Yigitcan, 2026-10-26; widened to every security-gate node by the R1c ruling), EDIT phase: the GATE_NODES (Main's
and Owner Actions' admission path, listed below) and every trigger (type webhook, *Trigger, or a LEGACY_TRIGGER_TYPES
type) are red in --allow (even unchanged) and in remove_nodes. A DECLARED edge (added or removed) that touches a gate
node, as source or target, is red unless it is one of RULED_GATE_EDGES (ruling R-Q2: the two Tag Turnstile Unavailable
edges). An UNDECLARED change of a gate node's connections is red like any other: an untouched source compares exactly,
and a gate source touched by a ruled edge keeps every other edge, in its committed order.
POSITION LOCK (R1c, M-c), EDIT phase: under executionOrder v1 the targets of one output run in canvas order (top to
bottom, then left to right), so a node present on both sides keeps its `position` — a move is red; no delta declares
one (the approved deltas move nothing). sibling_order_lines() reports the resulting v1 order of every output an added
node joins beside other targets (printed by main() and by workflow-step put).
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
       python3 scripts/diff-workflow-copy.py COMMITTED_COPY_EXPORT STAGED_EXPORT --phase edit --delta-file DELTA.json
       python3 scripts/diff-workflow-copy.py --selftest      (positive control, built from a committed export)
"""
import argparse
import copy as _copy
from collections import Counter
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORED = {'id', 'position', 'webhookId'}            # n8n assigns these per workflow; never behaviour
ALLOWED_ON_DATA_NODE = {'type', 'typeVersion', 'parameters', 'credentials'}
ALLOWED_ON_EDITED_NODE = {'parameters', 'alwaysOutputData'}   # the EDIT phase: code, SQL, and the flag item (2) removes


# Trigger types whose name does not end in "Trigger" (older n8n vintages). The ADDABLE_TYPES allow-list below is what
# keeps any OTHER unknown trigger type from being ADDED; this set is what lets the gate below see these as triggers.
LEGACY_TRIGGER_TYPES = {'n8n-nodes-base.cron', 'n8n-nodes-base.interval', 'n8n-nodes-base.emailReadImap',
                        'n8n-nodes-base.start'}
# GATE (Yigitcan, 2026-10-26; R1c ruling): every security-gate node, and EVERY trigger, is never in an edit's --allow nor
# in remove_nodes. The list is derived from the graph: on the path from the webhook trigger to the first node after
# admission (Main: the claim `Check Processed`; Owner Actions: its first store read, `Find Target Conversation`), every
# node whose output routes the request to a reject responder or onward — the reject builders and responders included
# (a responder has an output: an edge from it onward would run the bot after the reject reply) — plus the config that
# drives them.
GATE_NODES = (
    # Main
    'Receive Inbound Message', 'Is Zernio Inbound?', 'Compute Body HMAC', 'Verify Signature', 'Signature Valid?',
    'Load Config', 'Normalize Inbound', 'Normalized OK?', 'Turnstile Gate', 'Verify Turnstile', 'Turnstile Valid?',
    'Resume After Turnstile', 'Validate Payload',
    'Reject Unsigned Request', 'Reject Bot Request', 'Build Normalize Reject', 'Respond Normalize Reject', 'Send Reject Response',
    # Owner Actions (`Signature Valid?` is named in both workflows and listed once, above)
    'Receive Owner Action', 'Verify Owner Signature', 'Owner Request Fresh?', 'Validate Owner Action', 'Action Allowed?',
    'Reject Unsigned Owner Request', 'Reject Stale Owner Request', 'Reject Unknown Owner Action',
)
# Ruling R-Q2: the ONLY declared edges that may touch a gate node, by exact name — the Turnstile-unavailable tag fed from
# both Turnstile failure outputs. Any other declared edge from or to a gate node is red.
RULED_GATE_EDGES = frozenset({'Verify Turnstile|1|Tag Turnstile Unavailable|0',
                              'Turnstile Valid?|1|Tag Turnstile Unavailable|0'})
DELTA_KEYS = ('add_nodes', 'remove_nodes', 'add_edges', 'remove_edges')
EDGE_RE = re.compile(r'[^|]+\|\d+\|[^|]+\|\d+')
# Ruling FIXED (Yigitcan, 2026-10-26): the ONLY deltas the deploy tool applies — the two reviewed 7-2 Tur 2 edits, by exact
# identity (node name · "SRC|OUT|DST|IN" · settings key=value). The tool guards against OUR mistakes: a delta file that
# differs from this in any item is refused before any call. A copy with no entry here takes no delta at all.
APPROVED_DELTAS = {
    'main': {
        'add_nodes': {'Tag Turnstile Unavailable', 'Sticky — Tag Turnstile Unavailable'},
        'remove_nodes': {'Record Processed', 'Build Dedupe-Marker Alert'},
        'add_edges': {'Tag Turnstile Unavailable|0|Build Owner Alert|0', 'Turnstile Valid?|1|Tag Turnstile Unavailable|0',
                      'Verify Turnstile|1|Tag Turnstile Unavailable|0'},
        'remove_edges': {'Build Dedupe-Marker Alert|0|Build Owner Alert|0', 'Record Processed|1|Build Dedupe-Marker Alert|0',
                         'Save State (Post-Write)|0|Record Processed|0', 'Save State|0|Record Processed|0'},
        'settings': {},
    },
    'owner-actions': {
        'add_nodes': set(),
        'remove_nodes': {'Build Marker Failure Alert', 'Marker Written?', 'Record Owner Action Processed',
                         'Respond Owner OK (Marker Unwritten)', 'Send Marker Failure Alert (Telegram)'},
        'add_edges': {'Write Verified?|0|Build Owner Alert (Release)|0'},
        'remove_edges': {'Build Marker Failure Alert|0|Send Marker Failure Alert (Telegram)|0',
                         'Marker Written?|0|Build Owner Alert (Release)|0', 'Marker Written?|1|Build Marker Failure Alert|0',
                         'Record Owner Action Processed|0|Marker Written?|0',
                         'Send Marker Failure Alert (Telegram)|0|Respond Owner OK (Marker Unwritten)|0',
                         'Send Marker Failure Alert (Telegram)|1|Respond Owner OK (Marker Unwritten)|0',
                         'Write Verified?|0|Record Owner Action Processed|0'},
        'settings': {'saveDataSuccessExecution': 'none'},   # ruling T-4: execution data saved on error only
    },
}


def approved_errs(key, delta):
    """[] when `delta` (parse_delta's dict) is EXACTLY APPROVED_DELTAS[key] — every list and the settings map, items
    compared by identity, settings type-strict — or carries nothing at all (no list item, no setting: a plain --allow
    edit). Anything else lists what is extra and what is missing."""
    delta = delta or {}
    if not any(delta.get(k) for k in (*DELTA_KEYS, 'settings')):
        return []
    want = APPROVED_DELTAS.get(key)
    if want is None:
        return [f"'{key}' has no approved delta: it takes parameter edits (--allow) only"]
    errs = []
    for k in DELTA_KEYS:
        got = set(delta.get(k) or ())
        extra, missing = sorted(got - want[k]), sorted(want[k] - got)
        if extra or missing:
            errs.append(f"{k} is not the approved delta for '{key}' (not approved: {extra[:3]}; approved but absent: {missing[:3]})")
    if canon(delta.get('settings') or {}) != canon(want['settings']):
        errs.append(f"settings {canon(delta.get('settings') or {})} are not the approved {canon(want['settings'])} for '{key}'")
    return errs


def _is_trigger(node):
    t = str(node.get('type', ''))
    return t == 'n8n-nodes-base.webhook' or t.endswith('Trigger') or t in LEGACY_TRIGGER_TYPES


def is_gate(name, *wfs):
    """A GATE node: named in GATE_NODES, or a trigger in any of the given workflows."""
    return name in GATE_NODES or any(_is_trigger(n) for wf in wfs for n in wf.get('nodes') or [] if n.get('name') == name)


def load_delta_file(path):
    """A declared-delta JSON file → parse_delta(its content)."""
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f'the delta file does not read ({type(e).__name__})')
    return parse_delta(d)


def parse_delta(d):
    """A parsed declared-delta object → (allow list, delta dict). Keys: allow (non-empty) and the DELTA_KEYS (absent =
    empty), each a list of distinct non-empty strings, edges as "SRC|OUT|DST|IN"; `_doc` is ignored; any other key, or
    an object not of that shape, raises ValueError. (workflow-step.py hands in the content read from git HEAD.)"""
    if not isinstance(d, dict):
        raise ValueError('the delta file is not a JSON object')
    unknown = sorted(set(d) - {'_doc', 'allow', 'settings', *DELTA_KEYS})
    if unknown:
        raise ValueError(f'the delta file has unknown key(s): {unknown}')
    for k in ('allow', *DELTA_KEYS):
        v = d.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            raise ValueError(f"the delta file's '{k}' is not a list of non-empty strings")
        if len(set(v)) != len(v):
            raise ValueError(f"the delta file's '{k}' repeats an entry")
    if not d.get('allow'):
        raise ValueError("the delta file's 'allow' is missing or empty")
    bad = [e for k in ('add_edges', 'remove_edges') for e in d.get(k, []) if not EDGE_RE.fullmatch(e)]
    if bad:
        raise ValueError(f'the delta file has an edge not of the form "SRC|OUT|DST|IN": {bad[0]!r}')
    st = d.get('settings', {})
    if 'settings' in d and not (isinstance(st, dict) and st and all(
            k and isinstance(v, (str, bool, int, float)) for k, v in st.items())):
        raise ValueError("the delta file's 'settings' is not a non-empty object of workflow-settings keys to JSON scalars")
    return list(d['allow']), dict({k: set(d.get(k, [])) for k in DELTA_KEYS}, settings=dict(st))


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


def edge_list(wf):
    """The main connection graph as a LIST of 'SRC|OUT|DST|IN' strings (a repeated edge appears twice)."""
    out = []
    for src, by_type in (wf.get('connections') or {}).items():
        for i, lst in enumerate((by_type or {}).get('main') or []):
            for e in lst or []:
                out.append(f"{src}|{i}|{e.get('node')}|{e.get('index', 0)}")
    return out


def edges(wf):
    return set(edge_list(wf))


def _ends(e):
    """(source, target) of an 'SRC|OUT|DST|IN' string; a malformed string yields '' for a missing part."""
    p = e.split('|')
    return p[0], (p[2] if len(p) > 2 else '')


def _v1_key(node):
    """executionOrder v1 runs the targets of one output top to bottom, then left to right: sort by (y, x)."""
    pos = node.get('position') or [0, 0]
    return (pos[1], pos[0]) if isinstance(pos, list) and len(pos) == 2 else (0, 0)


def sibling_order_lines(cp, delta):
    """For every output of `cp` that an ADDED node joins beside other targets: the resulting v1 sibling order."""
    N = {n['name']: n for n in cp.get('nodes') or []}
    watch = set((delta or {}).get('add_nodes') or ())
    out = []
    for src, by_type in sorted((cp.get('connections') or {}).items()):
        for i, lst in enumerate((by_type or {}).get('main') or []):
            names = [e.get('node') for e in lst or []]
            if len(names) > 1 and watch & set(names):
                order = sorted(names, key=lambda n: _v1_key(N.get(n) or {}))
                out.append(f"v1 sibling order of '{src}' output {i}: " + ' → '.join(
                    f"{n} {list((N.get(n) or {}).get('position') or [])}" for n in order))
    return out


# A declared ADDED node may only be one of these types: logic and notes. Anything else (a trigger of any vintage, a
# data or messaging node) needs a review of its own, not a declaration (lane T review, 7-2 Tur 2, M5).
ADDABLE_TYPES = {'n8n-nodes-base.code', 'n8n-nodes-base.if', 'n8n-nodes-base.set', 'n8n-nodes-base.switch',
                 'n8n-nodes-base.noOp', 'n8n-nodes-base.stickyNote', 'n8n-nodes-base.merge', 'n8n-nodes-base.filter'}


def compare(orig, cp, allow, phase='swap', temp_trigger=None, trigger=None, settings_allow=None, delta=None):
    errs = []
    O = {n['name']: n for n in orig['nodes']}
    C = {n['name']: n for n in cp['nodes']}
    added, removed = set(C) - set(O), set(O) - set(C)
    delta = delta or {}
    if any(delta.get(k) for k in (*DELTA_KEYS, 'settings')) and phase != 'edit':
        return ['a declared delta exists only in the EDIT phase']
    if phase == 'edit':
        errs += [f"'{n}' is a GATE node (a security-gate node or a trigger): never in --allow"
                 for n in sorted(allow) if is_gate(n, orig, cp)]
        errs += [f"'{n}' is a GATE node (a security-gate node or a trigger): never removed"
                 for n in sorted(set(delta.get('remove_nodes') or ())) if is_gate(n, orig)]
        errs += [f"declared edge '{e}' touches a GATE node and is not a ruled edge (R-Q2)"
                 for e in sorted(set(delta.get('add_edges') or ()) | set(delta.get('remove_edges') or ()))
                 if e not in RULED_GATE_EDGES and any(x and is_gate(x, orig, cp) for x in _ends(e))]
        errs += [f"node moved: '{n}' (its position orders sibling branches under v1; an engine edit moves nothing)"
                 for n in sorted(set(O) & set(C)) if canon(O[n].get('position')) != canon(C[n].get('position'))]
        for n in sorted(set(delta.get('add_nodes') or ())):
            if n not in added:
                errs.append(f"declared added node '{n}' is not new in the staged export")
            elif _is_trigger(C[n]):
                errs.append(f"declared added node '{n}' is a trigger: an engine edit never adds one")
            elif C[n].get('type') not in ADDABLE_TYPES:
                errs.append(f"declared added node '{n}' is of type {C[n].get('type')}: only logic and note nodes may be declared")
        for n in sorted(set(delta.get('remove_nodes') or ())):
            if n not in removed:
                errs.append(f"declared removed node '{n}' is not gone from the staged export")
            elif _is_trigger(O[n]):
                errs.append(f"declared removed node '{n}' is a trigger: an engine edit never removes one")
        added -= set(delta.get('add_nodes') or ())
        removed -= set(delta.get('remove_nodes') or ())
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
    if phase == 'edit' and any(delta.get(k) for k in DELTA_KEYS):
        oe, ce = edges(orig), edges(cp)
        add_e, rem_e = set(delta.get('add_edges') or ()), set(delta.get('remove_edges') or ())
        dup = sorted(e for e, k in Counter(edge_list(cp)).items() if k > 1 and Counter(edge_list(orig)).get(e, 0) < k)
        errs += [f"edge repeated in the staged export: '{e}' (a repeated connection runs its target twice)" for e in dup]
        errs += [f"edge '{e}' points at a node the staged export does not have" for e in sorted(ce)
                 if e.split('|')[0] not in C or e.split('|')[2] not in C]
        errs += [f"declared added edge '{e}' already exists in the committed export" for e in sorted(add_e & oe)]
        errs += [f"declared removed edge '{e}' does not exist in the committed export" for e in sorted(rem_e - oe)]
        want = (oe - rem_e) | add_e
        errs += [f"edge added without a declaration: '{e}'" for e in sorted(ce - want)]
        errs += [f"declared added edge '{e}' is not in the staged export" if e in add_e
                 else f"edge removed without a declaration: '{e}'" for e in sorted(want - ce)]
        # A source the delta does not touch keeps its exact connection list (order included), as before.
        touched = {e.split('|', 1)[0] for e in add_e | rem_e} | set(delta.get('add_nodes') or ()) | set(delta.get('remove_nodes') or ())
        for k in sorted((set(oc) | set(cc)) - touched):
            if canon(oc.get(k)) != canon(cc.get(k)):
                errs.append(f"connections differ (from: {k})")
        for k in sorted(touched & (set(oc) | set(cc))):   # a touched source: its non-main connection types stay exact
            if canon({t: v for t, v in (oc.get(k) or {}).items() if t != 'main'}) != canon({t: v for t, v in (cc.get(k) or {}).items() if t != 'main'}):
                errs.append(f"connections differ outside 'main' (from: {k})")
        for k in sorted(touched & (set(oc) | set(cc))):   # a touched GATE source keeps its other edges in committed order
            if not is_gate(k, orig, cp):
                continue
            ol, cl = (oc.get(k) or {}).get('main') or [], (cc.get(k) or {}).get('main') or []
            for i in range(max(len(ol), len(cl))):
                keep_o = [f"{k}|{i}|{x.get('node')}|{x.get('index', 0)}" for x in (ol[i] if i < len(ol) else None) or []]
                keep_c = [f"{k}|{i}|{x.get('node')}|{x.get('index', 0)}" for x in (cl[i] if i < len(cl) else None) or []]
                if [e for e in keep_o if e not in rem_e] != [e for e in keep_c if e not in add_e]:
                    errs.append(f"GATE node '{k}' output {i}: its connections changed beyond the declared edges (order included)")
    elif canon(oc) != canon(cc):
        diff = sorted(k for k in set(oc) | set(cc) if canon(oc.get(k)) != canon(cc.get(k)))
        errs.append(f"connections differ (from: {', '.join(diff)})")
    declared = dict(delta.get('settings') or {})
    if phase == 'edit' and declared:   # a DECLARED settings change (ruling T-4): committed settings + exactly the map.
        # executionOrder is behaviour, not configuration: it decides the order sibling branches run in.
        if 'executionOrder' in declared:
            errs.append("a declared settings change may not touch 'executionOrder' (it decides sibling branch order)")
        base = dict(orig.get('settings') or {})
        if canon(cp.get('settings') or {}) != canon(dict(base, **declared)):
            errs.append('workflow settings differ from the committed settings plus exactly the declared settings change')
    elif settings_allow is None:            # offline: two committed files, strict equality
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
    mother = [n['name'] for n in mexp['nodes'] if n['type'] == 'n8n-nodes-base.code' and n['name'] != medit
              and not is_gate(n['name'], mexp)][0]
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
    # DECLARED DELTA (7-2 Tur 2): an added Code node fed by one edge, plus its sticky; two removed nodes with their edges.
    dcases = []                                                # (label, edited export, allow, delta, expect_pass)

    def with_added(e, edge=True):
        e['nodes'].append({'name': 'Tag Test', 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'parameters': {'jsCode': 'return [];'}})
        e['nodes'].append({'name': 'Sticky — Tag Test', 'type': 'n8n-nodes-base.stickyNote', 'typeVersion': 1, 'parameters': {'content': 'why'}})
        if edge:
            e['connections'].setdefault(mother, {'main': [[]]})['main'][0].append({'node': 'Tag Test', 'type': 'main', 'index': 0})
        return e
    add_d = {'add_nodes': {'Tag Test', 'Sticky — Tag Test'}, 'add_edges': {f'{mother}|0|Tag Test|0'}}
    dcases.append(('delta: a declared Code node + sticky + its one edge', with_added(edited()), {medit}, add_d, True))
    dcases.append(('delta: the same node added WITHOUT a declaration', with_added(edited()), {medit}, {}, False))
    dcases.append(('delta: node declared, its edge NOT declared', with_added(edited()), {medit}, dict(add_d, add_edges=set()), False))
    dcases.append(('delta: an edge declared that is not there', with_added(edited(), edge=False), {medit}, add_d, False))
    m = with_added(edited())
    m['nodes'].append({'name': 'Tag Test 2', 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'parameters': {'jsCode': 'return [];'}})
    m['connections'][mother]['main'][0].append({'node': 'Tag Test 2', 'type': 'main', 'index': 0})
    dcases.append(('delta: a second edge from a DECLARED source, not itself declared', m, {medit},
                   dict(add_d, add_nodes=add_d['add_nodes'] | {'Tag Test 2'}), False))
    dcases.append(('delta: a node declared added that the committed export already has', edited(), {medit},
                   {'add_nodes': {mother}}, False))
    m = with_added(edited()); node(m, 'Tag Test')['type'] = 'n8n-nodes-base.webhook'
    dcases.append(('delta: a TRIGGER declared added', m, {medit}, add_d, False))
    rm = ['Record Processed', 'Build Dedupe-Marker Alert']
    rm_edges = {e for e in edges(mexp) if e.split('|')[0] in rm or e.split('|')[2] in rm}

    def with_removed(e, keep_edge=None):
        e['nodes'] = [n for n in e['nodes'] if n['name'] not in rm]
        for k in list(e['connections']):
            if k in rm:
                e['connections'].pop(k); continue
            for lst in e['connections'][k].get('main') or []:
                lst[:] = [x for x in lst if x['node'] not in rm or x['node'] == keep_edge]
        return e
    rm_d = {'remove_nodes': set(rm), 'remove_edges': rm_edges}
    dcases.append(('delta: two declared removed nodes with all their edges', with_removed(edited()), {medit}, rm_d, True))
    dcases.append(('delta: removed node, one of its incoming edges NOT declared', with_removed(edited()), {medit},
                   dict(rm_d, remove_edges={e for e in rm_edges if not e.startswith('Save State|')}), False))
    m = with_added(edited()); m['connections'][mother]['main'][0].append({'node': 'Tag Test', 'type': 'main', 'index': 0})
    dcases.append(('delta: the declared edge REPEATED on a touched source', m, {medit}, add_d, False))
    m = with_added(edited()); node(m, 'Tag Test')['type'] = 'n8n-nodes-base.cron'
    dcases.append(('delta: an added node of an OLD trigger type (cron) / a non-logic type', m, {medit}, add_d, False))
    m = with_added(edited()); m['connections'][mother]['ai_tool'] = [[{'node': 'Tag Test', 'type': 'ai_tool', 'index': 0}]]
    dcases.append(("delta: a non-main connection added on a touched source", m, {medit}, add_d, False))
    m = with_added(edited()); m['connections'][mother]['main'][0].append({'node': 'No Such Node', 'type': 'main', 'index': 0})
    dcases.append(('delta: a declared edge to a node that does not exist', m, {medit},
                   dict(add_d, add_edges=add_d['add_edges'] | {f'{mother}|0|No Such Node|0'}), False))
    m = with_removed(edited()); src_o = next(k for k, v in m['connections'].items() if k not in rm and len((v.get('main') or [[]])[0]) > 1)
    m['connections'][src_o]['main'][0].reverse()
    dcases.append(('delta: an UNTOUCHED source reorders its edges', m, {medit}, rm_d, False))
    # GATE (2026-10-26, R1c): every security-gate node and every trigger — never allowed, never removed.
    oexp = json.load(open(os.path.join(ROOT, 'n8n', 'workflow.owner-actions.copy.sanitized.json')))
    mgate = [g for g in GATE_NODES if any(n['name'] == g for n in mexp['nodes'])]
    ogate = [g for g in GATE_NODES if any(n['name'] == g for n in oexp['nodes'])]
    assert len(mgate) == 18 and len(ogate) == 9 and len(GATE_NODES) == len(set(GATE_NODES)) == 26, f'the gate list and the exports disagree: {mgate} {ogate}'
    for g in mgate:
        dcases.append((f"gate: '{g}' in --allow, UNCHANGED", edited(), {medit, g}, {}, False))
    dcases.append((f'gate: the webhook trigger in --allow, UNCHANGED', edited(), {medit, mtrig}, {}, False))

    def without(e, name):
        """Remove `name` and its edges; re-wire each predecessor to each successor (the H1 shape). → (export, delta)."""
        ins = [x for x in edges(e) if x.split('|')[2] == name]
        outs = [x for x in edges(e) if x.split('|')[0] == name]
        rem = set(ins) | set(outs)
        add = {f"{i.split('|')[0]}|{i.split('|')[1]}|{o.split('|')[2]}|{o.split('|')[3]}" for i in ins for o in outs} - edges(e)
        e['nodes'] = [n for n in e['nodes'] if n['name'] != name]
        e['connections'].pop(name, None)
        for k in e['connections']:
            for i, lst in enumerate(e['connections'][k].get('main') or []):
                if any(x['node'] == name for x in lst):
                    lst[:] = [x for x in lst if x['node'] != name] + [
                        {'node': a.split('|')[2], 'type': 'main', 'index': int(a.split('|')[3])}
                        for a in sorted(add) if a.startswith(f'{k}|{i}|')]
        return e, {'remove_nodes': {name}, 'remove_edges': rem, 'add_edges': add}
    for g in mgate:
        e, d = without(edited(), g)
        dcases.append((f"gate: '{g}' removed, its edges declared and its predecessors re-wired (lane T H1)", e, {medit}, d, False))
    rcases = []                                                # a gate removed with NO edge declared: only the remove rule names it
    for g in ('Verify Turnstile', 'Verify Owner Signature'):
        src_wf = mexp if g == 'Verify Turnstile' else oexp
        e, _ = without(_copy.deepcopy(src_wf), g)
        rcases.append((f"gate: '{g}' removed, NO edge declared → 'never removed'", src_wf, e, {'remove_nodes': {g}}))
    e, d = without(edited(), 'Build Dedupe-Marker Alert')
    dcases.append(('gate control: the same removal of a NON-gate node passes', e, {medit}, d, True))
    TAG = 'Tag Turnstile Unavailable'

    def with_tag(e, *srcs):
        e['nodes'].append({'name': TAG, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': [2464, 4256],
                           'parameters': {'jsCode': 'return [];'}})
        for s in srcs:
            e['connections'][s]['main'][1].append({'node': TAG, 'type': 'main', 'index': 0})
        return e
    ruled = {'add_nodes': {TAG}, 'add_edges': set(RULED_GATE_EDGES)}
    m = with_tag(edited(), 'Verify Turnstile', 'Turnstile Valid?')
    dcases.append(('gate: the two RULED edges (R-Q2) declared pass', m, {medit}, ruled, True))
    dcases.append(('ruled edges: the same edges UNDECLARED are refused', m, {medit}, dict(ruled, add_edges=set()), False))
    m2 = _copy.deepcopy(m); m2['connections']['Verify Turnstile']['main'][0].append({'node': TAG, 'type': 'main', 'index': 0})
    dcases.append(('gate: a second, undeclared edge from Verify Turnstile beside the ruled ones', m2, {medit}, ruled, False))
    m = with_added(edited(), edge=False); m['connections']['Verify Turnstile']['main'][1].append({'node': 'Tag Test', 'type': 'main', 'index': 0})
    dcases.append(('gate: a DECLARED edge from Verify Turnstile that is not a ruled edge is refused', m, {medit},
                   dict(add_d, add_edges={'Verify Turnstile|1|Tag Test|0'}), False))
    # G1 (R1b re-review): A–D on Main, and the Owner Actions signature node.
    m = edited(); node(m, 'Turnstile Gate')['parameters']['conditions']['conditions'][0]['leftValue'] = '={{ false }}'
    dcases.append(("gate G1-A: 'Turnstile Gate' in --allow with a constant-false condition", m, {medit, 'Turnstile Gate'}, {}, False))
    m = edited(); node(m, 'Normalize Inbound')['parameters']['jsCode'] += '\n// admit everything'
    dcases.append(("gate G1-B: 'Normalize Inbound' in --allow, rewritten", m, {medit, 'Normalize Inbound'}, {}, False))
    m = edited(); m['connections']['Turnstile Valid?']['main'][1] = [{'node': 'Validate Payload', 'type': 'main', 'index': 0}]
    dcases.append(("gate G1-C: a declared edge 'Turnstile Valid?|1|Validate Payload|0' (Reject Bot Request edge declared removed)",
                   m, {medit}, {'add_edges': {'Turnstile Valid?|1|Validate Payload|0'},
                                'remove_edges': {'Turnstile Valid?|1|Reject Bot Request|0'}}, False))
    m = edited(); m['connections']['Normalized OK?']['main'][0] = [{'node': 'Validate Payload', 'type': 'main', 'index': 0}]
    dcases.append(('gate G1-D: a declared re-wire around Turnstile Gate (Normalized OK? straight to Validate Payload)', m, {medit},
                   {'add_edges': {'Normalized OK?|0|Validate Payload|0'}, 'remove_edges': {'Normalized OK?|0|Turnstile Gate|0'}}, False))
    m = edited(); m['connections']['Reject Bot Request'] = {'main': [[{'node': 'Check Processed', 'type': 'main', 'index': 0}]]}
    dcases.append(("gate: a declared edge 'Reject Bot Request|0|Check Processed|0' (onward after the reject reply)", m, {medit},
                   {'add_edges': {'Reject Bot Request|0|Check Processed|0'}}, False))
    # an UNDECLARED change of a gate node's connections, beside the ruled delta: retarget · reorder surviving edges
    m = with_tag(edited(), 'Verify Turnstile', 'Turnstile Valid?')
    m['connections']['Verify Turnstile']['main'][0] = [{'node': 'Resume After Turnstile', 'type': 'main', 'index': 0}]
    dcases.append(("gate: Verify Turnstile output 0 retargeted, UNDECLARED, beside the ruled delta", m, {medit}, ruled, False))
    o2 = _copy.deepcopy(mexp)
    o2['nodes'].append({'name': 'Extra Reject', 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [2464, 4400], 'parameters': {}})
    o2['connections']['Verify Turnstile']['main'][1].append({'node': 'Extra Reject', 'type': 'main', 'index': 0})
    m = with_tag(_copy.deepcopy(o2), 'Verify Turnstile', 'Turnstile Valid?')
    m['connections']['Verify Turnstile']['main'][1] = [m['connections']['Verify Turnstile']['main'][1][i] for i in (1, 0, 2)]
    ocases = [("gate: a gate source touched by a ruled edge REORDERS its other edges, undeclared", o2, m, {medit}, ruled, False)]
    m = with_tag(_copy.deepcopy(o2), 'Verify Turnstile', 'Turnstile Valid?')
    ocases.append(('gate control: the same ruled edges appended, committed order kept, pass', o2, m, {medit}, ruled, True))
    m = _copy.deepcopy(oexp); node(m, 'Verify Owner Signature')['parameters']['jsCode'] = 'return [{json: {valid: true}}];'
    ocases.append(("gate OA: 'Verify Owner Signature' in --allow, made always-valid", oexp, m, {'Verify Owner Signature'}, {}, False))
    for g in ogate:
        ocases.append((f"gate OA: '{g}' in --allow, UNCHANGED", oexp, _copy.deepcopy(oexp), {g}, {}, False))
    # POSITION LOCK (M-c): Reject Bot Request moved below the added tag reverses their v1 order on both Turnstile outputs
    m = with_tag(edited(), 'Verify Turnstile', 'Turnstile Valid?'); node(m, 'Reject Bot Request')['position'] = [2464, 4400]
    dcases.append(('position: Reject Bot Request moved below the tag (no delta declares a move)', m, {medit}, ruled, False))
    m = edited(); node(m, medit)['position'] = [0, 0]
    dcases.append(('position: an --allow node moved', m, {medit}, {}, False))
    pexp = json.load(open(os.path.join(ROOT, 'n8n', 'workflow.purge.copy.sanitized.json')))
    ptrig = [n['name'] for n in pexp['nodes'] if str(n['type']).endswith('Trigger')][0]
    m = _copy.deepcopy(pexp); node(m, ptrig)['parameters']['rule'] = {'interval': [{'field': 'minutes'}]}
    pcase = ('edit: a schedule trigger smuggled into --allow and re-timed', m, {ptrig}, False)

    ok = True
    lo = _copy.deepcopy(mexp); node(lo, mother)['type'] = 'n8n-nodes-base.cron'      # an OLD trigger type, both sides
    lerrs = compare(lo, _copy.deepcopy(lo), {mother}, 'edit')
    ok &= any('GATE' in x for x in lerrs)
    print(f"{'✓' if lerrs else '✗'} gate: a legacy trigger type (cron) in --allow: {'RED — ' + lerrs[0] if lerrs else 'pass'}")
    perrs = compare(pexp, pcase[1], pcase[2], 'edit')
    ok &= bool(perrs)
    print(f"{'✓' if perrs else '✗'} {pcase[0]}: {'RED — ' + perrs[0] if perrs else 'pass'}")
    for label, e, allow, expect_pass in ecases:
        errs = compare(mexp, e, allow, 'edit', temp_trigger='Temporary Test Trigger', trigger=mtrig,
                       settings_allow={'executionOrder': {'covers': 'absent', 'ruling': 'selftest'}})
        good = (not errs) == expect_pass
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    for label, e, allow, delta, expect_pass in dcases:
        errs = compare(mexp, e, allow, 'edit', delta=delta)
        good = (not errs) == expect_pass and (expect_pass or not label.startswith('gate') or 'control' in label
                                              or any('GATE' in x for x in errs))
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    for label, o, e, delta in rcases:
        errs = compare(o, e, set(), 'edit', delta=delta)
        good = any('never removed' in x for x in errs)
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    for label, o, e, allow, delta, expect_pass in ocases:
        errs = compare(o, e, allow, 'edit', delta=delta)
        good = (not errs) == expect_pass and (expect_pass or any('GATE' in x for x in errs))
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    tag = with_tag(edited(), 'Verify Turnstile', 'Turnstile Valid?')
    before = sibling_order_lines(tag, ruled)
    node(tag, 'Reject Bot Request')['position'] = [2464, 4400]
    after = sibling_order_lines(tag, ruled)
    good = (len(before) == 2 and all('Reject Bot Request [2464, 4064] → Tag Turnstile Unavailable' in x for x in before)
            and len(after) == 2 and all('Tag Turnstile Unavailable [2464, 4256] → Reject Bot Request' in x for x in after))
    ok &= good
    print(f"{'✓' if good else '✗'} sibling order report: Reject Bot Request then the tag, reversed when it sits lower: {before[:1]}")
    # APPROVED DELTAS (ruling FIXED): exact identity, per item; an --allow-only edit carries none
    n_appr = 1
    for key in APPROVED_DELTAS:
        appr = {k: set(v) for k, v in APPROVED_DELTAS[key].items() if k != 'settings'}
        appr['settings'] = dict(APPROVED_DELTAS[key]['settings'])
        acases = [(f'approved {key}: exactly the approved delta', appr, True),
                  (f'approved {key}: no delta at all (an --allow edit)', {}, True),
                  (f'approved {key}: one extra edge (T HIGH-1, between non-gate nodes)',
                   dict(appr, add_edges=appr['add_edges'] | {'Tag Turnstile Unavailable|0|Check Processed|0'}), False),
                  (f'approved {key}: one approved removal missing', dict(appr, remove_edges=set(sorted(appr['remove_edges'])[1:])), False),
                  (f'approved {key}: an extra node removed', dict(appr, remove_nodes=appr['remove_nodes'] | {'Send Error Response'}), False),
                  (f'approved {key}: a setting added', dict(appr, settings=dict(appr['settings'], availableInMCP=True)), False)]
        acases += [(f"approved {key}: '{k}' with a value of another type", dict(appr, settings=dict(appr['settings'], **{k: 0})), False)
                   for k in appr['settings']]
        n_appr += len(acases)
        for label, d, expect in acases:
            errs = approved_errs(key, d)
            good = (not errs) == expect
            ok &= good
            print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0][:110]}")
    for key, d in (('purge', {'settings': {'executionOrder': 'v0'}}), ('main', {'settings': {'saveDataSuccessExecution': 'none'}})):
        errs = approved_errs(key, d)   # a delta carrying ONLY a setting is a delta, never "nothing"
        n_appr += 1
        ok &= bool(errs)
        print(f"{'✓' if errs else '✗'} approved {key}: a settings-only delta: {'RED — ' + errs[0][:100] if errs else 'pass'}")
    errs = approved_errs('purge', {'remove_nodes': {'Find Old Leads'}})
    ok &= bool(errs)
    print(f"{'✓' if errs else '✗'} approved: a delta for a copy with no approved delta (purge): {'RED — ' + errs[0] if errs else 'pass'}")
    dw = compare(orig, swapped(), set(data), 'swap', delta=add_d)
    ok &= bool(dw)
    print(f"{'✓' if dw else '✗'} delta: a declared delta outside the EDIT phase: {'RED — ' + dw[0] if dw else 'pass'}")
    for label, cp, phase, expect_pass, kw in cases:
        kw = dict(kw); allow = set(data) | ({kw.pop('allow_extra')} if 'allow_extra' in kw else set())
        o = dict(orig, settings=kw.pop('_orig_settings')) if '_orig_settings' in kw else orig
        errs = compare(o, cp, allow, phase, **kw)
        good = (not errs) == expect_pass
        ok &= good
        print(f"{'✓' if good else '✗'} {label}: {'pass' if not errs else 'RED — ' + errs[0]}")
    print('diff-workflow-copy selftest:', 'OK' if ok else 'FAILED',
          f'({len(cases)} cases built from {os.path.basename(src)}, {len(ecases) + 1} edit-phase and {len(dcases) + len(ocases) + len(rcases) + 3} '
          f'declared-delta cases from the Main, Owner Actions and Purge copy exports, {n_appr} approved-delta cases)')
    return 0 if ok else 1


def main():
    if sys.argv[1:2] == ['--selftest']:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument('original'); ap.add_argument('copy')
    ap.add_argument('--allow', nargs='+', action='extend', default=[])
    ap.add_argument('--phase', choices=['test', 'swap', 'edit'], default='swap')
    ap.add_argument('--temp-trigger'); ap.add_argument('--trigger')
    ap.add_argument('--delta-file')
    a = ap.parse_args()
    if a.delta_file and a.allow:
        ap.error('--delta-file and --allow are mutually exclusive')
    if a.delta_file:
        try:
            allow, delta = load_delta_file(a.delta_file)
        except ValueError as e:
            ap.error(str(e))
    elif not a.allow:
        ap.error('one of --allow or --delta-file is required')
    else:
        allow, delta = a.allow, {}
    cp = json.load(open(a.copy))
    errs = compare(json.load(open(a.original)), cp, set(allow), a.phase, a.temp_trigger, a.trigger, delta=delta)
    for line in sibling_order_lines(cp, delta) if a.phase == 'edit' else []:
        print('  ' + line)
    if errs:
        print('diff-workflow-copy: FAILED')
        for e in errs:
            print('  - ' + e)
        return 1
    what = 'allowed node(s) may' if a.phase == 'edit' else 'data-layer node(s)'
    print(f'diff-workflow-copy: OK — only the {len(allow)} {what} differ ({a.phase} phase)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
