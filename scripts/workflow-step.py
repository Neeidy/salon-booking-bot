#!/usr/bin/env python3
"""workflow-step.py — API calls, each read back, for an engine edit on a post-cutover copy (7-F1 Round B, final shape,
ruling 2026-10-25; extended to the webhook copies in 7-2 Tur 2; shrunk to the approved deltas by the R1d rulings,
2026-10-26). No signal handling, no automatic recovery: a red step leaves the copy where its read-back says it is, and
the operator decides the next step.

THREAT (Yigitcan, 2026-10-26): this tool guards against OUR mistakes, not an adversary. It (a) applies only the approved
deltas, (b) never weakens a gate, (c) undoes reliably — by restoring the live snapshot taken before the PUT.

  deactivate SPEC COPY_ID                         POST deactivate → read back active == false
  put        SPEC COPY_ID EXPORT (--allow N … | --delta-file F) --snapshot FILE
                                                  refused unless the copy reads back INACTIVE and the edit is inside its
                                                  ALLOWLIST: scripts/diff-workflow-copy.py --phase edit, the copy's
                                                  committed export at HEAD vs EXPORT, only the named nodes may differ (and
                                                  in them only parameters/alwaysOutputData), plus exactly the delta of F.
                                                  F is a delta file TRACKED AT HEAD and UNMODIFIED (content read from git)
                                                  and must be EXACTLY one of diff-workflow-copy.APPROVED_DELTAS (ruling
                                                  FIXED: every node, edge and setting by identity; --allow alone carries
                                                  no delta). Immediately before the PUT the live workflow is read, must BE
                                                  its committed export (ruling R2b: the content and settings halves of
                                                  exports/content parity, parity_errs — so the snapshot, and any rollback
                                                  to it, is a reviewed state) and is kept in FILE (the SNAPSHOT: outside
                                                  the repository, created new, mode 0600 — it holds live values; delete
                                                  it once the edit is closed). The body is
                                                  EXPORT with every sanitize placeholder filled from the live copy at the
                                                  same path (the deploy helper's fill_by_path) and the LIVE settings: put
                                                  never carries a setting (T-4). Read back: live == EXPORT (content_drift
                                                  incl. alwaysOutputData/executeOnce/retryOnFail and the connections,
                                                  placeholder-only mask) and == the body sent, not sanitised, settings
                                                  unchanged, still inactive. The v1 sibling order of every output an added
                                                  node joins beside other targets is printed.
  settings   SPEC COPY_ID EXPORT --delta-file F --snapshot FILE
                                                  the approved delta's `settings` (today: Owner Actions
                                                  saveDataSuccessExecution "none", ruling T-4), applied as the LAST step:
                                                  refused unless the copy is INACTIVE, EXPORT IS the approved edit (the
                                                  same diff as put) and the live content already equals EXPORT (the edit
                                                  is live) with the committed settings (parity_errs against the edit);
                                                  snapshot as for put; the body is the live
                                                  draft with exactly those keys set. Read back: nodes, connections and name
                                                  == the snapshot, settings == the snapshot's plus exactly those keys
  rollback   SPEC COPY_ID SNAPSHOT                PUT the snapshot back (name, nodes, connections, settings — the fields
                                                  the API takes) to the INACTIVE copy the snapshot was taken from, and
                                                  prove GET == snapshot: every node (credential ids listed on their own),
                                                  the connections and the settings, exactly. For Main and Owner Actions a
                                                  snapshot that fails the webhook invariants below (Turnstile literal not
                                                  `enabled: true`, a trigger not as committed) is refused: a stale or
                                                  already-wrong snapshot never restores a weaker gate
  activate   SPEC COPY_ID                         refused if the workflow's LIVE NAME starts with "SCRATCH — " (read back
                                                  first, whatever ROLES says about the id); POST activate → read back
                                                  active == true and published == draft
  probe      SPEC COPY_ID                         an ACTIVE webhook copy answers as production must, judged on the n8n BODY,
                                                  on the path of the COMMITTED export's one webhook trigger (refused if the
                                                  live draft's trigger differs from it): Main → a dummy Turnstile token is
                                                  403 turnstile_failed, executed by the copy and not by the original; Owner
                                                  Actions (behind Access: the service token is sent) → unsigned 403
                                                  invalid_signature, and a SIGNED request for a well-formed record that does
                                                  not exist → 404 not_found or 503 store_unavailable (printed as "signature
                                                  path alive, store unavailable"), with ≥ 1 execution by the copy and none by
                                                  the original. It counts executions, so it runs BEFORE `settings` (after
                                                  T-4 a successful run is not saved). Main has NO positive probe without a
                                                  real Turnstile token: its forward path is proven by the live booking
                                                  inside a Turnstile window.
  scratch-create SPEC SOURCE_COPY_ID              POST an INACTIVE copy of the live copy's draft, named "SCRATCH — <spec name>";
                                                  its id is printed MASKED as soon as the POST returns it; never activated. A
                                                  POST that returns no usable id (none, malformed, curl's 0) exits 3: a
                                                  scratch MAY exist — find it by name and delete it by hand
  scratch-delete SPEC SCRATCH_ID                  DELETE that scratch; deleted ONLY if the follow-up GET answers exactly 404 —
                                                  any other status (200, 500, 403, 0) exits 3: it may still exist
  rehearse-rollback SPEC SOURCE_COPY_ID EXPORT (--allow N … | --delta-file F)
                                                  R3 on a scratch built from the live copy: scratch-create → put (snapshot
                                                  S0) → settings, when the delta has any → rollback to S0, proven equal →
                                                  scratch-delete in `finally`, proven by an exact 404; the snapshots live in
                                                  a temporary directory outside the repository, removed in `finally`. The
                                                  scratch is never activated. A red step exits 1 and says "deleted" only when
                                                  a DELETE was sent and read back as exactly 404; a delete not proven, or a
                                                  POST with no usable id, exits 3.

R3 ORDER, per copy: deactivate → put --snapshot S1 → activate → probe → (Owner Actions) deactivate → settings --snapshot
S2 → activate. A red step: deactivate (if active) → rollback S1 (it holds the pre-edit settings too) → activate.

GATE (Yigitcan, 2026-10-26; R1c ruling), kept as defence in depth beside the approved deltas: every security-gate node
(diff-workflow-copy.GATE_NODES: Main's and Owner Actions' admission path, incl. `Load Config`, which holds the Turnstile
literal) and EVERY trigger are never in --allow or a removal, and a declared edge touching one (as source or target) is
refused unless it is one of the two R-Q2 edges (diff-workflow-copy.RULED_GATE_EDGES) — refused by put itself before the
PUT AND by diff-workflow-copy --phase edit.

SCOPE: Purge and Reminders, and — since Option A (Yigitcan, 2026-10-25/26) lifted "Main is not edited before ship" so
that every 7-2 finding is fixed before ship — the two WEBHOOK copies, Main and Owner Actions. For them put also checks
DIRECTLY on EXPORT, before the PUT and independent of the diff: Load Config holds no malformed Turnstile literal
(_ts_shape_errs); the literal reads `enabled: true` in BOTH the committed export and EXPORT when the committed export has
one (so an export that is "unchanged" but already off is refused), and EXPORT adds none when it has none; every webhook
trigger's httpMethod/path/responseMode/rawBody equal the committed export's. Across the PUT the content read-back must
equal EXPORT, and each webhook trigger's live webhookId — which the content read-back does not compare — must be
unchanged. Drill State stays out of scope.

EXPORT is a file TRACKED AT HEAD and UNMODIFIED in the repo (the staged edit, as committed), read from git (`git show
HEAD:<path>`, never the working tree; pathspecs literal, so a glob-shaped name never matches another file), or REV:PATH
— PATH the copy's OWN export, REV `HEAD` or a commit SHA (7–40 hex digits naming a commit; no branch, tag, stash or
FETCH_HEAD): content that is not in git never reaches production. REV:PATH is NOT a restore route: since R2b put refuses
a live copy that is not its committed export, so the undo is `rollback` to the put's snapshot.

Every workflow id on the command line must be letters and digits only, or nothing is called. deactivate, activate,
probe, put, settings, rollback and scratch-create's SOURCE refuse a COPY_ID that ROLES does not pair with this spec's
export and declare live, or whose original is not parked (the deploy helper's pairing and ORDER guard, imported);
scratch-delete instead requires a target that ROLES does NOT know, named "SCRATCH — <spec name>", inactive. No n8n
version id is selected, kept or printed; a workflow id is printed only masked.

Usage (env: N8N_API_KEY, CF_ACCESS_CLIENT_ID/SECRET; N8N_HOST or CLAUDE.local.md; the Owner Actions probe also needs
OWNER_HMAC_SECRET and CF_OWNER_ACCESS_CLIENT_ID/SECRET — names only, never printed):
  python3 scripts/workflow-step.py deactivate db/copies/purge.json COPY_ID
  python3 scripts/workflow-step.py put db/copies/purge.json COPY_ID n8n/staged/workflow.purge.copy.sanitized.json --allow "Node A" "Node B" --snapshot /OUTSIDE/THE/REPO/s1.json
  python3 scripts/workflow-step.py put db/copies/main.json COPY_ID n8n/staged/workflow.main.copy.sanitized.json --delta-file DELTA.json --snapshot /OUTSIDE/THE/REPO/s1.json
  python3 scripts/workflow-step.py settings db/copies/owner-actions.json COPY_ID n8n/staged/workflow.owner-actions.copy.sanitized.json --delta-file DELTA.json --snapshot /OUTSIDE/THE/REPO/s2.json
  python3 scripts/workflow-step.py rollback db/copies/main.json COPY_ID /OUTSIDE/THE/REPO/s1.json
  python3 scripts/workflow-step.py rehearse-rollback db/copies/main.json COPY_ID n8n/staged/workflow.main.copy.sanitized.json --delta-file DELTA.json
  python3 scripts/workflow-step.py activate db/copies/purge.json COPY_ID
  python3 scripts/workflow-step.py probe db/copies/main.json COPY_ID
  (offline test: tests/unit/workflow-step.test.py)
Exit: 0 green · 1 refused or red (the message says the state the copy was read back in) · 2 usage · 3 a scratch was not
proven deleted (no exact 404, or a POST that returned no usable id; a masked id is printed when there is one: delete the
"SCRATCH — …" workflow by hand).
"""
import contextlib
import hashlib
import hmac
import importlib.util
import io
import json
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('deploy_workflow_copy', os.path.join(ROOT, 'scripts', 'deploy-workflow-copy.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)   # import-safe: the deploy helper keeps every live call under its main()
SHA_RE = re.compile(r'[0-9a-f]{7,40}')                    # REV of REV:PATH is HEAD or a commit SHA, nothing else (T MED-3)
WEBHOOK_SPECS = {'main', 'owner-actions'}                # the webhook copies Option A brought into scope
SCRATCH_PREFIX = 'SCRATCH — '
ID_RE = re.compile(r'[A-Za-z0-9]+')   # an n8n workflow id: anything else could be re-spelt by curl's path handling
PROBE_WAIT_S = 5                      # an execution appears in the API a few seconds after the webhook answers


class Refused(Exception):
    pass


class ScratchRed(Refused):
    """A red step AFTER the scratch was POSTed: carries its id so the caller can still delete it."""
    def __init__(self, msg, sid):
        super().__init__(msg)
        self.sid = sid


class ScratchLeft(Refused):
    """The scratch could not be PROVEN deleted (no exact 404): it may still exist. Exit 3."""


def mask_id(wid):
    return (wid or '????')[:4] + '…'


def spec_key(spec_path):
    return os.path.splitext(os.path.basename(os.path.realpath(os.path.join(ROOT, spec_path))))[0]


def export_path(spec_path):
    return f'n8n/workflow.{spec_key(spec_path)}.copy.sanitized.json'


def trigger_identity(wf):
    """Per webhook trigger: what decides which requests reach the workflow and how it answers."""
    out = {}
    for n in wf.get('nodes') or []:
        if n.get('type') == 'n8n-nodes-base.webhook':
            p = n.get('parameters') or {}
            out[n['name']] = (p.get('httpMethod'), p.get('path'), p.get('responseMode'),
                              json.dumps((p.get('options') or {}).get('rawBody'), sort_keys=True))
    return out


def webhook_ids(wf):
    return {n['name']: n.get('webhookId') for n in wf.get('nodes') or [] if n.get('type') == 'n8n-nodes-base.webhook'}


def target(spec_path, copy_id):
    """(spec, committed export) for a COPY_ID that ROLES pairs with this spec's export and declares live, its original
    parked, and inside the tool's scope: Purge, Reminders, or one of the WEBHOOK_SPECS (Drill State is refused)."""
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
    if (spec.get('trigger') or H._ts_literal(committed)) and spec_key(spec_path) not in WEBHOOK_SPECS:
        raise Refused('this copy has a webhook trigger or a Turnstile gate and is not Main or Owner Actions: outside this tool\'s scope')
    role = next((r for r in roles if r['copy'] == copy_id), None)
    if role is None:
        raise Refused('ROLES has no line for this copy')
    why = H.check_swap_declared(role['orig'], copy_id, (H._read(role['orig']) or {}).get('active'))
    if why:
        raise Refused(why)
    return spec, committed


def target_scratch(spec_path, scratch_id):
    """A rehearsal target: an INACTIVE workflow named "SCRATCH — <spec name>" that ROLES does NOT know. It is never
    production, so the pairing and ORDER guards do not apply; every other put check does."""
    full = os.path.realpath(os.path.join(ROOT, spec_path))
    if os.path.dirname(full) != os.path.join(ROOT, 'db', 'copies') or not os.path.isfile(full):
        raise Refused('SPEC must be a file in db/copies/')
    spec = json.load(open(full, encoding='utf-8'))
    try:
        pairs, _ = H._module('scripts/pair_roles.py', 'pair_roles').load(H.ROLES_FILE)
        committed = H.committed_export(export_path(spec_path))
    except (ValueError, OSError) as e:
        raise Refused(str(e))
    if scratch_id in pairs:
        raise Refused('this id is a production workflow in ROLES, not a scratch')
    d = H._read(scratch_id)
    if d is None:
        raise Refused('the scratch does not read back (GET failed)')
    if d.get('name') != SCRATCH_PREFIX + spec['name']:
        raise Refused(f"the target is not the workflow named '{SCRATCH_PREFIX + spec['name']}'")
    if d.get('active') is not False:
        raise Refused('the scratch reads back ACTIVE: a scratch is never activated')
    return spec, committed


def read_copy(copy_id, spec):
    d = H._read(copy_id)
    if d is None:
        raise Refused('the copy does not read back (GET failed)')
    if d.get('name') != spec['name']:
        raise Refused(f"the target is not the workflow named '{spec['name']}'")
    return d


def _outside_repo(path):
    """Is `path` (its directory resolved) outside the repository? A snapshot holds live values: it can never be committed."""
    d, root = os.path.realpath(os.path.dirname(os.path.abspath(path))), os.path.realpath(ROOT)   # both resolved
    return d != root and not d.startswith(root + os.sep)


def snapshot_write(path, wid, spec_path, draft):
    """Keep the live workflow taken immediately before a PUT: a NEW file (never overwritten), mode 0600, outside the repo."""
    if not _outside_repo(path) or not os.path.isdir(os.path.dirname(os.path.abspath(path))):
        raise Refused('the snapshot path must be in an existing directory OUTSIDE the repository (it holds live values)')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        raise Refused(f'the snapshot file cannot be created new ({type(e).__name__}): an existing snapshot is never overwritten')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'_what': 'workflow-step.py pre-PUT live snapshot: live values, never commit, delete once the edit is closed',
                   'workflow_id': wid, 'spec': spec_key(spec_path), 'taken_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   'workflow': {k: draft.get(k) for k in ('name', 'nodes', 'connections', 'settings')}}, f)


def snapshot_read(path, wid, spec_path):
    """The snapshot's workflow, refused unless the file is outside the repo and was taken from THIS copy of THIS spec."""
    if not _outside_repo(path) or not os.path.isfile(path):
        raise Refused('the snapshot is not a file outside the repository')
    try:
        snap = json.load(open(path, encoding='utf-8'))
        wf = snap['workflow']
        ok = isinstance(wf.get('name'), str) and isinstance(wf.get('nodes'), list) and isinstance(wf.get('connections'), dict)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise Refused(f'the snapshot does not read ({type(e).__name__})')
    if not ok:
        raise Refused('the snapshot does not hold a workflow (name, nodes, connections)')
    if snap.get('workflow_id') != wid or snap.get('spec') != spec_key(spec_path):
        raise Refused(f'the snapshot was taken from another workflow or spec ({mask_id(snap.get("workflow_id"))}, {snap.get("spec")})')
    return wf


def _cred_ids(wf):
    return sorted((n.get('name'), t, (c or {}).get('id')) for n in wf.get('nodes') or [] for t, c in (n.get('credentials') or {}).items())


def snapshot_errs(got, want):
    """GET == snapshot, exactly: every node (as a whole, order-free), the credential ids (listed on their own), the
    connections, the settings and the name. [] when equal."""
    canon = lambda o: json.dumps(o, sort_keys=True)
    errs = []
    gn, wn = [canon(n) for n in got.get('nodes') or []], [canon(n) for n in want.get('nodes') or []]
    if sorted(gn) != sorted(wn):
        G = {n.get('name'): canon(n) for n in got.get('nodes') or []}
        Wd = {n.get('name'): canon(n) for n in want.get('nodes') or []}
        bad = sorted(k for k in set(G) | set(Wd) if G.get(k) != Wd.get(k)) or ['(a repeated node name)']
        errs.append(f'nodes differ from the snapshot: {bad[:4]}')
    if _cred_ids(got) != _cred_ids(want):
        errs.append('credential ids differ from the snapshot')
    if canon(got.get('connections') or {}) != canon(want.get('connections') or {}):
        errs.append('connections differ from the snapshot')
    if canon(got.get('settings') or {}) != canon(want.get('settings') or {}):
        errs.append('settings differ from the snapshot')
    if got.get('name') != want.get('name'):
        errs.append('the name differs from the snapshot')
    return errs


def _git(*a):
    """git in the repo with LITERAL pathspecs: `delta[1].json` names that file, never `delta1.json` (lane T M-a)."""
    return subprocess.run(['git', '--literal-pathspecs', '-C', ROOT, *a], capture_output=True, stdin=subprocess.DEVNULL)


def tracked_clean(rel):
    """Is this repo file tracked AND identical to HEAD? An untracked, ignored or locally edited file is not reviewed."""
    return _git('ls-files', '--error-unmatch', '--', rel).returncode == 0 and _git('diff', '--quiet', 'HEAD', '--', rel).returncode == 0


def head_blob(rel):
    """The file's content AS COMMITTED AT HEAD (`git show HEAD:<rel>`: a path, never a pattern), or None when HEAD has no
    such file. What is sent is what git holds, not the working tree — a locally edited file is refused before this
    (tracked_clean), and an edit git cannot see (assume-unchanged, skip-worktree) is never read."""
    r = _git('show', f'HEAD:{rel}')
    return r.stdout.decode('utf-8') if r.returncode == 0 else None


def repo_text(arg, what):
    """A repo file → its content at HEAD; refused when it is outside the repo, not a file, untracked, not at HEAD or
    modified."""
    full = os.path.realpath(os.path.join(ROOT, arg))
    if not full.startswith(ROOT + os.sep) or not os.path.isfile(full):
        raise Refused(f'the {what} is not a file in the repository')
    rel = os.path.relpath(full, ROOT)
    text = head_blob(rel) if tracked_clean(rel) else None
    if text is None:
        raise Refused(f'the {what} is untracked, not at HEAD, or differs from HEAD: commit it first '
                      '(only reviewed content widens an edit or goes live)')
    return text


def load_delta_file(arg):
    """--delta-file: a file TRACKED AT HEAD and unmodified (the reviewed delta is the one sent), its content read from git
    and parsed by diff-workflow-copy.parse_delta (one parser) → (allow, delta)."""
    text = repo_text(arg, 'delta file')
    try:
        d = json.loads(text)
    except ValueError:
        raise Refused('the delta file does not read (JSONDecodeError)')
    try:
        return H.DIFF.parse_delta(d)
    except ValueError as e:
        raise Refused(str(e))


def webhook_invariant_errs(committed, export):
    """The webhook copies' pre-PUT invariants, checked DIRECTLY on EXPORT (not inferred from the diff): Load Config holds
    exactly one Turnstile literal of the exact shape; it reads `enabled: true` in both the committed export and EXPORT
    when the committed export has one (and EXPORT adds none when it has none); every webhook trigger's method, path,
    responseMode and rawBody equal the committed export's."""
    errs = list(H._ts_shape_errs(export, 'export'))
    lc, le = H._ts_literal(committed), H._ts_literal(export)
    if lc and not (le == lc == ['true']):
        errs.append(f'the Turnstile literal must read enabled: true in the committed export AND the export (committed {lc}, export {le})')
    if not lc and le:
        errs.append(f'the export holds a Turnstile literal {le} that the committed export does not')
    if trigger_identity(export) != trigger_identity(committed):
        errs.append("a webhook trigger's method/path/responseMode/rawBody (or the set of webhook triggers) differs from the committed export")
    return errs


def load_export(arg, spec_path):
    """A file tracked at HEAD and unmodified (its content read from git), or REV:PATH where PATH is this copy's OWN export
    as committed at REV."""
    full = os.path.realpath(os.path.join(ROOT, arg))
    if os.path.isfile(full):
        if not full.startswith(ROOT + os.sep):
            raise Refused('the export file is outside the repository')
        text = repo_text(arg, 'export file')
        try:
            return json.loads(text)
        except ValueError as e:
            raise Refused(f'the export does not read: {type(e).__name__}')
    rev, sep, path = arg.partition(':')
    if not sep or path != export_path(spec_path):
        raise Refused(f'EXPORT is neither a file in the repo nor REV:{export_path(spec_path)}')
    if rev != 'HEAD':
        r = _git('rev-parse', '--verify', '--quiet', f'{rev}^{{commit}}') if SHA_RE.fullmatch(rev) else None
        if r is None or r.returncode != 0 or not r.stdout.decode().strip().startswith(rev):
            raise Refused(f'REV must be HEAD or a commit SHA (7-40 hex digits naming a commit), not {rev[:40]!r}')
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


def _fresh(copy_id, spec, scratch):
    """The live workflow read IMMEDIATELY before a PUT: still the named target, still inactive."""
    cur = H._read(copy_id)
    if cur is None:
        raise Refused('the copy does not read back (GET failed) immediately before the PUT: nothing was written')
    want = SCRATCH_PREFIX + spec['name'] if scratch else spec['name']
    if cur.get('name') != want or cur.get('active') is not False:
        raise Refused('immediately before the PUT the copy no longer reads back as the inactive target: nothing was written')
    return cur


def parity_errs(spec, copy_id, draft, content_ref, settings_ref, scratch):
    """Ruling R2b DEPLOY: immediately before a snapshot, the live workflow must BE a reviewed, committed state, so a
    rollback to that snapshot always returns to one. The halves of exports-parity and content-parity that a copy
    DEACTIVATED for its edit can pass, for this one workflow: the live draft carries no sanitize placeholder, its
    content equals `content_ref` (the same projection check-content-parity compares), its settings equal
    `settings_ref`, and — for a production copy — they match its original's through the spec's allowlist. The pairing
    and ORDER half is target()'s. The active-state half (ROLES' live side is active) is red by construction while the
    copy is deactivated for the edit, so it is the one half not asked here; `activate` proves published == draft.
    A gate made weaker in the live copy by hand — its conditions, code, wiring, flags or credentials — is a content
    difference and is refused before anything is kept (Codex R2, deploy HIGH). NOT seen, because check-content-parity's
    projection normalises them away: an IF/Switch condition's `typeValidation`, `caseSensitive` and `version` options,
    and values behind sanitize placeholders (filled from live by put, so put never changes them and rollback returns
    them as they were). Recorded in ROADMAP's CONVERGE list (security review R2b, finding 1)."""
    ref = dict(content_ref, name=draft.get('name')) if scratch else content_ref
    errs = H.check_not_sanitised(draft, content_ref)
    errs += H.content_drift(draft, ref, H._ccp().placeholder_smap(draft, ref))
    errs += H._settings_parity().committed_vs_live(settings_ref, draft.get('settings'))
    if not scratch:
        _, roles = H._module('scripts/pair_roles.py', 'pair_roles').load(H.ROLES_FILE)
        orig = H._read(next(r['orig'] for r in roles if r['copy'] == copy_id)) or {}
        errs += H._settings_parity().copy_vs_original(orig.get('settings'), draft.get('settings'), spec.get('settings_allow', {}))
    return errs


def _state(after):
    """What the copy reads back as after a write, and the next step from that state (lane T review, R1d)."""
    if after is None:
        return 'its state was NOT read back: read it before anything else'
    if after.get('active') is True:
        return 'it reads back ACTIVE (serving production): `deactivate` it first'
    return 'it reads back inactive'


def _webhook_errs(a, hooks_before, webhook):
    return ['a webhook id changed across the PUT'] if webhook and webhook_ids(a) != hooks_before else []


def put(spec_path, copy_id, export_arg, allow, delta, snapshot, scratch=False):
    delta = delta or {}
    spec, committed = target_scratch(spec_path, copy_id) if scratch else target(spec_path, copy_id)
    live = H._read(copy_id) if scratch else read_copy(copy_id, spec)
    if live.get('active') is not False:
        raise Refused('the copy is not INACTIVE: deactivate it first (a PUT to an active workflow publishes at once)')
    webhook = spec_key(spec_path) in WEBHOOK_SPECS
    errs = H.DIFF.approved_errs(spec_key(spec_path), delta)
    if errs:
        raise Refused('not an approved delta (ruling FIXED: only the reviewed deltas are applied): ' + '; '.join(errs[:3]))
    export = load_export(export_arg, spec_path)
    gate = sorted(n for n in set(allow) | set(delta.get('remove_nodes') or ()) if H.DIFF.is_gate(n, committed, export))
    if gate:
        raise Refused(f'GATE node(s) {gate} are never in --allow or removed ({H.TS_NODE} holds the Turnstile literal; '
                      'every security-gate node and every trigger is the gate)')
    gate_e = sorted(e for e in set(delta.get('add_edges') or ()) | set(delta.get('remove_edges') or ())
                    if e not in H.DIFF.RULED_GATE_EDGES and any(x and H.DIFF.is_gate(x, committed, export) for x in H.DIFF._ends(e)))
    if gate_e:
        raise Refused(f'declared edge(s) {gate_e[:3]} touch a GATE node: only the ruled R-Q2 edges may (RULED_GATE_EDGES)')
    if webhook:
        errs = webhook_invariant_errs(committed, export)
        if errs:
            raise Refused('a webhook invariant does not hold in the export: ' + '; '.join(errs))
    errs = H.DIFF.compare(committed, export, set(allow), phase='edit', delta=delta)
    if errs:
        raise Refused('outside the edit allowlist (diff-workflow-copy --phase edit): ' + '; '.join(errs[:4]))
    for line in H.DIFF.sibling_order_lines(export, delta):
        print('  put: ' + line)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            H._ccp().check_sanitised(export)
    except SystemExit as e:
        if e.code:
            raise Refused('the export is not sanitised: ' + ' '.join(out.getvalue().split())[:200])
    cur = H._draft(_fresh(copy_id, spec, scratch))
    errs = parity_errs(spec, copy_id, cur, committed, committed.get('settings'), scratch)
    if errs:
        raise Refused('the live workflow is not its committed export (exports/content parity, ruling R2b): nothing was '
                      'kept or written — a rollback must return to a reviewed state; restore parity first: '
                      + '; '.join(errs[:3]))
    hooks_before = webhook_ids(cur)
    try:
        body = H.fill_by_path(cur, export)
    except ValueError as e:
        raise Refused(str(e))
    # ruling T-4: put never carries a setting. fill_by_path already returns the live settings; set here once more so
    # the body never depends on that helper's choice.
    body['settings'] = json.loads(json.dumps(cur.get('settings') or {}))
    snapshot_write(snapshot, copy_id, spec_path, cur)
    st, _ = H.api('PUT', f'/workflows/{copy_id}', body)
    after = H._read(copy_id)
    if st != 200 or after is None:
        raise Refused(f'PUT [{st}]: {_state(after)}; then restore it with `rollback` from the snapshot {snapshot}')
    try:
        a = H._draft(after)
        ref = dict(export, name=SCRATCH_PREFIX + spec['name']) if scratch else export   # a scratch keeps its own name
        errs = H.content_drift(a, ref, H._ccp().placeholder_smap(a, ref)) + H.content_drift(a, body, smap={})
        errs += H._settings_parity().committed_vs_live(cur.get('settings'), a.get('settings'))
        errs += H.check_not_sanitised(a, export)
        errs += _webhook_errs(a, hooks_before, webhook)   # content_drift compares parameters and code, not webhookId
    except Exception as e:   # a read-back of an unexpected shape is a red read-back, never a traceback after a write
        errs = [f'the read-back could not be compared ({type(e).__name__})']
    if after.get('active') is not False:
        errs.append('the copy does not read back inactive after the PUT')
    if errs:
        raise Refused(f'READ-BACK RED after the PUT (the copy holds what n8n kept; {_state(after)}; then restore it with '
                      f'`rollback` from the snapshot {snapshot}): ' + '; '.join(errs[:4]))
    n_delta = sum(len(delta.get(k) or ()) for k in H.DIFF.DELTA_KEYS)
    print(f"  put: [{st}] · inside the edit allowlist ({len(allow)} node(s), approved delta {n_delta}) · read back == export"
          f" and == the body sent (executable projection) · settings unchanged · still inactive"
          + (' · webhook ids unchanged' if webhook else '') + (' · SCRATCH' if scratch else '')
          + f' · pre-PUT snapshot kept at {snapshot}')
    return 0


def settings_step(spec_path, copy_id, export_arg, allow, delta, snapshot, scratch=False):
    """Ruling T-4: the approved delta's settings, applied as the LAST step — after the edit (its content must already be
    live) and after the probes (which count executions). The body is the live draft with exactly those keys set."""
    delta = delta or {}
    spec, committed = target_scratch(spec_path, copy_id) if scratch else target(spec_path, copy_id)
    live = H._read(copy_id) if scratch else read_copy(copy_id, spec)
    if live.get('active') is not False:
        raise Refused('the copy is not INACTIVE: deactivate it first (a PUT to an active workflow publishes at once)')
    errs = H.DIFF.approved_errs(spec_key(spec_path), delta)
    declared = dict(delta.get('settings') or {})
    if errs or not declared:
        raise Refused('not an approved settings change: ' + ('; '.join(errs[:3]) if errs else 'the delta declares no setting'))
    export = load_export(export_arg, spec_path)
    # EXPORT must BE the edit this delta describes, or "the live copy holds EXPORT" proves nothing: the committed
    # export passed here would land the setting on an unedited copy (lane T review, R1d).
    errs = H.DIFF.compare(committed, export, set(allow), phase='edit', delta=delta)
    if errs:
        raise Refused('EXPORT is not the approved edit (diff-workflow-copy --phase edit): ' + '; '.join(errs[:3]))
    ref = dict(export, name=SCRATCH_PREFIX + spec['name']) if scratch else export
    d = H._draft(live)
    if H.content_drift(d, ref, H._ccp().placeholder_smap(d, ref)):
        raise Refused('the live copy does not hold the edit yet: settings are applied LAST, after the edit and its probes')
    cur = H._draft(_fresh(copy_id, spec, scratch))
    errs = parity_errs(spec, copy_id, cur, export, committed.get('settings'), scratch)
    if errs:
        raise Refused('the live workflow is not the approved edit with the committed settings (parity, ruling R2b): '
                      'nothing was kept or written: ' + '; '.join(errs[:3]))
    body = json.loads(json.dumps(cur))
    body['settings'] = dict(body.get('settings') or {}, **declared)
    snapshot_write(snapshot, copy_id, spec_path, cur)
    st, _ = H.api('PUT', f'/workflows/{copy_id}', body)
    after = H._read(copy_id)
    if st != 200 or after is None:
        raise Refused(f'PUT [{st}]: {_state(after)}; then `rollback` from {snapshot} returns it to the probed edit (the put\'s '
                      'snapshot returns it to before the edit)')
    try:
        errs = snapshot_errs(H._draft(after), body)
    except Exception as e:
        errs = [f'the read-back could not be compared ({type(e).__name__})']
    if after.get('active') is not False:
        errs.append('the copy does not read back inactive after the PUT')
    if errs:
        raise Refused(f'READ-BACK RED after the settings PUT ({_state(after)}; then `rollback` from {snapshot} returns it to '
                      "the probed edit, the put's snapshot to before the edit): " + '; '.join(errs[:4]))
    print(f"  settings: [{st}] · {sorted(declared)} set as approved, every node, connection and other setting unchanged ·"
          f" still inactive{' · SCRATCH' if scratch else ''} · pre-PUT snapshot kept at {snapshot}")
    return 0


def rollback(spec_path, copy_id, snapshot, scratch=False):
    """PUT the pre-edit snapshot back and prove GET == snapshot (nodes incl. credential ids, connections, settings). For the
    webhook copies the snapshot must first pass the same webhook invariants put checks on an export (Turnstile literal
    `enabled: true`, the triggers as committed): a snapshot is restored, never trusted (T+D security review T-1, R1d —
    a leftover snapshot, or a live copy already wrong when it was taken, would otherwise go back green)."""
    spec, committed = target_scratch(spec_path, copy_id) if scratch else target(spec_path, copy_id)
    live = H._read(copy_id) if scratch else read_copy(copy_id, spec)
    if live.get('active') is not False:
        raise Refused('the copy is not INACTIVE: deactivate it first (a PUT to an active workflow publishes at once)')
    want = snapshot_read(snapshot, copy_id, spec_path)
    if want['name'] != live.get('name'):
        raise Refused('the snapshot names another workflow than the live copy')
    if spec_key(spec_path) in WEBHOOK_SPECS:
        try:
            errs = webhook_invariant_errs(committed, want)
        except Exception as e:   # a snapshot of an unexpected shape is refused, never half-checked
            errs = [f'the snapshot could not be checked ({type(e).__name__})']
        if errs:
            raise Refused('the snapshot fails a webhook invariant — it would restore a weaker gate: ' + '; '.join(errs[:3]))
    body = {k: want.get(k) for k in ('name', 'nodes', 'connections', 'settings')}
    st, _ = H.api('PUT', f'/workflows/{copy_id}', body)
    after = H._read(copy_id)
    if after is None:
        raise Refused(f'rollback PUT [{st}]: {_state(after)}; the snapshot {snapshot} is unchanged — retry the rollback')
    try:
        errs = snapshot_errs(H._draft(after), body)
    except Exception as e:
        errs = [f'the read-back could not be compared ({type(e).__name__})']
    if after.get('active') is not False:
        errs.append('the copy does not read back inactive after the PUT')
    if st != 200:   # judged on what was read back, not on the status alone (lane T review, R1d)
        raise Refused(f'rollback PUT [{st}]: ' + ('yet the copy reads back == the snapshot (restored); the non-200 is not '
                      'explained' if not errs else f'NOT restored ({"; ".join(errs[:3])}); {_state(after)}; the snapshot '
                      f'{snapshot} is unchanged — retry the rollback'))
    if errs:
        raise Refused(f'ROLLBACK READ-BACK RED (the copy holds what n8n kept; {_state(after)}; the snapshot {snapshot} is '
                      'unchanged): ' + '; '.join(errs[:4]))
    print(f"  rollback: [{st}] · read back == the snapshot: {len(body['nodes'])} nodes, {len(_cred_ids(body))} credential "
          f"id(s), connections, settings · still inactive{' · SCRATCH' if scratch else ''}")
    return 0


def webhook_post(path, body, headers):
    """POST to the production webhook path; secrets travel in a 0600 header file, never on argv. (status, json|None)."""
    fd, hpath = tempfile.mkstemp(suffix='.hdr')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(''.join(f'{k}: {v}\n' for k, v in headers.items()))
        r = subprocess.run(['curl', '-4', '-s', '-m', '30', '-X', 'POST', '-w', '\n%{http_code}', '-H', '@' + hpath,
                            '--data-binary', '@-', f'https://{H._host()}/webhook/{path}'],
                           input=body, capture_output=True, text=True)
    finally:
        os.unlink(hpath)
    text, _, code = r.stdout.rpartition('\n')
    try:
        return int(code), json.loads(text)
    except ValueError:
        return (int(code) if code.isdigit() else 0), None


def executions_since(wid, since):
    """Executions of `wid` started at or after `since` — the same GET turnstile-window.executions_since makes for Main's
    probe, here through the deploy helper's api (so the offline fake answers it)."""
    st, d = H.api('GET', f'/executions?workflowId={wid}&limit=100')
    if st != 200 or not isinstance(d, dict):
        raise Refused(f'GET executions {mask_id(wid)} answered {st}: which workflow answered is NOT MEASURED')
    return sum(1 for e in d.get('data') or [] if (e.get('startedAt') or '') >= since)


def oa_probe(path, orig, copy_id):
    """Owner Actions sits behind Access: the service token is sent, so a 403 is n8n's, judged on its body. Like Main's
    probe, the copy must have executed and the original must not."""
    need = ('OWNER_HMAC_SECRET', 'CF_OWNER_ACCESS_CLIENT_ID', 'CF_OWNER_ACCESS_CLIENT_SECRET')
    if any(not os.environ.get(k) for k in need):
        raise Refused('the Owner Actions probe needs ' + ', '.join(need) + ' in the environment: NOT MEASURED')
    hdr = {'Content-Type': 'application/json', 'CF-Access-Client-Id': os.environ['CF_OWNER_ACCESS_CLIENT_ID'],
           'CF-Access-Client-Secret': os.environ['CF_OWNER_ACCESS_CLIENT_SECRET']}
    since = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    rid = 'rec' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
    body = json.dumps({'action': 'release_handoff', 'record_id': rid, 'messageId': f'wsprobe-{int(time.time())}-{secrets.token_hex(3)}',
                       'ts': int(time.time())})
    st1, b1 = webhook_post(path, body, hdr)
    unsigned_ok = st1 == 403 and isinstance(b1, dict) and b1.get('error') == 'invalid_signature'
    sig = hmac.new(os.environ['OWNER_HMAC_SECRET'].encode(), body.encode(), hashlib.sha256).hexdigest()
    st2, b2 = webhook_post(path, body, dict(hdr, **{'X-Owner-Signature': sig}))
    err2 = b2.get('error') if isinstance(b2, dict) else None
    signed_ok = (st2, err2) in ((404, 'not_found'), (503, 'store_unavailable'))
    time.sleep(PROBE_WAIT_S)
    ec, eo = executions_since(copy_id, since), executions_since(orig, since)
    served = ec >= 1 and eo == 0
    ok = unsigned_ok and signed_ok and served
    note = ' · signature path alive, store unavailable' if ok and st2 == 503 else ''
    print(f"  probe: unsigned → {st1} {b1.get('error') if isinstance(b1, dict) else '-'} · signed, unknown record → {st2} {err2}"
          f" · copy executions {ec} · original executions {eo}{note} · {'OK' if ok else 'RED'}")
    return ok


def probe(spec_path, copy_id):
    spec, committed = target(spec_path, copy_id)
    live = read_copy(copy_id, spec)
    if spec_key(spec_path) not in WEBHOOK_SPECS:
        raise Refused('probe is for the webhook copies (Main, Owner Actions)')
    if live.get('active') is not True:
        raise Refused('the copy is not ACTIVE: nothing answers on its path')
    ti = trigger_identity(committed)          # the path comes from the COMMITTED export, never from the live draft
    if len(ti) != 1:
        raise Refused(f'the committed export has {len(ti)} webhook triggers, not one: no single path to probe')
    if trigger_identity(H._draft(live)) != ti:
        raise Refused('the live copy\'s webhook trigger differs from the committed export: not probed')
    path = next(iter(ti.values()))[1]
    _, roles = H._module('scripts/pair_roles.py', 'pair_roles').load(H.ROLES_FILE)
    orig = next(r['orig'] for r in roles if r['copy'] == copy_id)
    if spec_key(spec_path) == 'main':
        ok, _ = H.turnstile_probe(path, orig, copy_id)
    else:
        ok = oa_probe(path, orig, copy_id)
    if not ok:
        raise Refused('the probe is RED: the copy does not answer as production must; deactivate it and `rollback` from '
                      "the put's snapshot")
    return 0


def scratch_post(spec_path, source_id):
    """POST the scratch and read it back → its id. Its MASKED id is printed the moment the POST returns one, and any
    red step after that raises ScratchRed carrying the id, so a scratch is never left without a way to find it."""
    spec, _ = target(spec_path, source_id)
    if spec_key(spec_path) not in WEBHOOK_SPECS:
        raise Refused('a scratch rehearsal is for the webhook copies')
    src = H._draft(read_copy(source_id, spec))
    body = {'name': SCRATCH_PREFIX + spec['name'], 'nodes': src['nodes'], 'connections': src['connections'],
            'settings': src.get('settings') or {}}
    st, d = H.api('POST', '/workflows', body)
    sid = d.get('id') if isinstance(d, dict) else None
    if not (isinstance(sid, str) and ID_RE.fullmatch(sid)):   # the POST was SENT: a scratch may exist with no id to delete it by
        raise ScratchLeft(f'POST [{st}] was sent but returned {"no id" if sid is None else "an id of an unexpected form"}: '
                          f'a scratch MAY EXIST — find the workflow named "{body["name"]}" in n8n and delete it by hand')
    print(f'  scratch-create: [{st}] · id {mask_id(sid)} (named "{body["name"]}")')
    try:
        got = H._read(sid)
        errs = ['the scratch does not read back'] if got is None else \
            H.content_drift(H._draft(got), dict(src, name=body['name']), smap={})   # the name differs by design
        if got is not None and (got.get('name') != body['name'] or got.get('active') is not False):
            errs.append(f"name/active read back wrong (active {got.get('active')})")
    except Exception as e:   # a red read-back after the POST: the id is already printed and travels in the exception
        errs = [f'the read-back could not be compared ({type(e).__name__})']
    if st != 200 or errs:
        raise ScratchRed(f'POST [{st}]: the scratch {mask_id(sid)} reads back wrong ({"; ".join(errs[:2])}); delete it', sid)
    print('  scratch-create: inactive · reads back == the live copy\'s draft')
    return sid


def scratch_create(spec_path, source_id):
    scratch_post(spec_path, source_id)
    return 0


def scratch_delete(spec_path, scratch_id):
    """DELETE a scratch; deletion is proven only by an EXACT 404 on the follow-up GET. Any other answer (200, 500, an
    Access 403, curl's 0) is ScratchLeft: the scratch may still exist (it holds a copy of production and its path)."""
    target_scratch(spec_path, scratch_id)
    st, _ = H.api('DELETE', f'/workflows/{scratch_id}')
    gst, _ = H.api('GET', f'/workflows/{scratch_id}')
    print(f'  scratch-delete: [{st}] · read back [{gst}]{" (gone)" if gst == 404 else ""}')
    if gst != 404:
        raise ScratchLeft(f'the follow-up GET answered {gst}, not 404: the scratch {mask_id(scratch_id)} MAY STILL EXIST — '
                          f'find the workflow named "{SCRATCH_PREFIX}…" in n8n and delete it by hand')
    return 0


def rehearse_rollback(spec_path, source_id, export_arg, allow, delta):
    """R3 end to end on a scratch built from the live copy: scratch-create → put (snapshot S0) → settings, when the
    approved delta has any → rollback to S0, proven GET == S0 → scratch-delete in `finally`, proven by an exact 404. The
    snapshots sit in a temporary directory outside the repository, removed in `finally`.
    The scratch is never activated. Exit 1 if a step was red (the scratch was deleted); 3 if it was not proven deleted."""
    sid, err, deleted = None, None, False
    tmpd = tempfile.mkdtemp(prefix='workflow-step-rehearsal-')
    s0 = os.path.join(tmpd, 'before-edit.json')
    try:
        sid = scratch_post(spec_path, source_id)
        print('  rehearse-rollback: step 1 — the edit')
        put(spec_path, sid, export_arg, allow, delta, s0, scratch=True)
        if (delta or {}).get('settings'):
            print('  rehearse-rollback: step 2 — the settings, last')
            settings_step(spec_path, sid, export_arg, allow, delta, os.path.join(tmpd, 'before-settings.json'), scratch=True)
        print('  rehearse-rollback: step 3 — the rollback to the pre-edit snapshot')
        rollback(spec_path, sid, s0, scratch=True)
    except ScratchLeft:
        raise   # a POST with no usable id: nothing to delete by id, exit 3 with the find-by-name instruction
    except Refused as e:
        sid = getattr(e, 'sid', None) or sid
        err = e
        print(f'  rehearse-rollback: RED — {e}')
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
        if sid is not None:
            try:
                deleted = scratch_delete(spec_path, sid) == 0   # 0 only after a DELETE read back as exactly 404
            except ScratchLeft:
                raise
            except Refused as e:
                raise ScratchLeft(f'the scratch {mask_id(sid)} was NOT deleted ({e}): it may still exist — delete the '
                                  f'workflow named "{SCRATCH_PREFIX}…" in n8n by hand')
    if err:
        raise Refused('a rehearsal step was RED; ' + ('the scratch was deleted (DELETE sent, exact 404 read back)' if deleted
                                                      else 'no scratch was created (refused before the POST)'))
    if not deleted:
        raise ScratchLeft(f'the scratch {mask_id(sid)} was not proven deleted: find the workflow named "{SCRATCH_PREFIX}…" '
                          'in n8n and delete it by hand')
    print(f"  rehearse-rollback: edit{', settings' if (delta or {}).get('settings') else ''} and rollback read back green on "
          'the scratch · snapshots removed · scratch deleted (DELETE sent, 404 read back)')
    return 0


def refuse_scratch_name(wid):
    """Read the live name back: a workflow named "SCRATCH — …" is never activated, whatever ROLES says about its id."""
    name = (H._read(wid) or {}).get('name')
    if isinstance(name, str) and name.startswith(SCRATCH_PREFIX):
        raise Refused('the target is a SCRATCH (its live name starts with "SCRATCH — "): a scratch is never activated')


def activate(spec_path, copy_id):
    refuse_scratch_name(copy_id)
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


def parse_edit(rest, need_snapshot):
    """EXPORT (--allow N … | --delta-file F) [--snapshot FILE] → (export, allow, dfile, snapshot), or None for a usage
    error. --allow and --delta-file are mutually exclusive; --snapshot is required exactly when need_snapshot."""
    if len(rest) < 3 or rest[0].startswith('-'):
        return None
    export, cur, allow, dfile, snap = rest[0], None, [], None, None
    for a in rest[1:]:
        if a == '--allow':
            if cur is not None or allow:
                return None
            cur = 'allow'
        elif a in ('--delta-file', '--snapshot'):
            if (a == '--delta-file' and dfile is not None) or (a == '--snapshot' and snap is not None) or cur not in (None, 'allow'):
                return None
            cur = a
        elif a.startswith('-'):
            return None
        elif cur == '--delta-file':
            dfile, cur = a, None
        elif cur == '--snapshot':
            snap, cur = a, None
        elif cur == 'allow':
            allow.append(a)
        else:
            return None
    if cur in ('--delta-file', '--snapshot') or (dfile is not None) == bool(allow) or (snap is not None) != need_snapshot:
        return None
    return export, allow, dfile, snap


def main(argv):
    args = argv[1:]
    cmd = args[0] if args else None
    single = {'deactivate': deactivate, 'activate': activate, 'probe': probe, 'scratch-create': scratch_create,
              'scratch-delete': scratch_delete}
    parsed = parse_edit(args[3:], cmd != 'rehearse-rollback') if cmd in ('put', 'settings', 'rehearse-rollback') and len(args) >= 4 else None
    if cmd in single and len(args) == 3 and not any(a.startswith('-') for a in args[1:]):
        fn, call = single[cmd], args[1:]
    elif cmd == 'rollback' and len(args) == 4 and not any(a.startswith('-') for a in args[1:]):
        fn, call = rollback, args[1:]
    elif parsed and not any(a.startswith('-') for a in args[1:3]) and not (cmd == 'settings' and parsed[2] is None):
        fn = {'put': put, 'settings': settings_step, 'rehearse-rollback': rehearse_rollback}[cmd]
    else:
        print(__doc__.split('Usage')[1].split('Exit:')[0].strip())
        return 2
    if not ID_RE.fullmatch(args[2]):
        print(f'workflow-step {cmd}: REFUSED — a workflow id is letters and digits only; this one is not (nothing was called)')
        return 1
    try:
        if fn in (put, settings_step, rehearse_rollback):
            export, allow, dfile, snap = parsed
            delta = {}
            if dfile is not None:
                allow, delta = load_delta_file(dfile)
            call = {put: [args[1], args[2], export, allow, delta, snap],
                    settings_step: [args[1], args[2], export, allow, delta, snap],
                    rehearse_rollback: [args[1], args[2], export, allow, delta]}[fn]
        return fn(*call)
    except ScratchLeft as e:
        print(f'workflow-step {cmd}: SCRATCH NOT PROVEN DELETED — {e}')
        return 3
    except Refused as e:
        print(f'workflow-step {cmd}: REFUSED/RED — {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
