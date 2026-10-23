#!/usr/bin/env python3
"""check-import-safe.py — a script that can make LIVE calls must do nothing when it is imported (testing.md,
ruling D4-7, 2026-10-23).

Why: twice in this migration a live-probe script ran its body on import — the D3b race script, and the D3c drill
script, imported as a module to reuse one function, which ran a second, unplanned drill pass inside a K-4 window.
Both lived in the session scratchpad, so this check runs over the repo in check-all AND over the scripts a live
window will use, as a named pre-window step (pass their paths).

A file is LIVE-CAPABLE if it holds a network marker (`curl` as a subprocess word, urllib.request, http.client,
requests, socket) or imports a module from its own directory that is live-capable (to a fixpoint: a drill script
that only imports `spike` is live-capable). In a live-capable file, every top-level statement must be one of:
  import · def · class · a docstring · the `if __name__ == '__main__':` guard ·
  an assignment or expression whose every call has a stdlib root that cannot reach the network
  (os, re, json, importlib, sys, and the builtins in SAFE_ROOTS).
Anything else at the top level (a call to a helper, a loop, an `assert`, `T0 = time.time()`) is red. A line that
must stay may carry `# import-safe: <reason>`; an empty reason does not count.
Not covered: Node scripts (both incidents were Python), and what a guarded `main()` does once it is called.

Usage: python3 scripts/check-import-safe.py [PATH ...]   (files or directories; default: scripts tests)
       python3 scripts/check-import-safe.py --selftest
"""
import ast
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = re.compile(r"""['"]curl['"]|\burllib\.request\b|\bhttp\.client\b|^\s*(?:import|from)\s+(?:requests|socket)\b""", re.M)
SAFE_ROOTS = {'os', 're', 'json', 'importlib', 'sys', 'str', 'int', 'float', 'bool', 'set', 'dict', 'list', 'tuple',
              'frozenset', 'len', 'open', 'sorted', 'range'}
PRAGMA = re.compile(r'#\s*import-safe:\s*\S')


def _root(f):
    while isinstance(f, ast.Attribute):
        f = f.value
    return f.id if isinstance(f, ast.Name) else None


def _local_imports(tree):
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            names.add(n.module.split('.')[0])
    return names


def _is_main_guard(node):
    t = node.test
    return (isinstance(node, ast.If) and isinstance(t, ast.Compare) and isinstance(t.left, ast.Name)
            and t.left.id == '__name__' and any(isinstance(c, ast.Constant) and c.value == '__main__' for c in t.comparators))


def _top_level_faults(tree, lines):
    faults = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.If) and _is_main_guard(node):
            continue
        if PRAGMA.search(lines[node.lineno - 1]):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr)):
            bad = sorted({str(_root(c.func)) for c in ast.walk(node) if isinstance(c, ast.Call)} - SAFE_ROOTS)
            if not bad:
                continue
            faults.append((node.lineno, f'runs on import: a top-level call to {", ".join(bad)}'))
            continue
        faults.append((node.lineno, f'runs on import: a top-level {type(node).__name__}'))
    return faults


def check(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for d, _, fs in os.walk(p):
                files += [os.path.join(d, f) for f in fs if f.endswith('.py') and '__pycache__' not in d]
        elif p.endswith('.py'):
            files.append(p)
    wanted = set(files)
    # Liveness also counts the siblings of a file named alone: a drill script is live because of the helper it
    # imports, and that helper need not be on the command line.
    for d in {os.path.dirname(f) for f in wanted}:
        files += [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.py')]
    parsed, errors = {}, []
    for f in sorted(set(files)):
        src = open(f, encoding='utf-8').read()
        try:
            parsed[f] = (src, ast.parse(src))
        except SyntaxError as e:
            if f in wanted:          # a sibling read only for liveness is skipped; a named file must parse
                errors.append(f'{f}: cannot parse ({e.msg}, line {e.lineno})')
    live = {f for f, (src, _) in parsed.items() if MARKER.search(src)}
    grew = True
    while grew:                      # a file that imports a live-capable sibling is live-capable itself
        grew = False
        for f, (_, tree) in parsed.items():
            if f in live:
                continue
            sib = {os.path.splitext(os.path.basename(g))[0] for g in live if os.path.dirname(g) == os.path.dirname(f)}
            if _local_imports(tree) & sib:
                live.add(f); grew = True
    for f in sorted(live & wanted):
        src, tree = parsed[f]
        errors += [f'{f}:{ln}: {msg}' for ln, msg in _top_level_faults(tree, src.splitlines())]
    return errors, len(wanted), len(live & wanted)


def selftest():
    cases = {
        'live helper, clean': ({'helper.py': "import subprocess\ndef hit():\n    return subprocess.run(['curl', '-s'])\n"}, 0),
        'drill script guarded': ({'helper.py': "import subprocess\ndef hit(): subprocess.run(['curl'])\n",
                                  'drill.py': "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\nimport helper as S\n"
                                              "P = 'x'\ndef run(): S.hit()\nif __name__ == '__main__':\n    run()\n"}, 0),
        'drill script that runs on import (the D3c incident)': (
            {'helper.py': "import subprocess\ndef hit(): subprocess.run(['curl'])\n",
             'drill.py': "import time\nimport helper as S\nT0 = time.time()\nS.hit()\n"}, 2),
        'an assert at the top level': ({'helper.py': "import subprocess\ndef activate(): return subprocess.run(['curl'])\n",
                                        'd.py': "import helper as S\nassert S.activate()\n"}, 1),
        'a loop at the top level, two imports deep': (
            {'helper.py': "import urllib.request\n", 'mid.py': "import helper\n", 'top.py': "import mid\nfor i in range(3):\n    pass\n"}, 1),
        'a non-live file may run code (not checked)': ({'gen.py': "import json\nfor x in range(2):\n    print(x)\n"}, 0),
        'pragma with a reason exempts that line': ({'helper.py': "import subprocess\nX = load('y')  # import-safe: loads a guarded sibling\n"
                                                                 "def load(p): subprocess.run(['curl'])\n"}, 0),
        'a file named alone is live through an unnamed sibling': (
            {'helper.py': "import subprocess\ndef hit(): subprocess.run(['curl'])\n", 'drill.py': "import helper\nhelper.hit()\n"}, 1, ['drill.py']),
        'pragma without a reason does not': ({'helper.py': "import subprocess\nX = load('y')  # import-safe:\n"
                                                           "def load(p): subprocess.run(['curl'])\n"}, 1),
    }
    ok = True
    for label, (files, want, *only) in cases.items():
        with tempfile.TemporaryDirectory() as d:
            for name, src in files.items():
                open(os.path.join(d, name), 'w').write(src)
            errs, _, _ = check([os.path.join(d, f) for f in only[0]] if only else [d])
        good = len(errs) == want
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}: {len(errs)} fault(s), expected {want}" + (f" — {errs[0].split(': ', 1)[1]}" if errs else ''))
    print('check-import-safe selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    paths = argv[1:] or [os.path.join(ROOT, 'scripts'), os.path.join(ROOT, 'tests')]
    errs, n, nlive = check(paths)
    for e in errs:
        print('✗ ' + os.path.relpath(e, ROOT) if e.startswith(ROOT) else '✗ ' + e)
    print(f"check-import-safe: {'OK' if not errs else 'FAILED'} — {n} Python file(s), {nlive} live-capable, {len(errs)} fault(s)")
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
