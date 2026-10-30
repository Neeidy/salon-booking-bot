#!/usr/bin/env python3
"""Mutants of the staged `Eval Spend` (public demo Ruling (d), fail-closed). Each one breaks ONE property the node must
hold, and each must turn tests/unit/eval-spend-fail-closed.test.cjs red — a mutant that survives means the test does
not measure that property.

Each mutant is a single text replacement in one node's jsCode — Eval Spend's, Build Spend-Meter Alert's (whose edit
must stay comment-only), or Build Spend-Cap Reply's (R2a: its own class for a blind meter) — that must apply exactly once, or the run fails; it is written into a copy
of the staged Main export in a temporary directory and handed to the test as its argument.

Not in check-all: it re-runs the test once per mutant. Run before a change to Eval Spend or its test is pushed.
Run: python3 tests/unit/eval-spend-mutants.py        (exit 0 = every mutant killed)
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGED = os.path.join(ROOT, 'n8n', 'staged', 'workflow.main.sanitized.json')
TEST = os.path.join(ROOT, 'tests', 'unit', 'eval-spend-fail-closed.test.cjs')
MUTANTS = {
    'the error output not read':
        ("try { readFailed = $('Read Spend').all(1).length > 0; } catch (e) { readFailed = true; }",
         "readFailed = false;"),
    'a thrown error read as "no error"':
        ("catch (e) { readFailed = true; }", "catch (e) { readFailed = false; }"),
    'the cap itself counted as under':
        ("prev !== null && prev < cap", "prev !== null && prev <= cap"),
    'an unreadable meter counted as zero spend':
        ("let prev = null;", "let prev = 0;"),
    'a negative cost accepted':
        ("&& Number.isFinite(Number(c)) && Number(c) >= 0", "&& Number.isFinite(Number(c))"),
    'any text accepted as a cost':
        ("(typeof c === 'string' && /^[0-9]+(\\.[0-9]+)?$/.test(c))", "typeof c === 'string'"),
    'more than one item accepted':
        ("items.length === 1 ? items[0].json : null", "items.length >= 1 ? items[0].json : null"),
    'any item without fields read as "no row"':
        ("Object.keys(rec).length === 0", "!rec.fields"),
    'the cost rounded to cents (Codex CRT #15 F1)':
        ("{ prev = Number(c); meter = 'row'; }", "{ prev = Math.round(Number(c) * 100) / 100; meter = 'row'; }"),
    'the read error ignored on the no-row path':
        ("if (!readFailed && rec && Object.keys(rec).length === 0)", "if (rec && Object.keys(rec).length === 0)"),
}
OTHER_NODE_MUTANTS = {   # node → {label: (old, new)}
    'Build Spend-Meter Alert': {
        'the meter alert changed beyond its comments':
            ("    spend_meter_unavailable: true,", "    spend_meter_unavailable: false,"),
    },
    'Build Spend-Cap Reply': {   # R2a, Yigitcan's ruling on bound (i)
        'a blind meter reported as a reached budget':
            ("const blind = ($json._spend || {}).meter === 'unreadable';", "const blind = false;"),
        'every closed turn reported as a blind meter':
            ("const blind = ($json._spend || {}).meter === 'unreadable';", "const blind = true;"),
        'the error flag dropped from the body':
            ('({ ok: false, error: "spend_meter_unavailable", handoff: true, reply })', '({ ok: true, handoff: true, reply })'),
        'the budget flag set beside the meter flag':
            ("...(blind ? { spend_meter_unavailable: true } : { spend_cap_tripped: true })",
             "spend_meter_unavailable: blind, spend_cap_tripped: true"),
        'a 503 after the claim':
            ("    _outbound_status: 200,", "    _outbound_status: blind ? 503 : 200,"),
    },
}


def main():
    wf = json.load(open(STAGED, encoding='utf-8'))
    byname = {n['name']: n for n in wf['nodes']}
    plan = [('Eval Spend', label, old, new) for label, (old, new) in MUTANTS.items()]
    plan += [(node, label, old, new) for node, m in OTHER_NODE_MUTANTS.items() for label, (old, new) in m.items()]
    base = subprocess.run(['node', TEST, STAGED], capture_output=True, text=True, timeout=120)
    if base.returncode != 0:
        print('✗ the unmutated staged export does not pass the test — nothing to measure against')
        return 1
    survived = 0
    with tempfile.TemporaryDirectory(prefix='eval-spend-mutants-') as tmp:
        for i, (name, label, old, new) in enumerate(plan):
            node = byname[name]
            code = node['parameters']['jsCode']
            if code.count(old) != 1:
                print(f'✗ {label}: the anchor occurs {code.count(old)} times (want 1) — the mutant does not apply')
                survived += 1
                continue
            node['parameters']['jsCode'] = code.replace(old, new)
            path = os.path.join(tmp, f'm{i}.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(wf, f)
            node['parameters']['jsCode'] = code
            r = subprocess.run(['node', TEST, path], capture_output=True, text=True, timeout=120)
            killed = r.returncode != 0
            survived += not killed
            print(f"{'✓ killed' if killed else '✗ SURVIVED'}: {label}")
    print(f'eval-spend mutants: {len(plan) - survived}/{len(plan)} killed')
    return 0 if survived == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
