#!/usr/bin/env python3
# Drift-guard for Refactor #4 — the cancel-validation rules are DUPLICATED across nodes (n8n Code nodes
# can't share a helper), so a single source of truth is enforced by this check instead. If any copy drifts
# (a regex bound weakened, a rule dropped), the guard FAILs. Static; reads the committed sanitized only.
#
# Concepts guarded:
#   1. gid shape regex  ^[0-9a-v]{5,1024}$  — MUST be identical everywhere; 5x
#      (Event ID Valid?, Cancel Lookup ask structOk, Validate Cancel Target, Reschedule Lookup — CP4,
#      Validate Reschedule Target — CP4 sub-step 3a).
#   2. confirm_turn canonical regex  ^[1-9][0-9]*$  — 3x (Confirm Fresh?, Verify Confirm Live,
#      Reschedule Fresh? — CP4 sub-step 2).
#   3. cancel-target structural rule parity — Cancel Lookup (ask structOk), Validate Cancel Target,
#      Reschedule Lookup (CP4), AND Validate Reschedule Target (CP4 sub-step 3a) must ALL validate
#      {finite start_utc, gid shape, calendar_id present}.
#   4. confirm-TTL byte-identity — Confirm Fresh? and Reschedule Fresh? share ONE TTL expression
#      (clarification 1: reschedule reuses the cancel-confirm TTL verbatim); the two IF leftValues MUST match.
#   5. *_confirming ↔ stageContext branch — EVERY *_confirming stage keyed on in an IF/Switch routing
#      condition MUST have a matching branch in Build LLM Request's stageContext ternary. Without it a "yes"
#      on that stage cannot be classified as confirm → it silently falls to handoff. (This is not
#      speculative: reschedule_confirming was routed but had no stageContext branch, so a reschedule "yes"
#      handed off — the exact failure this guard now forbids. 2026-08-18.)
#
# Prove-it: break a copy and the guard FAILs (a guard never seen to FAIL is an assumed guard — learned at #5).
# Exit 0 = parity OK, 1 = drift. Run at every close gate / pre-push (with the #5 coverage guard).
import json, sys, re, collections, os

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
GID_NODES = ['Event ID Valid?', 'Cancel Lookup', 'Validate Cancel Target', 'Reschedule Lookup', 'Validate Reschedule Target']
gid_forms = collections.Counter()
gid_seen = []
for name, t in ALL.items():
    for lo, hi in re.findall(r'\[0-9a-v\]\{(\d+),(\d+)\}', t):
        gid_forms[(lo, hi)] += 1
        gid_seen.append(name)
if set(gid_forms) != {('5', '1024')}:
    fails.append(f"gid shape regex DRIFT — expected only [0-9a-v]{{5,1024}}, found forms {dict(gid_forms)} in {sorted(set(gid_seen))}")
elif gid_forms[('5', '1024')] != 5:
    fails.append(f"gid shape regex count {gid_forms[('5', '1024')]} != 5 — expected in {GID_NODES}, found in {sorted(set(gid_seen))}")

# 2) confirm_turn canonical regex ^[1-9][0-9]*$ — exactly the three confirm-freshness gates
CT_NODES = ['Confirm Fresh?', 'Verify Confirm Live', 'Reschedule Fresh?']
ct_seen = sorted(name for name, t in ALL.items() if re.search(r'\[1-9\]\[0-9\]\*', t))
if ct_seen != sorted(CT_NODES):
    fails.append(f"confirm_turn canonical regex ^[1-9][0-9]*$ nodes {ct_seen} != {sorted(CT_NODES)} (a weakened/moved confirm-turn check?)")

# 3) cancel-target structural rule parity — both validators check finite start + gid + calendar_id
for name in ['Cancel Lookup', 'Validate Cancel Target', 'Reschedule Lookup', 'Validate Reschedule Target']:
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


def if_leftvalue(name):
    """First IF condition's leftValue expression, or None if the node/condition is absent."""
    n = by.get(name)
    if not n:
        return None
    for c in (n.get('parameters', {}).get('conditions', {}) or {}).get('conditions', []) or []:
        return c.get('leftValue', '')
    return None


# 4) confirm-TTL byte-identity — Confirm Fresh? and Reschedule Fresh? must share ONE TTL expression
cf_ttl = if_leftvalue('Confirm Fresh?')
rf_ttl = if_leftvalue('Reschedule Fresh?')
if cf_ttl is None or rf_ttl is None:
    fails.append(f"confirm-TTL nodes missing (Confirm Fresh?={cf_ttl is not None}, Reschedule Fresh?={rf_ttl is not None})")
elif cf_ttl != rf_ttl:
    fails.append("confirm-TTL DRIFT — Confirm Fresh? and Reschedule Fresh? leftValue not byte-identical "
                 "(reschedule must reuse the cancel-confirm TTL verbatim)")

# 5) *_confirming ↔ stageContext — every *_confirming stage keyed in an IF/Switch routing condition
#    must have a matching branch in Build LLM Request's stageContext ternary.
routed = set()
for n in w['nodes']:
    if n['type'] not in ('n8n-nodes-base.if', 'n8n-nodes-base.switch'):
        continue
    p = n.get('parameters', {})
    blobs = []
    conds = p.get('conditions')
    if isinstance(conds, dict):
        blobs += [str(c.get('rightValue', '')) for c in (conds.get('conditions', []) or [])]
    rules = p.get('rules')
    if isinstance(rules, dict):
        for r in rules.get('values', []) or []:
            blobs += [str(c.get('rightValue', '')) for c in ((r.get('conditions', {}) or {}).get('conditions', []) or [])]
    for b in blobs:
        routed.update(re.findall(r'\b(\w+_confirming)\b', b))
