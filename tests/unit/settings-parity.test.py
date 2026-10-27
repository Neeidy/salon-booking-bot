#!/usr/bin/env python3
"""settings_parity: the rule check-content-parity, workflow-step and the deploy helper share — a live workflow's
settings against its committed export (MIGRATION-PLAN §3r, settings-parity, O1; reshaped at D6c, 2026-10-27, when the
copy↔original pairing ended). Every mutant must be red for ITS reason; the controls must be green.
Run: python3 tests/unit/settings-parity.test.py"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('settings_parity', os.environ.get('SP_SRC', os.path.join(ROOT, 'scripts', 'settings_parity.py')))
SP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SP)

MAIN = {'availableInMCP': False, 'callerPolicy': 'workflowsFromSameOwner', 'executionOrder': 'v1', 'timeSavedMode': 'fixed'}
BIN = {'binaryMode': {'covers': 'value', 'value': 'separate', 'ruling': 'test ruling'}}
with_ = lambda d, **kv: dict(d, **kv)
without = lambda d, *ks: {k: v for k, v in d.items() if k not in ks}


def safe(f):   # a traceback is a failed case with its type shown, never a crash of the suite
    try:
        return f()
    except Exception as e:
        return [f'crashed: {type(e).__name__}']


cases = [
    # (label, errors, expect_red[, a phrase one error must contain: a red for the WRONG reason is a failure])
    ('control: committed equals live', SP.committed_vs_live(dict(MAIN), dict(MAIN)), False),
    ('control: the allowlisted key live with exactly its value, absent from the export',
     SP.committed_vs_live(MAIN, with_(MAIN, binaryMode='separate'), BIN), False),
    ('control: the allowlisted key absent on both sides', SP.committed_vs_live(MAIN, dict(MAIN), BIN), False),
    ('mutant 1: a key removed from the committed export', SP.committed_vs_live(without(MAIN, 'callerPolicy'), MAIN), True,
     "'callerPolicy' is live but not"),
    ('mutant 2: a value changed in the committed export', SP.committed_vs_live(with_(MAIN, callerPolicy='any'), MAIN), True,
     "'callerPolicy' differs"),
    ('mutant 3: a key in the export that is not live', SP.committed_vs_live(with_(MAIN, stale='x'), MAIN), True,
     "'stale' is in the committed export"),
    ('mutant 4: a new key appears live, nobody allowlisted it', SP.committed_vs_live(MAIN, with_(MAIN, redactionPolicy='none')), True,
     "'redactionPolicy' is live but not"),
    ('mutant 5: binaryMode live WITHOUT the allowlist', SP.committed_vs_live(MAIN, with_(MAIN, binaryMode='separate')), True,
     "'binaryMode' is live but not"),
    ('mutant 6: the allowlisted key live with another value ("combined")',
     SP.committed_vs_live(MAIN, with_(MAIN, binaryMode='combined'), BIN), True, "allowlisted live only as exactly 'separate'"),
    ('mutant 7: type-strict — 1 is not True', SP.committed_vs_live({}, {'flag': 1}, {'flag': {'covers': 'value', 'value': True, 'ruling': 'r'}}),
     True, 'allowlisted live only as exactly True'),
    ('mutant 8: the export carries the allowlisted key too',
     SP.committed_vs_live(with_(MAIN, binaryMode='separate'), with_(MAIN, binaryMode='separate'), BIN), True,
     'the allowance and the export cannot both hold the key'),
    ('mutant 9: an entry that is not "value" (the old "absent" kind)',
     SP.committed_vs_live(MAIN, dict(MAIN), {'binaryMode': {'covers': 'absent', 'ruling': 'r'}}), True, 'must cover "value"'),
    ('mutant 10: an entry without a ruling',
     SP.committed_vs_live(MAIN, with_(MAIN, binaryMode='separate'), {'binaryMode': {'covers': 'value', 'value': 'separate'}}), True,
     'names no ruling'),
    ('mutant 11: an entry without a value', SP.committed_vs_live(MAIN, dict(MAIN), {'k': {'covers': 'value', 'ruling': 'r'}}), True,
     'names no single scalar value'),
    ('mutant 12: an entry whose value is a list (a range in disguise)',
     SP.committed_vs_live(MAIN, dict(MAIN), {'k': {'covers': 'value', 'value': ['separate', 'combined'], 'ruling': 'r'}}), True,
     'names no single scalar value'),
    ('mutant 13: the allowlist is not an object', SP.check_allowlist(['binaryMode']), True, 'must be an object'),
    ('mutant 13b: committed_vs_live with an allowlist that is not an object: red, no traceback',
     safe(lambda: SP.committed_vs_live(MAIN, dict(MAIN), ['binaryMode'])), True, 'must be an object'),
    ('extra: live settings that are not an object', SP.committed_vs_live({}, ['not', 'a', 'dict']), True, 'not an object'),
]
ok = True
for label, errs, expect_red, *why in cases:
    good = bool(errs) == expect_red and (not why or any(why[0] in e for e in errs))
    ok &= good
    shown = next((e for e in errs if why and why[0] in e), errs[0]) if errs else None
    print(f"{'✓' if good else '✗'} {label}: {'RED — ' + shown if errs else 'green'}")
print(f"settings-parity test: {'OK' if ok else 'FAILED'} ({len(cases)} cases)")
sys.exit(0 if ok else 1)
