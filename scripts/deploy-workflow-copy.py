#!/usr/bin/env python3
"""deploy-workflow-copy.py — deploy a migration copy to n8n and VERIFY it before any drill (MIGRATION-PLAN §3r).

Why the copy is not deployed as generated: scripts/build-workflow-copy.py builds it from the SANITIZED export,
so every node outside the data layer carries placeholders (a Telegram chat id, credential ids). Deployed as is,
such a copy cannot do what its original does: at D3b its owner alerts all went undelivered. So a copy is
deployed as THE LIVE ORIGINAL plus only the generated copy's data-layer delta: the spec's data nodes (with the
real Postgres credential swapped in), the real trigger's test path, and a declared temporary trigger.

After the write it runs these checks, and exits non-zero if any is red, so no drill starts on a broken copy:
  0. swapped: every spec data node is a Postgres node on a real credential, the trigger is on its test path,
     and the declared temporary trigger exists (so the original itself, or an unswapped copy, cannot pass).
     Separately, run() fails unless the copy reads back INACTIVE (live only; the selftest does not cover it);
  1. placeholders: the live copy holds no REPLACE_WITH_* / XXXX-id token that the live original does not hold;
  2. scripts/diff-workflow-copy.py, live original vs live copy (test phase): only the data nodes, the test path
     and the temporary trigger differ;
  3. scripts/check-content-parity.py's own check_live_not_sanitised (the "LIVE IS SANITISED" check), run on the
     live copy against the generated copy.
The copy is created INACTIVE and the pre-cutover modes never activate anything. It prints names, counts and the
copy's workflow id; never a credential, a host or a secret.

AFTER THE CUTOVER (ruling K1, 2026-10-25): since D6b the five copies are the LIVE production holders and their originals
are parked until D6c, so each copy's reference is ITS OWN committed export (n8n/workflow.<x>.copy.sanitized.json, paired
in scripts/check-exports-parity.sh's PAIRS/ROLES, read through scripts/pair_roles.py) as committed at a git revision,
never the working tree. *The node-level copy↔original comparison (checks 0-3 above, the diff tool's test and swap
phases) is RETIRED for the post-cutover modes:* it proved copy = original during the migration, but the copies now
evolve on purpose and the originals go at D6c, so measuring a copy against its original would call every intended
engine change drift. What the post-cutover modes measure instead (post_cutover_check): the copy equals its committed
export under scripts/check-content-parity.py's own mask and projection, plus connections; the trigger is on the
production path (the parked original's live path) and the temporary trigger absent; every spec data node is Postgres on
a real credential; the Turnstile literal, where the copy carries one, is ON; no placeholder the live copy lacks, and none
by shape or by the export's inventory (check_live_not_sanitised); the export's settings equal the live settings. Settings
copy↔original parity (scripts/settings_parity.py) STAYS, unchanged: an engine edit never touches settings. The ORDER
guard (check_swap_declared), check-before-write and read-back-after-write stay. No ledger, no hash list.

Usage (env: N8N_API_KEY, CF_ACCESS_CLIENT_ID/SECRET; N8N_HOST or CLAUDE.local.md):
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID [--update COPY_ID]
      (--update, --verify, --turnstile, --turnstile-swapped and --swap refuse the original's id and any target that
       is active or not named as the spec; they are exclusive, one target per run)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --verify COPY_ID
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --turnstile off|on COPY_ID
      (the Turnstile window on an INACTIVE copy in the TEST phase: one literal in its Load Config; 'off' checks that
       nothing else differs, 'on' runs the full verify. The check runs on the patched content BEFORE the write (red:
       no write) and again on the live copy after it. Settings the spec allowlists are never sent, on any write.)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --turnstile-swapped off|on COPY_ID
      (the same window on an INACTIVE copy after the cutover: trigger on the original's live path, no temporary
       trigger. Judged by window_check, i.e. post_cutover_check against the copy's committed export at HEAD (K1; it
       was swap_check against the live original until then): 'off' with the one literal put back in memory, 'on' as
       is; before the write and again after it. The body keeps the live settings as they are.
       *Why a separate flag and not phase detection:* a swapped copy is the PRODUCTION holder, so lowering its gate is
       a production act. The operator names the phase, the check measures it, and the run proceeds only when both
       agree; a copy that is not in the named phase is refused before any write, in either direction.
       *ORDER guard (ruling 2026-10-24), 'off' and 'on' alike, before the content check and before any write:* the
       swap must be DECLARED, i.e. scripts/check-exports-parity.sh's ROLES (read through scripts/pair_roles.py, the one
       parser) holds a line for exactly this original and this copy with LIVE = copy; and the original must read back
       INACTIVE from n8n. A swapped-shaped copy is not yet a production holder: it becomes one when the swap is declared
       in a commit and the original is parked, and only then is lowering its gate a legitimate production act rather
       than a window opened on a workflow nobody has handed production to. The test-phase --turnstile reads neither:
       there the original is active and ROLES says original, and that is correct.)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --swap COPY_ID
      (D6b's cutover write, MIGRATION-PLAN §3a/§3t: refused unless the original AND the copy both read back
       INACTIVE. The copy's trigger moves to the original's live path and its temporary trigger is removed; the
       swap-phase checks run on that content BEFORE the write and again on the live copy after it. It never
       activates anything: the operator's next step does, one workflow at a time.)
  (--update, --verify, the test-phase --turnstile and --swap are the PRE-cutover modes and stay as they were: each
   refuses an active target, and after D6b every copy is active, so none of them has a legitimate target any more.)
  ⛔ --engine-edit and --restore below are DISABLED (ENGINE_EDIT_ENABLED = False): main() refuses them before any API call
     until the final review's two critical recovery findings are closed (docs/PHASE-7-PLAN.md §4d).
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --engine-edit COPY_ID [--from-rev REV]
      (K1's edit path for an ACTIVE post-cutover copy: puts the copy's committed export at REV (default HEAD) live.
       Rollback = the same command with the previous commit's REV.
       *THE RULE: an engine edit never changes a masked value* — a credential, a chat id, the Turnstile secret, the
       calendar id are operator/credential operations, not engine edits. So the PUT body is the target export with each
       sanitize placeholder replaced by the LIVE copy's value at the SAME path (node name + key path; an embedded one,
       the calendar id in Load Config's code, by the text before it on its line); a renamed placeholder changes nothing.
       Refused before any write: a placeholder with no live counterpart at its path (a new node needing a credential:
       an operator step) or whose live value is itself placeholder-shaped; an export failing the sanitise check (a
       masked value written out); an export that renames or drops a node carrying a live webhookId (every live
       webhookId is kept by node name). The live settings go as they are.
       Also BEFORE any write: the ORDER guard; the live copy's published graph equals its draft (else "pre-edit" is
       ambiguous); no Turnstile window open on the live copy (its literal [] or true); a Load Config that mentions
       turnstile holds exactly one exact literal; post_cutover_check on the body (Turnstile literal ON, production
       path, no temporary trigger, no placeholder the live copy lacks, settings unchanged); red → exit 1, nothing
       touched. No executable difference → nothing written (exit 0). Then: deactivate → PUT → read back = committed
       export AND, raw, = the body sent → activate → read back active, published = draft → where the copy carries a
       Turnstile literal, the window script's own dummy-token probe (403 turnstile_failed, executed by the copy, none
       by the original; an exception in it is a failure).
       *While the copy is out of production* SIGINT/SIGTERM/SIGHUP are NOTED, never raised: the forward steps stop at
       the next step boundary, the recovery runs to its end, and every message goes through _say(), which swallows
       OSError (a hung-up terminal after an ssh drop raises EIO on print). *If anything after the deactivation is red,
       raises or was signalled:* the copy goes back to the pre-edit live body held in memory — read first, PUT only
       when its content changed, read back raw — re-activated and probed by the PRE body's gate → exit 3 (edit NOT
       applied, production on its pre-edit body, verified). A deactivate that does not take stops the run with no PUT
       (exit 1). If the rollback is not proven → exit 4 SAFETY: the copy is left INACTIVE, except when its content is
       proven back and only the probe answered something other than 200, where it is left ACTIVE and the message says
       so; nothing is activated in its place (never the original). For the INACTIVE case the message prints the exact
       --restore command, with the revision the run started from.
       The pre-edit body holds real ids and the Turnstile secret: it is held in memory, but like every body this script
       sends it passes through a 0600 temp file (api()), deleted when curl returns, and so does the header file, which
       carries the API key and the Access secret; a kill -9 can leave either. While the copy is inactive the production
       path has no holder.)
  python3 scripts/deploy-workflow-copy.py db/copies/<x>.json --original-id ID --restore COPY_ID [--from-rev REV]
      (Recovery for a copy a SAFETY exit left INACTIVE, and only for that: the same name, spec, ORDER-guard and sanitise
       checks, but the target must be INACTIVE. Fills by path from the inactive copy's OWN live values, which the rule
       above makes sound (no edit ever changes them); PUT → read back = export and, raw, = body → activate → prove.
       Writes no pre-edit body anywhere. Exit 0 proven · 1 refused before any write · 4 SAFETY as above.)
  python3 scripts/deploy-workflow-copy.py --selftest      (offline: the checks on simulated live workflows)
"""
import contextlib
import copy as _copy
import glob
import importlib.util
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The post-cutover edit and restore modes stay off until the final review's two CRITICAL findings are fixed and
# re-reviewed (PHASE-7-PLAN §4d): a second Ctrl-C during recovery can leave the copy INACTIVE with no restore command
# printed, and the printed restore revision is the failed edit's, not production's. Off is the cheap failure mode.
ENGINE_EDIT_ENABLED = False
PLACEHOLDER = re.compile(r'REPLACE_WITH_[A-Z0-9_]+|\b(?:app|tbl)X{14}\b')


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [path]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return mod


BUILD = _module('scripts/build-workflow-copy.py', 'build_workflow_copy')   # import-safe: an offline sibling, itself guarded
DIFF = _module('scripts/diff-workflow-copy.py', 'diff_workflow_copy')      # import-safe: an offline sibling, itself guarded


# ── the three checks (pure: no network) ──────────────────────────────────────────────────────────────────────
def check_placeholders(live_orig, live_copy, ref_name='the live original'):
    extra = set(PLACEHOLDER.findall(json.dumps(live_copy))) - set(PLACEHOLDER.findall(json.dumps(live_orig)))
    return [f'placeholder in the live copy that {ref_name} does not hold: {p}' for p in sorted(extra)]


def check_diff(live_orig, live_copy, spec):
    return DIFF.compare(live_orig, live_copy, set(spec['nodes']), phase='test',
                        temp_trigger=(spec.get('temp_trigger') or {}).get('name'),
                        trigger=(spec.get('trigger') or {}).get('node'),
                        settings_allow=spec.get('settings_allow', {}))


_MODS = {}


def _ccp():
    """scripts/check-content-parity.py, loaded once: its sanitise checks, mask and projection are the one truth."""
    if 'ccp' not in _MODS:
        _MODS['ccp'] = _module('scripts/check-content-parity.py', 'check_content_parity')
    return _MODS['ccp']


def _settings_parity():
    if 'sp' not in _MODS:
        _MODS['sp'] = _module('scripts/settings_parity.py', 'settings_parity')
    return _MODS['sp']


def copy_settings(settings, spec):
    """A copy's settings from its original's: the spec's "absent" keys dropped, its "value" keys set to exactly that value."""
    sp, allow = _settings_parity(), spec.get('settings_allow') or {}
    out = {k: v for k, v in (settings or {}).items() if k not in sp.absent_keys(allow)}
    out.update(sp.carried(allow))
    return out


def check_not_sanitised(live_copy, generated):
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            _ccp().check_live_not_sanitised(live_copy, generated)
    except SystemExit as e:
        if e.code:
            return ['check-content-parity: ' + ' '.join(out.getvalue().split())[:300]]
    return []


def _data_nodes_real(wf, spec):
    errs, N = [], {n['name']: n for n in wf['nodes']}
    for name in spec['nodes']:
        n = N.get(name) or {}
        cred = ((n.get('credentials') or {}).get('postgres') or {}).get('id', '')
        if n.get('type') != 'n8n-nodes-base.postgres' or not cred or PLACEHOLDER.search(cred):
            errs.append(f"data node '{name}' is not a Postgres node on a real credential")
    return errs


def check_swapped(live_copy, spec):
    """The copy must actually BE a copy: every spec data node is a Postgres node on a real (non-placeholder)
    credential, the trigger sits on the spec's test path, and a declared temporary trigger exists. Without this,
    the original itself (or an unswapped copy) passed the three checks above (pre-push audit, 2026-10-20)."""
    errs, N = _data_nodes_real(live_copy, spec), {n['name']: n for n in live_copy['nodes']}
    trig = spec.get('trigger')
    if trig and (N.get(trig['node']) or {}).get('parameters', {}).get('path') != trig['test_path']:
        errs.append(f"trigger '{trig['node']}' is not on the spec's test path")
    temp = spec.get('temp_trigger')
    if temp and temp['name'] not in N:
        errs.append(f"the declared temporary trigger '{temp['name']}' is missing")
    return errs


def verify(live_orig, live_copy, generated, spec):
    errs = check_swapped(live_copy, spec) + check_placeholders(live_orig, live_copy) \
        + check_diff(live_orig, live_copy, spec) + check_not_sanitised(live_copy, generated)
    return errs


def assemble(generated, live_orig, spec, pg_credential):
    """The live original + the generated copy's data-layer delta. Nothing else comes from the generated copy."""
    LO = {n['name']: n for n in live_orig['nodes']}
    data, trig, temp = set(spec['nodes']), spec.get('trigger') or {}, spec.get('temp_trigger') or {}
    nodes = []
    for g in generated['nodes']:
        if g['name'] in data:
            n = _copy.deepcopy(g)
            n['credentials'] = {'postgres': dict(pg_credential)}
        elif g['name'] == temp.get('name'):
            n = _copy.deepcopy(g)
        else:
            n = _copy.deepcopy(LO[g['name']])
            if g['name'] == trig.get('node'):
                n['parameters']['path'] = trig['test_path']
        if n['type'] == 'n8n-nodes-base.webhook':
            n['webhookId'] = str(uuid.uuid4())
        nodes.append(n)
    # Keys the spec allowlists as ABSENT are never sent: the guard now reds a copy that carries one (D4-1), and
    # sending Main's `availableInMCP: true` would create the copy exactly as exposed as Main. Keys it allowlists as a
    # VALUE are sent with exactly that value (T-4, 2026-10-26): the copy must be narrower than its original.
    settings = copy_settings(live_orig.get('settings') or generated.get('settings') or {}, spec)
    return {'name': generated['name'], 'nodes': nodes, 'connections': generated['connections'], 'settings': settings}


