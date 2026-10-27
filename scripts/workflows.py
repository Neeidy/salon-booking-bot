"""workflows — the production workflows and their committed exports (D6c, 2026-10-27).

The WORKFLOWS array in scripts/check-exports-parity.sh is the ONE source: one line per workflow,
"<workflow id>:n8n/workflow.<key>.sanitized.json", where <key> also names the workflow's spec db/copies/<key>.json.
It replaced the migration's PAIRS/ROLES (scripts/pair_roles.py): after D6c each workflow has one id and one committed
export, and nothing is compared with an original any more. Nothing here calls the network: callers fetch what n8n says
and hand it in, so the rules are testable offline (tests/unit/workflows.test.py).

The rules, all of them, in one place:
  · the list parses: every line is `"<letters/digits id>:n8n/workflow.<key>.sanitized.json"`, no id and no export twice,
    and every <key> has a spec file;
  · the ACTIVE SET (judge_active): every listed workflow is active (an inactive one is a stopped production role), and
    every active workflow on the instance is listed (an unlisted active one is a second holder nobody reviews — a
    schedule trigger has no webhook path to collide on, so this is the only place that sees it). An unlisted INACTIVE
    workflow passes: a rehearsal scratch, or an archived or parked one;
  · holder(): exactly one active workflow listens on a webhook path, and it is a listed one.

WHAT holder() REPLACED, and what it does not see (code-reviewer L3, D6c). The probes used to require that the
ORIGINAL had not executed — a behavioural check. holder() is structural, and it reads each workflow's DRAFT `nodes`, not
its published graph: a second active workflow whose published graph holds the path while its draft does not would not
count. Two things cover that: n8n refuses a second activation on the same method + path with 409 (measured in S1,
MIGRATION-PLAN §3a), and judge_active turns any unlisted ACTIVE workflow red whatever its graph says.
"""
import os
import re

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE = re.compile(r'"([A-Za-z0-9]+):(n8n/workflow\.([a-z0-9-]+)\.sanitized\.json)"')


def _block(src, name):
    start = src.index(f'{name}=(')
    return src[start:src.index('\n)', start)]


def load(path=None, specs_dir=None):
    """{id: export path} from check-exports-parity.sh's WORKFLOWS. Raises ValueError on any malformed or inconsistent
    line: a guard must not run on a declaration it misread."""
    src = open(path or os.path.join(_REPO, 'scripts', 'check-exports-parity.sh'), encoding='utf-8').read()
    if re.search(r'^\s*(PAIRS|ROLES)=\(', src, re.M):
        raise ValueError('a PAIRS or ROLES block is still declared: the pairing ended at D6c, WORKFLOWS is the one list')
    out = {}
    for raw in _block(src, 'WORKFLOWS').splitlines()[1:]:
        line = raw.split('#')[0].strip()
        if not line:
            continue
        m = LINE.fullmatch(line)
        if not m:
            raise ValueError(f'WORKFLOWS line is malformed: {line}')
        wid, export, key = m.groups()
        if wid in out:
            raise ValueError(f'WORKFLOWS names an id twice: {line}')
        if export in out.values():
            raise ValueError(f'WORKFLOWS names an export twice: {line}')
        if not os.path.isfile(os.path.join(specs_dir or os.path.join(_REPO, 'db', 'copies'), f'{key}.json')):
            raise ValueError(f'WORKFLOWS names a workflow with no spec db/copies/{key}.json: {line}')
        out[wid] = export
    if not out:
        raise ValueError('WORKFLOWS is empty')
    return out


def key_of(export):
    m = re.fullmatch(r'n8n/workflow\.([a-z0-9-]+)\.sanitized\.json', export or '')
    if not m:
        raise ValueError(f'not a workflow export path: {export}')
    return m.group(1)


def id_for(workflows, key):
    """The listed workflow id whose export is n8n/workflow.<key>.sanitized.json; ValueError unless exactly one."""
    hits = [w for w, e in workflows.items() if key_of(e) == key]
    if len(hits) != 1:
        raise ValueError(f"WORKFLOWS lists {len(hits)} workflows for '{key}' (exactly one must)")
    return hits[0]


def judge_active(workflows, instance):
    """Errors for the active-set rule. `instance` is every workflow n8n lists: [{id, active, name}]."""
    errs = []
    seen = {w.get('id'): w for w in instance}
    for wid in workflows:
        w = seen.get(wid)
        if w is None:
            errs.append(f'{wid[:4]}… is listed in WORKFLOWS but n8n does not list it')
        elif w.get('active') is not True:
            errs.append(f'{wid[:4]}… is listed but INACTIVE: a production role has stopped')
    for w in instance:
        if w.get('active') is True and w.get('id') not in workflows:
            errs.append(f"{str(w.get('id'))[:4]}… is ACTIVE but not listed in WORKFLOWS: a second holder nobody reviews")
    return errs


def holder(instance, path, workflows):
    """(id, export) of the ONE active workflow whose webhook listens on `path`; ValueError unless exactly one, listed."""
    hits = [w for w in instance if w.get('active') and any(
        n.get('type') == 'n8n-nodes-base.webhook' and (n.get('parameters') or {}).get('path') == path
        for n in (w.get('nodes') or []))]
    if len(hits) != 1:
        raise ValueError(f"{len(hits)} active workflows listen on '{path}' (exactly one must)")
    wid = hits[0]['id']
    if wid not in workflows:
        raise ValueError(f"the active holder of '{path}' is not listed in WORKFLOWS, so it has no committed export")
    return wid, workflows[wid]
