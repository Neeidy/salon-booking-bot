#!/usr/bin/env python3
"""Mutants of the Purge's leads branch (Codex CRT #15 F2, public demo 2026-10-29: the suite stayed green with the
deletion verifier disabled). Each one breaks ONE property, and each must turn tests/unit/leads-purge-read-error.test.cjs
red, run against both the committed and the staged Purge export.

Each mutant is a single text replacement in one node's jsCode (it must apply exactly once, or the run fails), written
into a copy of the export in a temporary directory and handed to the test as its argument.

Not in check-all: it re-runs the test once per mutant and export. Run before a change to the leads branch or its test.
Run: python3 tests/unit/leads-purge-mutants.py        (exit 0 = every mutant killed)
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPORTS = [os.path.join(ROOT, 'n8n', 'workflow.purge.sanitized.json'),
           os.path.join(ROOT, 'n8n', 'staged', 'workflow.purge.sanitized.json')]
TEST = os.path.join(ROOT, 'tests', 'unit', 'leads-purge-read-error.test.cjs')
MUTANTS = {   # (node, old, new)
    'the deletion verifier disabled':
        ('Verify Leads Purge', "if (before - after !== deleted) {", "if (false) {"),
    'the verifier counting a failed delete as done':
        ('Verify Leads Purge', ".filter(i => i.json && !i.json.error).length", ".length + 1"),
    'the candidate cap ignored':
        ('Leads Purge Sane?', "const within = rows.length > 0 && rows.length <= cap;", "const within = rows.length > 0;"),
}


def main():
    survived = total = 0
    if not os.path.exists(EXPORTS[0]):
        print('✗ the committed Purge export is missing — nothing to measure')
        return 2
    for e in EXPORTS[1:]:
        if not os.path.exists(e):
            print(f'· skipped (absent, e.g. after the promotion): {os.path.relpath(e, ROOT)}')
    with tempfile.TemporaryDirectory(prefix='leads-purge-mutants-') as tmp:
        for export in [e for e in EXPORTS if os.path.exists(e)]:
            wf = json.load(open(export, encoding='utf-8'))
            byname = {n['name']: n for n in wf['nodes']}
            tag = os.path.relpath(export, ROOT)
            if subprocess.run(['node', TEST, export], capture_output=True, timeout=120).returncode != 0:
                print(f'✗ {tag}: the unmutated export does not pass the test — nothing to measure against')
                return 1
            for i, (label, (name, old, new)) in enumerate(MUTANTS.items()):
                total += 1
                code = byname[name]['parameters']['jsCode']
                if code.count(old) != 1:
                    print(f'✗ {tag} · {label}: the anchor occurs {code.count(old)} times (want 1)')
                    survived += 1
                    continue
                byname[name]['parameters']['jsCode'] = code.replace(old, new)
                path = os.path.join(tmp, f'{len(tag)}-{i}.json')
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(wf, f)
                byname[name]['parameters']['jsCode'] = code
                killed = subprocess.run(['node', TEST, path], capture_output=True, timeout=120).returncode != 0
                survived += not killed
                print(f"{'✓ killed' if killed else '✗ SURVIVED'}: {tag} · {label}")
    print(f'leads-purge mutants: {total - survived}/{total} killed')
    return 0 if survived == 0 and total > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