# ── the Turnstile window on a COPY (MIGRATION-PLAN §4.5, D4 plan §6) ─────────────────────────────────────────
# The copy carries Main's Turnstile gate, so drills with a dummy token need it lowered ON THE COPY ONLY. The change
# is ONE literal in the copy's Load Config; nothing else may move, and the copy must be inactive while it is
# written (a PUT to an active workflow publishes at once). Restoring it must leave the copy verify-green again.
TS_NODE = 'Load Config'
TS_LITERAL = re.compile(r'turnstile\s*:\s*\{\s*enabled\s*:\s*(true|false)\s*\}')


def turnstile_patch(wf, state):
    """Return a copy of wf with the one Turnstile literal set to `state` ('off' or 'on'). Refuses (ValueError)
    unless Load Config holds exactly ONE such literal and it is currently in the opposite state."""
    want, have = ('false', 'true') if state == 'off' else ('true', 'false')
    out = _copy.deepcopy(wf)
    node = next((n for n in out['nodes'] if n['name'] == TS_NODE), None)
    code = ((node or {}).get('parameters') or {}).get('jsCode', '')
    found = TS_LITERAL.findall(code)
    if len(found) != 1:
        raise ValueError(f"'{TS_NODE}' holds {len(found)} Turnstile literal(s), not exactly one — refused")
    if found[0] != have:
        raise ValueError(f'the Turnstile literal is already {found[0]!r}, so turning it {state} changes nothing — refused')
    node['parameters']['jsCode'] = TS_LITERAL.sub(lambda m: m.group(0).replace(have, want), code, count=1)
    return out


def turnstile_check(live_orig, live_copy, generated, spec, state):
    """The TEST-phase window, before AND after its write. 'on': verify() (the copy is a plain test-phase copy again).
    'off': the copy with that ONE literal put back in memory must pass verify(), so nothing else can ride along with
    the lowered gate. (A second, textual comparison of the two Load Configs was written first; its mutant survived,
    because this check already reds every other difference, so it was removed rather than kept as a check that
    measures nothing.) The post-cutover window is window_check(), against the copy's committed export (K1); the
    'swap' phase this function had until then judged it against the live original and is gone with that comparison."""
    if state == 'on':
        return verify(live_orig, live_copy, generated, spec)
    try:
        restored = turnstile_patch(live_copy, 'on')
    except ValueError as e:
        return [f'turnstile off: {e}']
    return verify(live_orig, restored, generated, spec)


ROLES_FILE = None   # None = pair_roles' own default, the committed check-exports-parity.sh; the selftest points it at a fixture


def check_swap_declared(original_id, copy_id, original_active):
    """--turnstile-swapped's ORDER guard (ruling 2026-10-24): the reason the window is refused, or None.
    (1) the swap is DECLARED: a ROLES line for exactly this pair, LIVE = copy; (2) the original is PARKED: read back
    inactive. ROLES is read through pair_roles, so there is one parser; a declaration it cannot read declares nothing."""
    try:
        _, roles = _module('scripts/pair_roles.py', 'pair_roles').load(ROLES_FILE)
    except (ValueError, OSError) as e:
        return f'ROLES does not read, so nothing is declared ({e})'
    role = next((r for r in roles if r['orig'] == original_id and r['copy'] == copy_id), None)
    if role is None:
        return 'ROLES has no line for this original and this copy, so the swap is not declared'
    if role['live'] != 'copy':
        return f"ROLES declares the {role['live']} live, so the swap is not declared (flip the pair to copy first)"
    if original_active is not False:
        return 'the original is not INACTIVE; park it first (§3a), its copy is not the production holder yet'
    return None


# ── the SWAP (D6b, MIGRATION-PLAN §3a, §3t) ─────────────────────────────────────────────────────────────────
# §3a: deactivate the original → put the copy on the production path → activate the copy → measure. This is the
# middle step only. Its content comes from the LIVE copy (already verified, real credentials, Load Config as live),
# with exactly two changes: the trigger takes the ORIGINAL's live path (read, never hard-coded), and the declared
# temporary trigger is removed (Q13: it must be gone at the swap, proven by the diff tool's swap phase).
def swap_patch(live_copy, live_orig, spec):
    out = _copy.deepcopy(live_copy)
    trig, temp = spec.get('trigger') or {}, (spec.get('temp_trigger') or {}).get('name')
    if trig:
        prod = next(n for n in live_orig['nodes'] if n['name'] == trig['node'])['parameters']['path']
        next(n for n in out['nodes'] if n['name'] == trig['node'])['parameters']['path'] = prod
    if temp:
        out['nodes'] = [n for n in out['nodes'] if n['name'] != temp]
        (out.get('connections') or {}).pop(temp, None)
    out['settings'] = copy_settings(out.get('settings') or {}, spec)
    return out


def swap_check(live_orig, live_copy, generated, spec):
    """The swap phase: only the data nodes may differ from the original (the trigger on the original's path, no
    temporary trigger: the diff tool's swap phase reds both), each data node a Postgres node on a REAL credential
    (the diff tool allows a data node's credentials to change, so it cannot see a placeholder there), and no
    placeholder the original lacks (the diff tool also allows a data node's PARAMETERS to change).
    *Declared:* verify()'s not-sanitised check was in this list first and its mutant SURVIVED: in the swap phase every
    non-data node must equal the live original, so a sanitised copy is already red in the diff. It was removed rather
    than kept as a check that measures nothing (the same call as the Turnstile window's textual comparison).
    `generated` stays in the signature so the swap and verify checks are called alike."""
    errs = _data_nodes_real(live_copy, spec)
    errs += check_placeholders(live_orig, live_copy)
    errs += DIFF.compare(live_orig, live_copy, set(spec['nodes']), phase='swap',
                         temp_trigger=(spec.get('temp_trigger') or {}).get('name'),
                         trigger=(spec.get('trigger') or {}).get('node'),
                         settings_allow=spec.get('settings_allow', {}))
    return errs


# ── after the cutover (ruling K1): each copy is judged by ITS OWN committed export ───────────────────────────
# The reasons and the retired comparison are in the module docstring. Everything below is pure except the `git show`.
def copy_export_path(spec_path, copy_id):
    """The copy's committed export, through PAIRS (pair_roles, the one parser). It must be the export named after the
    spec (db/copies/<x>.json → n8n/workflow.<x>.copy.sanitized.json), so a mis-paired id cannot hand another
    workflow's export in as the reference."""
    pairs, _ = _module('scripts/pair_roles.py', 'pair_roles').load(ROLES_FILE)
    want = f'n8n/workflow.{os.path.splitext(os.path.basename(spec_path))[0]}.copy.sanitized.json'
    if pairs.get(copy_id) != want:
        raise ValueError(f"PAIRS pairs this copy with {pairs.get(copy_id) or 'no export'}, not {want}")
    return want


def committed_export(path, rev='HEAD'):
    """The export as COMMITTED at `rev`, never the working tree: an uncommitted edit is not a reference. A revision
    must start with a letter or digit, so it can never be read by git as an option."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/~^@{}-]*', rev or ''):
        raise ValueError(f'{rev!r} is not a plain git revision')
    out = subprocess.run(['git', '-C', ROOT, 'show', f'{rev}:{path}'], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        raise ValueError(f'git show {rev}:{path} failed: ' + ' '.join(out.stderr.split())[:160])
    return json.loads(out.stdout)


def resolve_rev(rev):
    """The full commit hash `rev` names (for the SAFETY message's restore command, so it cannot drift with HEAD)."""
    out = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--verify', '--quiet', f'{rev}^{{commit}}'], capture_output=True,
                         text=True, stdin=subprocess.DEVNULL)
    return out.stdout.strip() or rev


# Execution fields check-content-parity's projection does not compare (a gap it records itself). Compared HERE only:
# widening ccp's projection would change all ten parity runs, and that is a separate decision. Round B removes
# `alwaysOutputData` on Purge nodes, and without this neither the edit's diff nor its read-back could see it land.
EXEC_FLAGS = ('alwaysOutputData', 'executeOnce', 'retryOnFail')


def content_drift(live, committed, smap=None):
    """check-content-parity's own content_drift (its placeholder-only mask, executable node sets and projection; one
    truth), plus what
    a copy judged by its export needs beside it: per node the three execution flags (absent = False, n8n omits a
    default) and typeVersion (compared exactly; carried on one side only is a difference), the CONNECTIONS, which
    ccp's content half does not compare and an engine edit rewires, and the name. `smap={}` compares two LIVE bodies
    raw (the rollback read-back): a mask derived from two real bodies would map a changed credential onto the old one
    and hide it."""
    ccp = _ccp()
    smap = ccp.placeholder_smap(live, committed) if smap is None else smap
    errs = ccp.content_drift(live, committed, smap)
    L, C = ccp._executable(live), ccp._executable(committed)
    for nm in sorted(set(L) & set(C)):
        lv, cv = L[nm], C[nm]
        diff = [f'{k} (committed={bool(cv.get(k))!r} live={bool(lv.get(k))!r})' for k in EXEC_FLAGS
                if bool(lv.get(k)) != bool(cv.get(k))]
        if ('typeVersion' in lv) != ('typeVersion' in cv) or lv.get('typeVersion') != cv.get('typeVersion'):
            diff.append(f"typeVersion (committed={cv.get('typeVersion', 'absent')!r} live={lv.get('typeVersion', 'absent')!r})")
        if diff:
            errs.append(f"execution fields differ in '{nm}': {diff} (committed != live)")
    if json.dumps(live.get('connections') or {}, sort_keys=True) != json.dumps(committed.get('connections') or {}, sort_keys=True):
        errs.append('the connections differ (live copy != committed export)')
    if live.get('name') != committed.get('name'):
        errs.append('the workflow name differs (live copy != committed export)')
    return errs


def _ts_literal(wf):
    code = next((n for n in wf.get('nodes') or [] if n.get('name') == TS_NODE), {}).get('parameters', {}).get('jsCode', '')
    return TS_LITERAL.findall(code or '')


def _ts_shape_errs(wf, side):
    """A Load Config that mentions turnstile but does not hold EXACTLY one `turnstile: { enabled: … }` literal (e.g.
    `{ enabled: false, mode: "x" }`) would make every Turnstile check above see "no gate" and skip itself: red instead."""
    code = next((n for n in wf.get('nodes') or [] if n.get('name') == TS_NODE), {}).get('parameters', {}).get('jsCode', '') or ''
    if 'turnstile' in code.lower() and len(TS_LITERAL.findall(code)) != 1:
        return [f"the {side}'s {TS_NODE} mentions turnstile but holds {len(TS_LITERAL.findall(code))} exact Turnstile "
                'literal(s), not one: its gate cannot be judged']
    return []


def prod_path(live_orig, spec):
    """The production path is the PARKED original's live trigger path: read, never hard-coded (as swap_patch does)."""
    trig = (spec.get('trigger') or {}).get('node')
    return ((next((n for n in live_orig['nodes'] if n['name'] == trig), None) or {}).get('parameters') or {}).get('path') if trig else None


def post_cutover_check(cand, committed, spec, prod, ref, original_settings):
    """A post-cutover copy, or a body about to become one, against the copy's committed export. `ref` is the live copy
    as it stands before the write (the source of "no placeholder the live copy lacks"); `original_settings` the parked
    original's live settings, for the settings parity that stays."""
    errs = _data_nodes_real(cand, spec)
    trig, temp = spec.get('trigger') or {}, (spec.get('temp_trigger') or {}).get('name')
    N = {n['name']: n for n in cand['nodes']}
    if trig and (not prod or ((N.get(trig['node']) or {}).get('parameters') or {}).get('path') != prod):
        errs.append(f"trigger '{trig['node']}' is not on the production path")
    if temp and temp in N:
        errs.append(f"the temporary trigger '{temp}' is present")
    # The content comparison below only proves cand == export; this proves the export's gate is UP. A committed export
    # carrying a lowered literal would otherwise go live green, and every later 'on' would restore it to off.
    errs += _ts_shape_errs(committed, 'committed export') + _ts_shape_errs(cand, 'candidate')
    lit_c, lit = _ts_literal(committed), _ts_literal(cand)
    if (lit_c or lit) and (lit_c != ['true'] or lit != ['true']):
        errs.append(f'the Turnstile literal is not ON (committed export {lit_c}, candidate {lit})')
    errs += content_drift(cand, committed)
    sp = _settings_parity()
    errs += sp.committed_vs_live(committed.get('settings'), cand.get('settings'))
    errs += sp.copy_vs_original(original_settings, cand.get('settings'), spec.get('settings_allow', {}))
    errs += check_placeholders(ref, cand, 'the live copy before the write')
    errs += check_not_sanitised(cand, committed)
    return errs


def window_check(cand, committed, spec, prod, state, ref, original_settings):
    """--turnstile-swapped after the cutover, before AND after its write. 'on': post_cutover_check as is. 'off': the
    candidate with its ONE Turnstile literal put back on in memory must pass it, so that literal is the only thing
    that may differ from the committed export ("except the one Turnstile literal")."""
    if state == 'on':
        return post_cutover_check(cand, committed, spec, prod, ref, original_settings)
    try:
        restored = turnstile_patch(cand, 'on')
    except ValueError as e:
        return [f'turnstile off: {e}']
    return post_cutover_check(restored, committed, spec, prod, ref, original_settings)


def _path_seg(i, v):
    """A list element is addressed by its `name` when it has one (n8n's bodyParameters, assignments), so a parameter
    inserted before it does not shift the secret onto its neighbour; otherwise by index."""
    return f"[name={v['name']}]" if isinstance(v, dict) and isinstance(v.get('name'), str) else f'[{i}]'


