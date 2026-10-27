#!/usr/bin/env python3
"""check-active-set — the active workflows on the instance are exactly the ones listed in WORKFLOWS (D6c, 2026-10-27).

scripts/check-exports-parity.sh's WORKFLOWS is the declaration; the rules live in scripts/workflows.py (judge_active) and
are tested offline in tests/unit/workflows.test.py. This script only reads n8n's workflow list (id, active) and hands it
to those rules. It replaced check-pair-roles.py when the copy↔original pairing ended. Prints shortened ids only.
Exit: 0 the active set is exactly the listed workflows · 1 it is not · 2 NOT MEASURED (no credentials, or the listing
did not read completely — never a pass).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workflows  # noqa: E402

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'


def main():
    api, key = os.environ.get('N8N_API_URL'), os.environ.get('N8N_API_KEY')
    if not (api and key):
        print('check-active-set: NOT MEASURED — N8N_API_URL / N8N_API_KEY not set.')
        return 2
    cf = ({'CF-Access-Client-Id': os.environ['CF_ACCESS_CLIENT_ID'], 'CF-Access-Client-Secret': os.environ['CF_ACCESS_CLIENT_SECRET']}
          if os.environ.get('CF_ACCESS_CLIENT_ID') and os.environ.get('CF_ACCESS_CLIENT_SECRET') else {})
    try:
        listed = workflows.load()
    except ValueError as e:
        print(f'check-active-set: FAIL — the WORKFLOWS declaration cannot be read: {e}')
        return 1
    instance, cursor = [], None
    for _ in range(20):
        url = f'{api.rstrip("/")}/api/v1/workflows?limit=250' + (f'&cursor={urllib.parse.quote(cursor, safe="")}' if cursor else '')
        req = urllib.request.Request(url, headers={'X-N8N-API-KEY': key, 'accept': 'application/json', 'User-Agent': UA, **cf})
        try:
            page = json.load(urllib.request.urlopen(req, timeout=30))
        except (urllib.error.URLError, OSError, ValueError) as e:   # HTTPError is a URLError: a refused or broken read
            print(f'check-active-set: NOT MEASURED — the workflow listing did not read ({type(e).__name__}).')
            return 2
        instance += [{'id': w.get('id'), 'active': w.get('active')} for w in page.get('data') or []]
        cursor = page.get('nextCursor')
        if not cursor:
            break
    else:
        print('check-active-set: NOT MEASURED — the workflow listing did not end within 20 pages.')
        return 2
    errs = workflows.judge_active(listed, instance)
    for wid in listed:
        a = next((w['active'] for w in instance if w['id'] == wid), None)
        print(f"  {'✓' if a is True else '✗'} {wid[:4]}…  listed · active: {a}")
    for e in errs:
        print('  ✗ ' + e)
    if errs:
        print('check-active-set: FAIL')
        return 1
    others = sum(1 for w in instance if w['id'] not in listed)
    print(f'check-active-set: OK — {len(listed)} listed workflows, all active; {others} unlisted, none active.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
