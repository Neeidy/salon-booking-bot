#!/usr/bin/env python3
"""Mutants of scripts/render-client.py (Phase 8, CRT #14). Each one breaks ONE property the render must hold, and each
must turn tests/unit/render-client.test.py red — a mutant that survives means the test does not measure that property.

The first eight are R1's; the four marked (review) are the ones code-reviewer showed SURVIVING the first version of
the test (example-b shares many values with the demo, so a slot fed from the demo still "held B's value"); the last five
cover the list-element, empty-string, empty-day, write re-check and FIFO checks added in the same round.

Not in check-all: it re-runs the whole test once per mutant. Run before a change to the render or its test is pushed.
Run: python3 tests/unit/render-client-mutants.py        (exit 0 = every mutant killed)
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, 'scripts', 'render-client.py')
TEST = os.path.join(ROOT, 'tests', 'unit', 'render-client.test.py')
MUTANTS = {
    'the Reminders literal not rendered':
        ("        if key in LITERALS:\n", "        if key in LITERALS and key != 'reminders':\n"),
    'the tenth slot not rendered':
        ("                code = code.replace(anchor, make(first))\n", "                pass\n"),
    'the anchor count not checked':
        ("                if code.count(anchor) != want:\n", "                if False:\n"),
    'the repository check removed':
        ("    return real == root or real.startswith(root + os.sep)\n", "    return False\n"),
    'the secrets-file mode not checked':
        ("        if st.st_mode & 0o077:\n", "        if False:\n"),
    'only the first chat id filled':
        ("        for n in tg:\n            n['parameters']['chatId']", "        for n in tg[:1]:\n            n['parameters']['chatId']"),
    'a missing key defaulted to the demo value':
        ("        if not isinstance(cfg, dict) or k not in cfg:\n            raise Refused(f'the config lacks {p}')\n        got = cfg[k]",
         "        got = cfg.get(k) if isinstance(cfg, dict) else None\n        if got is None:\n            out[k] = want\n            continue"),
    'the literal written with JSON-style quoted keys':
        ("        items = [f\"{k if BARE.fullmatch(k) else _scalar(k)}:", "        items = [f\"{_scalar(k)}:"),
    '(review) the calendar id and Zernio account taken from the demo literal':
        ("    body = project(js_literal(literal), cfg, '')\n",
         "    body = project(js_literal(literal), cfg, '')\n    demo = js_literal(literal)\n"
         "    if 'googleCalendarId' in body: body['googleCalendarId'] = demo['googleCalendarId']\n"
         "    if 'channels' in body and 'whatsapp' in body['channels'] and 'accountId' in demo['channels']['whatsapp']:\n"
         "        body['channels']['whatsapp']['accountId'] = demo['channels']['whatsapp']['accountId']\n"),
    '(review) the Purge literal re-written from the demo, not the client':
        ("    body = project(js_literal(literal), cfg, '')\n",
         "    body = js_literal(literal) if where.startswith('purge') else project(js_literal(literal), cfg, '')\n"),
    '(review) the bot / ownerAlert policy kept at the demo values':
        ("    body = project(js_literal(literal), cfg, '')\n",
         "    body = project(js_literal(literal), cfg, '')\n    demo = js_literal(literal)\n"
         "    for k in ('bot', 'ownerAlert', 'leadsRetentionDays'):\n        if k in body: body[k] = demo[k]\n"),
    '(review) the repository check on abspath, not realpath':
        ("    if _inside_repo(os.path.realpath(out)):\n", "    if _inside_repo(os.path.abspath(out)):\n"),
    'list elements not checked against the committed element':
        ("    if isinstance(want, list) and want:\n", "    if False:\n"),
    'an empty string accepted where the demo has text':
        ("    if isinstance(want, str) and want and not got:\n", "    if False:\n"),
    'an empty demo list left unchecked (no sibling shape)':
        ("            if isinstance(want, list) and not want:", "            if False:"),
    'the re-check after mkdir removed':
        ("        if _inside_repo(real) or (here.st_dev, here.st_ino) != (there.st_dev, there.st_ino):\n", "        if False:\n"),
    'the secrets file opened blocking (a FIFO hangs it)':
        ("os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK", "os.O_RDONLY | os.O_NOFOLLOW"),
}


def main():
    src = open(SCRIPT, encoding='utf-8').read()
    leftover = os.path.join(ROOT, 'n8n', 'render-test-must-not-exist')
    survived = []
    with tempfile.TemporaryDirectory(prefix='render-mutants-') as tmp:
        path = os.path.join(tmp, 'mutant-render.py')
        for name, (a, b) in MUTANTS.items():
            if src.count(a) != 1:
                print(f'✗ {name}: its anchor occurs {src.count(a)}× in the script (the mutant is stale; fix it)')
                survived.append(name)
                continue
            open(path, 'w', encoding='utf-8').write(src.replace(a, b))
            r = subprocess.run([sys.executable, TEST], env=dict(os.environ, RENDER_CLIENT=path), capture_output=True,
                               text=True, timeout=900)
            red = [l for l in r.stdout.splitlines() if l.startswith('✗')]
            killed = r.returncode != 0 and bool(red)
            print(f"{'✓' if killed else '✗'} {name}: {'killed by ' + red[0][2:90] + (f' (+{len(red) - 1} more)' if len(red) > 1 else '') if killed else 'SURVIVED'}")
            if not killed:
                survived.append(name)
            if os.path.lexists(leftover):    # the test removes what a broken render writes there; if not, stop here
                print(f'✗ {name} left {os.path.relpath(leftover, ROOT)} inside the repository — stopped (remove it by hand)')
                return 1
    print(f'render-client mutants: {len(MUTANTS) - len(survived)}/{len(MUTANTS)} killed', '' if not survived else '— FAILED')
    return 0 if not survived else 1


if __name__ == '__main__':
    sys.exit(main())
