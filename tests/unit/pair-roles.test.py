#!/usr/bin/env python3
"""scripts/pair_roles.py — the rules behind the declared role inversion (MIGRATION-PLAN §3t, decision 9). Offline:
the declaration is read from temporary copies of check-exports-parity.sh, and the active flags are handed in.

Run: python3 tests/unit/pair-roles.test.py   (PAIR_ROLES=<path> runs it against another copy of the module)
"""
import importlib.util, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('pair_roles', os.environ.get('PAIR_ROLES', os.path.join(ROOT, 'scripts', 'pair_roles.py')))
pr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pr)

ok = True
def check(label, cond):
    global ok
    ok = ok and bool(cond)
    print(f"{'✓' if cond else '✗'} {label}")

# ── the real declaration reads, and says `original` for all five today ──
pairs, roles = pr.load()
check('the committed ROLES reads: 5 pairs, every one declared original', len(roles) == 5 and {r['live'] for r in roles} == {'original'})
check('every ROLES id has a PAIRS line, originals on plain exports, copies on .copy exports',
      all(not pairs[r['orig']].endswith('.copy.sanitized.json') and pairs[r['copy']].endswith('.copy.sanitized.json') for r in roles))

# ── judge: every combination of the two flags, under both declarations ──
R = [{'orig': 'O1', 'copy': 'C1', 'live': 'original'}]
Rc = [{'orig': 'O1', 'copy': 'C1', 'live': 'copy'}]
for live_side, roles_, want in (('original', R, {(True, False): 0, (False, True): 1, (True, True): 1, (False, False): 1}),
                                ('copy', Rc, {(True, False): 1, (False, True): 0, (True, True): 1, (False, False): 1})):
    for (o, c), n in want.items():
        errs = pr.judge(roles_, {'O1': o, 'C1': c})
        check(f'judge, declared {live_side}: original {"on" if o else "off"} / copy {"on" if c else "off"} → {"green" if n == 0 else "red"}', len(errs) == n)
check('judge: a flag that was not read is red, not green', pr.judge(R, {'O1': True}) != [])
check('judge names BOTH active / BOTH inactive / an undeclared swap distinctly',
      'BOTH active' in pr.judge(R, {'O1': True, 'C1': True})[0] and 'BOTH inactive' in pr.judge(R, {'O1': False, 'C1': False})[0]
      and 'undeclared swap' in pr.judge(R, {'O1': False, 'C1': True})[0])

# ── may_be_inactive ──
check('declared original: the copy may be parked, the original may not', pr.may_be_inactive('C1', R)[0] and not pr.may_be_inactive('O1', R)[0])
check('declared copy: the original may be parked, the copy may not', pr.may_be_inactive('O1', Rc)[0] and not pr.may_be_inactive('C1', Rc)[0])
check('a workflow ROLES does not name may not be inactive', not pr.may_be_inactive('Zz', R)[0])

# ── holder: the ONE active workflow on the production path ──
def wf(wid, active, path):
    return {'id': wid, 'active': active, 'nodes': [{'type': 'n8n-nodes-base.webhook', 'parameters': {'path': path}}]}
P = {'O1': 'n8n/workflow.sanitized.json', 'C1': 'n8n/workflow.main.copy.sanitized.json'}
def outcome(fn):   # the value, or the exception's class name: a crash is reported as a failed check, not raised
    try:
        return fn()
    except Exception as e:
        return type(e).__name__
check('holder: the active original on barber-inbound', outcome(lambda: pr.holder([wf('O1', True, 'barber-inbound'), wf('C1', False, 'owner-mig-main')], 'barber-inbound', P)) == ('O1', P['O1']))
check('holder: after the swap, the active copy and ITS export', outcome(lambda: pr.holder([wf('O1', False, 'barber-inbound'), wf('C1', True, 'barber-inbound')], 'barber-inbound', P)) == ('C1', P['C1']))
for label, wfs, p in (('no holder', [wf('O1', False, 'barber-inbound')], P),
                      ('two holders', [wf('O1', True, 'barber-inbound'), wf('C1', True, 'barber-inbound')], P),
                      ('a holder with no PAIRS line', [wf('X9', True, 'barber-inbound')], P)):
    check(f'holder: {label} is refused (ValueError)', outcome(lambda: pr.holder(wfs, 'barber-inbound', p)) == 'ValueError')

# ── load: every malformed or inconsistent declaration is refused ──
src = open(os.path.join(ROOT, 'scripts', 'check-exports-parity.sh'), encoding='utf-8').read()
first = next(l for l in src[src.index('ROLES=('):].splitlines()[1:] if l.strip().startswith('"'))
o, c, _ = first.strip().split('#')[0].strip().strip('"').split(':')
for label, line in (('a malformed line', '  "nonsense"'),
                    ('an unknown role', f'  "{o}:{c}:both"'),
                    ('an id with no PAIRS line', f'  "Zzzzzzzzzzzzzzzz:{c}:original"'),
                    ('a pair the wrong way round', f'  "{c}:{o}:original"'),
                    ('an id named twice', first + '\n' + first)):
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as t:
        t.write(src.replace(first, line, 1)); path = t.name
    try:
        check(f'load: {label} is refused (ValueError)', outcome(lambda: pr.load(path)) == 'ValueError')
    finally:
        os.unlink(path)
with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as t:
    t.write(src.replace(first, first.replace(':original"', ':copy"'), 1)); path = t.name
try:
    check('load: a flipped line reads as declared copy', [r['live'] for r in pr.load(path)[1]][0] == 'copy')
finally:
    os.unlink(path)

print('pair-roles:', 'OK' if ok else 'FAILED')
sys.exit(0 if ok else 1)
