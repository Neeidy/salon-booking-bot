#!/usr/bin/env python3
# Drift-guard for Refactor #4 — the cancel-validation rules are DUPLICATED across nodes (n8n Code nodes
# can't share a helper), so a single source of truth is enforced by this check instead. If any copy drifts
# (a regex bound weakened, a rule dropped), the guard FAILs. Static; reads the committed sanitized only.
#
# Concepts guarded:
#   1. gid shape regex  ^[0-9a-v]{5,1024}$  — MUST be identical everywhere; 4x
#      (Event ID Valid?, Cancel Lookup ask structOk, Validate Cancel Target, Reschedule Lookup — CP4).
#   2. confirm_turn canonical regex  ^[1-9][0-9]*$  — 2x (Confirm Fresh?, Verify Confirm Live).
#      (CP4 sub-step 2 adds Reschedule Fresh? as a 3rd — bump to 3 then.)
#   3. cancel-target structural rule parity — Cancel Lookup (ask structOk), Validate Cancel Target, AND
#      Reschedule Lookup (CP4) must ALL validate {finite start_utc, gid shape, calendar_id present}.
#
# Prove-it: break a copy and the guard FAILs (a guard never seen to FAIL is an assumed guard — learned at #5).
# Exit 0 = parity OK, 1 = drift. Run at every close gate / pre-push (with the #5 coverage guard).
import json, sys, re, collections

PATH = sys.argv[1] if len(sys.argv) > 1 else 'n8n/workflow.sanitized.json'
w = json.load(open(PATH, encoding='utf-8'))
by = {n['name']: n for n in w['nodes']}


def text(name):
    """All code + IF/Switch condition text for a node (validation lives in both)."""
    n = by.get(name)
    if not n:
        return ''
    p = n.get('parameters', {})
    t = p.get('jsCode', '') or ''
    conds = p.get('conditions')
    if isinstance(conds, dict):
        for c in conds.get('conditions', []) or []:
            t += ' ' + str(c.get('leftValue', '')) + ' ' + str(c.get('rightValue', ''))
    rules = p.get('rules')
    if isinstance(rules, dict):
        for r in rules.get('values', []) or []:
            for c in (r.get('conditions', {}) or {}).get('conditions', []) or []:
                t += ' ' + str(c.get('leftValue', '')) + ' ' + str(c.get('rightValue', ''))
    return t


ALL = {n['name']: text(n['name']) for n in w['nodes']}
fails = []

# 1) gid shape regex — every [0-9a-v]{lo,hi} must be exactly {5,1024}; exactly 3 occurrences
GID_NODES = ['Event ID Valid?', 'Cancel Lookup', 'Validate Cancel Target', 'Reschedule Lookup']
gid_forms = collections.Counter()
gid_seen = []
for name, t in ALL.items():
    for lo, hi in re.findall(r'\[0-9a-v\]\{(\d+),(\d+)\}', t):
        gid_forms[(lo, hi)] += 1
        gid_seen.append(name)
if set(gid_forms) != {('5', '1024')}:
    fails.append(f"gid shape regex DRIFT — expected only [0-9a-v]{{5,1024}}, found forms {dict(gid_forms)} in {sorted(set(gid_seen))}")
elif gid_forms[('5', '1024')] != 4:
    fails.append(f"gid shape regex count {gid_forms[('5', '1024')]} != 4 — expected in {GID_NODES}, found in {sorted(set(gid_seen))}")

# 2) confirm_turn canonical regex ^[1-9][0-9]*$ — exactly the two confirm gates
CT_NODES = ['Confirm Fresh?', 'Verify Confirm Live']
ct_seen = sorted(name for name, t in ALL.items() if re.search(r'\[1-9\]\[0-9\]\*', t))
if ct_seen != sorted(CT_NODES):
    fails.append(f"confirm_turn canonical regex ^[1-9][0-9]*$ nodes {ct_seen} != {sorted(CT_NODES)} (a weakened/moved confirm-turn check?)")

# 3) cancel-target structural rule parity — both validators check finite start + gid + calendar_id
for name in ['Cancel Lookup', 'Validate Cancel Target', 'Reschedule Lookup']:
    t = text(name)
    missing = []
    if 'Number.isFinite' not in t:
        missing.append('finite start_utc (Number.isFinite)')
    if '[0-9a-v]{5,1024}' not in t:
        missing.append('gid shape [0-9a-v]{5,1024}')
    if not re.search(r'cal\.length\s*>\s*0', t):
        missing.append('calendar_id present (cal.length > 0)')
    if missing:
        fails.append(f"cancel-target rule DRIFT in '{name}': missing {missing}")

if fails:
    print('DRIFT — cancel-validation single-source violated:')
    for f in fails:
        print('  -', f)
    sys.exit(1)

print('cancel-validation parity OK — gid regex 4x identical [0-9a-v]{5,1024} (incl. Reschedule Lookup); '
      'confirm_turn regex 2x ^[1-9][0-9]*$; Cancel Lookup + Validate Cancel Target + Reschedule Lookup all '
      'check {finite start_utc, gid shape, calendar_id present}')
sys.exit(0)
