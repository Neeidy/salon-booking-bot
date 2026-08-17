#!/usr/bin/env python3
# Drift-guard for Refactor #5 — INVARIANT: every reply-producing builder writes `computed_reply`.
#
# WHY: Build Reply Payload now reads the per-turn reply from the `computed_reply` column (the single
# source), with its old per-intent node lists demoted to a fallback. That makes the column the thing
# that must never drift: if a state-builder feeds a Save State but forgets to set `computed_reply`, the
# reader gets an empty reply (→ reply_fallback). The old bug class (F1: a builder's message silently
# dropped because it wasn't in a hand-list) is replaced by ONE machine-checkable rule enforced here.
# CP4 adds ~5 new builders (reschedule) — this guard catches any that forget the field.
#
# CHECK: for each Save State node, walk backwards to the nearest Code-node ancestors (through IF/Switch
# passthroughs) — those are the "builders" whose output is persisted+replied. Every such Code node's
# jsCode must contain `computed_reply`. Missing one = FAIL. Static (reads the committed sanitized only).
# Exit 0 = OK, 1 = a builder is missing computed_reply. Run at every close gate / pre-push.
import json, sys, collections

PATH = sys.argv[1] if len(sys.argv) > 1 else 'n8n/workflow.sanitized.json'
SAVE_NODES = ('Save State', 'Save State (Post-Write)')

w = json.load(open(PATH, encoding='utf-8'))
by_name = {n['name']: n for n in w['nodes']}

# reverse adjacency: target -> [source names]
rev = collections.defaultdict(list)
for src, d in (w.get('connections') or {}).items():
    for outs in d.get('main', []) or []:
        for c in (outs or []):
            rev[c['node']].append(src)

def is_code(node):
    return node and node['type'].endswith('.code')

# nearest Code-node ancestors of a target (stop at each Code node; recurse through non-Code)
def code_feeders(target, seen=None):
    seen = seen or set()
    feeders = set()
    for src in rev.get(target, []):
        if src in seen:
            continue
        seen.add(src)
        node = by_name.get(src)
        if is_code(node):
            feeders.add(src)
        else:
            feeders |= code_feeders(src, seen)  # walk through IF/Switch/gate
    return feeders

builders = set()
for sv in SAVE_NODES:
    if sv in by_name:
        builders |= code_feeders(sv)

missing = []
for b in sorted(builders):
    js = by_name[b].get('parameters', {}).get('jsCode', '')
    if 'computed_reply' not in js:
        missing.append(b)

if missing:
    print('DRIFT — these reply-producing builders feed a Save State but do NOT set computed_reply:')
    for m in missing:
        print('  -', m)
    print('Fix: set computed_reply in each (the thin reader would otherwise emit an empty reply).')
    sys.exit(1)

print(f'computed_reply coverage OK — all {len(builders)} reply-producing builders set computed_reply')
sys.exit(0)
