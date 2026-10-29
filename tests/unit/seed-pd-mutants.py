#!/usr/bin/env python3
"""Mutants of the public demo's seed actions in scripts/seed-workflow.py (pd-lead-insert, pd-conv-insert, clean-pd,
2026-10-29). Each one breaks ONE property those actions must hold, and each must turn tests/unit/seed-workflow.test.py
red — a mutant that survives means the test does not measure that property.

Each mutant is a single text replacement in a copy of the script (it must apply exactly once, or the run fails); the
test runs against the copy through its SEED_WORKFLOW variable.

EQUIVALENT, not listed: making payload() copy a given name into the pd lead. It cannot be reached — payload() refuses
an option outside ALLOWED before it builds the row, so a name never arrives there; the two mutants of ALLOWED below
are what measure that layer.

Not in check-all: it re-runs the whole test once per mutant. Run before a change to the pd actions or their test is pushed.
Run: python3 tests/unit/seed-pd-mutants.py        (exit 0 = every mutant killed)
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, 'scripts', 'seed-workflow.py')
TEST = os.path.join(ROOT, 'tests', 'unit', 'seed-workflow.test.py')
MUTANTS = {
    "clean-pd's conversation guard widened to every widget session":
        ("\"WITH c AS (DELETE FROM salon.conversations WHERE sender_key LIKE 'widget:w-pd-%' RETURNING 1), \"",
         "\"WITH c AS (DELETE FROM salon.conversations WHERE sender_key LIKE 'widget:w-%' RETURNING 1), \""),
    "clean-pd's lead guard widened to every lead":
        ("\"l AS (DELETE FROM salon.leads WHERE message LIKE 'pd-%' RETURNING 1) \"",
         "\"l AS (DELETE FROM salon.leads WHERE message LIKE '%' RETURNING 1) \""),
    "pd-lead-insert's guard loosened to 'p%'":
        ("created_at FROM r, ok WHERE ok.all_ok AND message LIKE 'pd-%' AND created_at IS NOT NULL ",
         "created_at FROM r, ok WHERE ok.all_ok AND message LIKE 'p%' AND created_at IS NOT NULL "),
    "pd-lead-insert's SQL insert letting a phone through":
        ("\"AND name IS NULL AND phone IS NULL RETURNING 1) \"", "\"AND name IS NULL RETURNING 1) \""),
    "pd-lead-insert's SQL check letting a name through":
        ("AND q.created_at IS NOT NULL AND q.name IS NULL AND q.phone IS NULL, false)", "AND q.created_at IS NOT NULL AND q.phone IS NULL, false)"),
    'pd-lead-insert accepting --name':
        ("    'pd-lead-insert': {'message', 'created_at', 'source'},",
         "    'pd-lead-insert': {'message', 'created_at', 'source', 'name'},"),
    'pd-lead-insert accepting --phone':
        ("    'pd-lead-insert': {'message', 'created_at', 'source'},",
         "    'pd-lead-insert': {'message', 'created_at', 'source', 'phone'},"),
    'the pd session pattern loosened to any widget session':
        ("PD_SESSION_RE = re.compile(r'^w-pd-[a-z0-9][a-z0-9-]{0,60}$')",
         "PD_SESSION_RE = re.compile(r'^w-[a-z0-9][a-z0-9-]{0,60}$')"),
    "pd-conv-insert's stage taken from the input":
        ("\"SELECT p.j ->> 'sender_key', 'handoff', (p.j ->> 'turn_count')::int, 'handoff', now(), now() FROM p \"",
         "\"SELECT p.j ->> 'sender_key', p.j ->> 'stage', (p.j ->> 'turn_count')::int, 'handoff', now(), now() FROM p \""),
    "pd-conv-insert's guard removed from its WHERE":
        ("\"WHERE (p.j ->> 'sender_key') LIKE 'widget:w-pd-%' RETURNING 1) \"", "\"WHERE true RETURNING 1) \""),
}


def main():
    src = open(SCRIPT, encoding='utf-8').read()
    survived = 0
    with tempfile.TemporaryDirectory(prefix='seed-pd-mutants-') as tmp:
        for i, (label, (old, new)) in enumerate(MUTANTS.items()):
            if src.count(old) != 1:
                print(f'✗ {label}: the anchor occurs {src.count(old)} times (want 1) — the mutant does not apply')
                survived += 1
                continue
            path = os.path.join(tmp, f'm{i}.py')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(src.replace(old, new))
            r = subprocess.run([sys.executable, TEST], env=dict(os.environ, SEED_WORKFLOW=path), capture_output=True,
                               text=True, timeout=300, stdin=subprocess.DEVNULL)
            killed = r.returncode != 0
            survived += not killed
            print(f"{'✓ killed' if killed else '✗ SURVIVED'}: {label}")
    print(f'seed pd mutants: {len(MUTANTS) - survived}/{len(MUTANTS)} killed')
    return 0 if survived == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
