"""pair_roles — which workflow of each original/copy pair holds production (MIGRATION-PLAN §3t, decision 9).

The ROLES array in scripts/check-exports-parity.sh is the ONE source: one line per pair, "ORIGINAL_ID:COPY_ID:LIVE",
LIVE being `original` or `copy`. Before the cutover every line says `original`; D6b flips each pair to `copy` in a
commit, and that commit IS the declaration the guards read. Nothing here calls the network: the callers fetch the
active flags and hand them in, so the rules are testable offline (tests/unit/pair-roles.test.py).

The rules, all of them, in one place:
  · exactly ONE workflow of each pair is active — both active is red (two holders of one production role; S1 shows
    n8n refuses a second activation on the same path, but a schedule trigger has no path), both inactive is red
    (the role has no holder: production stopped);
  · the active one is the one ROLES declares live — an undeclared swap is red, in either direction;
  · a single workflow read on its own (check-content-parity) may be inactive ONLY when ROLES declares the OTHER one
    of its pair live: a parked copy before the cutover, a parked original after it. A workflow ROLES does not name
    at all may not be inactive (the rule that existed before ROLES: an inactive original is a stopped production).
"""
import os
import re

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = ('original', 'copy')


def _block(src, name):
    start = src.index(f'{name}=(')
    return src[start:src.index('\n)', start)]


def load(path=None):
    """(pairs, roles) from check-exports-parity.sh. pairs = {id: export path}; roles = [{orig, copy, live}].
    Raises ValueError on any malformed or inconsistent line: a guard must not run on a declaration it misread."""
    src = open(path or os.path.join(_REPO, 'scripts', 'check-exports-parity.sh'), encoding='utf-8').read()
    pairs = dict(re.findall(r'^\s*"([A-Za-z0-9]+):([^"\s]+)"', _block(src, 'PAIRS'), re.M))
    lines = [l.split('#')[0].strip() for l in _block(src, 'ROLES').splitlines()[1:]]
    roles, seen = [], set()
    for l in filter(None, lines):
        m = re.fullmatch(r'"([A-Za-z0-9]+):([A-Za-z0-9]+):([a-z]+)"', l)
        if not m:
            raise ValueError(f'ROLES line is malformed: {l}')
        orig, cp, live = m.groups()
        if live not in LIVE:
            raise ValueError(f'ROLES line names an unknown role {live!r}: {l}')
        if orig not in pairs or cp not in pairs:
            raise ValueError(f'ROLES names an id with no PAIRS line: {l}')
        if pairs[orig].endswith('.copy.sanitized.json') or not pairs[cp].endswith('.copy.sanitized.json'):
            raise ValueError(f'ROLES pairs them the wrong way round (the original must be a plain export, the copy a .copy one): {l}')
        if orig in seen or cp in seen:
            raise ValueError(f'ROLES names an id twice: {l}')
        seen |= {orig, cp}
        roles.append({'orig': orig, 'copy': cp, 'live': live})
    return pairs, roles


def judge(roles, active):
    """Errors for the pair rules. `active` maps every id in ROLES to True/False (as read from n8n)."""
    errs = []
    for r in roles:
        o, c = active.get(r['orig']), active.get(r['copy'])
        if o is None or c is None:
            errs.append(f"pair {r['orig'][:4]}…/{r['copy'][:4]}…: an active flag was not read")
            continue
        if o and c:
            errs.append(f"pair {r['orig'][:4]}…/{r['copy'][:4]}…: BOTH active — two holders of one production role")
        elif not o and not c:
            errs.append(f"pair {r['orig'][:4]}…/{r['copy'][:4]}…: BOTH inactive — the role has no holder, production stopped")
        elif (o and r['live'] != 'original') or (c and r['live'] != 'copy'):
            held = 'original' if o else 'copy'
            errs.append(f"pair {r['orig'][:4]}…/{r['copy'][:4]}…: the {held} is active but ROLES declares the {r['live']} live (an undeclared swap)")
    return errs


def may_be_inactive(wf_id, roles):
    """(allowed, why) for one workflow read on its own."""
    for r in roles:
        if wf_id == r['copy']:
            return (r['live'] == 'original',
                    'a parked copy (ROLES: its original is live)' if r['live'] == 'original'
                    else 'ROLES declares this COPY live, so it must be active')
        if wf_id == r['orig']:
            return (r['live'] == 'copy',
                    'a parked original (ROLES: cut over, its copy is live)' if r['live'] == 'copy'
                    else 'ROLES declares this ORIGINAL live, so it must be active')
    return (False, 'not named in ROLES, so it is a production workflow and must be active')


def holder(workflows, path, pairs):
    """(id, export) of the ONE active workflow whose webhook listens on `path`; ValueError unless exactly one."""
    hits = [w for w in workflows if w.get('active') and any(
        n.get('type') == 'n8n-nodes-base.webhook' and (n.get('parameters') or {}).get('path') == path
        for n in (w.get('nodes') or []))]
    if len(hits) != 1:
        raise ValueError(f"{len(hits)} active workflows listen on '{path}' (exactly one must)")
    wid = hits[0]['id']
    if wid not in pairs:
        raise ValueError(f"the active holder of '{path}' has no PAIRS line, so no committed export to compare")
    return wid, pairs[wid]
