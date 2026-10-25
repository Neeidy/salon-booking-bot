#!/usr/bin/env python3
"""Every export PREPARED in n8n/staged/ is sanitised exactly like the committed copy export it will replace (7-F1).

WHY: the staged files are committed to a public repo, but no sanitise assertion reads them — check-content-parity's
check_sanitised runs per paired export, and n8n/staged/ is paired with nothing. Only the value-shape secret scan and
the host-leak guard saw them (security-auditor LOW-3, 2026-10-25). An engine edit changes node logic, never what is
masked, so the staged file must carry the SAME placeholder set as its committed counterpart and pass the same
check_sanitised, and must not carry a top-level key the committed export does not (an `id`, `pinData`, `staticData`).

Run: python3 tests/unit/staged-sanitised.test.py [staged_export.json …]   (default: every n8n/staged/*.sanitized.json)
"""
import contextlib
import glob
import importlib.util
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location('ccp', os.path.join(ROOT, 'scripts', 'check-content-parity.py'))
CCP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CCP)   # import-safe: check-content-parity keeps its live half under main()


def sanitised(wf):
    """check_sanitised's verdict without its exit: (ok, node count or its message)."""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            return True, CCP.check_sanitised(wf)
    except SystemExit as e:
        return not e.code, ' '.join(out.getvalue().split())[:200]


def check(staged_path):
    committed_path = os.path.join(ROOT, 'n8n', os.path.basename(staged_path))
    if not os.path.exists(committed_path):
        return [f'no committed counterpart {os.path.relpath(committed_path, ROOT)}']
    st, cm = (json.load(open(p, encoding='utf-8')) for p in (staged_path, committed_path))
    errs = []
    ps, pc = CCP._committed_placeholders(st), CCP._committed_placeholders(cm)
    if ps != pc:
        errs.append(f'placeholder set differs: only staged {sorted(ps - pc)}, only committed {sorted(pc - ps)}')
    ok_s, n_s = sanitised(st)
    ok_c, n_c = sanitised(cm)
    if not ok_s:
        errs.append(f'check_sanitised fails on the staged export: {n_s}')
    elif ok_c and n_s != n_c:
        errs.append(f'check_sanitised counts {n_s} masked node(s) staged vs {n_c} committed')
    extra = sorted(set(st) - set(cm))
    if extra:
        errs.append(f'top-level key(s) the committed export does not carry: {extra}')
    return errs


if __name__ == '__main__':
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'n8n', 'staged', '*.sanitized.json')))
    if not paths:
        print('staged-sanitised: 0 staged exports under n8n/staged/ — nothing prepared, nothing to check')
        sys.exit(0)
    bad = 0
    for p in paths:
        errs = check(p)
        name = os.path.relpath(p, ROOT)
        print(('✓ ' if not errs else '✗ ') + name + ('' if not errs else ' — ' + '; '.join(errs)))
        bad += bool(errs)
    print(f'staged-sanitised: {"FAILED" if bad else "OK"} ({len(paths)} staged export(s))')
    sys.exit(1 if bad else 0)
