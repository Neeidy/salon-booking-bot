#!/usr/bin/env python3
"""workflow-step.py — three API calls, each read back, for an engine edit on a post-cutover copy (7-F1 Round B, final
shape, ruling 2026-10-25). No signal handling, no automatic recovery: a red step leaves the copy where its read-back
says it is, and the operator decides the next step.

  deactivate SPEC COPY_ID                       POST deactivate → read back active == false
  put        SPEC COPY_ID EXPORT --allow N …    refused unless the copy reads back INACTIVE and the edit is inside its
                                                ALLOWLIST: scripts/diff-workflow-copy.py --phase edit, the copy's
                                                committed export at HEAD vs EXPORT, only the named nodes may differ
                                                (and in them only parameters/alwaysOutputData). The body is EXPORT with
                                                every sanitize placeholder filled from the live copy at the same path
                                                (the deploy helper's fill_by_path). Read back: live == EXPORT
                                                (content_drift, placeholder-only mask) and == the body sent (the same
                                                executable projection, unmasked), not sanitised, settings unchanged,
                                                still inactive
  activate   SPEC COPY_ID                       POST activate → read back active == true and published == draft

SCOPE: copies with no webhook trigger and no Turnstile gate (Purge, Reminders). Main is not edited before ship
(ruling), and Owner Actions / Drill State are out of 7-F1; their production path and gate would need checks this tool
deliberately does not have.

EXPORT is a TRACKED, UNMODIFIED file in the repo (the staged edit, as committed) or REV:PATH (the copy's OWN export as
committed at REV): content that is not in git never reaches production.
RESTORE = `deactivate` (if active) → `put SPEC COPY_ID <REV>:<the copy's export> --allow <the same nodes>` → `activate`,
REV = the commit whose export production held before the edit (parity proved live == committed before it).

Every command refuses a COPY_ID that ROLES does not pair with this spec's export and declare live, or whose original is
not parked (the deploy helper's pairing and ORDER guard, imported). No n8n version id is selected, kept or printed
(the GET responses that carry one are only read for the draft and the published graph).

Usage (env: N8N_API_KEY, CF_ACCESS_CLIENT_ID/SECRET; N8N_HOST or CLAUDE.local.md):
  python3 scripts/workflow-step.py deactivate db/copies/purge.json COPY_ID
  python3 scripts/workflow-step.py put db/copies/purge.json COPY_ID n8n/staged/workflow.purge.copy.sanitized.json --allow "Node A" "Node B"
  python3 scripts/workflow-step.py activate db/copies/purge.json COPY_ID
  (offline test: tests/unit/workflow-step.test.py)
Exit: 0 green · 1 refused or red (the message says the state the copy was read back in) · 2 usage.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('deploy_workflow_copy', os.path.join(ROOT, 'scripts', 'deploy-workflow-copy.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)   # import-safe: the deploy helper keeps every live call under its main()
REV_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/~^-]*')    # a plain revision: no option, no reflog/stash selector @{…}


class Refused(Exception):
    pass


def export_path(spec_path):
    return f'n8n/workflow.{os.path.splitext(os.path.basename(spec_path))[0]}.copy.sanitized.json'


def target(spec_path, copy_id):
    """The spec, for a COPY_ID that ROLES pairs with this spec's export and declares live, its original parked, inside
    the tool's scope (no webhook trigger, no Turnstile gate in the committed export)."""
    full = os.path.realpath(os.path.join(ROOT, spec_path))
    if os.path.dirname(full) != os.path.join(ROOT, 'db', 'copies') or not os.path.isfile(full):
        raise Refused('SPEC must be a file in db/copies/')
    spec = json.load(open(full, encoding='utf-8'))
    try:
        H.copy_export_path(spec_path, copy_id)
        _, roles = H._module('scripts/pair_roles.py', 'pair_roles').load(H.ROLES_FILE)
        committed = H.committed_export(export_path(spec_path))
    except (ValueError, OSError) as e:
        raise Refused(str(e))
    if spec.get('trigger') or H._ts_literal(committed):
        raise Refused('this copy has a webhook trigger or a Turnstile gate: outside this tool\'s scope')
    role = next((r for r in roles if r['copy'] == copy_id), None)
    if role is None:
        raise Refused('ROLES has no line for this copy')
    why = H.check_swap_declared(role['orig'], copy_id, (H._read(role['orig']) or {}).get('active'))
    if why:
        raise Refused(why)
    return spec, committed


def read_copy(copy_id, spec):
    d = H._read(copy_id)
    if d is None:
        raise Refused('the copy does not read back (GET failed)')
    if d.get('name') != spec['name']:
        raise Refused(f"the target is not the workflow named '{spec['name']}'")
    return d


def tracked_clean(rel):
    """Is this repo file tracked AND identical to HEAD? An untracked, ignored or locally edited file is not reviewed."""
    git = lambda *a: __import__('subprocess').run(['git', '-C', ROOT, *a], capture_output=True, stdin=__import__('subprocess').DEVNULL)
    return git('ls-files', '--error-unmatch', '--', rel).returncode == 0 and git('diff', '--quiet', 'HEAD', '--', rel).returncode == 0