def _strings(o, path=''):
    """(path, string) for every string leaf of a node, paths as _path_seg builds them."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, f'{path}/{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _strings(v, path + _path_seg(i, v))
    elif isinstance(o, str):
        yield path, o


def _set_at(node, path, value):
    """Set the string leaf at `path` (as _strings yields it) inside `node`."""
    parts = re.findall(r'/([^/\[]+)|\[name=([^\]]+)\]|\[(\d+)\]', path)
    cur, last = node, None
    for i, (key, name, idx) in enumerate(parts):
        nxt = cur[key] if key else (next(v for v in cur if isinstance(v, dict) and v.get('name') == name) if name else cur[int(idx)])
        if i == len(parts) - 1:
            last = (key, name, idx)
            break
        cur = nxt
    key, name, idx = last
    if key:
        cur[key] = value
    elif name:
        cur[next(j for j, v in enumerate(cur) if isinstance(v, dict) and v.get('name') == name)] = value
    else:
        cur[int(idx)] = value


def _shaped(v):
    return any(re.search(pat, v, re.I) for pat in _ccp().PLACEHOLDER_SHAPES)


def fill_by_path(live, committed, removable=()):
    """The --engine-edit / --restore PUT body. THE RULE: an engine edit never changes a masked value — a credential, a
    chat id, the Turnstile secret, the calendar id are operator/credential operations, not engine edits. So every
    sanitize placeholder in the target export is replaced by the LIVE copy's value at the SAME path (node name + key
    path); a placeholder renamed in the export therefore changes nothing. A placeholder embedded in a longer string
    (the calendar id inside Load Config's code) is located in the live string by the text before it on its line,
    which must occur exactly once there. Refused (ValueError) when a placeholder has no live counterpart at its path
    (a new node needing a credential: an operator step) or the live value there is itself placeholder-shaped (except
    the exact token check-content-parity exempts as live by design). Also: every live node's webhookId kept by node
    name, and an export that renames or drops a node carrying one is refused — except a node named in `removable` (the
    approved delta's remove_nodes, passed by workflow-step put; ruling 2026-10-26, R3) that is NOT a trigger: n8n gives
    Telegram nodes a webhookId too, and the approved Owner Actions delta removes one. A trigger (diff-workflow-copy's own
    _is_trigger, the one definition: webhook, `…Trigger` and the legacy trigger types) is never removable here;
    settings: live, as they are."""
    ph_re = re.compile(r'REPLACE_WITH_[A-Za-z0-9_]+(?:@[A-Za-z0-9.\-]+)?|(?:app|tbl|viw|rec|fld)[A-Za-z0-9]*X{4,}[A-Za-z0-9]*')
    L = {n['name']: n for n in live['nodes']}
    nodes, missing = _copy.deepcopy(committed['nodes']), []
    for n in nodes:
        lstr = dict(_strings(L[n['name']])) if n['name'] in L else {}
        for path, val in list(_strings(n)):
            if not ph_re.search(val):
                continue
            where = f"'{n['name']}' {path}"
            lv = lstr.get(path)
            if lv is None:
                missing.append(f'{where}: no live value at this path')
                continue
            if ph_re.fullmatch(val):
                new, pieces = lv, [lv]
            else:
                new, pieces = val, []
                for m in ph_re.finditer(val):
                    before = val[:m.start()].rsplit('\n', 1)[-1].lstrip()
                    after = val[m.end():m.end() + 1]
                    start = lv.index(before) + len(before) if before and after and lv.count(before) == 1 else -1
                    end = lv.find(after, start) if start >= 0 else -1
                    if end < 0:
                        pieces = None
                        break
                    pieces.append(lv[start:end])
                    new = new.replace(m.group(0), lv[start:end], 1)
                if pieces is None:
                    missing.append(f'{where}: an embedded placeholder cannot be located in the live text')
                    continue
            if any(_shaped(v) and v not in _ccp().EXEMPT for v in pieces):
                missing.append(f'{where}: the live value is itself placeholder-shaped')
                continue
            _set_at(n, path, new)
    if missing:
        raise ValueError('an engine edit never changes a masked value, and these cannot be filled from the live copy '
                         '(an operator step): ' + '; '.join(missing[:4]))
    hooks = {n['name']: n['webhookId'] for n in live['nodes'] if n.get('webhookId')}
    rm = set(removable)
    droppable = {n['name'] for n in live['nodes'] if n['name'] in rm and not DIFF._is_trigger(n)}
    gone = sorted(set(hooks) - {n['name'] for n in nodes} - droppable)
    if gone:
        raise ValueError(f'the export renames or drops node(s) carrying a live webhookId: {gone}')
    for n in nodes:
        if n['name'] in hooks:
            n['webhookId'] = hooks[n['name']]
    return {'name': live['name'], 'nodes': nodes, 'connections': _copy.deepcopy(committed['connections']),
            'settings': _copy.deepcopy(live.get('settings') or {})}


# ── n8n API (the real curl: urllib is refused at the edge) ───────────────────────────────────────────────────
def _host():
    h = os.environ.get('N8N_HOST')
    if not h:
        m = re.search(r'^N8N_HOST=\s*(\S+)', open(os.path.join(ROOT, 'CLAUDE.local.md'), encoding='utf-8').read(), re.M)
        h = m.group(1) if m else None
    if not h:
        sys.exit('deploy-workflow-copy: N8N_HOST is not set and CLAUDE.local.md has none')
    return h


def api(method, path, body=None):
    hdr = {'X-N8N-API-KEY': os.environ['N8N_API_KEY'], 'Content-Type': 'application/json',
           'CF-Access-Client-Id': os.environ.get('CF_ACCESS_CLIENT_ID', ''),
           'CF-Access-Client-Secret': os.environ.get('CF_ACCESS_CLIENT_SECRET', '')}
    args = ['curl', '-4', '-s', '-m', '60', '-X', method, '-w', '\n%{http_code}', f'https://{_host()}/api/v1{path}']
    files = []
    try:
        # Secrets go in a 0600 header file, never on the command line (argv is readable by other local users).
        fd, hpath = tempfile.mkstemp(suffix='.hdr'); files.append(hpath)
        with os.fdopen(fd, 'w') as f:
            f.write(''.join(f'{k}: {v}\n' for k, v in hdr.items()))
        args += ['-H', '@' + hpath]
        if body is not None:
            fd, bpath = tempfile.mkstemp(suffix='.json'); files.append(bpath)
            with os.fdopen(fd, 'w') as f:
                json.dump(body, f)
            args += ['--data-binary', '@' + bpath]
        out = subprocess.run(args, capture_output=True, text=True).stdout
    finally:
        for p in files:
            os.unlink(p)
    raw, code = out.rsplit('\n', 1)
    try:
        return int(code), json.loads(raw)
    except ValueError:
        return int(code), raw


def _workflow(wid, meta=False):
    st, w = api('GET', f'/workflows/{wid}')
    if st != 200:
        sys.exit(f'deploy-workflow-copy: GET workflow failed [{st}]')
    wf = {k: w.get(k) for k in ('name', 'nodes', 'connections', 'settings')}
    return (wf, {'active': w.get('active'), 'name': w.get('name')}) if meta else wf


def _pg_credential():
    st, d = api('GET', '/credentials')
    pg = [c for c in (d.get('data') or []) if c.get('type') == 'postgres'] if st == 200 else []
    if len(pg) != 1:
        sys.exit(f'deploy-workflow-copy: expected exactly one postgres credential, found {len(pg)}')
    return {'id': pg[0]['id'], 'name': pg[0]['name']}


def _draft(d):
    return {k: d.get(k) for k in ('name', 'nodes', 'connections', 'settings')}


def _say(msg):
    """Every message while a copy is out of production (and in its recovery): output must never be what stops the
    recovery. On a hung-up terminal (SIGHUP after an ssh drop) print raises EIO, into a closed pipe EPIPE."""
    try:
        print(msg, flush=True)
    except (OSError, ValueError):
        pass


def _read(wid):
    """The full workflow, or None. Never sys.exit: inside an opened edit a failed read must reach the rollback."""
    st, d = api('GET', f'/workflows/{wid}')
    return d if st == 200 and isinstance(d, dict) else None


def _set_active(wid, on):
    st, _ = api('POST', f"/workflows/{wid}/{'activate' if on else 'deactivate'}")
    got = (_read(wid) or {}).get('active')
    _say(f"  {'activate' if on else 'deactivate'} the copy: [{st}] · read back active {got}")
    return got is on


def _published_matches_draft(full):
    """check-content-parity's own published-vs-draft check, on an ACTIVE workflow; its errors as a list."""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            _ccp().check_published_matches_draft(full)
    except SystemExit as e:
        if e.code:
            return ['published vs draft: ' + ' '.join(out.getvalue().split())[:300]]
    return []


def turnstile_probe(path, original_id, copy_id):
    """The committed window script's own end-of-window measurement (dummy_probe): a dummy token to the production path
    must answer 403 turnstile_failed, executed by the copy, none by the original. (ok, status)."""
    return _module('scripts/turnstile-window.py', 'turnstile_window').dummy_probe(path, original_id, copy_id)


def run(spec_path, original_id, update=None, verify_only=None, turnstile=None, swap=None, turnstile_swapped=None,
        engine_edit=None, from_rev=None, restore=None):
    # One target per run. With --turnstile beside --update/--verify the guards below checked ONE id and the PUT went
    # to the OTHER, unchecked: the production original's id would have taken the copy (pre-push audit, 2026-10-23).
    if sum(x is not None for x in (update, verify_only, turnstile, swap, turnstile_swapped, engine_edit, restore)) > 1:
        sys.exit('deploy-workflow-copy: refused — --update, --verify, --turnstile, --turnstile-swapped, --swap, '
                 '--engine-edit and --restore are exclusive (one target per run)')
    if from_rev is not None and engine_edit is None and restore is None:
        sys.exit('deploy-workflow-copy: refused — --from-rev belongs to --engine-edit or --restore')
    spec = json.load(open(spec_path, encoding='utf-8'))
    generated = BUILD.build(spec)
    live_orig, om = _workflow(original_id, meta=True)
    if engine_edit:
        return engine_edit_run(spec_path, spec, original_id, live_orig, om, engine_edit, from_rev or 'HEAD')
    if restore:
        return restore_run(spec_path, spec, original_id, live_orig, om, restore, from_rev or 'HEAD')
    window = turnstile or turnstile_swapped
    target = verify_only or update or swap or (window or (None, None))[1]
    if target:
        if target == original_id:
            sys.exit('deploy-workflow-copy: refused — the copy id equals the original id')
        tw, m = _workflow(target, meta=True)
        if m['name'] != spec['name'] or m['active'] is not False:
            sys.exit(f"deploy-workflow-copy: refused — the target must be the INACTIVE workflow named '{spec['name']}'")
        T = {n['name']: n for n in tw['nodes']}
        if any((T.get(name) or {}).get('type') != 'n8n-nodes-base.postgres' for name in spec['nodes']):
            # Name and state can collide; an original's data nodes are Airtable, a copy's are Postgres.
            sys.exit('deploy-workflow-copy: refused — the target\'s data nodes are not Postgres, so it is not a copy')
    if swap:
        assert swap == target, 'the swap write must go to the id the guards above checked'
        if om['active'] is not False:
            # Two active workflows cannot hold one path (S1: the second activation is refused with 409), but the
            # copy is not activated here; the point is ORDER: §3a deactivates the original first, and this write is
            # only safe after that step has happened and been read back.
            sys.exit('deploy-workflow-copy: refused — the original is not INACTIVE; deactivate it first (§3a)')
        wf = swap_patch(tw, live_orig, spec)
        errs = swap_check(live_orig, wf, generated, spec)
        if errs:
            print('SWAP REFUSED before any write — the swap-phase content is not clean:')
            for e in errs:
                print('  - ' + e)
            return 1
        st, d = api('PUT', f'/workflows/{swap}', wf)
        if st != 200:
            sys.exit(f'deploy-workflow-copy: swap write failed [{st}]')
        live_copy, m = _workflow(swap, meta=True)
        errs = swap_check(live_orig, live_copy, generated, spec)
        if m['active'] is not False:
            errs.append('the copy is not inactive (read back from n8n)')
        if errs:
            print('SWAP CHECK FAILED after the write — do not activate this copy:')
            for e in errs:
                print('  - ' + e)
            return 1
        trig = (spec.get('trigger') or {}).get('node')
        print(f"swap written · swap phase green · {'trigger on the original' + chr(39) + 's live path' if trig else 'no webhook trigger moved'}"
              f" · temporary trigger absent · original and copy both inactive (nothing activated)")
        return 0
    if window:
        # The phase is NAMED by the flag and MEASURED by the check; a copy in the other phase is red before the write.
        phase = 'post-cutover' if turnstile_swapped else 'test'
        state, wid = window
        assert wid == target, 'the Turnstile write must go to the id the guards above checked'
        if turnstile_swapped:
            # The ORDER guard: lowering a swapped copy's gate is a production act only once the swap is declared and
            # the original parked. Before the content check, so a refusal here never depends on what the copy holds.
            why = check_swap_declared(original_id, wid, om['active'])
            if why:
                sys.exit(f'deploy-workflow-copy: refused before any write — {why}')
            try:
                committed = committed_export(copy_export_path(spec_path, wid))
            except (ValueError, OSError) as e:
                sys.exit(f'deploy-workflow-copy: refused before any write — no committed export to judge by ({e})')
            prod, ref = prod_path(live_orig, spec), _copy.deepcopy(tw)
            check = lambda wf: window_check(wf, committed, spec, prod, state, ref, live_orig.get('settings'))
        else:
            check = lambda wf: turnstile_check(live_orig, wf, generated, spec, state)
        try:
            wf = turnstile_patch(tw, state)
        except ValueError as e:
            sys.exit(f'deploy-workflow-copy: {e}')
        if not turnstile_swapped:
            # Test phase only: after the cutover the body keeps the live settings as they are, and an allowlisted key
            # on the live copy is red in the settings parity before the write instead of being dropped silently.
            wf['settings'] = copy_settings(wf.get('settings') or {}, spec)
        # Check BEFORE the write. The first version PUT first and checked after, so a red copy (or a copy in the
        # wrong phase) was already written with its gate lowered by the time the check said so.
        errs = check(wf)
        if errs:
            print(f'TURNSTILE {state.upper()} REFUSED before any write — the {phase}-phase content is not clean:')
            for e in errs:
                print('  - ' + e)
            return 1
        st, d = api('PUT', f'/workflows/{wid}', wf)
        if st != 200:
            sys.exit(f'deploy-workflow-copy: Turnstile write failed [{st}]')
        # And AFTER it, on what n8n actually holds: a 200 does not prove the write landed as sent.
        live_copy, m = _workflow(wid, meta=True)
        errs = check(live_copy)
        if m['active'] is not False:
            errs.append('the copy is not inactive (read back from n8n)')
        if errs:
            print(f'TURNSTILE {state.upper()} CHECK FAILED after the write — no drill may start on this copy:')
            for e in errs:
                print('  - ' + e)
            return 1
        print(f"turnstile {state} on the copy ({phase} phase) · check OK before and after the write — "
              f"{'only the one literal differs' if state == 'off' else phase + '-phase check green'}"
              f"{' from the committed export' if turnstile_swapped else ''} · active read back: {m['active']}")
        return 0
    if verify_only:
        wid = verify_only
    else:
        wf = assemble(generated, live_orig, spec, _pg_credential())
        if update:
            st, d = api('PUT', f'/workflows/{update}', wf)
            wid = update
        else:
            st, d = api('POST', '/workflows', wf)
            wid = d.get('id') if isinstance(d, dict) else None
        if st != 200 or not wid:
            sys.exit(f'deploy-workflow-copy: write failed [{st}]')
    live_copy, m = _workflow(wid, meta=True)
    if not verify_only:
        print(f"deployed '{wf['name']}' ({len(wf['nodes'])} nodes) as workflow {wid} · {'updated' if update else 'created'}"
              f" · active read back: {m['active']}")
    errs = verify(live_orig, live_copy, generated, spec)
    if m['active'] is not False:
        errs.append('the copy is not inactive (read back from n8n)')
    if errs:
        print('VERIFY FAILED — no drill may start on this copy:')
        for e in errs:
            print('  - ' + e)
        return 1
    print(f'verify OK — no new placeholder · only the {len(spec["nodes"])} data node(s), the test path and the '
          f'temporary trigger differ from the live original · not sanitised')
    return 0


# ── --engine-edit / --restore (K1): a copy's committed export put live, recovered when the result is not proven ──
# While a copy is out of production, SIGINT/SIGTERM/SIGHUP are NOTED, never raised: an exception raised by a signal can
# land anywhere, including inside the recovery (a second Ctrl-C, an ssh drop). The forward steps check the note at
# each step boundary and stop into the recovery; the recovery ignores it and runs to its end.
_WINDOW = {'forward': False, 'signals': []}


class Stopped(Exception):
    """A noted signal, raised at the next forward step boundary."""


def _note_signal(signum, _frame):
    _WINDOW['signals'].append(signal.Signals(signum).name)


def _stop_check():
    if _WINDOW['forward'] and _WINDOW['signals']:
        raise Stopped('signal ' + ', '.join(_WINDOW['signals']))


def _guarded(forward, recover):
    """forward() → [] (proven), a list of errors, or an int exit code to return as is; any exception is an error.
    recover(errs) runs on errors, and anything it raises is a SAFETY exit 4. Returns None when forward was proven."""
    old = {sg: signal.signal(sg, _note_signal) for sg in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    _WINDOW.update(forward=True, signals=[])
    try:
        try:
            errs = forward()
        except BaseException as e:
            errs = [f'{type(e).__name__}: {str(e)[:160]}']
        _WINDOW['forward'] = False
        if isinstance(errs, int) or not errs:
            return errs if isinstance(errs, int) else None
        try:
            return recover(errs)
        except BaseException as e:
            _say(f'SAFETY: the recovery itself raised {type(e).__name__}: {str(e)[:160]}. The copy may be INACTIVE and '
                 'the original stays parked, so the production path may have NO holder.')
            return 4
    finally:
        _WINDOW['forward'] = False
        for sg, h in old.items():
            signal.signal(sg, h)


def _prove(wid, check, prod, original_id, gate, after_write):
    """Read back (check) → activate unless already active → read back active, published = draft → the dummy-token probe
    where the copy carries a Turnstile gate. (errors, probe status); no errors = every step proven. `after_write`: the
    copy must read back INACTIVE first (a PUT to an active workflow would have published at once). Any exception in
    the probe is a probe failure (status 'error'), never an escape."""
    got = _read(wid)
    _stop_check()
    if got is None:
        return ['the copy could not be read back'], None
    errs = check(_draft(got))
    if after_write and got.get('active') is not False:
        errs.append('the copy is not inactive after the write (read back)')
    if errs:
        return errs, None
    if got.get('active') is not True and not _set_active(wid, True):
        return ['the copy did not read back ACTIVE after the activation'], None
    _stop_check()
    got = _read(wid)
    errs = _published_matches_draft(got) if got else ['the copy could not be read back after the activation']
    if errs or not gate:
        return errs, None
    try:
        ok, code = turnstile_probe(prod, original_id, wid)
    except Exception as e:                    # e.g. the window script's Refused from executions_since
        ok, code = False, 'error'
        _say(f'  the dummy-token probe raised {type(e).__name__}: {str(e)[:120]}')
    return ([] if ok else [f'the dummy-token probe answered {code}, not 403 turnstile_failed through the copy']), code


def _write_and_prove(wid, body, check, prod, original_id, gate):
    """On an INACTIVE copy: PUT, then _prove."""
    st, _ = api('PUT', f'/workflows/{wid}', body)
    _stop_check()
    if st != 200:
        return [f'the write answered {st}'], None
    return _prove(wid, check, prod, original_id, gate, after_write=True)


def _restore_cmd(spec_path, original_id, copy_id, rev_hash):
    return (f'python3 scripts/deploy-workflow-copy.py {os.path.relpath(spec_path, ROOT)} --original-id {original_id} '
            f'--restore {copy_id} --from-rev {rev_hash}')


def _safety(restore_cmd, active):
    if active:
        _say('SAFETY: the copy is ACTIVE on its proven body, but the dummy-token probe is not proven: measure it again with '
             'python3 scripts/turnstile-window.py --precheck-only (read-only plus one dummy-token probe).')
    else:
        _say('SAFETY: the copy is INACTIVE and the original stays parked, so the production path has NO holder. Restore '
             f'it (the run started from that revision; --from-rev may name an earlier one):\n  {restore_cmd}')
    return 4


def _edit_rollback(wid, pre, prod, original_id, gate, restore_cmd):
    """Something after the deactivation is red: the copy goes back to its pre-edit live body (held in memory), judged
    RAW against it. It reads FIRST: when the content is still the pre-edit body (the write was refused outright, or
    never sent), it does not PUT again — a refused body shape is refused twice — and goes straight to activate +
    prove. `gate` is the PRE body's. 3 = rolled back and proven. 4 = SAFETY: the copy is left INACTIVE, except when
    its content is proven back and only the probe answered something other than 200 (it is then left ACTIVE, and the
    message says so); nothing is activated in its place, never the original."""
    _say('ROLLING BACK to the pre-edit body held in memory:')
    raw = lambda wf: content_drift(wf, pre, smap={})
    now = _read(wid)
    untouched = now is not None and isinstance(now.get('nodes'), list) and not raw(_draft(now))
    if untouched:
        _say('  the copy still holds its pre-edit body: no PUT, activate and prove')
        errs, code = _prove(wid, raw, prod, original_id, gate, after_write=False)
    elif (now or {}).get('active') is not False and not _set_active(wid, False):
        errs, code = ['the copy did not deactivate for the rollback'], None
    else:
        errs, code = _write_and_prove(wid, pre, raw, prod, original_id, gate)
    if not errs:
        _say('ROLLED BACK — the edit is NOT applied; the copy holds its pre-edit body again, active, published = draft'
             + (', dummy token 403' if gate else '') + '. The committed export and production now differ.')
        return 3
    for e in errs:
        _say('  - ' + e)
    return _settle(wid, code, restore_cmd)


def _settle(wid, code, restore_cmd):
    """After an unproven recovery: a copy whose content is proven and only its probe answered non-200 stays ACTIVE;
    anything else (content unproven, or a gate that answered 200) is stopped. SAFETY either way."""
    if code is not None and code != 200:
        return _safety(restore_cmd, active=True)
    if (_read(wid) or {}).get('active') is not False:
        _say('  the copy is active on an unproven body (or its gate answered 200) — deactivating it')
        _set_active(wid, False)
    return _safety(restore_cmd, active=False)


def _target(spec_path, spec, original_id, om, copy_id, rev, want_active):
    """The checks --engine-edit and --restore share before anything is touched: (live draft, full, export path,
    committed export, rev hash). sys.exit on any refusal."""
    if copy_id == original_id:
        sys.exit('deploy-workflow-copy: refused — the copy id equals the original id')
    # The ORDER guard first: a write to a copy is a production act only once its swap is declared and its original parked.
    why = check_swap_declared(original_id, copy_id, om['active'])
    if why:
        sys.exit(f'deploy-workflow-copy: refused before any write — {why}')
    full = _read(copy_id)
    if full is None or full.get('name') != spec['name'] or full.get('active') is not want_active:
        sys.exit(f"deploy-workflow-copy: refused — the target must be the {'ACTIVE' if want_active else 'INACTIVE'} "
                 f"workflow named '{spec['name']}'")
    try:
        export = copy_export_path(spec_path, copy_id)
        committed = committed_export(export, rev)
    except (ValueError, OSError) as e:
        sys.exit(f'deploy-workflow-copy: refused before any write — {e}')
    # The export must pass the sanitise check: a non-placeholder chat id, secret, calendar or credential id in it would
    # be an engine edit changing a masked value, which the rule forbids (and which the public repo forbids anyway).
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            _ccp().check_sanitised(committed)
    except SystemExit:
        sys.exit('deploy-workflow-copy: refused before any write — the export fails the sanitise check: '
                 + ' '.join(out.getvalue().split())[:200])
    return _draft(full), full, export, committed, resolve_rev(rev)


def engine_edit_run(spec_path, spec, original_id, live_orig, om, copy_id, rev):
    live, full, export, committed, rev_hash = _target(spec_path, spec, original_id, om, copy_id, rev, want_active=True)
    try:
        body = fill_by_path(live, committed)
    except ValueError as e:
        sys.exit(f'deploy-workflow-copy: refused before any write — {e}')
    prod, gate = prod_path(live_orig, spec), bool(_ts_literal(committed) or _ts_literal(live))
    check = lambda wf: post_cutover_check(wf, committed, spec, prod, live, live_orig.get('settings'))
    # After the write the copy must equal the export AND, raw, the body sent: the body is what says which real value
    # stands behind each placeholder (a value that drifted behind a placeholder is otherwise invisible).
    after = lambda wf: check(wf) + content_drift(wf, body, smap={})
    # Everything that can be judged without writing is judged here, BEFORE the deactivation: a red body never costs
    # production its holder. The published graph must equal the draft, or "the pre-edit body" would be ambiguous.
    errs = _data_nodes_real(live, spec) + _published_matches_draft(full) + check(body) + _ts_shape_errs(live, 'live copy')
    if _ts_literal(live) not in ([], ['true']):
        # A lowered literal on the live copy means a Turnstile window is open: the edit would restore the gate under
        # the window's feet, and the window's own close would then find nothing to restore.
        errs.append(f"the live copy's Turnstile literal is {_ts_literal(live)}: a Turnstile window is open — close it first")
    if errs:
        print(f'ENGINE EDIT REFUSED before any write — nothing touched (export at {rev}):')
        for e in errs:
            print('  - ' + e)
        return 1
    changes = content_drift(live, committed)
    if not changes:
        print(f'engine edit: no executable difference from the committed export at {rev} (sticky notes, positions and '
              'renamed placeholders are not differences) — nothing written, nothing (de)activated')
        return 0
    print(f'engine edit from {rev}: {len(changes)} difference(s) to put live:')
    for c in changes:
        print('  · ' + c)
    pre, pre_gate = _copy.deepcopy(live), bool(_ts_literal(live))
    restore = _restore_cmd(spec_path, original_id, copy_id, rev_hash)

    def forward():
        if _set_active(copy_id, False):
            _stop_check()
            return _write_and_prove(copy_id, body, after, prod, original_id, gate)[0]
        now = _read(copy_id)
        if now and now.get('active') is True and isinstance(now.get('nodes'), list) \
                and not content_drift(_draft(now), pre, smap={}):
            _say('ENGINE EDIT STOPPED — a deactivate was sent and did not take; no PUT was sent; the copy reads back '
                 'ACTIVE on its pre-edit body')
            return 1
        return ['a deactivate was sent and its read-back is not ACTIVE-and-unchanged (inactive or unknown)']

    def recover(errs):
        _say('ENGINE EDIT FAILED after the deactivation' + (f" (signals noted: {', '.join(_WINDOW['signals'])})"
                                                             if _WINDOW['signals'] else '') + ':')
        for e in errs:
            _say('  - ' + e)
        return _edit_rollback(copy_id, pre, prod, original_id, pre_gate, restore)
    rc = _guarded(forward, recover)
    if rc is None:
        _say(f'engine edit written · read back = the committed export at {rev} and = the body sent · active · published '
             '= draft' + (' · dummy token 403' if gate else ' · no Turnstile gate on this copy, no probe'))
        return 0
    return rc


def restore_run(spec_path, spec, original_id, live_orig, om, copy_id, rev):
    """--restore: an INACTIVE copy (a SAFETY exit left it so) put back on the committed export at `rev`, filled by path
    from its OWN live values, which no engine edit ever changes; then PUT → raw read-back → activate → prove."""
    live, _, export, committed, rev_hash = _target(spec_path, spec, original_id, om, copy_id, rev, want_active=False)
    try:
        body = fill_by_path(live, committed)
    except ValueError as e:
        sys.exit(f'deploy-workflow-copy: refused before any write — {e}')
    prod, gate = prod_path(live_orig, spec), bool(_ts_literal(committed))
    check = lambda wf: post_cutover_check(wf, committed, spec, prod, live, live_orig.get('settings'))
    after = lambda wf: check(wf) + content_drift(wf, body, smap={})
    errs = _data_nodes_real(live, spec) + check(body)
    if errs:
        print(f'RESTORE REFUSED before any write — nothing touched (export at {rev}):')
        for e in errs:
            print('  - ' + e)
        return 1
    restore = _restore_cmd(spec_path, original_id, copy_id, rev_hash)
    last = {'code': None}

    def forward():
        errs, last['code'] = _write_and_prove(copy_id, body, after, prod, original_id, gate)
        return errs

    def recover(errs):
        _say('RESTORE FAILED:')
        for e in errs:
            _say('  - ' + e)
        return _settle(copy_id, last['code'], restore)
    rc = _guarded(forward, recover)
    if rc is None:
        _say(f'restored · read back = the committed export at {rev} and = the body sent · active · published = draft'
             + (' · dummy token 403' if gate else ' · no Turnstile gate on this copy, no probe'))
        return 0
    return rc


# ── selftest: the checks on simulated live workflows, every spec ─────────────────────────────────────────────
def _simulated_live(sanitized, keep=()):
    """A stand-in for a live workflow: every committed placeholder replaced by a real-looking value, except `keep`."""
    s = json.dumps(sanitized)
    for i, ph in enumerate(sorted(set(PLACEHOLDER.findall(s)) - set(keep))):
        s = s.replace(ph, f'Live{i:02d}Value{uuid.uuid5(uuid.NAMESPACE_URL, ph).hex[:8]}')
    return json.loads(s)


def _simulated_live_copy(spec_file):
    """(committed export at HEAD, a stand-in for the live post-cutover copy built from it)."""
    x = os.path.splitext(os.path.basename(spec_file))[0]
    committed = committed_export(f'n8n/workflow.{x}.copy.sanitized.json')
    return committed, _simulated_live(committed, keep=_ccp().EXEMPT)   # what live holds as a placeholder by design


def selftest():
    ok = True
    # T-4 (2026-10-26): copy_settings drops the "absent" keys and sets the "value" keys to exactly their value. No real
    # spec carries a value entry until R3, so it is checked here on a synthetic allowlist.
    syn = {'settings_allow': {'binaryMode': {'covers': 'absent', 'ruling': 'selftest'},
                              'saveDataSuccessExecution': {'covers': 'value', 'value': 'none', 'ruling': 'selftest'}}}
    for label, got, want in [
            ('copy_settings: absent dropped, value set, the rest kept',
             copy_settings({'executionOrder': 'v1', 'binaryMode': 'separate', 'saveDataSuccessExecution': 'all'}, syn),
             {'executionOrder': 'v1', 'saveDataSuccessExecution': 'none'}),
            ('copy_settings: the value is set even when the original lacks the key',
             copy_settings({'executionOrder': 'v1'}, syn), {'executionOrder': 'v1', 'saveDataSuccessExecution': 'none'}),
            ('copy_settings: no allowlist → unchanged', copy_settings({'executionOrder': 'v1'}, {}), {'executionOrder': 'v1'})]:
        good = got == want
        ok &= good
        print(f"{'✓' if good else '✗'} {label}" + ('' if good else f' — got {got!r}'))
    specs = sorted(glob.glob(os.path.join(ROOT, 'db', 'copies', '*.json')))
    assert specs, 'no copy specs under db/copies/'
    for f in specs:
        spec = json.load(open(f, encoding='utf-8'))
        generated = BUILD.build(spec)
        live_orig = _simulated_live(json.load(open(os.path.join(ROOT, spec['original']), encoding='utf-8')))
        clean = assemble(generated, live_orig, spec, {'id': 'LiveCredential01', 'name': 'Postgres account'})
        other = next(n['name'] for n in clean['nodes'] if n['name'] not in spec['nodes']
                     and n['type'] not in ('n8n-nodes-base.webhook', 'n8n-nodes-base.stickyNote'))
        placeholder_copy = _copy.deepcopy(clean)
        nd = next(n for n in placeholder_copy['nodes'] if n['name'] == other)
        nd['parameters']['_probe'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
        drifted = _copy.deepcopy(clean)
        next(n for n in drifted['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
        sanitized_whole = _copy.deepcopy(generated)          # what the first D3b deploy effectively was
        for n in sanitized_whole['nodes']:
            if n['name'] in spec['nodes']:
                n['credentials'] = {'postgres': {'id': 'LiveCredential01', 'name': 'Postgres account'}}
        data_param_ph = _copy.deepcopy(clean)                 # only the two placeholder checks can see this one:
        dn = next(n for n in data_param_ph['nodes'] if n['name'] in spec['nodes'])   # diff allows data-node parameters,
        dn['parameters']['query'] += ' -- REPLACE_WITH_SOMETHING'                    # swapped looks at the credential only
        data_ph = _copy.deepcopy(clean)                       # the diff tool allows a data node's credentials to change
        next(n for n in data_ph['nodes'] if n['name'] in spec['nodes'])['credentials'] = \
            {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}}
        no_order = _copy.deepcopy(clean)                     # a key the API might drop that NO ruling allows
        no_order['settings'] = {k: v for k, v in (no_order.get('settings') or {}).items() if k != 'executionOrder'}
        cases = [('clean copy', clean, True), ('settings: executionOrder missing on the copy', no_order, False), (f"placeholder in a non-data node ('{other}')", placeholder_copy, False),
                 (f"non-data node changed ('{other}')", drifted, False),
                 ('a data node still carrying the credential placeholder', data_ph, False),
                 ('the ORIGINAL itself passed as the copy', _copy.deepcopy(live_orig), False),
                 ("a placeholder inside a data node's parameters", data_param_ph, False)]
        for key in sorted(_settings_parity().absent_keys(spec.get('settings_allow', {}))):   # assemble()'s output LACKS each
            if key in (clean.get('settings') or {}):
                cases.append((f"assemble() sent the allowlisted '{key}'", clean, False))
            kept = _copy.deepcopy(clean)                       # what the helper produced before D4-1, if the original has it
            if key in (live_orig.get('settings') or {}):
                kept['settings'] = dict(kept.get('settings') or {}, **{key: live_orig['settings'][key]})
                cases.append((f"settings: allowlisted '{key}' kept with the original's value", kept, False))
            other_val = _copy.deepcopy(clean); other_val['settings'] = dict(other_val.get('settings') or {}, **{key: '__different__'})
            cases.append((f"settings: allowlisted '{key}' with a different value", other_val, False))
        lcode = next((n for n in live_orig['nodes'] if n['name'] == TS_NODE), {}).get('parameters', {}).get('jsCode', '')
        ts_cases = []
        if len(TS_LITERAL.findall(lcode)) == 1:               # the copies that carry a Turnstile gate (Main)
            off = turnstile_patch(clean, 'off')
            ts_cases.append(('turnstile off: only the one literal changed', off, 'off', True))
            rider = _copy.deepcopy(off)                        # something else slips in with the lowered gate
            rn = next(n for n in rider['nodes'] if n['name'] == TS_NODE)
            rn['parameters']['jsCode'] = rn['parameters']['jsCode'].replace('enabled: true', 'enabled: false', 1)
            ts_cases.append(('turnstile off: a second literal changed with it', rider, 'off', False))
            ride2 = _copy.deepcopy(off)
            next(n for n in ride2['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
            ts_cases.append((f"turnstile off: another node ('{other}') changed with it", ride2, 'off', False))
            ts_cases.append(('turnstile on: restored copy', turnstile_patch(off, 'on'), 'on', True))
            ts_cases.append(("turnstile 'on' check while the literal is still off", off, 'on', False))
            for label, wf, st_ in (('turnstile off twice', off, 'off'), ('turnstile on while already on', clean, 'on')):
                try:
                    turnstile_patch(wf, st_)
                    print(f'✗ {os.path.basename(f)} · {label}: NOT refused'); ok = False
                except ValueError as e:
                    print(f'✓ {os.path.basename(f)} · {label}: refused — {e}')
            two = _copy.deepcopy(clean)
            tn = next(n for n in two['nodes'] if n['name'] == TS_NODE)
            tn['parameters']['jsCode'] += '\n// turnstile: { enabled: true }'
            try:
                turnstile_patch(two, 'off')
                print(f'✗ {os.path.basename(f)} · two Turnstile literals: NOT refused'); ok = False
            except ValueError as e:
                print(f'✓ {os.path.basename(f)} · two Turnstile literals: refused — {e}')
        for label, wf, st_, want_green in ts_cases:
            errs = turnstile_check(live_orig, wf, generated, spec, st_)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        if PLACEHOLDER.search(json.dumps([n for n in generated['nodes'] if n['name'] not in spec['nodes']])):
            cases.append(('the generated (sanitized) copy deployed whole', sanitized_whole, False))
        # The SWAP (D6b): the clean deployed copy, patched for the swap, must be green in the swap phase, and every
        # way of getting the swap content wrong must be red.
        swapped = swap_patch(clean, live_orig, spec)
        sw_cases = [('swap: the clean copy, patched', swapped, True),
                    ('swap: the deployed copy NOT patched (test path / temporary trigger)', clean, not (spec.get('trigger') or spec.get('temp_trigger'))),
                    ('swap: the original itself passed as the copy', _copy.deepcopy(live_orig), False)]
        sw_other = _copy.deepcopy(swapped); next(n for n in sw_other['nodes'] if n['name'] == other)['parameters']['_probe'] = 'changed'
        sw_cases.append((f"swap: a non-data node changed ('{other}')", sw_other, False))
        sw_ph = _copy.deepcopy(swapped)
        next(n for n in sw_ph['nodes'] if n['name'] in spec['nodes'])['credentials'] = \
            {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}}
        sw_cases.append(('swap: a data node on the credential placeholder', sw_ph, False))
        sw_qph = _copy.deepcopy(swapped)                      # only the placeholder check can see this one
        next(n for n in sw_qph['nodes'] if n['name'] in spec['nodes'])['parameters']['query'] += ' -- REPLACE_WITH_SOMETHING'
        sw_cases.append(("swap: a placeholder inside a data node's parameters", sw_qph, False))
        if spec.get('temp_trigger') and spec['temp_trigger']['name'] in {n['name'] for n in clean['nodes']}:
            kept = _copy.deepcopy(swapped)
            kept['nodes'].append(next(n for n in clean['nodes'] if n['name'] == spec['temp_trigger']['name']))
            kept['connections'][spec['temp_trigger']['name']] = clean['connections'][spec['temp_trigger']['name']]
            sw_cases.append(('swap: the temporary trigger left in', kept, False))
        if spec.get('trigger'):
            stay = _copy.deepcopy(swapped)
            next(n for n in stay['nodes'] if n['name'] == spec['trigger']['node'])['parameters']['path'] = spec['trigger']['test_path']
            sw_cases.append(('swap: the trigger left on its test path', stay, False))
        if len(TS_LITERAL.findall(lcode)) == 1:
            sw_cases.append(('swap: the Turnstile literal still lowered', swap_patch(turnstile_patch(clean, 'off'), live_orig, spec), False))
            # The test-phase window still reds a swapped-shaped copy (it is judged against the live original).
            for label, wf, st_ in (('turnstile (test phase) off on the SWAPPED copy (wrong phase)', turnstile_patch(swapped, 'off'), 'off'),
                                   ('turnstile (test phase) on on the SWAPPED copy (wrong phase)', swapped, 'on')):
                errs = turnstile_check(live_orig, wf, generated, spec, st_)
                ok = ok and bool(errs)
                print(f"{'✓' if errs else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        # AFTER THE CUTOVER (K1): the live copy against ITS OWN committed export, no longer against the original.
        committed, plive = _simulated_live_copy(f)
        prod, osets = prod_path(live_orig, spec), live_orig.get('settings')
        pother = next(n['name'] for n in plive['nodes'] if n['name'] not in spec['nodes']
                      and n['type'] not in ('n8n-nodes-base.webhook', 'n8n-nodes-base.stickyNote'))

        def pvariant(fn):
            w = _copy.deepcopy(plive)
            fn(w)
            return w
        N_ = lambda w, name: next(n for n in w['nodes'] if n['name'] == name)
        pc_cases = [('post-cutover: the live copy equals its committed export', plive, True),
                    (f"post-cutover: a non-data node ('{pother}') differs from the committed export",
                     pvariant(lambda w: N_(w, pother)['parameters'].__setitem__('_probe', 'changed')), False),
                    (f"post-cutover: a placeholder in a non-data node ('{pother}')",
                     pvariant(lambda w: N_(w, pother)['parameters'].__setitem__('_probe', 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID')), False),
                    ('post-cutover: a data node on the credential placeholder',
                     pvariant(lambda w: N_(w, next(iter(spec['nodes']))).__setitem__('credentials', {'postgres': {'id': 'REPLACE_WITH_POSTGRES_CREDENTIAL_ID', 'name': 'Postgres account'}})), False),
                    ('post-cutover: a node the committed export does not have',
                     pvariant(lambda w: w['nodes'].append(dict(_copy.deepcopy(N_(w, pother)), name='Extra Node', id='extra'))), False),
                    ('post-cutover: one connection removed',
                     pvariant(lambda w: w['connections'].pop(sorted(w['connections'])[0])), False),
                    ('post-cutover: settings: executionOrder missing',
                     pvariant(lambda w: w['settings'].pop('executionOrder', None)), False),
                    ('post-cutover: the ORIGINAL itself passed as the copy', _copy.deepcopy(live_orig), False),
                    ('post-cutover: the test-phase deployed copy (assembled from the original)', clean, not (spec.get('trigger') or spec.get('temp_trigger')))]
        for key in sorted(_settings_parity().absent_keys(spec.get('settings_allow', {}))):
            pc_cases.append((f"post-cutover: settings: allowlisted '{key}' present on the copy",
                             pvariant(lambda w, key=key: w['settings'].__setitem__(key, (osets or {}).get(key, '__x__'))), False))
        if spec.get('trigger'):
            pc_cases.append(('post-cutover: the trigger on its test path',
                             pvariant(lambda w: N_(w, spec['trigger']['node'])['parameters'].__setitem__('path', spec['trigger']['test_path'])), False))
        if spec.get('temp_trigger'):
            pc_cases.append(('post-cutover: the temporary trigger present',
                             pvariant(lambda w: w['nodes'].append({'name': spec['temp_trigger']['name'], 'type': 'n8n-nodes-base.webhook',
                                                                   'parameters': {'path': 'temp'}, 'id': 'tmp'})), False))
        pc_cases = [(label, wf, committed, plive, want) for label, wf, want in pc_cases]
        for key in sorted(_settings_parity().absent_keys(spec.get('settings_allow', {}))):   # equal on both sides: only the settings parity sees it
            both = lambda w, key=key: dict(w, settings=dict(w['settings'], **{key: (osets or {}).get(key, '__x__')}))
            pc_cases.append((f"post-cutover: the export AND the copy both carry the allowlisted '{key}'", both(plive), both(committed), plive, False))
        # Round B's shape (ccp's projection cannot see this one): the export lacks alwaysOutputData on a node where the
        # live copy carries it. Built on the LIVE side, so it exists whether or not the committed export has the flag
        # anywhere (after E1 the Purge export has none, and an `if` here silently dropped the case).
        aod = next(n['name'] for n in committed['nodes'] if n['type'] == 'n8n-nodes-base.postgres')
        dropped = _copy.deepcopy(committed)
        N_(dropped, aod).pop('alwaysOutputData', None)
        live_aod = _copy.deepcopy(plive)
        N_(live_aod, aod)['alwaysOutputData'] = True
        pc_cases.append((f"post-cutover: the export drops alwaysOutputData on '{aod}' while the live copy keeps it", live_aod, dropped, live_aod, False))
        tg = next((n['name'] for n in plive['nodes'] if n['type'] == 'n8n-nodes-base.telegram'), None)
        if tg:                                               # R1: a masked path whose COMMITTED value is not a placeholder is drift
            c_expr = _copy.deepcopy(committed)
            N_(c_expr, tg)['parameters']['chatId'] = '={{ $json.ownerChat }}'
            pc_cases.append((f"post-cutover: R1 the export's chatId on '{tg}' is an expression, live still holds the value",
                             plive, c_expr, plive, False))
        tv_up = pvariant(lambda w: N_(w, pother).__setitem__('typeVersion', (N_(w, pother).get('typeVersion') or 1) + 1))
        tv_gone = pvariant(lambda w: N_(w, pother).pop('typeVersion', None))
        pc_cases += [(f"post-cutover: typeVersion differs on '{pother}'", tv_up, committed, plive, False),
                     (f"post-cutover: typeVersion carried by the export only ('{pother}')", tv_gone, committed, plive, False),
                     (f"post-cutover: executeOnce set on '{pother}' live only", pvariant(lambda w: N_(w, pother).__setitem__('executeOnce', True)), committed, plive, False),
                     (f"post-cutover: retryOnFail set on '{pother}' live only", pvariant(lambda w: N_(w, pother).__setitem__('retryOnFail', True)), committed, plive, False),
                     (f"post-cutover: executeOnce: false written out live, absent in the export ('{pother}')",
                      pvariant(lambda w: N_(w, pother).__setitem__('executeOnce', False)), committed, plive, True)]
        for token in sorted(_ccp().EXEMPT):                  # exempt from the shape scan, so only the "live copy lacks" check sees it
            if token in json.dumps(committed):
                real_ref = json.loads(json.dumps(plive).replace(token, 'LiveRealValue01'))
                pc_cases.append((f'post-cutover: brings back {token} where the live copy holds a real value', plive, committed, real_ref, False))
        for label, wf, comm, ref, want_green in pc_cases:
            errs = post_cutover_check(wf, comm, spec, prod, ref, osets)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        if _ts_literal(committed):
            # The export's gate is checked, not only the copy's equality to it: both lowered alike is still red.
            errs = post_cutover_check(turnstile_patch(plive, 'off'), turnstile_patch(committed, 'off'), spec, prod, plive, osets)
            ok = ok and bool(errs)
            print(f"{'✓' if errs else '✗'} {os.path.basename(f)} · post-cutover: the committed export AND the copy both lowered: "
                  f"{'green' if not errs else 'red — ' + errs[0][:90]}")
            # The window (--turnstile-swapped) after the cutover: only the ONE literal may differ from the export.
            p_off = turnstile_patch(plive, 'off')
            p_rider = _copy.deepcopy(p_off)                    # a second literal (here the first `enabled: true`) lowered with it
            rn = N_(p_rider, TS_NODE)
            rn['parameters']['jsCode'] = rn['parameters']['jsCode'].replace('enabled: true', 'enabled: false', 1)
            p_ride2 = _copy.deepcopy(p_off)
            N_(p_ride2, pother)['parameters']['_probe'] = 'changed'
            win_cases = [('window off: only the one literal changed', p_off, 'off', True),
                         ('window off: a second literal changed with it', p_rider, 'off', False),
                         (f"window off: another node ('{pother}') changed with it", p_ride2, 'off', False),
                         ('window on: restored copy', turnstile_patch(p_off, 'on'), 'on', True),
                         ("window 'on' check while the literal is still off", p_off, 'on', False),
                         ('window off on the test-phase copy (wrong phase)', turnstile_patch(clean, 'off'), 'off', False)]
            for label, wf, st_, want_green in win_cases:
                errs = window_check(wf, committed, spec, prod, st_, plive, osets)
                good = (not errs) == want_green
                ok = ok and good
                print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        for label, wf, want_green in sw_cases:
            errs = swap_check(live_orig, wf, generated, spec)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
        for label, live_copy, want_green in cases:
            errs = verify(live_orig, live_copy, generated, spec)
            good = (not errs) == want_green
            ok = ok and good
            print(f"{'✓' if good else '✗'} {os.path.basename(f)} · {label}: {'green' if not errs else 'red — ' + errs[0][:90]}")
    # The target selection in main()/run(): every pair of write modes is refused BEFORE any API call.
    global api, ROLES_FILE, turnstile_probe, committed_export
    real_api, calls, real_roles, fixtures = api, [], ROLES_FILE, []
    real_probe, real_committed_export = turnstile_probe, committed_export
    api = lambda *a, **k: calls.append(a) or (599, {})

    def roles_fixture(line):
        """A check-exports-parity.sh-shaped file with fake ids, so no case depends on what the committed ROLES says."""
        pairs = (('O1', 'workflow'), ('O2', 'workflow.reminders'), ('O3', 'workflow.purge'), ('C1', 'workflow.main.copy'),
                 ('C2', 'workflow.reminders.copy'), ('C3', 'workflow.purge.copy'))
        with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as t:
            t.write('PAIRS=(\n' + ''.join(f'  "{i}:n8n/{p}.sanitized.json"\n' for i, p in pairs) + ')\n\n'
                    f'ROLES=(\n  "{line}"\n)\n')
        fixtures.append(t.name)
        return t.name
    try:
        for flags in (['--update', 'C1', '--turnstile', 'off', 'O1'], ['--verify', 'C1', '--turnstile', 'on', 'O1'],
                      ['--update', 'C1', '--verify', 'C1']):
            argv = ['deploy', specs[0], '--original-id', 'O1', *flags]
            try:
                rc = main(argv)
            except SystemExit:
                rc = 'SystemExit (main() did not refuse first)'
            try:
                run(specs[0], 'O1', **{'update': 'C1', 'turnstile': ('off', 'O1')}) if '--turnstile' in flags else None
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and not calls and ('--turnstile' not in flags or rrc == 'refused')
            ok = ok and good
            print(f"{'✓' if good else '✗'} {' '.join(f for f in flags if f.startswith('--'))} together: main() exit {rc}, run() {rrc if '--turnstile' in flags else '—'}, API calls {len(calls)}")
        for other_flag in (['--update', 'C1'], ['--verify', 'C1'], ['--turnstile', 'on', 'C1']):
            calls.clear()
            rc = main(['deploy', specs[0], '--original-id', 'O1', '--swap', 'C1', *other_flag])
            try:
                run(specs[0], 'O1', swap='C1', **({'update': 'C1'} if other_flag[0] == '--update' else {'verify_only': 'C1'} if other_flag[0] == '--verify' else {'turnstile': ('on', 'C1')}))
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and rrc == 'refused' and not calls
            ok = ok and good
            print(f"{'✓' if good else '✗'} --swap with {other_flag[0]}: main() exit {rc}, run() {rrc}, API calls {len(calls)}")
        for other_flag, kw in ((['--update', 'C1'], {'update': 'C1'}), (['--verify', 'C1'], {'verify_only': 'C1'}),
                               (['--swap', 'C1'], {'swap': 'C1'}), (['--turnstile', 'on', 'C1'], {'turnstile': ('on', 'C1')})):
            calls.clear()
            try:
                rc = main(['deploy', specs[0], '--original-id', 'O1', '--turnstile-swapped', 'off', 'C1', *other_flag])
            except SystemExit:
                rc = 'SystemExit (main() did not refuse first)'
            try:
                run(specs[0], 'O1', turnstile_swapped=('off', 'C1'), **kw)
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and rrc == 'refused' and not calls
            ok = ok and good
            print(f"{'✓' if good else '✗'} --turnstile-swapped with {other_flag[0]}: main() exit {rc}, run() {rrc}, API calls {len(calls)}")
        for other_flag, kw in ((['--update', 'C1'], {'update': 'C1'}), (['--swap', 'C1'], {'swap': 'C1'}),
                               (['--turnstile-swapped', 'on', 'C1'], {'turnstile_swapped': ('on', 'C1')}), ([], {})):
            calls.clear()
            argv = ['deploy', specs[0], '--original-id', 'O1', *(other_flag or ['--from-rev', 'HEAD'])]
            argv += ['--engine-edit', 'C1'] if other_flag else []
            rc = main(argv)
            try:
                run(specs[0], 'O1', **(dict(kw, engine_edit='C1') if kw else {'from_rev': 'HEAD'}))
                rrc = 'not refused'
            except SystemExit:
                rrc = 'refused'
            good = rc == 2 and rrc == 'refused' and not calls
            ok = ok and good
            print(f"{'✓' if good else '✗'} --engine-edit with {other_flag[0] if other_flag else '--from-rev, but no --engine-edit'}: "
                  f"main() exit {rc}, run() {rrc}, API calls {len(calls)}")
        # --swap's ORDER guard, on a simulated instance: the original and the copy must both read back inactive,
        # and the one PUT goes to the copy's id. (Spec: Main; its copy simulated as the clean deployed copy.)
        mspec_path = os.path.join(ROOT, 'db', 'copies', 'main.json')
        mspec = json.load(open(mspec_path, encoding='utf-8'))
        mgen = BUILD.build(mspec)
        morig = _simulated_live(json.load(open(os.path.join(ROOT, mspec['original']), encoding='utf-8')))
        mcopy = assemble(mgen, morig, mspec, {'id': 'LiveCredential01', 'name': 'Postgres account'})
        dirty = _copy.deepcopy(mcopy)                     # a placeholder in a non-data node: refused BEFORE the PUT
        next(n for n in dirty['nodes'] if n['name'] == 'Normalize Inbound')['parameters']['_probe'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
        for label, o_active, c_active, want, copy_wf, drop in (
                ('original still ACTIVE', True, False, 'refused', mcopy, False),
                ('copy ACTIVE', False, True, 'refused', mcopy, False),
                ('both inactive', False, False, 'written', mcopy, False),
                ('the copy carries a placeholder (pre-write check)', False, False, 'rc 1', dirty, False),
                ('n8n drops the path change on write (post-write check)', False, False, 'rc 1', mcopy, True)):
            db = {'O1': dict(morig, active=o_active, name='Salon Booking Bot — Main'), 'C1': dict(copy_wf, active=c_active)}
            calls.clear()
            def fake(method, path, body=None, db=db, drop=drop):
                calls.append((method, path))
                wid = path.rsplit('/', 1)[-1]
                if method == 'PUT':
                    db[wid] = dict(_copy.deepcopy(body), active=db[wid]['active'], name=db[wid]['name'])
                    if drop:                                 # the API answers 200 but keeps the old trigger path
                        next(n for n in db[wid]['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path'] = mspec['trigger']['test_path']
                return 200, db[wid]
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(mspec_path, 'O1', swap='C1')
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit:
                got = 'refused'
            puts = [c for c in calls if c[0] == 'PUT']
            good = got == want and (puts == [('PUT', '/workflows/C1')] if (want == 'written' or drop) else not puts)
            if want == 'written':
                trig = next(n for n in db['C1']['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path']
                good = good and trig == next(n for n in morig['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path']
            ok = ok and good
            print(f"{'✓' if good else '✗'} --swap, {label}: {got} · PUTs {puts}")
            api = lambda *a, **k: calls.append(a) or (599, {})
        # The Turnstile window through run(), both phases (Main): checked BEFORE the write (red → no PUT) and again on
        # the read-back after it; an ACTIVE target is refused before anything. The original is inactive, as after --swap.
        # After the cutover the window's copy is judged by its committed export, so it is simulated FROM that export.
        mcommitted, msw = _simulated_live_copy(mspec_path)
        msw_off, mcopy_off = turnstile_patch(msw, 'off'), turnstile_patch(mcopy, 'off')
        msw_dirty = _copy.deepcopy(msw)
        next(n for n in msw_dirty['nodes'] if n['name'] == 'Normalize Inbound')['parameters']['_probe'] = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
        TS, TT = 'turnstile_swapped', 'turnstile'
        ROLES_FILE = roles_fixture('O1:C1:copy')          # the swap declared, as the ORDER guard requires
        for label, mode, state, copy_wf, c_active, mangle, want in (
                ('swapped copy, off', TS, 'off', msw, False, None, 'written'),
                ('swapped copy, on (restored)', TS, 'on', msw_off, False, None, 'written'),
                ('swapped copy ACTIVE', TS, 'off', msw, True, None, 'refused'),
                ('swapped copy with a placeholder (pre-write check)', TS, 'off', msw_dirty, False, None, 'rc 1'),
                ('an UNSWAPPED copy (wrong phase, pre-write check)', TS, 'off', mcopy, False, None, 'rc 1'),
                ('n8n keeps the old literal on write (post-write check)', TS, 'off', msw, False, 'keep', 'rc 1'),
                ('the copy reads back ACTIVE after the write (post-write check)', TS, 'off', msw, False, 'activate', 'rc 1'),
                ('unswapped copy, off', TT, 'off', mcopy, False, None, 'written'),
                ('unswapped copy, on (restored)', TT, 'on', mcopy_off, False, None, 'written'),
                ('unswapped copy ACTIVE', TT, 'off', mcopy, True, None, 'refused'),
                ('unswapped copy with a placeholder (pre-write check)', TT, 'off', dirty, False, None, 'rc 1'),
                ('n8n keeps the old literal on write (post-write check)', TT, 'off', mcopy, False, 'keep', 'rc 1'),
                ('the SWAPPED copy (wrong phase, pre-write check)', TT, 'off', msw, False, None, 'rc 1')):
            db = {'O1': dict(morig, active=False, name='Salon Booking Bot — Main'), 'C1': dict(copy_wf, active=c_active)}
            calls.clear()
            def fake(method, path, body=None, db=db, mangle=mangle):
                calls.append((method, path))
                wid = path.rsplit('/', 1)[-1]
                if method == 'PUT' and mangle != 'keep':      # 'keep': the API answers 200 and stores nothing
                    db[wid] = dict(_copy.deepcopy(body), active=db[wid]['active'], name=db[wid]['name'])
                if method == 'PUT' and mangle == 'activate':
                    db[wid]['active'] = True
                return 200, db[wid]
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(mspec_path, 'O1', **{mode: (state, 'C1')})
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit:
                got = 'refused'
            puts = [c for c in calls if c[0] == 'PUT']
            wrote = want == 'written' or mangle is not None
            good = got == want and (puts == [('PUT', '/workflows/C1')] if wrote else not puts)
            if want == 'written':
                lit = TS_LITERAL.findall(next(n for n in db['C1']['nodes'] if n['name'] == TS_NODE)['parameters']['jsCode'])
                good = good and lit == (['false'] if state == 'off' else ['true'])
            ok = ok and good
            print(f"{'✓' if good else '✗'} --{mode.replace('_', '-')} {state}, {label}: {got} · PUTs {puts}")
            api = lambda *a, **k: calls.append(a) or (599, {})
        # --turnstile-swapped's ORDER guard (ruling 2026-10-24): refused, with no PUT, unless ROLES declares exactly this
        # pair with the copy live AND the original reads back inactive. The test-phase --turnstile reads neither, so it
        # writes with the original ACTIVE and ROLES saying original (the test phase as it really is) or silent.
        for label, mode, state, copy_wf, roles_line, o_active, want in (
                ('ROLES declares the copy, original inactive', TS, 'off', msw, 'O1:C1:copy', False, 'written'),
                ('ROLES still declares the original', TS, 'off', msw, 'O1:C1:original', False, 'refused'),
                ('ROLES still declares the original (restore)', TS, 'on', msw_off, 'O1:C1:original', False, 'refused'),
                ('ROLES has no line for this pair', TS, 'off', msw, 'O2:C2:copy', False, 'refused'),
                ('ROLES does not read (the pair written the wrong way round)', TS, 'off', msw, 'C1:O1:copy', False, 'refused'),
                ('the original still ACTIVE (ROLES declares the copy)', TS, 'off', msw, 'O1:C1:copy', True, 'refused'),
                ('the original still ACTIVE (restore)', TS, 'on', msw_off, 'O1:C1:copy', True, 'refused'),
                ('test phase: ROLES declares the original, original ACTIVE', TT, 'off', mcopy, 'O1:C1:original', True, 'written'),
                ('test phase: ROLES has no line for this pair', TT, 'off', mcopy, 'O2:C2:copy', True, 'written')):
            ROLES_FILE = roles_fixture(roles_line)
            db = {'O1': dict(morig, active=o_active, name='Salon Booking Bot — Main'), 'C1': dict(copy_wf, active=False)}
            calls.clear()
            def fake(method, path, body=None, db=db):
                calls.append((method, path))
                wid = path.rsplit('/', 1)[-1]
                if method == 'PUT':
                    db[wid] = dict(_copy.deepcopy(body), active=db[wid]['active'], name=db[wid]['name'])
                return 200, db[wid]
            api = fake
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(mspec_path, 'O1', **{mode: (state, 'C1')})
                got = 'written' if rc == 0 else f'rc {rc}'
            except SystemExit as e:
                got, why = 'refused', str(e.code)
            puts = [c for c in calls if c[0] == 'PUT']
            good = got == want and (puts == [('PUT', '/workflows/C1')] if want == 'written' else not puts)
            ok = ok and good
            print(f"{'✓' if good else '✗'} --{mode.replace('_', '-')} {state}, ORDER guard, {label}: {got}"
                  f"{' (' + why.split('— ', 1)[-1][:120] + ')' if got == 'refused' else ''} · PUTs {puts}")
            api = lambda *a, **k: calls.append(a) or (599, {})
        # --engine-edit (K1) through run(), on a simulated instance. Whatever can be judged is judged BEFORE the
        # deactivation (red → no PUT and no (de)activation at all); a red result after the write is rolled back to the
        # pre-edit body; an unprovable rollback is SAFETY with the copy left inactive.
        pspec_path = os.path.join(ROOT, 'db', 'copies', 'purge.json')
        pspec = json.load(open(pspec_path, encoding='utf-8'))
        porig = _simulated_live(json.load(open(os.path.join(ROOT, pspec['original']), encoding='utf-8')))
        pcommitted, plive = _simulated_live_copy(pspec_path)

        def edited(wf, node, value):
            w = _copy.deepcopy(wf)
            next(n for n in w['nodes'] if n['name'] == node)['parameters']['_probe'] = value
            return w
        mold = edited(msw, 'Normalize Inbound', 'the old engine')     # production before the edit; the export = the new one
        pold = edited(plive, 'Compute Purge Cutoff', 'the old engine')
        c_low = turnstile_patch(mcommitted, 'off')
        c_ph = edited(mcommitted, 'Normalize Inbound', 'REPLACE_WITH_SOMETHING_NEW')
        c_test = _copy.deepcopy(mcommitted)
        next(n for n in c_test['nodes'] if n['name'] == mspec['trigger']['node'])['parameters']['path'] = mspec['trigger']['test_path']
        c_mcp = dict(_copy.deepcopy(mcommitted), settings=dict(mcommitted['settings'], availableInMCP=True))
        # Round B: the export REMOVES alwaysOutputData on a Purge node that production still carries it on. Built on the
        # live side (after E1 the committed Purge export carries the flag nowhere).
        p_aod_node = next(n['name'] for n in pcommitted['nodes'] if n['type'] == 'n8n-nodes-base.postgres')
        p_aod = _copy.deepcopy(pcommitted)
        next(n for n in p_aod['nodes'] if n['name'] == p_aod_node).pop('alwaysOutputData', None)
        plive_aod = _copy.deepcopy(plive)
        next(n for n in plive_aod['nodes'] if n['name'] == p_aod_node)['alwaysOutputData'] = True
        two_pg = _copy.deepcopy(mold)                       # two different live credentials behind one placeholder
        next(n for n in two_pg['nodes'] if n['name'] == next(iter(mspec['nodes'])))['credentials']['postgres']['id'] = 'LiveOtherPostgres01'

        TG = 'Send Owner Alert (Telegram)'

        def nodeset(wf, node, **kv):
            w = _copy.deepcopy(wf)
            n = next(n for n in w['nodes'] if n['name'] == node)
            for k, v in kv.items():
                if k == 'params':
                    n['parameters'].update(v)
                else:
                    n[k] = v
            return w

        def lcode(wf, old, new):
            w = _copy.deepcopy(wf)
            n = next(n for n in w['nodes'] if n['name'] == TS_NODE)
            assert old in n['parameters']['jsCode']
            n['parameters']['jsCode'] = n['parameters']['jsCode'].replace(old, new, 1)
            return w
        c_chat = nodeset(mcommitted, TG, params={'chatId': '={{ $json.ownerChat }}'})      # a masked value changed
        c_pg2 = _copy.deepcopy(mcommitted)                  # every Postgres credential renamed to a NEW placeholder
        for n in c_pg2['nodes']:
            if (n.get('credentials') or {}).get('postgres'):
                n['credentials']['postgres']['id'] = 'REPLACE_WITH_POSTGRES2_CREDENTIAL_ID'
        c_ren = nodeset(mcommitted, TG, params={'chatId': 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID_V2'})  # a placeholder NAME only
        live_chat = next(n for n in msw['nodes'] if n['name'] == TG)['parameters']['chatId']
        c_new = _copy.deepcopy(mcommitted)                  # a new node that needs a credential: an operator step
        c_new['nodes'].append(dict(_copy.deepcopy(next(n for n in mcommitted['nodes'] if n['name'] == next(iter(mspec['nodes'])))),
                                   name='New Lookup', id='new-lookup'))
        m_open = turnstile_patch(mold, 'off')               # a Turnstile window is open
        m_hook = nodeset(mold, TG, webhookId='live-hook-1')
        c_hook = nodeset(mcommitted, TG, webhookId='export-hook-x')
        c_renamed = nodeset(mcommitted, mspec['trigger']['node'], name='Receive Inbound (renamed)')   # carries a webhookId, no placeholder
        m_sticky = _copy.deepcopy(msw)                      # only a sticky note and a position differ from the export
        next(n for n in m_sticky['nodes'] if n['name'] == 'Sticky Note')['parameters']['content'] = 'moved'
        m_sticky['nodes'][1]['position'] = [9999, 9999]
        m_nogate = lcode(mold, ', turnstile: { enabled: true }', '')      # production without the gate; the export adds it
        c_shape = lcode(mcommitted, 'turnstile: { enabled: true }', 'turnstile: { enabled: true, mode: "x" }')

        def publish(w):
            w['activeVersion'] = {'nodes': _copy.deepcopy(w['nodes']), 'connections': _copy.deepcopy(w['connections'])}
        M, P = (mspec_path, 'O1', 'C1', morig, mcommitted, 'Normalize Inbound'), (pspec_path, 'O3', 'C3', porig, pcommitted, 'Compute Purge Cutoff')
        broken = [False]

        class Out(io.StringIO):
            """stdout that turns into a hung-up terminal once `broken` is set (EIO, as after an ssh drop)."""
            def write(self, t):
                if broken[0]:
                    raise OSError(5, 'Input/output error')
                return super().write(t)

        def world(spec_t, pre, c_active, o_active, state, forced):
            """A simulated instance: (db, fake api, fake probe, probes). `state['mangle']` can change between runs."""
            spath, oid, cid, orig_wf, exp, gnode = spec_t
            c = dict(_copy.deepcopy(pre), active=c_active)
            publish(c)
            if state.get('mangle') == 'unpublished':
                next(n for n in c['activeVersion']['nodes'] if n['name'] == gnode)['parameters']['_probe'] = 'published, never saved'
            db, once, probes = {oid: dict(orig_wf, active=o_active, name=pre['name']), cid: c}, set(), []

            def fake(method, path, body=None):
                mangle = state.get('mangle')
                calls.append((method, path))
                parts = path.split('/')
                w = db[parts[2]]
                if method == 'GET':
                    if mangle == 'deact-readback-fails' and 'deact' in once and 'rb' not in once:
                        once.add('rb')
                        return 500, {}
                    if mangle == 'bad-shape-once' and 'put' in once and 'shape' not in once:
                        once.add('shape')
                        return 200, dict(_copy.deepcopy(w), nodes=None)
                    return 200, _copy.deepcopy(w)
                if method == 'POST':
                    if parts[3] == 'deactivate':
                        once.add('deact')
                        if mangle == 'deact-ignored':
                            return 200, {}
                    if parts[3] == 'activate':
                        if mangle == 'activation-ignored-once' and 'act' not in once:
                            once.add('act')
                            return 200, {}
                        w['active'] = True
                        publish(w)
                    else:
                        w['active'] = False
                    return 200, {}
                if mangle == 'put-500-once' and 'put' not in once:
                    once.add('put')
                    return 500, {}
                if mangle == 'put-400':
                    return 400, {'message': 'request/body must NOT have additional properties'}
                if mangle == 'put-raises-kbi' and 'kbi' not in once:
                    once.add('kbi')
                    raise KeyboardInterrupt()
                if mangle in ('put-sigterm', 'put-sighup-eio') and 'sig' not in once:
                    once.add('sig')
                    if mangle == 'put-sighup-eio':
                        broken[0] = True
                    os.kill(os.getpid(), signal.SIGTERM if mangle == 'put-sigterm' else signal.SIGHUP)
                once.add('put')
                if mangle != 'keep':
                    w.update(_copy.deepcopy(body))
                    if mangle == 'keep-flag' and len([x for x in calls if x[0] == 'PUT']) == 1:
                        next(n for n in w['nodes'] if n['name'] == p_aod_node)['alwaysOutputData'] = True
                    if mangle == 'swap-chat' and len([x for x in calls if x[0] == 'PUT']) == 1:
                        next(n for n in w['nodes'] if n['name'] == TG)['parameters']['chatId'] = 'LiveSomeOtherChat'
                    if mangle == 'garble':
                        next(n for n in w['nodes'] if n['name'] == gnode)['parameters']['_probe'] = 'garbled'
                    if w['active']:
                        publish(w)                        # a PUT to an ACTIVE workflow publishes at once
                return 200, {}

            def probe(path, o, cc):
                probes.append(path)
                if state.get('mangle') == 'probe-raises' and len(probes) == 1:
                    raise RuntimeError('GET executions answered 502')
                if len(probes) in forced:
                    return False, forced[len(probes)]
                up = db[cc]['active'] and _ts_literal({'nodes': db[cc]['activeVersion']['nodes']}) == ['true']
                return (True, 403) if up else (False, 200)
            return db, fake, probe, probes

        def go(spec_t, mode, rev, override):
            """Run one mode through run(); (got, why, output)."""
            nonlocal_out = Out()
            why = ''
            try:
                with contextlib.redirect_stdout(nonlocal_out):
                    rc = run(spec_t[0], spec_t[1], **{mode: spec_t[2]}, from_rev=rev)
                got = {0: 'written', 1: 'rc 1', 3: 'rc 3', 4: 'rc 4'}.get(rc, f'rc {rc}')
                if got == 'written' and 'nothing written' in nonlocal_out.getvalue():
                    got = 'nothing'
            except SystemExit as e:
                got, why = 'refused', str(e.code)
            except BaseException as e:                       # an escaped exception is a red case, never a crash
                got = f'escaped {type(e).__name__}'
            broken[0] = False
            return got, why, nonlocal_out.getvalue()
        # label, (spec, o, c, original, committed export, a node to garble), pre-edit live, export override, rev,
        # roles line, original active, copy active, mangle, forced probe answers, want, PUTs wanted
        # PUTs wanted: a rollback that reads its pre-edit body back unchanged (nothing stored, a refused write) does not
        # PUT again, so those cases write once.
        E = [('a clean edit', M, mold, None, 'HEAD', 'copy', False, True, None, {}, 'written', 1),
             ('a clean edit on a copy with no Turnstile gate (no probe)', P, pold, None, 'HEAD', 'copy', False, True, None, {}, 'written', 1),
             ('the live copy already equals the export', M, msw, None, 'HEAD', 'copy', False, True, None, {}, 'nothing', 0),
             ('the export drops alwaysOutputData on one node (Round B): a change to write, read back without it', P, plive_aod, p_aod, 'HEAD', 'copy', False, True, None, {}, 'written', 1),
             ('the export drops alwaysOutputData, n8n keeps it on write (read-back red → rollback)', P, plive_aod, p_aod, 'HEAD', 'copy', False, True, 'keep-flag', {}, 'rc 3', 1),
             ('the export carries a lowered Turnstile literal', M, mold, c_low, 'HEAD', 'copy', False, True, None, {}, 'rc 1', 0),
             ('the export carries a placeholder at a path where live holds an ordinary value', M, mold, c_ph, 'HEAD', 'copy', False, True, None, {}, 'rc 1', 0),
             ('the export puts the trigger on its test path', M, mold, c_test, 'HEAD', 'copy', False, True, None, {}, 'rc 1', 0),
             ("the export adds an allowlisted setting ('availableInMCP')", M, mold, c_mcp, 'HEAD', 'copy', False, True, None, {}, 'rc 1', 0),
             ('the live copy runs a published graph that is not its draft', M, mold, None, 'HEAD', 'copy', False, True, 'unpublished', {}, 'rc 1', 0),
             ('two live credentials behind one placeholder: each path keeps its own', M, two_pg, None, 'HEAD', 'copy', False, True, None, {}, 'written', 1),
             ('the copy is INACTIVE', M, mold, None, 'HEAD', 'copy', False, False, None, {}, 'refused', 0),
             ('the original is ACTIVE', M, mold, None, 'HEAD', 'copy', True, True, None, {}, 'refused', 0),
             ('ROLES still declares the original', M, mold, None, 'HEAD', 'original', False, True, None, {}, 'refused', 0),
             ("--from-rev that git would read as an option ('-p')", M, mold, 'real', '-p', 'copy', False, True, None, {}, 'refused', 0),
             ('--from-rev that does not exist', M, mold, 'real', 'no-such-rev-k1', 'copy', False, True, None, {}, 'refused', 0),
             ('n8n answers 200 and stores nothing (read-back red → rollback)', M, mold, None, 'HEAD', 'copy', False, True, 'keep', {}, 'rc 3', 1),
             ('the write answers 500 once (rollback)', M, mold, None, 'HEAD', 'copy', False, True, 'put-500-once', {}, 'rc 3', 1),
             ('the activation does not take once (rollback)', M, mold, None, 'HEAD', 'copy', False, True, 'activation-ignored-once', {}, 'rc 3', 2),
             ('the dummy token answers 200 after the edit (rollback)', M, mold, None, 'HEAD', 'copy', False, True, None, {1: 200}, 'rc 3', 2),
             ('n8n garbles every write: the rollback is not proven (SAFETY, copy left inactive)', M, mold, None, 'HEAD', 'copy', False, True, 'garble', {}, 'rc 4', 2),
             ('the gate answers 200 after the rollback too (SAFETY, copy stopped)', M, mold, None, 'HEAD', 'copy', False, True, None, {1: 200, 2: 200}, 'rc 4', 2),
             ('R1 the export changes the Telegram chatId to an expression: a masked value, refused (sanitise)', M, msw, c_chat, 'HEAD', 'copy', False, True, None, {}, 'refused', 0),
             ('R1 the write lands a different real value behind a placeholder: the raw read-back sees it (rollback)', M, mold, None, 'HEAD', 'copy', False, True, 'swap-chat', {}, 'rc 3', 2),
             ('R2 Ctrl-C (KeyboardInterrupt) during the write: rolled back', M, mold, None, 'HEAD', 'copy', False, True, 'put-raises-kbi', {}, 'rc 3', 1),
             ('R2 the probe raises (as executions_since does): a probe failure, rolled back', M, mold, None, 'HEAD', 'copy', False, True, 'probe-raises', {}, 'rc 3', 2),
             ('R2 a read-back of an unexpected shape (TypeError): rolled back', M, mold, None, 'HEAD', 'copy', False, True, 'bad-shape-once', {}, 'rc 3', 2),
             ('R3 the write is refused outright (400): the rollback finds the body untouched and does not PUT', M, mold, None, 'HEAD', 'copy', False, True, 'put-400', {}, 'rc 3', 1),
             ('R4 the deactivate lands but its read-back fails: re-activated and proven, never "nothing written"', M, mold, None, 'HEAD', 'copy', False, True, 'deact-readback-fails', {}, 'rc 3', 0),
             ('R4 the deactivate does not take: stopped, no PUT, still active', M, mold, None, 'HEAD', 'copy', False, True, 'deact-ignored', {}, 'rc 1', 0),
             ('R5 a Turnstile window is open on the live copy: refused before any write', M, m_open, None, 'HEAD', 'copy', False, True, None, {}, 'rc 1', 0),
             ("R6 a Telegram node's live webhookId is kept over the export's", M, m_hook, c_hook, 'HEAD', 'copy', False, True, None, {}, 'written', 1),
             ('R6 the export renames a node that carries a live webhookId: refused', M, mold, c_renamed, 'HEAD', 'copy', False, True, None, {}, 'refused', 0),
             ('R7 only a sticky note and a position differ: "no executable difference"', M, m_sticky, None, 'HEAD', 'copy', False, True, None, {}, 'nothing', 0),
             ('R2 SIGTERM during the write: noted, the write stops at the next step, rolled back', M, mold, None, 'HEAD', 'copy', False, True, 'put-sigterm', {}, 'rc 3', 2),
             # Last fix round (2026-10-25): each case was red before its fix.
             ('A every Postgres credential renamed to a NEW placeholder, nothing else: "no executable difference"', M, msw, c_pg2, 'HEAD', 'copy', False, True, None, {}, 'nothing', 0),
             ('A a placeholder renamed, with an engine change: written, the live chat id at that path', M, mold, c_ren, 'HEAD', 'copy', False, True, None, {}, 'written', 1),
             ('A a placeholder renamed, nothing else: "no executable difference"', M, msw, c_ren, 'HEAD', 'copy', False, True, None, {}, 'nothing', 0),
             ('A the export adds a node that needs a credential: refused (an operator step)', M, mold, c_new, 'HEAD', 'copy', False, True, None, {}, 'refused', 0),
             ('B SIGHUP during the write, and stdout then raises EIO: rolled back, active', M, mold, None, 'HEAD', 'copy', False, True, 'put-sighup-eio', {}, 'rc 3', 2),
             ('D content restored but the rollback probe answers 502: SAFETY with the copy ACTIVE', M, mold, None, 'HEAD', 'copy', False, True, None, {1: 200, 2: 502}, 'rc 4', 2),
             ('E production has no gate, the export adds one: the rollback probes by the PRE body (none)', M, m_nogate, None, 'HEAD', 'copy', False, True, None, {1: 200}, 'rc 3', 2),
             ('F the export\'s Turnstile literal has an extra key: refused, not skipped', M, mold, c_shape, 'HEAD', 'copy', False, True, None, {}, 'rc 1', 0)]
        for label, spec_t, pre, override, rev, live_role, o_active, c_active, mangle, forced, want, want_puts in E:
            spath, oid, cid, orig_wf, exp, gnode = spec_t
            ROLES_FILE = roles_fixture(f'{oid}:{cid}:{live_role}')
            state = {'mangle': mangle}
            db, fake, probe, probes = world(spec_t, pre, c_active, o_active, state, forced)
            calls.clear()
            api, turnstile_probe = fake, probe
            committed_export = real_committed_export if override == 'real' else \
                (lambda path, rev='HEAD', o=override or exp: _copy.deepcopy(o))
            got, why, out = go(spec_t, 'engine_edit', rev, override)
            puts = [x for x in calls if x[0] == 'PUT']
            toggles = [x[1].rsplit('/', 1)[-1] for x in calls if x[0] == 'POST']
            final = db[cid]
            target = override if isinstance(override, dict) else exp
            good = got == want and len(puts) == want_puts and all(x[1] == f'/workflows/{cid}' for x in puts)
            if want in ('rc 1', 'refused', 'nothing') and not (mangle or '').startswith('deact'):
                good = good and not toggles                  # nothing touched: production kept its holder throughout
            if want == 'written':
                good = good and final['active'] is True and not content_drift(_draft(final), target) \
                    and len(probes) == (1 if _ts_literal(target) else 0)
            if want == 'rc 3':
                good = good and final['active'] is True and not content_drift(_draft(final), pre, smap={})
            if want == 'rc 4':
                good = good and final['active'] is label.startswith('D ') and 'SAFETY' in out
            if mangle and mangle.startswith('deact'):
                good = good and 'nothing written' not in out and final['active'] is True
            if label.startswith("R6 a Telegram"):
                good = good and next(n for n in final['nodes'] if n['name'] == TG).get('webhookId') == 'live-hook-1'
            if label.startswith('R6 the export renames'):
                good = good and 'webhookId' in why
            if label.startswith('R5'):
                good = good and 'window' in out
            if want == 'nothing':
                good = good and 'no executable difference' in out
            if label.startswith('two live'):
                good = good and any((n.get('credentials') or {}).get('postgres', {}).get('id') == 'LiveOtherPostgres01' for n in final['nodes'])
            if label.startswith('A a placeholder renamed, with'):
                good = good and next(n for n in final['nodes'] if n['name'] == TG)['parameters']['chatId'] == live_chat
            if label.startswith('A the export adds'):
                good = good and 'operator step' in why
            if label.startswith('E '):
                good = good and len(probes) == 1
            if label.startswith('F '):
                good = good and 'exact Turnstile literal' in out
            ok = ok and good
            print(f"{'✓' if good else '✗'} --engine-edit, {label}: {got}"
                  f"{' (' + why.split('— ', 1)[-1][:100] + ')' if got == 'refused' else ''} · PUTs {len(puts)} · "
                  f"(de)activations {toggles} · copy active {final['active']}")
            api = lambda *a, **k: calls.append(a) or (599, {})
            turnstile_probe, committed_export = real_probe, real_committed_export
        # C: an exit 4 that leaves the copy INACTIVE, then --restore brings it back active and proven; the SAFETY
        # message printed exactly that command. --restore refuses an ACTIVE copy.
        ROLES_FILE = roles_fixture('O1:C1:copy')
        state = {'mangle': 'garble'}
        db, fake, probe, probes = world(M, mold, True, False, state, {})
        api, turnstile_probe = fake, probe
        committed_export = lambda path, rev='HEAD': _copy.deepcopy(mcommitted)
        calls.clear()
        got1, _, out1 = go(M, 'engine_edit', 'HEAD', None)
        printed = next((l.strip() for l in out1.splitlines() if '--restore C1 --from-rev ' in l), '')
        state['mangle'] = None
        calls.clear()
        got2, why2, out2 = go(M, 'restore', 'HEAD', None)
        good = got1 == 'rc 4' and bool(printed) and got2 == 'written' and db['C1']['active'] is True \
            and not content_drift(_draft(db['C1']), mcommitted) and [x for x in calls if x[0] == 'PUT'] == [('PUT', '/workflows/C1')]
        ok = ok and good
        print(f"{'✓' if good else '✗'} C an exit 4 leaves the copy inactive ({got1}, restore command printed: {bool(printed)}), "
              f"then --restore: {got2} · copy active {db['C1']['active']}")
        calls.clear()
        got3, why3, _ = go(M, 'restore', 'HEAD', None)    # the copy is ACTIVE now
        good = got3 == 'refused' and 'INACTIVE' in why3 and not [x for x in calls if x[0] != 'GET']
        ok = ok and good
        print(f"{'✓' if good else '✗'} C --restore on an ACTIVE copy: {got3}")
        api = lambda *a, **k: calls.append(a) or (599, {})
        turnstile_probe, committed_export = real_probe, real_committed_export
        # R7: a flag given as the LAST argument is a usage error (exit 2), never an IndexError.
        for argv in (['deploy', specs[0], '--original-id', 'O1', '--engine-edit'],
                     ['deploy', specs[0], '--original-id', 'O1', '--engine-edit', 'C1', '--from-rev'],
                     ['deploy', specs[0], '--original-id', 'O1', '--engine-edit', '--from-rev', 'HEAD'],
                     ['deploy', '--engine-edit', 'C1', '--original-id', 'O1'],          # G: the spec path must come first
                     ['deploy', specs[0], '--original-id', 'O1', '--restore']):
            calls.clear()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = main(argv)
            except BaseException as e:
                rc = f'escaped {type(e).__name__}'
            good = rc == 2 and not calls
            ok = ok and good
            print(f"{'✓' if good else '✗'} R7/G argv '{' '.join(argv[1:]).replace(specs[0], '<spec>')}': main() exit {rc}, API calls {len(calls)}")
        # DISABLED: a well-formed --engine-edit / --restore is refused by main() before any API call while the
        # final review's two critical findings are open (ENGINE_EDIT_ENABLED). engine_edit_run itself is still tested
        # above, so the mode stays proven offline for the day it is re-enabled.
        for argv in (['deploy', specs[0], '--original-id', 'O1', '--engine-edit', 'C1'],
                     ['deploy', specs[0], '--original-id', 'O1', '--restore', 'C1', '--from-rev', 'HEAD']):
            calls.clear()
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out):
                    rc = main(argv)
            except BaseException as e:
                rc = f'escaped {type(e).__name__}'
            good = rc == 2 and not calls and 'DISABLED' in out.getvalue()
            ok = ok and good
            print(f"{'✓' if good else '✗'} disabled mode '{argv[4]}' refused by main(): exit {rc}, API calls {len(calls)}")
    finally:
        api, ROLES_FILE = real_api, real_roles
        turnstile_probe, committed_export = real_probe, real_committed_export
        for p in fixtures:
            os.unlink(p)
    print('deploy-workflow-copy selftest:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


def main(argv):
    if argv[1:2] == ['--selftest']:
        return selftest()
    if len(argv) < 2 or '--original-id' not in argv or argv[1].startswith('--'):
        print('usage: deploy-workflow-copy.py db/copies/<x>.json --original-id ID <mode> … (the spec path comes first; '
              'see the module docstring)')
        return 2
    for k in ('--original-id', '--update', '--verify', '--swap', '--engine-edit', '--from-rev', '--restore'):
        # A value-taking flag given last, or followed by another flag, is a usage error, never an IndexError.
        if k in argv and (argv.index(k) + 1 >= len(argv) or argv[argv.index(k) + 1].startswith('--')):
            print(f'usage: … {k} VALUE (see --help in the module docstring)')
            return 2
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    if sum(k in argv for k in ('--update', '--verify', '--turnstile', '--swap', '--turnstile-swapped', '--engine-edit',
                               '--restore')) > 1:
        print('deploy-workflow-copy: refused — --update, --verify, --turnstile, --turnstile-swapped, --swap, '
              '--engine-edit and --restore are exclusive (one target per run)')
        return 2
    if '--from-rev' in argv and '--engine-edit' not in argv and '--restore' not in argv:
        print('usage: … --engine-edit COPY_ID [--from-rev REV] | --restore COPY_ID [--from-rev REV]')
        return 2
    if not ENGINE_EDIT_ENABLED and ('--engine-edit' in argv or '--restore' in argv):
        print('deploy-workflow-copy: --engine-edit and --restore are DISABLED (7-F1 Round A): the final code review '
              'found two critical recovery defects still open (docs/PHASE-7-PLAN.md §4d). Nothing was read or written.')
        return 2
    windows = {}
    for flag in ('--turnstile', '--turnstile-swapped'):
        if flag in argv:
            i = argv.index(flag)
            windows[flag] = tuple(argv[i + 1:i + 3])
            if len(windows[flag]) != 2 or windows[flag][0] not in ('off', 'on'):
                print(f'usage: … {flag} off|on COPY_ID')
                return 2
    return run(argv[1], opt('--original-id'), update=opt('--update'), verify_only=opt('--verify'),
               turnstile=windows.get('--turnstile'), swap=opt('--swap'), turnstile_swapped=windows.get('--turnstile-swapped'),
               engine_edit=opt('--engine-edit'), from_rev=opt('--from-rev'), restore=opt('--restore'))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
