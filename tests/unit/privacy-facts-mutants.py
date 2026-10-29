#!/usr/bin/env python3
"""Mutants of the public demo's privacy statements (2026-10-29). Each one makes the page, the notice or a number behind
them say something the engine does not do, and each must turn tests/unit/privacy-facts.test.cjs red.

The repository files are never touched: the files the test reads are copied into a temporary tree, ONE text replacement
is made there (it must apply exactly once, or the run fails), and the copied test runs against that tree.

Not in check-all: it re-runs the test once per mutant. Run before a change to the privacy page, the notice or the test.
Run: python3 tests/unit/privacy-facts-mutants.py        (exit 0 = every mutant killed)
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TREE = ['tests/unit/privacy-facts.test.cjs', 'web/site/lib', 'web/site/app/privacy', 'web/site/components/site',
        'n8n', 'db/ops/pg-backup.sh']
PAGE = 'web/site/app/privacy/page.tsx'
PRIVACY = 'web/site/lib/privacy.ts'
MUTANTS = {
    'the message-text retention changed on the site only': ('web/site/lib/retention.ts',
        'export const MESSAGE_TEXT_DAYS = 30;', 'export const MESSAGE_TEXT_DAYS = 14;'),
    'Telegram dropped from the services': (PRIVACY, "  { name: 'Telegram', use: \"alerts to the demo's owner\" },\n", ''),
    'the notice shown on every build': ('web/site/components/site/LiveChatPanel.tsx',
        '{config.demoMode === true && (', '{true && ('),
    'the page served on a non-demo build': (PAGE, 'if (!isDemo) notFound();', ''),
    'the lead retention written as a number of its own': (PRIVACY,
        'Number.isInteger(days) && (days as number) >= 1 ? (days as number) : null', '30'),
    'the backup retention changed on the site only': (PRIVACY, 'export const BACKUP_DAYS = 14;', 'export const BACKUP_DAYS = 7;'),
    'the leads safety limit misstated': (PAGE, 'more than a fifth of all callback requests', 'more than a third of all callback requests'),
    'the copies outside the database left out': (PAGE, '<h2>Copies outside the database</h2>', '<h2>Other notes</h2>'),
    'the notice promising erasure without its limits': ('web/site/components/site/LiveChatPanel.tsx',
        'owner alerts (Telegram) can keep copies longer', 'nothing is kept longer'),
}


def main():
    survived = 0
    with tempfile.TemporaryDirectory(prefix='privacy-mutants-') as tmp:
        for i, (label, (rel, old, new)) in enumerate(MUTANTS.items()):
            tree = os.path.join(tmp, f'm{i}')
            for t in TREE:
                src, dst = os.path.join(ROOT, t), os.path.join(tree, t)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, dst)
            path = os.path.join(tree, rel)
            text = open(path, encoding='utf-8').read()
            if text.count(old) != 1:
                print(f'✗ {label}: the anchor occurs {text.count(old)} times (want 1) — the mutant does not apply')
                survived += 1
                continue
            open(path, 'w', encoding='utf-8').write(text.replace(old, new))
            r = subprocess.run(['node', os.path.join(tree, 'tests/unit/privacy-facts.test.cjs')], capture_output=True,
                               text=True, timeout=120)
            killed = r.returncode != 0
            survived += not killed
            print(f"{'✓ killed' if killed else '✗ SURVIVED'}: {label}")
    print(f'privacy-facts mutants: {len(MUTANTS) - survived}/{len(MUTANTS)} killed')
    return 0 if survived == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