def load_export(arg, spec_path):
    """A tracked, unmodified file in the repo, or REV:PATH where PATH is this copy's OWN export as committed at REV."""
    full = os.path.realpath(os.path.join(ROOT, arg))
    if os.path.isfile(full):
        if not full.startswith(ROOT + os.sep):
            raise Refused('the export file is outside the repository')
        if not tracked_clean(os.path.relpath(full, ROOT)):
            raise Refused('the export file is untracked or differs from HEAD: commit it first (only reviewed content goes live)')
        try:
            return json.load(open(full, encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise Refused(f'the export does not read: {type(e).__name__}')
    rev, sep, path = arg.partition(':')
    if not sep or not REV_RE.fullmatch(rev) or path != export_path(spec_path):
        raise Refused(f'EXPORT is neither a file in the repo nor REV:{export_path(spec_path)}')
    try:
        return H.committed_export(path, rev)
    except ValueError as e:
        raise Refused(str(e))


def deactivate(spec_path, copy_id):
    spec, _ = target(spec_path, copy_id)
    read_copy(copy_id, spec)
    st, _ = H.api('POST', f'/workflows/{copy_id}/deactivate')
    got = (H._read(copy_id) or {}).get('active')
    print(f'  deactivate: [{st}] · read back active {got}')
    if got is not False:
        raise Refused(f'the copy does not read back inactive (active {got})')
    return 0


def put(spec_path, copy_id, export_arg, allow):
    spec, committed = target(spec_path, copy_id)
    live = read_copy(copy_id, spec)
    if live.get('active') is not False:
        raise Refused('the copy is not INACTIVE: deactivate it first (a PUT to an active workflow publishes at once)')
    export = load_export(export_arg, spec_path)
    errs = H.DIFF.compare(committed, export, set(allow), phase='edit')
    if errs:
        raise Refused('outside the edit allowlist (diff-workflow-copy --phase edit): ' + '; '.join(errs[:4]))
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            H._ccp().check_sanitised(export)
    except SystemExit as e:
        if e.code:
            raise Refused('the export is not sanitised: ' + ' '.join(out.getvalue().split())[:200])
    cur = H._draft(live)
    try:
        body = H.fill_by_path(cur, export)
    except ValueError as e:
        raise Refused(str(e))
    st, _ = H.api('PUT', f'/workflows/{copy_id}', body)
    after = H._read(copy_id)
    if st != 200 or after is None:
        raise Refused(f'PUT [{st}], read back {"failed" if after is None else "ok"}: the copy was inactive before it; '
                      f'read it again, and restore from the committed export')
    try:
        a = H._draft(after)
        errs = H.content_drift(a, export, H._ccp().placeholder_smap(a, export)) + H.content_drift(a, body, smap={})
        errs += H._settings_parity().committed_vs_live(body.get('settings'), a.get('settings'))
        errs += H.check_not_sanitised(a, export)
    except Exception as e:   # a read-back of an unexpected shape is a red read-back, never a traceback after a write
        errs = [f'the read-back could not be compared ({type(e).__name__})']
    if after.get('active') is not False:
        errs.append('the copy does not read back inactive after the PUT')
    if errs:
        raise Refused('READ-BACK RED after the PUT (the copy holds what n8n kept, inactive): ' + '; '.join(errs[:4]))
    print(f"  put: [{st}] · inside the edit allowlist ({len(allow)} node(s)) · read back == export and == the body sent"
          f" (executable projection) · settings unchanged · still inactive")
    return 0


def activate(spec_path, copy_id):
    spec, _ = target(spec_path, copy_id)
    read_copy(copy_id, spec)
    st, _ = H.api('POST', f'/workflows/{copy_id}/activate')
    after = H._read(copy_id) or {}
    print(f"  activate: [{st}] · read back active {after.get('active')}")
    if after.get('active') is not True:
        raise Refused('the copy does not read back active')
    errs = H._published_matches_draft(after)
    if errs:
        raise Refused('the copy reads back ACTIVE but ' + '; '.join(errs))
    print('  activate: published == draft')
    return 0


def main(argv):
    args = argv[1:]
    cmd = args[0] if args else None
    if cmd in ('deactivate', 'activate') and len(args) == 3 and not any(a.startswith('-') for a in args[1:]):
        fn, call = (deactivate if cmd == 'deactivate' else activate), args[1:]
    elif cmd == 'put' and len(args) >= 6 and args[4] == '--allow' and not any(a.startswith('-') for a in args[1:4] + args[5:]):
        fn, call = put, [args[1], args[2], args[3], args[5:]]
    else:
        print(__doc__.split('Usage')[1].split('Exit:')[0].strip())
        return 2
    try:
        return fn(*call)
    except Refused as e:
        print(f'workflow-step {cmd}: REFUSED/RED — {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
