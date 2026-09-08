#!/usr/bin/env python3
# Content parity: does the COMMITTED sanitized workflow match the LIVE workflow node-for-node in its
# EXECUTABLE content? The structural parity guard (check-live-parity.py) compares only node count / names /
# connection topology — it is blind to a changed expression, mapping, or Code body. That blind spot let a
# real drift hide (the Save State `|| ''` slot-clear, present in committed but missing live — caught only by
# eye in CP4 sub-step 2). Codex audits and the portfolio proof both read the committed file, so a silent
# content drift means we audit something the running system is not. This guard closes that gap.
#
# WHAT IT COMPARES: for every executable node present in both, a normalized projection of `parameters`
# (+ `credentials` + `type`). Normalization removes the DIFFERENCES THAT ARE EXPECTED and not drift:
#   - sanitize placeholders — real base/table/calendar/host/credential ids are masked in committed; the live
#     ids are mapped to the same placeholders before compare (else the guard screams every run).
#   - n8n serialization noise that is not logic — Airtable/resource-locator `__rl` display cache
#     (cachedResultName/Url), an omitted-vs-default httpRequest `method`, empty `options: {}`, and the
#     IF/Switch condition `options` meta (typeValidation/version/caseSensitive) — none of which change behaviour.
#   - Code-node bodies compared line-rstripped (trailing whitespace / final newline only).
# Sticky notes (n8n-nodes-base.stickyNote) are EXCLUDED — they document the canvas, they do not execute.
#
# WHAT IT CATCHES: any real change to a Code body, an IF/Switch condition value, an Airtable column mapping,
# an HTTP url/body, a switch rule — i.e. the drift class the structural guard cannot see.
#
# USAGE:  N8N_API_URL=... N8N_API_KEY=... python3 scripts/check-content-parity.py [committed_path]
# Exit 0 = parity OK, 1 = DRIFT (prints node + field), 2 = fetch/config error. Runs at every close gate.
import os, sys, json, re, urllib.request

WF = os.environ.get('N8N_WORKFLOW_ID', 'SL142I47mK6SAz6p')
API = os.environ.get('N8N_API_URL')
KEY = os.environ.get('N8N_API_KEY')
# Default resolves against the REPO, not the caller's cwd: a relative default made the guard die with
# FileNotFoundError when run from scripts/, which reads as "the guard failed" rather than "you were in the
# wrong directory" — a guard that reports a false failure erodes trust as fast as one that stays silent.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMITTED = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    'SANITIZED_PATH', os.path.join(_REPO, 'n8n/workflow.sanitized.json'))
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36')
# Cloudflare Access service-token headers — added ONLY when both env vars are present (no-op otherwise), so the
# same guard works whether /api is CF-Access "Bypass" (today) or "Service Auth" (CRT #7 follow-up).
CF_HDRS = ({'CF-Access-Client-Id': os.environ['CF_ACCESS_CLIENT_ID'],
            'CF-Access-Client-Secret': os.environ['CF_ACCESS_CLIENT_SECRET']}
           if os.environ.get('CF_ACCESS_CLIENT_ID') and os.environ.get('CF_ACCESS_CLIENT_SECRET') else {})

# --- SANITISE CHECK -------------------------------------------------------------------------------
# These three literals must be placeholders in the COMMITTED export, unconditionally. They live here, at
# module level and independent of any live fetch, because of a defect found on 2026-09-08: the assertion
# used to sit INSIDE build_smap(), which only runs after a successful n8n API call — so on a machine with
# no n8n credentials the script exited before the sanitise check ever ran, and a commit got NO sanitise
# coverage at all while `.claude/commands/sanitize.md` claimed it "FAILS loudly". A guard that only works
# where you happen to have credentials is the same class of untested safety net as the inverted test this
# assertion was written to replace (ARCH-DEC 2026-08-17).
def _cal_id(node):
    m = re.search(r'googleCalendarId:\s*"([^"]+)"', (node.get('parameters', {}) or {}).get('jsCode', '') or '')
    return m.group(1) if m else None


