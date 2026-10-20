#!/usr/bin/env python3
"""check-content-parity.py's inactive-workflow rule (MIGRATION-PLAN §3r, ruling 2026-10-20): ONLY a migration
copy paired with a `.copy.sanitized.json` export in check-exports-parity.sh may be inactive; an inactive
original is RED (exit 1); an active workflow whose published graph cannot be seen stays "could not measure"
(exit 2). Runs the guard's own function on fake live responses: no network, no credentials.

Run: python3 tests/unit/content-parity-inactive.test.py   (GUARD=<path> runs it against another copy of the guard)
"""
import contextlib, importlib.util, io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD = os.environ.get('GUARD', os.path.join(ROOT, 'scripts', 'check-content-parity.py'))
argv, sys.argv = sys.argv, ['x', os.path.join(ROOT, 'n8n', 'workflow.drill-state.sanitized.json')]
spec = importlib.util.spec_from_file_location('ccp', GUARD); m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass
sys.argv = argv

src = open(os.path.join(ROOT, 'scripts', 'check-exports-parity.sh'), encoding='utf-8').read()
pairs = [l.strip().strip('"').split('"')[0].split(':') for l in src[src.index('PAIRS=('):].split('\n)')[0].splitlines()[1:]
         if l.strip().startswith('"')]
copy = next(p for p in pairs if p[1].endswith('.copy.sanitized.json'))
orig = next(p for p in pairs if not p[1].endswith('.copy.sanitized.json'))


def run(wf, committed, live):
    m.WF, m.COMMITTED = wf, os.path.join(ROOT, committed)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            m.check_published_matches_draft(live)
        return 'pass'
    except SystemExit as e:
        return f'exit {e.code}'


CASES = [
    ('an inactive paired copy', copy, {'active': False, 'nodes': []}, 'pass'),
    ('an inactive original', orig, {'active': False, 'nodes': []}, 'exit 1'),
    ('an inactive original that still shows a published graph', orig, {'active': False, 'nodes': [], 'activeVersion': {'nodes': []}}, 'exit 1'),
    ('an active workflow with no visible published graph', orig, {'active': True, 'nodes': []}, 'exit 2'),
    ('a copy-named export with an unpaired id', ('Zzzzzzzzzzzzzzzz', copy[1]), {'active': False, 'nodes': []}, 'exit 1'),
    ("a copy's id on a non-copy export", (copy[0], orig[1]), {'active': False, 'nodes': []}, 'exit 1'),
]
ok = True
for label, (wf, committed), live, want in CASES:
    got = run(wf, committed, live)
    ok = ok and got == want
    print(f"{'✓' if got == want else '✗'} {label}: expected {want}, got {got}")
print('content-parity inactive rule:', 'OK' if ok else 'FAILED', f'({len(CASES)} cases)')
sys.exit(0 if ok else 1)