blr = by.get('Build LLM Request', {}).get('parameters', {}).get('jsCode', '')
ctx = set(re.findall(r"st\.stage\s*===\s*'(\w+_confirming)'", blr))
missing_ctx = routed - ctx
if missing_ctx:
    fails.append(f"routed *_confirming stage(s) {sorted(missing_ctx)} have NO Build LLM Request stageContext "
                 f"branch — a 'yes' there cannot classify as confirm and silently hands off (routed={sorted(routed)}, "
                 f"stageContext={sorted(ctx)})")

# 6) two-Load-Config shared-key parity (CP5) — the reminders workflow carries a THIRD inline config copy
#    (config-lives-in-two-places → now three). The keys SHARED by both Load Configs (business.timezone,
#    bot.killSwitch) MUST be identical, or the two workflows silently diverge: content-parity can't catch it
#    (each workflow is compared only to its OWN committed file, never to the other one). We hit this drift
#    class once (repo <-> Load-Config node). Kill-switch especially must be one truth — a bot halted on the
#    inbound side but still firing reminders is exactly the split this forbids.
REM_PATH = os.environ.get('REMINDERS_SANITIZED', 'n8n/workflow.reminders.sanitized.json')


def load_config_shared(jscode):
    tz = re.search(r'timezone:\s*"([^"]+)"', jscode)
    ks = re.search(r'killSwitch:\s*(true|false)', jscode)
    return (tz.group(1) if tz else None, ks.group(1) if ks else None)


def owner_alert_shared(jscode):
    """ownerAlert.{enabled,throttleMinutes} — the keys EVERY workflow that can alert must agree on."""
    en = re.search(r'ownerAlert:\s*\{[^}]*enabled:\s*(true|false)', jscode)
    th = re.search(r'ownerAlert:\s*\{[^}]*throttleMinutes:\s*(\d+)', jscode)
    return (en.group(1) if en else None, th.group(1) if th else None)


main_lc = (by.get('Load Config', {}).get('parameters', {}) or {}).get('jsCode', '')
try:
    rem_by = {n['name']: n for n in json.load(open(REM_PATH, encoding='utf-8'))['nodes']}
    rem_lc = (rem_by.get('Load Config (Reminders)', {}).get('parameters', {}) or {}).get('jsCode', '')
except FileNotFoundError:
    rem_lc = None
if not main_lc or not rem_lc:
    fails.append(f"two-Load-Config check: missing 'Load Config' in {PATH} (found={bool(main_lc)}) or "
                 f"'Load Config (Reminders)' in {REM_PATH} (found={bool(rem_lc)})")
else:
    if load_config_shared(main_lc) != load_config_shared(rem_lc):
        fails.append(f"two-Load-Config SHARED-KEY DRIFT — main{load_config_shared(main_lc)} != "
                     f"reminders{load_config_shared(rem_lc)} (timezone, killSwitch) MUST match")

# 6b) THREE-way ownerAlert parity (FIX-1) — the purge workflow gained its own `Load Config (Purge)` when it
#     got an owner-alert branch, so there are now THREE inline config copies that can alert. `ownerAlert`
#     MUST be one truth across all three: if `enabled:false` silences the main + reminders alerts but NOT
#     purge, the kill is not a kill — a switch that does not stop everything cannot be trusted. Content-parity
#     cannot catch this (each workflow is compared only to its OWN committed file, never to the others).
PURGE_PATH = os.environ.get('PURGE_SANITIZED', 'n8n/workflow.purge.sanitized.json')
try:
    purge_by = {n['name']: n for n in json.load(open(PURGE_PATH, encoding='utf-8'))['nodes']}
    purge_lc = (purge_by.get('Load Config (Purge)', {}).get('parameters', {}) or {}).get('jsCode', '')
except FileNotFoundError:
    purge_lc = None
if not purge_lc:
    fails.append(f"ownerAlert three-way check: missing 'Load Config (Purge)' in {PURGE_PATH} — the purge "
                 f"workflow alerts, so it must carry the shared ownerAlert config")
elif main_lc and rem_lc:
    oa = {'main': owner_alert_shared(main_lc), 'reminders': owner_alert_shared(rem_lc),
          'purge': owner_alert_shared(purge_lc)}
    if None in oa['main'] or None in oa['reminders'] or None in oa['purge']:
        fails.append(f"ownerAlert three-way check: could not read ownerAlert.{{enabled,throttleMinutes}} "
                     f"from all three Load Configs ({oa})")
    elif len(set(oa.values())) != 1:
        fails.append(f"ownerAlert THREE-WAY DRIFT — {oa} — enabled/throttleMinutes MUST match across "
                     f"main, reminders and purge (a kill-switch that silences only some alerts is broken)")

if fails:
    print('DRIFT — cancel-validation single-source violated:')
    for f in fails:
        print('  -', f)
    sys.exit(1)

print('cancel-validation parity OK — gid regex 5x identical [0-9a-v]{5,1024} (incl. Reschedule Lookup + '
      'Validate Reschedule Target); '
      'confirm_turn regex 3x ^[1-9][0-9]*$ (Confirm Fresh?, Verify Confirm Live, Reschedule Fresh?); '
      'Cancel Lookup + Validate Cancel Target + Reschedule Lookup all check {finite start_utc, gid shape, '
      'calendar_id present}; Confirm Fresh?==Reschedule Fresh? TTL byte-identical; '
      f'routed *_confirming {sorted(routed)} all have a Build LLM Request stageContext branch; '
      'two Load Configs share identical business.timezone + bot.killSwitch; '
      'three Load Configs share identical ownerAlert.enabled + throttleMinutes')
sys.exit(0)
