#!/usr/bin/env python3
"""settings_parity: the rules check-content-parity, the diff tool and the deploy helper share
(MIGRATION-PLAN §3r, settings-parity, O1). Six mutants must be red; the positive controls must be green.
Run: python3 tests/unit/settings-parity.test.py"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('settings_parity', os.path.join(ROOT, 'scripts', 'settings_parity.py'))
SP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SP)

MAIN = {'availableInMCP': True, 'binaryMode': 'separate', 'callerPolicy': 'workflowsFromSameOwner',
        'executionOrder': 'v1', 'timeSavedMode': 'fixed'}
ALLOW = {'binaryMode': {'covers': 'absent', 'ruling': 'test ruling'},
         'availableInMCP': {'covers': 'absent', 'ruling': 'test ruling'}}
without = lambda d, *ks: {k: v for k, v in d.items() if k not in ks}

cases = [
    # (label, errors, expect_red)
    ('control: committed equals live', SP.committed_vs_live(dict(MAIN), dict(MAIN)), False),
    ('control: copy lacks only allowlisted keys', SP.copy_vs_original(MAIN, without(MAIN, 'binaryMode', 'availableInMCP'), ALLOW), False),
    ('control: copy equals original, no allowlist', SP.copy_vs_original(MAIN, dict(MAIN), {}), False),
    ('mutant 1: a key removed from the committed export', SP.committed_vs_live(without(MAIN, 'binaryMode'), MAIN), True),
    ('mutant 2: a value changed in the committed export', SP.committed_vs_live(dict(MAIN, callerPolicy='any'), MAIN), True),
    ('mutant 3: the copy carries binaryMode "combined" (the allowlist covers absent only)',
     SP.copy_vs_original(MAIN, dict(MAIN, binaryMode='combined'), ALLOW), True),
    ('mutant 4: an allowlist entry without a ruling',
     SP.copy_vs_original(MAIN, without(MAIN, 'binaryMode'), {'binaryMode': {'covers': 'absent'}}), True),
    ('mutant 5: a new key appears live (redactionPolicy)', SP.committed_vs_live(MAIN, dict(MAIN, redactionPolicy='none')), True),
    # The copy LACKS the key here, so only the "covers absent only" rule can turn this red (an earlier version gave
    # the copy a different value, which the value check caught instead: the rule itself was never measured).
    ('mutant 6: an availableInMCP allowlist entry that is not "absent"',
     SP.copy_vs_original(MAIN, without(MAIN, 'availableInMCP'), {'availableInMCP': {'covers': 'false', 'ruling': 'test ruling'}}), True),
    ('extra: a key in the committed export that is not live', SP.committed_vs_live(dict(MAIN, stale='x'), MAIN), True),
    ('extra: live settings that are not an object', SP.committed_vs_live({}, ['not', 'a', 'dict']), True),
    ('extra: a key missing on the copy and not allowlisted (executionOrder)',
     SP.copy_vs_original(MAIN, without(MAIN, 'executionOrder'), ALLOW), True),
    ('extra: a key on the copy that the original lacks', SP.copy_vs_original(without(MAIN, 'timeSavedMode'), MAIN, {}), True),
]
ok = True
for label, errs, expect_red in cases:
    good = bool(errs) == expect_red
    ok &= good
    print(f"{'✓' if good else '✗'} {label}: {'RED — ' + errs[0] if errs else 'green'}")
print(f"settings-parity test: {'OK' if ok else 'FAILED'} ({len(cases)} cases)")
sys.exit(0 if ok else 1)
