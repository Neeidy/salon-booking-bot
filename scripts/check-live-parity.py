#!/usr/bin/env python3
# Live <-> committed structural parity for the n8n workflow.
#
# WHY: n8n/workflow.sanitized.json is now hand-maintained (surgical, sanitized-preserving
# edits — a raw full export is unreliable here: the compiled ajv validator in "Validate Intent"
# bloats/mangles). A hand-built artifact can silently drift from the live workflow. Codex (L3)
# audits the COMMITTED file, so drift means we audit something that is not the running system.
# This gate compares STRUCTURE only — node count, the set of node names, and the connection
# topology (source -> target, per output index). It never touches the heavy Code-node bodies,
# so the ajv bloat is irrelevant.
#
# USAGE:
#   N8N_API_URL="https://<n8n-host>" N8N_API_KEY="<key>" python3 scripts/check-live-parity.py [workflow_id]
#   workflow_id defaults to $N8N_WORKFLOW_ID or the main workflow id below.
# Host + key come from env only — nothing sensitive is hardcoded (this is a public template).
# Exit 0 = parity OK, 1 = DRIFT (or error). Run at every refactor step's close gate.
import os, sys, json, urllib.request

MAIN_ID = 'SL142I47mK6SAz6p'
WF  = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('N8N_WORKFLOW_ID', MAIN_ID)
API = os.environ.get('N8N_API_URL')
KEY = os.environ.get('N8N_API_KEY')
COMMITTED = os.environ.get('SANITIZED_PATH', 'n8n/workflow.sanitized.json')


def summarize(nodes, conns):
    names = sorted(n['name'] for n in nodes)
    pairs = set()
    for src, d in (conns or {}).items():
        for out_idx, outs in enumerate(d.get('main', []) or []):
            for c in (outs or []):
                pairs.add((src, out_idx, c['node'], c.get('index', 0)))
    return len(nodes), names, pairs


def main():
    if not (API and KEY):
        sys.exit('ERROR: set N8N_API_URL and N8N_API_KEY (n8n public API) to fetch the live workflow')

    cw = json.load(open(COMMITTED, encoding='utf-8'))
    c_count, c_names, c_pairs = summarize(cw['nodes'], cw.get('connections', {}))

    # A browser-like User-Agent is required: the n8n host sits behind Cloudflare, whose
    # browser-integrity check (Error 1010) rejects default library UAs. This is not auth —
    # the API key still authenticates; the UA only clears the bot fingerprint.
    UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')
    req = urllib.request.Request(
        f'{API.rstrip("/")}/api/v1/workflows/{WF}',
        headers={'X-N8N-API-KEY': KEY, 'accept': 'application/json', 'User-Agent': UA},
    )
    lw = json.load(urllib.request.urlopen(req, timeout=30))
    l_count, l_names, l_pairs = summarize(lw['nodes'], lw.get('connections', {}))

    ok = True
    if c_count != l_count:
        ok = False
        print(f'NODE COUNT DIFF: committed={c_count} live={l_count}')
    only_c = sorted(set(c_names) - set(l_names))
    only_l = sorted(set(l_names) - set(c_names))
    if only_c:
        ok = False
        print('NODE NAMES only in COMMITTED:', only_c)
    if only_l:
        ok = False
        print('NODE NAMES only in LIVE     :', only_l)
    pc = sorted(c_pairs - l_pairs)
    pl = sorted(l_pairs - c_pairs)
    if pc:
        ok = False
        print('CONNECTIONS only in COMMITTED:', pc)
    if pl:
        ok = False
        print('CONNECTIONS only in LIVE     :', pl)

    print(f'PARITY {"OK" if ok else "DRIFT"} — nodes committed {c_count}/live {l_count}; '
          f'names {len(c_names)}; connections committed {len(c_pairs)}/live {len(l_pairs)}')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
