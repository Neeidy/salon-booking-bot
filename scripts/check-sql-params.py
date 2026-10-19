#!/usr/bin/env python3
"""check-sql-params.py — every Postgres node runs PARAMETERIZED SQL (docs/MIGRATION-PLAN.md §3f).

Why a gate and not a habit: the node accepts BOTH. Its schema says the query may use "n8n expressions and
$1, $2, $3 … 'Query Parameters'", and the docs say only that "n8n sanitizes data in query parameters". An
expression pasted into the SQL text is string concatenation, i.e. SQL injection, and the node will run it
without complaint. Over every committed workflow export, this FAILS on a Postgres node where:
  1. operation is not executeQuery (one review surface: no table-builder operations);
  2. the query is an n8n expression (starts with "=") or contains "{{";
  3. a $N in the query has no matching parameter, or a parameter is never referenced;
  4. Query Parameters is present but is not an ARRAY expression ("={{ [ … ] }}"). The comma-separated
     string form splits a value that contains a comma, and spike S3 has not yet measured what it does;
  5. a formatting FILTER or a NAMED placeholder is used: `$N:name`/`$N:raw`/`$N:value`…, the short forms
     `$N^` (raw text: injection by design), `$N#` (unquoted value) and `$N~` (identifier), or named
     `${…}` `$(…)` `$<…>` `$[…]` `$/…/` (pg-promise's formatter, which n8n's node uses, accepts all of them;
     whether this n8n build honours each one is spike S3's question, and this gate does not wait for it).

It prints how many Postgres nodes it checked, so a green run over ZERO nodes cannot pass for evidence.
`--selftest` runs the fixtures in tests/fixtures/sql-params/: every good-* must pass, and every bad-* must
fail WITH THE REASON MAPPED TO ITS NAME below. A fixture that fails for some other reason proves nothing
about the rule it is named after (pre-push audit, 2026-10-19: rule 4 could be switched off and the
selftest stayed green, because its fixture was also failing rule 3).

Usage: python3 scripts/check-sql-params.py [export.json …]   (default: n8n/*.sanitized.json)
       python3 scripts/check-sql-params.py --selftest
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PG = ('n8n-nodes-base.postgres', 'n8n-nodes-base.postgresTool')
REASON = {                       # bad-* fixture → a substring its failure MUST contain
    'bad-expression-in-query': 'n8n expression',
    'bad-insert-operation': 'not executeQuery',
    'bad-missing-param': 'without a parameter',
    'bad-unused-param': 'never referenced',
    'bad-string-params': 'not an array expression',
    'bad-identifier-placeholder': 'filter or named placeholder',
    'bad-raw-filter': 'filter or named placeholder',
    'bad-hash-filter': 'filter or named placeholder',
    'bad-named-placeholder': 'filter or named placeholder',
    'bad-non-string-query': 'not a string',
    'bad-tool-node-expression': 'n8n expression',
}


def split_top_level(inner):
    """Split an array literal's inside on commas at depth 0 (brackets and quotes respected)."""
    parts, depth, cur, quote = [], 0, '', None
    for ch in inner:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in '\'"`':
            quote = ch
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p for p in parts if p.strip()]


def check_node(n):
    p = n.get('parameters') or {}
    op = p.get('operation', 'insert')        # the node's own default operation is insert
    if op != 'executeQuery':
        return [f"operation is '{op}', not executeQuery"]
    errs = []
    q = p.get('query') or ''
    if not isinstance(q, str):
        return ['the query is not a string']
    if q.startswith('=') or '{{' in q:
        errs.append('the query text is an n8n expression (string-built SQL)')
    if re.search(r'\$\d+(?::\w+|[\^#~])', q) or re.search(r'\$[{(<\[/]', q):
        errs.append('formatting filter or named placeholder in the query ($N:…, $N^, $N#, $N~, ${…})')
    refs = {int(m) for m in re.findall(r'\$(\d+)\b', q)}
    qr = ((p.get('options') or {}).get('queryReplacement'))
    count = 0
    if qr not in (None, ''):
        m = re.fullmatch(r'\s*=\s*\{\{\s*\[(.*)\]\s*\}\}\s*', qr, re.S)
        if not m:
            errs.append('Query Parameters is not an array expression ={{ [ … ] }}')
        else:
            count = len(split_top_level(m.group(1)))
    missing = sorted(r for r in refs if r < 1 or r > count)
    unused = sorted(i for i in range(1, count + 1) if i not in refs)
    if missing:
        errs.append(f'$N without a parameter: {missing}')
    if unused:
        errs.append(f'parameter(s) never referenced: {unused}')
    return errs


def check_export(path):
    wf = json.load(open(path))
    found, bad = 0, []
    for n in wf.get('nodes', []):
        if n.get('type') not in PG:
            continue
        found += 1
        for e in check_node(n):
            bad.append(f"{os.path.basename(path)} · {n['name']}: {e}")
    return found, bad


def selftest():
    d = os.path.join(ROOT, 'tests', 'fixtures', 'sql-params')
    files = sorted(glob.glob(os.path.join(d, '*.json')))
    assert files, 'no fixtures found'
    ok = True
    for f in files:
        name = os.path.basename(f)
        found, bad = check_export(f)
        expect_bad = name.startswith('bad-')
        reason = REASON.get(name[:-5])
        if found == 0:
            print(f'✗ {name}: holds no Postgres node, so it tests nothing')
            ok = False
        elif expect_bad and not bad:
            print(f'✗ {name}: expected a FAILURE, got a pass')
            ok = False
        elif expect_bad and (reason is None or not any(reason in b for b in bad)):
            print(f'✗ {name}: red, but not for its own reason ({reason!r}): {bad}')
            ok = False
        elif not expect_bad and bad:
            print(f'✗ {name}: expected a pass, got {bad}')
            ok = False
        else:
            print(f"✓ {name}: {'red — ' + bad[0].split(': ', 1)[1] if bad else 'green'}")
    print('check-sql-params selftest:', 'OK' if ok else 'FAILED', f'({len(files)} fixtures)')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    paths = argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'n8n', '*.sanitized.json')))
    total, problems = 0, []
    for p in paths:
        found, bad = check_export(p)
        total += found
        problems += bad
    if problems:
        print('check-sql-params: FAILED')
        for b in problems:
            print('  - ' + b)
        return 1
    print(f'check-sql-params: OK — {total} Postgres node(s) checked in {len(paths)} export(s)'
          + ('  (zero: nothing has been migrated yet, so this run proves only that no unchecked node exists)'
             if total == 0 else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
