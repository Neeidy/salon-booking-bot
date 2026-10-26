#!/usr/bin/env python3
"""Every export PREPARED in n8n/staged/ is sanitised exactly like the committed copy export it will replace (7-F1).

WHY: the staged files are committed to a public repo, but no sanitise assertion reads them — check-content-parity's
check_sanitised runs per paired export, and n8n/staged/ is paired with nothing. Only the value-shape secret scan and
the host-leak guard saw them (security-auditor LOW-3, 2026-10-25). An engine edit changes node logic, never what is
masked, so the staged file must carry the SAME placeholder set as its committed counterpart and pass the same
check_sanitised, and must not carry a top-level key the committed export does not (an `id`, `pinData`, `staticData`).

DELTA-AWARE (7-2 Tur 2 R1b): an edit may add or remove nodes, but only as DECLARED in the staged export's delta file
(`<name>.copy.delta.json` beside it — the same file `workflow-step.py put --delta-file` sends). The staged node set must
equal committed − remove_nodes + add_nodes, and check_sanitised's count must move by exactly that much. A staged export
without a delta file is refused. APPROVED (ruling FIXED, R1d): the delta file must be EXACTLY its copy's entry in
diff-workflow-copy.APPROVED_DELTAS (diff-workflow-copy.approved_errs) — the reviewed delta, the one workflow-step applies.
PROMOTED (7-2 R3): once a staged edit is live and committed as its copy export, the staged file is IDENTICAL to its
committed counterpart; that is reported as promoted (nothing pending) and the delta check is not applied to it — the
delta described the step from the old export, which no longer exists at HEAD. A staged file that differs in any byte of
its parsed content is checked as before.
Five negative controls run first on every invocation (an undeclared removal, an undeclared addition, a declared removal
of a node that is not there, a delta key the shared parser refuses, one edge more than the approved delta): each must
come out RED, or the test fails — a check that cannot go red has measured nothing.

Run: python3 tests/unit/staged-sanitised.test.py [staged_export.json …]   (default: every n8n/staged/*.sanitized.json)
"""
import contextlib
import glob
import importlib.util
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location('ccp', os.path.join(ROOT, 'scripts', 'check-content-parity.py'))
CCP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CCP)   # import-safe: check-content-parity keeps its live half under main()
_dspec = importlib.util.spec_from_file_location('dwc', os.path.join(ROOT, 'scripts', 'diff-workflow-copy.py'))
DIFF = importlib.util.module_from_spec(_dspec)
_dspec.loader.exec_module(DIFF)  # import-safe: the diff tool's CLI is under main(); its parser is the delta's authority


def sanitised(wf):
    """check_sanitised's verdict without its exit: (ok, node count or its message)."""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            return True, CCP.check_sanitised(wf)
    except SystemExit as e:
        return not e.code, ' '.join(out.getvalue().split())[:200]


def delta_path(staged_path):
    return staged_path[:-len('.sanitized.json')] + '.delta.json'


def copy_key(staged_path):
    """workflow.<key>.copy.sanitized.json → <key> (the APPROVED_DELTAS key, as db/copies/<key>.json names it)."""
    return os.path.basename(staged_path).split('.')[1]


def node_delta_errs(st, cm, delta, key):
    """The node set and the masked-node count against the declared delta, and the delta against the approved one."""
    errs = []
    try:
        parsed = DIFF.parse_delta(delta)[1]   # the one delta parser (put and the diff CLI use it): no hand-kept key list here
        errs += [f'not the approved delta: {e}' for e in DIFF.approved_errs(key, parsed)]
    except ValueError as e:
        errs.append(f'delta file refused by diff-workflow-copy.parse_delta: {e}')
    add, rem = set(delta.get('add_nodes') or ()), set(delta.get('remove_nodes') or ())
    names_s, names_c = {n['name'] for n in st['nodes']}, {n['name'] for n in cm['nodes']}
    if rem - names_c:
        errs.append(f'declared removal of node(s) the committed export does not have: {sorted(rem - names_c)}')
    if add & names_c:
        errs.append(f'declared addition of node(s) the committed export already has: {sorted(add & names_c)}')
    expected = (names_c - rem) | add
    if names_s - expected:
        errs.append(f'UNDECLARED node addition(s): {sorted(names_s - expected)}')
    if expected - names_s:
        errs.append(f'UNDECLARED node removal(s): {sorted(expected - names_s)}')
    return errs


def promoted(st, cm):
    """Is the staged export the committed export already (the edit promoted)? Parsed content, key order ignored."""
    return json.dumps(st, sort_keys=True) == json.dumps(cm, sort_keys=True)


