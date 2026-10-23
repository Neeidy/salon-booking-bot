#!/usr/bin/env python3
"""check-pair-roles — each original/copy pair has exactly ONE active workflow, and it is the one ROLES declares live.

The ROLES array in scripts/check-exports-parity.sh is the declaration (MIGRATION-PLAN §3t, decision 9); the rules live
in scripts/pair_roles.py and are tested offline in tests/unit/pair-roles.test.py. This script only reads each
workflow's `active` flag from the n8n API and hands the flags to those rules. It prints shortened ids and roles only.
Exit: 0 all pairs hold their declared roles · 1 a pair is wrong · 2 NOT MEASURED (no credentials, never a pass).
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pair_roles  # noqa: E402

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'


def main():
    api, key = os.environ.get('N8N_API_URL'), os.environ.get('N8N_API_KEY')
    if not (api and key):
        print('check-pair-roles: NOT MEASURED — N8N_API_URL / N8N_API_KEY not set.')
        return 2
    cf = ({'CF-Access-Client-Id': os.environ['CF_ACCESS_CLIENT_ID'], 'CF-Access-Client-Secret': os.environ['CF_ACCESS_CLIENT_SECRET']}
          if os.environ.get('CF_ACCESS_CLIENT_ID') and os.environ.get('CF_ACCESS_CLIENT_SECRET') else {})
    try:
        _, roles = pair_roles.load()
    except ValueError as e:
        print(f'check-pair-roles: FAIL — the ROLES declaration cannot be read: {e}')
        return 1
    active = {}
    for wid in [r[k] for r in roles for k in ('orig', 'copy')]:
        req = urllib.request.Request(f'{api.rstrip("/")}/api/v1/workflows/{wid}',
                                     headers={'X-N8N-API-KEY': key, 'accept': 'application/json', 'User-Agent': UA, **cf})
        active[wid] = json.load(urllib.request.urlopen(req, timeout=30)).get('active')
    errs = pair_roles.judge(roles, active)
    for r in roles:
        held = 'original' if active[r['orig']] and not active[r['copy']] else 'copy' if active[r['copy']] and not active[r['orig']] else '?'
        print(f"  {'✓' if held == r['live'] else '✗'} pair {r['orig'][:4]}…/{r['copy'][:4]}…  declared live: {r['live']:8}  active: {held}")
    for e in errs:
        print('  ✗ ' + e)
    if errs:
        print('check-pair-roles: FAIL')
        return 1
    print(f'check-pair-roles: OK — {len(roles)} pairs, exactly one active in each, each the declared one.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
