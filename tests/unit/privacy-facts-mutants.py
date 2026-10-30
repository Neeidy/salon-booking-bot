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
    # R2a: the residue of HIGH-1's class, and the two measured copies outside the database
    'the safety limit described as a one-night pause': (PAGE,
        'The limit\n              is checked again every night, so it can keep stopping the job, night after night, until enough new requests\n              arrive or the owner deletes the old ones by hand — and with',
        'And with'),
    'the run-record retention left as an unmeasured setting': (PAGE, 'for about {RUN_RECORD_DAYS} days', 'for a while'),
    'the run-record constant stripped of its measurement': (PRIVACY, 'Measured by behaviour (R2 measurement 4', 'Assumed (R2'),
    # R2h: the controller and the contact come from build-time env only
    'an invented privacy contact': (PRIVACY, 'envValue(process.env.NEXT_PUBLIC_PRIVACY_CONTACT)', "'privacy@example.com'"),
    'an invented controller': (PRIVACY, 'envValue(process.env.NEXT_PUBLIC_PRIVACY_CONTROLLER)', "'Test Controller'"),
    'a default value behind an unset env': ('web/site/lib/privacyEnv.ts', "return t === '' ? null : t;",
        "return t === '' ? 'privacy@example.com' : t;"),
    'the controller never shown on the page': (PAGE, ': `${PRIVACY_CONTROLLER} is responsible for this demo', ': `Someone is responsible for this demo'),
    'an address typed into the page': (PAGE, 'Write to ${PRIVACY_CONTACT} to ask', 'Write to privacy@example.com to ask'),
    # R2h: the GDPR basics and the measured retention of the two kept records
    'the legal basis left out': (PAGE, 'legitimate interest (GDPR Art. 6(1)(f))', 'our interest'),
    'the complaint right left out': (PAGE, 'You also have the right to lodge a complaint with a data-protection\n          supervisory authority.', ''),
    'the conversation record said to be deleted automatically': (PAGE, 'not deleted automatically; it is deleted on request.</li>',
        'deleted with the messages.</li>'),
    'the kept last reply left unsaid': (PAGE, "the assistant&apos;s last reply and ", ''),
    'Purge deleting conversations while the page says kept': ('n8n/workflow.purge.sanitized.json',
        'DELETE FROM salon.leads', 'DELETE FROM salon.conversations WHERE false; DELETE FROM salon.leads'),
    # R2h, security-auditor L1: the forms the first version of the test could not see
    'Reminders truncating the bookings': ('n8n/workflow.reminders.sanitized.json',
        'UPDATE salon.appointments SET reminder_sent', 'TRUNCATE salon.appointments; UPDATE salon.appointments SET reminder_sent'),
    'Main deleting conversations under quoted names': ('n8n/workflow.main.sanitized.json',
        'UPDATE salon.conversations SET last_alert_class',
        'DELETE FROM \\"salon\\".\\"conversations\\" WHERE false; UPDATE salon.conversations SET last_alert_class'),
    'Owner Actions emptying the last reply': ('n8n/workflow.owner-actions.sanitized.json',
        "SET stage = 'new', last_intent = ''", "SET stage = 'new', last_intent = '', computed_reply = NULL"),
    'the copies of a record deleted on request left unsaid': (PAGE, 'remain until they expire as described', 'are removed too'),
    'Main deleting bookings across a line break': ('n8n/workflow.main.sanitized.json',
        'UPDATE salon.conversations SET last_alert_class',
        'DELETE FROM\\nsalon.appointments WHERE false; UPDATE salon.conversations SET last_alert_class'),
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
