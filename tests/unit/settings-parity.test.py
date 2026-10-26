#!/usr/bin/env python3
"""settings_parity: the rules check-content-parity, the diff tool and the deploy helper share
(MIGRATION-PLAN §3r, settings-parity, O1; D4-1). Eight mutants must be red; the positive controls must be green.
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
CARRY = {'saveDataSuccessExecution': {'covers': 'value', 'value': 'none', 'ruling': 'test ruling'}}
without = lambda d, *ks: {k: v for k, v in d.items() if k not in ks}

cases = [
    # (label, errors, expect_red[, a phrase one error must contain: a red for the WRONG reason is a failure])
    ('control: committed equals live', SP.committed_vs_live(dict(MAIN), dict(MAIN)), False),
    ('control: copy lacks only allowlisted keys', SP.copy_vs_original(MAIN, without(MAIN, 'binaryMode', 'availableInMCP'), ALLOW), False),
    ('control: copy equals original, no allowlist', SP.copy_vs_original(MAIN, dict(MAIN), {}), False),
    ('mutant 1: a key removed from the committed export', SP.committed_vs_live(without(MAIN, 'binaryMode'), MAIN), True, "'binaryMode' is live but not"),
    ('mutant 2: a value changed in the committed export', SP.committed_vs_live(dict(MAIN, callerPolicy='any'), MAIN), True, "'callerPolicy' differs"),
    ('mutant 3: the copy carries binaryMode "combined" (the allowlist covers absent only)',
     SP.copy_vs_original(MAIN, dict(without(MAIN, 'availableInMCP'), binaryMode='combined'), ALLOW), True,
     "'binaryMode' is allowlisted as absent but present"),
    ('mutant 4: an allowlist entry without a ruling',
     SP.copy_vs_original(MAIN, without(MAIN, 'binaryMode'), {'binaryMode': {'covers': 'absent'}}), True, 'names no ruling'),
    ('mutant 5: a new key appears live (redactionPolicy)', SP.committed_vs_live(MAIN, dict(MAIN, redactionPolicy='none')), True, "'redactionPolicy'"),
    # The copy LACKS the key here, so only the "covers absent only" rule can turn this red (an earlier version gave
    # the copy a different value, which the value check caught instead: the rule itself was never measured).
    ('mutant 6: an availableInMCP allowlist entry that is not "absent"',
     SP.copy_vs_original(MAIN, without(MAIN, 'availableInMCP'), {'availableInMCP': {'covers': 'false', 'ruling': 'test ruling'}}), True,
     'must cover "absent" or "value"'),
    # D4-1 (2026-10-23): the allowlist names what a copy LACKS. An EQUAL value used to pass, so a Main copy created
    # with `availableInMCP: true` was exactly as exposed as Main while the guard stayed green.
    ('mutant 7: the copy carries availableInMCP true, equal to the original (allowlisted as absent)',
     SP.copy_vs_original(MAIN, without(MAIN, 'binaryMode'), ALLOW), True, "'availableInMCP' is allowlisted as absent but present"),
    ('mutant 8: the copy carries binaryMode "separate", equal to the original (allowlisted as absent)',
     SP.copy_vs_original(MAIN, without(MAIN, 'availableInMCP'), ALLOW), True, "'binaryMode' is allowlisted as absent but present"),
    ('extra: a key in the committed export that is not live', SP.committed_vs_live(dict(MAIN, stale='x'), MAIN), True, "'stale' is in the committed export"),
    ('extra: live settings that are not an object', SP.committed_vs_live({}, ['not', 'a', 'dict']), True, 'not an object'),
    ('extra: a key missing on the copy and not allowlisted (executionOrder)',
     SP.copy_vs_original(MAIN, without(MAIN, 'executionOrder', 'binaryMode', 'availableInMCP'), ALLOW), True,
     "'executionOrder' is missing on the copy"),
    ('extra: a key on the copy that the original lacks', SP.copy_vs_original(without(MAIN, 'timeSavedMode'), MAIN, {}), True, "'timeSavedMode' is on the copy"),
    # T-4 (2026-10-26): a "value" entry — the copy must carry EXACTLY one value its original may lack (narrower copy).
    ('control: a value entry and the copy carries exactly it',
     SP.copy_vs_original(MAIN, dict(MAIN, saveDataSuccessExecution='none'), CARRY), False),
    ('value 1: the copy lacks the carried key', SP.copy_vs_original(MAIN, dict(MAIN), CARRY), True, "must carry exactly 'none'"),
    ('value 2: the copy carries another value', SP.copy_vs_original(MAIN, dict(MAIN, saveDataSuccessExecution='all'), CARRY), True,
     "must carry exactly 'none'"),
    ('value 3: type-strict — 1 is not True', SP.copy_vs_original({}, {'flag': 1}, {'flag': {'covers': 'value', 'value': True, 'ruling': 'r'}}),
     True, 'must carry exactly True'),
    ('value 4: a value entry without a value', SP.copy_vs_original(MAIN, dict(MAIN), {'k': {'covers': 'value', 'ruling': 'r'}}), True,
     'names no single scalar value'),
    ('value 5: a value entry whose value is a list (a range in disguise)',
     SP.copy_vs_original(MAIN, dict(MAIN), {'k': {'covers': 'value', 'value': ['none', 'all'], 'ruling': 'r'}}), True,
     'names no single scalar value'),
    ('value 6: a value entry without a ruling',
     SP.copy_vs_original(MAIN, dict(MAIN, saveDataSuccessExecution='none'), {'saveDataSuccessExecution': {'covers': 'value', 'value': 'none'}}),
     True, 'names no ruling'),
    ('value 7: absent_keys / carried split the kinds',
     [] if (SP.absent_keys(dict(ALLOW, **CARRY)) == set(ALLOW) and SP.carried(dict(ALLOW, **CARRY)) == {'saveDataSuccessExecution': 'none'})
     else ['split wrong'], False),
]
ok = True
for label, errs, expect_red, *why in cases:
    good = bool(errs) == expect_red and (not why or any(why[0] in e for e in errs))
    ok &= good
    shown = next((e for e in errs if why and why[0] in e), errs[0]) if errs else None
    print(f"{'✓' if good else '✗'} {label}: {'RED — ' + shown if errs else 'green'}")
print(f"settings-parity test: {'OK' if ok else 'FAILED'} ({len(cases)} cases)")
sys.exit(0 if ok else 1)