def _turnstile_secret(node):
    bp = (((node.get('parameters') or {}).get('bodyParameters') or {}).get('parameters') or [])
    for prm in bp:
        if isinstance(prm, dict) and prm.get('name') == 'secret':
            return prm.get('value')
    return None


def _is_placeholder(v):
    return isinstance(v, str) and (v.startswith('REPLACE_WITH') or 'XXXX' in v)


def _walk_ids(obj, out):
    """Collect Airtable base/table ids and credential ids from anywhere in a node."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'credentials' and isinstance(v, dict):
                for cred in v.values():
                    if isinstance(cred, dict) and isinstance(cred.get('id'), str):
                        out.append(('credential id', cred['id']))
            # SUBSTRING, not fullmatch: a real id pasted inside an httpRequest URL or a Code-node string
            # literal escaped a fullmatch entirely (flow-reviewer planted both, 2026-09-08). view/record/field
            # ids are included because `sanitize.md` step 2 covers pinned data and Airtable ids generally.
            if isinstance(v, str):
                for m in re.finditer(r'(app|tbl|viw|rec|fld)[A-Za-z0-9]{14}', v):
                    if not _is_placeholder(m.group(0)):
                        out.append(('airtable id', m.group(0)))
                for m in re.finditer(r'[0-9a-f]{16,}@group\.calendar\.google\.com', v):
                    out.append(('google calendar id', m.group(0)))
            _walk_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_ids(v, out)


def check_sanitised(comm):
    """Committed-side only: no live workflow, no credentials, no network. Exits 1 on a real value.

    Covers the classes `.claude/commands/sanitize.md` step 2 names: calendar id (anywhere, not just
    Load Config), telegram chatId, turnstile secret, Airtable app/tbl/viw/rec/fld ids (as SUBSTRINGS, so an id
    inside a URL or a code string is caught), credential ids, and pinData. Webhook URLs / tunnel hostnames are
    covered by scripts/check-no-host-leak.sh instead, not here. It used to cover only
    three: a `flow-reviewer` pass on 2026-09-08 planted a real-looking Airtable base id, table id and
    credential id in a copy and the guard went GREEN — and would have stayed green on the credentialled
    path too, because when live == committed no mask is built and parity compares equal. That is the SAME
    shape as the inverted test this function was written to replace, still open for two classes.
    """
    bad = []
    for n in comm['nodes']:
        ids = []
        _walk_ids(n, ids)
        for kind, val in ids:
            if not _is_placeholder(val):
                bad.append('%s %r (%s)' % (kind, val[:6] + '…', n['name']))
        # pinData is named in sanitize.md step 2 and had NO automated check at all: pinned test data is the
        # most likely carrier of real customer PII in an export refreshed from live.
        if n.get('pinData') or (isinstance(comm.get('pinData'), dict) and n['name'] in comm['pinData']):
            bad.append('pinData present (%s) — pinned data must be stripped before commit' % n['name'])
        v = _cal_id(n)
        if isinstance(v, str) and v and not _is_placeholder(v):
            bad.append('googleCalendarId (%s)' % n['name'])
        if n.get('type') == 'n8n-nodes-base.telegram':
            ch = (n.get('parameters') or {}).get('chatId')
            if isinstance(ch, str) and ch and not _is_placeholder(ch):
                bad.append('telegram chatId (%s)' % n['name'])
        ts = _turnstile_secret(n)
        if isinstance(ts, str) and ts and not _is_placeholder(ts):
            bad.append('turnstile secret (%s)' % n['name'])
    if bad:
        print('SANITISE FAILURE — the committed export carries REAL values (not placeholders):')
        for kind in bad:
            print('  - ' + kind)
        print('Restore the placeholders in n8n/workflow.sanitized.json before committing (see .claude/commands/sanitize.md).')
        sys.exit(1)
    return len(comm['nodes'])


# The real-id -> committed-placeholder map is DERIVED from the (live, committed) pair itself — NEVER
# hardcoded. This file is committed to a PUBLIC repo, so it must contain no real base/table/calendar/host/
# credential id (security-secrets.md). The reals are read from the LIVE workflow (via the API) and $N8N_HOST;
# the committed side supplies the placeholder each one maps to.
def build_smap(live, comm):
    import re
    lby = {n['name']: n for n in live['nodes']}
    cby = {n['name']: n for n in comm['nodes']}
    smap = {}

    def leaves(node):
        """resource-locator `value`s (base/table ids) + credential ids, keyed by a structural path so live
        and committed pair up exactly — a mask applied to the wrong node/path would hide a real drift."""
        out = {}

        def walk(o, path):
            if isinstance(o, dict):
                if o.get('__rl') and isinstance(o.get('value'), str):
                    out[path] = o['value']
                for k, v in o.items():
                    walk(v, f'{path}/{k}')
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f'{path}[{i}]')
        walk(node.get('parameters', {}) or {}, 'p')
        for cn, cv in (node.get('credentials') or {}).items():
            if isinstance(cv, dict) and isinstance(cv.get('id'), str):
                out[f'cred/{cn}'] = cv['id']
        return out

    for nm in set(lby) & set(cby):
        lp, cp = leaves(lby[nm]), leaves(cby[nm])
        for path, lval in lp.items():
            cval = cp.get(path)
            if cval and lval != cval:
                smap[lval] = cval  # real (live) -> placeholder (committed)

    # --- SANITISE ASSERTION (added 2026-09-07 after a real calendar id reached the committed export) ---
    # The masks below used to be applied ONLY when live != committed. That made the PASS condition CONTAIN
    # the leak condition: if the committed export carried the REAL value, both sides were equal, no mask was
    # built, and this guard went GREEN at exactly the moment it had to shout. Inverted test, not a gap.
    # The placeholder ASSERTIONS are not here — they run in check_sanitised() before any live fetch, so a
    # machine without n8n credentials still gets them. This function only builds the real->placeholder mask.
    lcal, ccal = _cal_id(lby.get('Load Config', {})), _cal_id(cby.get('Load Config', {}))
    if lcal and ccal and lcal != ccal:
        smap[lcal] = ccal

    # Telegram owner-alert chatId is a plain-string secret (PII target — not a resource-locator or
    # credential, so the leaf walk above cannot see it). Map live chatId -> committed placeholder so a
    # masked committed value is not screamed as drift, AND the real chatId never has to sit in git (CP5a).
    for nm in set(lby) & set(cby):
        if lby[nm].get('type') == 'n8n-nodes-base.telegram':
            lch = (lby[nm].get('parameters') or {}).get('chatId')
            cch = (cby[nm].get('parameters') or {}).get('chatId')
            if isinstance(lch, str) and isinstance(cch, str) and lch != cch:
                smap[lch] = cch

    # Cloudflare Turnstile secret is a plain-string literal in the siteverify `bodyParameters` (name=='secret')
    # — not a resource-locator or credential, so the leaf walk cannot see it. Map live -> committed placeholder
    # so the masked committed value is not screamed as drift, AND the real secret (when swapped in for the
    # public test secret in Phase 6) never has to sit in git (CP5b-3).
    for nm in set(lby) & set(cby):
        lts, cts = _turnstile_secret(lby[nm]), _turnstile_secret(cby[nm])
        if isinstance(lts, str) and isinstance(cts, str) and lts != cts:
            smap[lts] = cts

    # the n8n host does not normally appear as a node literal; if it ever does, mask it from $N8N_HOST
    # (read from the environment / gitignored CLAUDE.local.md — never written here).
    host = os.environ.get('N8N_HOST')
    if host:
        smap[host] = 'N8N_HOST_PLACEHOLDER'
    return smap


def canon(obj, smap):
    """Recursively normalize a node fragment: mask derived ids, drop serialization noise, keep logic."""
    if isinstance(obj, dict):
        # resource-locator: keep only the (masked) value; drop the display cache + mode
        if obj.get('__rl') is True:
            return {'value': canon(obj.get('value'), smap)}
        out = {}
        for k, v in obj.items():
            if k in ('cachedResultName', 'cachedResultUrl', 'cachedResultId'):
                continue
            if k == 'options' and v == {}:      # empty options == absent
                continue
            out[k] = canon(v, smap)
        return out
    if isinstance(obj, list):
        return [canon(x, smap) for x in obj]
    if isinstance(obj, str):
        for a, b in smap.items():
            obj = obj.replace(a, b)
        return obj
    return obj


def project(node, smap):
    """The executable projection of a node used for the parity hash."""
    p = canon(node.get('parameters', {}) or {}, smap)
    # Code body: ignore trailing-whitespace / final-newline only differences
    if isinstance(p.get('jsCode'), str):
        p['jsCode'] = '\n'.join(line.rstrip() for line in p['jsCode'].rstrip().splitlines())
    # httpRequest method: an omitted method is a GET (n8n default) — coalesce so null == "GET"
    if node.get('type') == 'n8n-nodes-base.httpRequest' and not p.get('method'):
        p['method'] = 'GET'
    # IF/Switch condition meta that is not logic: the container `options`
    # (typeValidation/version/caseSensitive) and each condition's auto-generated `id`.
    def strip_cond_meta(container):
        if isinstance(container, dict):
            container.pop('options', None)
            for c in container.get('conditions', []) or []:
                if isinstance(c, dict):
                    c.pop('id', None)
        return container
    if isinstance(p.get('conditions'), dict):
        strip_cond_meta(p['conditions'])
    if isinstance(p.get('rules'), dict):
        for r in p['rules'].get('values', []) or []:
            if isinstance(r.get('conditions'), dict):
                strip_cond_meta(r['conditions'])
    return {'type': node.get('type'), 'parameters': p, 'credentials': canon(node.get('credentials'), smap)}


def main():
    # SANITISE FIRST — it needs no credentials and no network, so it runs even where the parity half cannot.
    comm_only = json.load(open(COMMITTED, encoding='utf-8'))
    n_checked = check_sanitised(comm_only)
    if not (API and KEY):
        print('sanitise OK — %d committed nodes carry placeholders for every class sanitize.md names: '
              'calendar id, telegram chatId, turnstile secret, Airtable ids, credential ids, pinData' % n_checked)
        print('ERROR: set N8N_API_URL and N8N_API_KEY (n8n public API) to fetch the live workflow '
              '(parity half NOT run)')
        sys.exit(2)
    req = urllib.request.Request(f'{API.rstrip("/")}/api/v1/workflows/{WF}',
        headers={'X-N8N-API-KEY': KEY, 'accept': 'application/json', 'User-Agent': UA, **CF_HDRS})
    live = json.load(urllib.request.urlopen(req, timeout=30))
    comm = json.load(open(COMMITTED, encoding='utf-8'))

    smap = build_smap(live, comm)

    STICKY = 'n8n-nodes-base.stickyNote'
    lby = {n['name']: n for n in live['nodes'] if n['type'] != STICKY}
    cby = {n['name']: n for n in comm['nodes'] if n['type'] != STICKY}

    fails = []
    only_l = sorted(set(lby) - set(cby))
    only_c = sorted(set(cby) - set(lby))
    if only_l:
        fails.append(f'executable nodes only in LIVE: {only_l}')
    if only_c:
        fails.append(f'executable nodes only in COMMITTED: {only_c}')

    for nm in sorted(set(lby) & set(cby)):
        lp, cp = project(lby[nm], smap), project(cby[nm], smap)
        if json.dumps(lp, sort_keys=True) != json.dumps(cp, sort_keys=True):
            # find the differing top-level parameter keys for a precise report
            lk, ck = lp['parameters'], cp['parameters']
            diff_keys = sorted(k for k in set(lk) | set(ck)
                               if json.dumps(lk.get(k), sort_keys=True) != json.dumps(ck.get(k), sort_keys=True))
            extra = [] if lp['credentials'] == cp['credentials'] else ['credentials']
            fails.append(f"content DRIFT in '{nm}': fields {diff_keys + extra} differ (committed != live)")

    if fails:
        print('CONTENT DRIFT — committed sanitized does not match the live workflow:')
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print(f'content parity OK — {len(lby)} executable nodes match live byte-for-byte '
          '(sanitize placeholders + n8n serialization noise normalized; sticky notes excluded)')
    sys.exit(0)


if __name__ == '__main__':
    main()