def check(staged_path, st=None, delta=None):
    committed_path = os.path.join(ROOT, 'n8n', os.path.basename(staged_path))
    if not os.path.exists(committed_path):
        return [f'no committed counterpart {os.path.relpath(committed_path, ROOT)}']
    if st is None:
        st = json.load(open(staged_path, encoding='utf-8'))
    cm = json.load(open(committed_path, encoding='utf-8'))
    if promoted(st, cm):
        return []
    if delta is None:
        dp = delta_path(staged_path)
        if not os.path.exists(dp):
            return [f'no declared delta {os.path.relpath(dp, ROOT)} — an edit declares what it adds and removes']
        delta = json.load(open(dp, encoding='utf-8'))
    errs = node_delta_errs(st, cm, delta, copy_key(staged_path))
    ps, pc = CCP._committed_placeholders(st), CCP._committed_placeholders(cm)
    if ps != pc:
        errs.append(f'placeholder set differs: only staged {sorted(ps - pc)}, only committed {sorted(pc - ps)}')
    ok_s, n_s = sanitised(st)
    ok_c, n_c = sanitised(cm)
    if not ok_s:
        errs.append(f'check_sanitised fails on the staged export: {n_s}')
    elif ok_c:
        want = n_c - len(delta.get('remove_nodes') or ()) + len(delta.get('add_nodes') or ())
        if n_s != want:
            errs.append(f'check_sanitised counts {n_s} masked node(s) staged; committed {n_c} with the declared delta gives {want}')
    extra = sorted(set(st) - set(cm))
    if extra:
        errs.append(f'top-level key(s) the committed export does not carry: {extra}')
    return errs


if __name__ == '__main__':
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'n8n', 'staged', '*.sanitized.json')))
    if not paths:
        print('staged-sanitised: 0 staged exports under n8n/staged/ — nothing prepared, nothing to check')
        sys.exit(0)
    # Negative controls first: each must be RED, or this test cannot see the defect it exists for.
    ctl_path = paths[0]
    ctl_st = json.load(open(ctl_path, encoding='utf-8'))
    ctl_delta = json.load(open(delta_path(ctl_path), encoding='utf-8')) if os.path.exists(delta_path(ctl_path)) else {}
    keep = sorted({n['name'] for n in ctl_st['nodes']} - set(ctl_delta.get('add_nodes') or ()))
    dropped = dict(ctl_st, nodes=[n for n in ctl_st['nodes'] if n['name'] != keep[0]])
    extra = dict(ctl_st, nodes=ctl_st['nodes'] + [{'name': 'Undeclared Control Node', 'type': 'n8n-nodes-base.noOp', 'parameters': {}}])
    ghost = dict(ctl_delta, remove_nodes=sorted(set(ctl_delta.get('remove_nodes') or ()) | {'No Such Node'}))
    controls = [('undeclared removal', dropped, ctl_delta, 'UNDECLARED node removal'),
                ('undeclared addition', extra, ctl_delta, 'UNDECLARED node addition'),
                ('declared removal of an absent node', ctl_st, ghost, 'does not have'),
                ('a delta key the shared parser does not know', ctl_st, dict(ctl_delta, bogus_key=[]), 'parse_delta'),
                ('one edge more than the approved delta', ctl_st,
                 dict(ctl_delta, add_edges=sorted(set(ctl_delta.get('add_edges') or ()) | {'Approved Control|0|Check Processed|0'})),
                 'not the approved delta')]
    for label, cst, cdelta, want in controls:
        errs = check(ctl_path, st=cst, delta=cdelta)
        if not any(want in e for e in errs):
            print(f'✗ negative control "{label}" stayed GREEN ({errs}) — the delta check is blind')
            sys.exit(1)
    print(f'✓ {len(controls)} negative controls red as expected (on {os.path.relpath(ctl_path, ROOT)})')
    bad = 0
    for p in paths:
        errs = check(p)
        name = os.path.relpath(p, ROOT)
        cm_path = os.path.join(ROOT, 'n8n', os.path.basename(p))
        note = ' (promoted: identical to the committed export, nothing pending)' if not errs and os.path.exists(cm_path) and \
            promoted(json.load(open(p, encoding='utf-8')), json.load(open(cm_path, encoding='utf-8'))) else ''
        print(('✓ ' if not errs else '✗ ') + name + note + ('' if not errs else ' — ' + '; '.join(errs)))
        bad += bool(errs)
    print(f'staged-sanitised: {"FAILED" if bad else "OK"} ({len(paths)} staged export(s))')
    sys.exit(1 if bad else 0)
