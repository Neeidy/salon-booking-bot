#!/usr/bin/env python3
"""Offline test for scripts/workflow-step.py (7-F1 Round B, final shape; shrunk to the approved deltas in 7-2 Tur 2 R1d):
a fake n8n behind the deploy helper's `api` (an UNEXPECTED call raises, so a case cannot pass on a 404 it did not ask
for), fake ids in a fixture ROLES file, and live copies simulated from the committed exports. The Main and Owner Actions
cases use the REAL staged exports and the REAL delta files.

What it proves: put refuses an ACTIVE copy, an edit outside its allowlist (a node not named, an edge, a flag, a
setting, an older revision that brings the temporary trigger back), an export that is not sanitised, a copy ROLES does
not declare live, an original that is not parked, a copy of another spec, a spec outside db/copies, an export outside
the repo or not this copy's own REV:PATH, a REV that is not HEAD or a commit SHA, and Drill State — each before any PUT;
a PUT whose read-back differs from the export, whose settings or active flag come back changed, or that answers non-200
is RED; deactivate and activate are RED when their read-back disagrees, activate also when published != draft.
FIXED: the two real delta files ARE the approved deltas; a delta that differs by one edge (T HIGH-1's Turnstile reject →
claim), one missing removal, an added setting or another setting value, and any delta for a copy with none approved are
refused, 0 PUT; the removed CLI flags and delta keys are refused. GATE, kept as defence in depth: gate nodes in --allow
(G1-A/B, OA's Verify Owner Signature, the triggers) are refused; a gate-touching delta (H1, G1-C/D, a non-ruled edge from
Verify Turnstile, an edge onward from a reject responder) is refused as NOT APPROVED and — with APPROVED_DELTAS patched
to it, the diff in place and blind — by the GATE, 0 PUT; the webhook invariants are checked by put itself.
SNAPSHOT: put writes the live workflow taken immediately before its PUT to a NEW 0600 file outside the repo (an existing
file, a path in the repo or a missing directory: refused, 0 PUT; a put refused earlier writes none); rollback puts it back
and reads back == the pre-edit workflow exactly; it is RED when n8n changes a credential id, a setting or the connections,
or answers 500, and refused (no write) for an active copy, another workflow's or spec's snapshot, a snapshot that fails
a webhook invariant (Turnstile literal off, trigger path moved — security T-1), a path in the repo (also when the repo
is reached through a symlink — T-2), a missing or malformed file. R2b (Codex R2 deploy HIGH/MEDIUM): put and settings
refuse, before keeping a snapshot, a live copy that is not its committed export (a gate weakened by hand, a drifted
setting, a placeholder; after an edit, a second put) — so every snapshot is a reviewed state; an edge whose connection
type changed is refused. T-4: put never sends a setting (the approved delta's setting is not live after put, and a
setting changing across the PUT is RED); `settings` is refused before the edit is live, on an active copy, for Main's
delta, an unapproved value and an extra key, applies exactly the approved key with nodes unchanged, is RED when n8n drops
the value or changes a node, and rollback to the pre-edit snapshot undoes edit and setting. rehearse-rollback runs put →
settings (Owner Actions) → rollback on a scratch, the scratch ending exactly as built, production untouched, snapshots
removed; a rollback n8n does not keep is RED. Lane T review (R1d): `settings` with the committed export as EXPORT on an
unedited copy, and a settings-only delta for Purge, are refused; a copy that comes back ACTIVE is RED with a message that
says ACTIVE (put, settings, rollback); a rollback answered 502 but applied is reported from the read-back; n8n changing a
credential id across put, merging settings or renaming on rollback is RED; put re-reads the copy immediately before
its PUT; a valid snapshot inside the repo is refused for where it is; the scratch is deleted in `finally` (a 500 PUT, a red scratch read-back, an
exception) with exit 3 when the delete is not proven. Kept from R1c: ids not letters/digits refused before any call;
the scratch deleted only on an exact 404 and never activated (by its live name); M-a in a throwaway git repo; M-b; the
position lock.
What it does NOT prove: n8n's real behaviour on PUT/DELETE (the live read-back and the R3 rehearsal on a scratch prove
that).
Run: python3 tests/unit/workflow-step.test.py [path/to/workflow-step.py [path/to/diff-workflow-copy.py]]   (the paths: mutants)
"""
import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'scripts', 'workflow-step.py')
_spec = importlib.util.spec_from_file_location('workflow_step', SRC)
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)
H = W.H
DIFF_SRC = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'scripts', 'diff-workflow-copy.py')
if len(sys.argv) > 2:   # a mutant of diff-workflow-copy.py under test: the put path and the CLI cases both use it
    _ds = importlib.util.spec_from_file_location('diff_workflow_copy_under_test', DIFF_SRC)
    H.DIFF = importlib.util.module_from_spec(_ds)
    _ds.loader.exec_module(H.DIFF)

# THE BEFORE SIDE of the two approved deltas (R3): the Main and Owner Actions copy exports as committed before R3 promoted
# the staged edits. After that promotion HEAD's copy exports ARE the edit, so every "committed export" the tool reads for
# these two is the baseline fixture here (tests/fixtures/7-2-baseline/README.md); Purge and Reminders read HEAD as before.
BASELINE = {'n8n/workflow.main.copy.sanitized.json': 'tests/fixtures/7-2-baseline/workflow.main.copy.json',
            'n8n/workflow.owner-actions.copy.sanitized.json': 'tests/fixtures/7-2-baseline/workflow.owner-actions.copy.json'}
_real_committed_export = H.committed_export


def _committed_or_baseline(path, rev='HEAD'):
    if rev == 'HEAD' and path in BASELINE:
        return json.load(open(os.path.join(ROOT, BASELINE[path]), encoding='utf-8'))
    return _real_committed_export(path, rev)


H.committed_export = _committed_or_baseline
# ...and the spec as it stood on that baseline: until R3 promoted the edit the Owner Actions spec carried no
# settings_allow (T-4's exact-value entry arrives WITH the promoted export, whose live copy then holds the value). A
# pre-edit Owner Actions copy judged against the post-promotion spec would read as drift, which it was not at the time.
BASELINE_SPEC_DROP = {'owner-actions': ('settings_allow',)}
_real_target, _real_target_scratch = W.target, W.target_scratch


def _baseline_spec(fn):
    def wrapped(spec_path, wid):
        spec, committed = fn(spec_path, wid)
        drop = BASELINE_SPEC_DROP.get(W.spec_key(spec_path), ())
        return ({k: v for k, v in spec.items() if k not in drop} if drop else spec), committed
    return wrapped


W.target, W.target_scratch = _baseline_spec(_real_target), _baseline_spec(_real_target_scratch)

E1 = ['Aggregate Leads Total', 'Build Owner Alert (Purge)', 'Count Leads After', 'Count Leads Total', 'Find Old Leads',
      'Leads Purge Sane?', 'Verify Leads Purge']
E2 = ['Build Owner Alert (Reminders)']
IDS = {'purge': ('OP', 'CP'), 'reminders': ('OR', 'CR'), 'main': ('OM', 'CM'), 'owner-actions': ('OO', 'CO'),
       'drill-state': ('OD', 'CD')}


class FakeN8n:
    """delete_mode: 'gone' (DELETE removes; GET then 404) · 'keep' (DELETE does nothing; GET 200) · an int status (DELETE
    does nothing; every later GET of that id answers that status: 500, an Access 403, curl's 0). execs: {id: [startedAt]}
    for GET /executions. create_mangle: applied to the workflow a POST /workflows stores (a scratch that reads back wrong)."""
    def __init__(self, wfs, mangle=None, flip_ok=True, stale_published=False, put_status=200, delete_mode='gone',
                 create_mangle=None, create_answer=None):
        self.wfs, self.mangle, self.calls = wfs, mangle, []
        self.flip_ok, self.stale_published, self.put_status = flip_ok, stale_published, put_status
        self.delete_mode, self.create_mangle, self.deleted, self.broken, self.execs = delete_mode, create_mangle, set(), {}, {}
        self.create_answer = create_answer   # (status, body) a POST /workflows answers instead of the id (it still stores one)

    def api(self, method, path, body=None):
        self.calls.append((method, path))
        if method == 'POST' and path == '/workflows':
            sid = f'SCR{len(self.wfs):09d}'          # long enough that a masked id is NOT the id
            self.wfs[sid] = dict(copy.deepcopy(body), id=sid, active=False)
            if self.create_mangle:
                self.create_mangle(self.wfs[sid])
            return self.create_answer or (200, {'id': sid})
        e = re.fullmatch(r'/executions\?workflowId=(\w+)&limit=100', path)
        if method == 'GET' and e:
            return 200, {'data': [{'startedAt': t} for t in self.execs.get(e.group(1), [])]}
        m = re.fullmatch(r'/workflows/(\w+)(?:/(activate|deactivate))?', path)
        if method == 'DELETE' and m and m.group(1) in self.wfs and not m.group(2):
            if self.delete_mode == 'gone':
                self.wfs.pop(m.group(1))
                self.deleted.add(m.group(1))
            elif isinstance(self.delete_mode, int):
                self.broken[m.group(1)] = self.delete_mode
            return 200, {}
        if method == 'GET' and m and m.group(1) in self.broken:
            return self.broken[m.group(1)], None
        if method == 'GET' and m and m.group(1) in self.deleted:
            return 404, {'message': 'Not Found'}
        if not m or m.group(1) not in self.wfs:
            raise AssertionError(f'unexpected API call {method} {path}')
        w = self.wfs[m.group(1)]
        if method == 'GET' and not m.group(2):
            out = copy.deepcopy(w)
            out.pop('_published', None)
            out['activeVersion'] = (w.get('_published') if self.stale_published else None) or \
                {'nodes': copy.deepcopy(w['nodes']), 'connections': copy.deepcopy(w['connections'])}
            return 200, out
        if method == 'POST' and m.group(2):
            if self.flip_ok:
                w['active'] = m.group(2) == 'activate'
            return 200, {}
        if method == 'PUT':
            if self.put_status != 200:
                return self.put_status, {}
            b = copy.deepcopy(body)
            if self.mangle:
                self.mangle(b)
            w.update({k: b[k] for k in ('name', 'nodes', 'connections', 'settings')})
            if '_active' in b:
                w['active'] = b['_active']
            return 200, {}
        raise AssertionError(f'unexpected API call {method} {path}')

    def puts(self):
        return sum(1 for m, _ in self.calls if m == 'PUT')

    def writes(self):
        return sum(1 for m, _ in self.calls if m != 'GET')


def roles_file(live='copy'):
    t = tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False)
    t.write('PAIRS=(\n' + ''.join(f'  "{o}:n8n/workflow.{x}.sanitized.json"\n  "{c}:n8n/workflow.{x}.copy.sanitized.json"\n'
                                  .replace('workflow.main.sanitized', 'workflow.sanitized') for x, (o, c) in IDS.items())
            + ')\n\nROLES=(\n' + ''.join(f'  "{o}:{c}:{live}"\n' for o, c in IDS.values()) + ')\n')
    t.close()
    return t.name


HOOK_TYPES = ('n8n-nodes-base.webhook', 'n8n-nodes-base.telegram')


def live_hooks(wf):
    """The webhookIds n8n gives a live workflow: the sanitized exports carry none, and measured on the live Owner
    Actions copy (R3, 2026-10-26) the webhook trigger AND every Telegram node carry one. Without them the fake could not
    produce the R3 defect (the approved delta drops a Telegram node; put refused it live and passed here)."""
    for n in wf['nodes']:
        if n.get('type') in HOOK_TYPES:
            n['webhookId'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'wstest-hook:' + n['name']))
    return wf


def world(spec='purge', copy_active=False, orig_active=False, **fake_kw):
    committed, live = H._simulated_live_copy(f'db/copies/{spec}.json')
    live = live_hooks(live)
    oid, cid = IDS[spec]
    orig = dict(copy.deepcopy(live), name='original', active=orig_active)
    cp = dict(copy.deepcopy(live), active=copy_active)
    return committed, FakeN8n({oid: orig, cid: cp}, **fake_kw), oid, cid


SNAPDIR = tempfile.mkdtemp(prefix='wstest-snap-')   # snapshots live OUTSIDE the repo (put refuses a path inside it)
_snap_n = [0]


def snap_path():
    _snap_n[0] += 1
    return os.path.join(SNAPDIR, f's{_snap_n[0]}.json')


def run(fake, argv, snap=True):
    """W.main on argv; a put/settings without --snapshot gets a fresh one outside the repo (its path: run.last_snap)."""
    if snap and argv[:1] in (['put'], ['settings']) and '--snapshot' not in argv and len(argv) > 4:
        run.last_snap = snap_path()
        argv = [*argv, '--snapshot', run.last_snap]
    H.api = fake.api
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            rc = W.main(['workflow-step', *argv])
        except BaseException as e:   # an escaped exception is a failed case, never a crash of the suite
            rc = f'escaped {type(e).__name__}'
    return rc, out.getvalue()


tmp = []


def repo_file(obj, name='.wstest-'):
    # Inside the repo (put refuses an export file outside it), in a gitignored name (n8n/**/*.json unless workflow.*.sanitized.json).
    t = tempfile.NamedTemporaryFile('w', prefix=name, suffix='.json', delete=False, dir=os.path.join(ROOT, 'n8n', 'staged'))
    json.dump(obj, t)
    t.close()
    tmp.append(t.name)
    TEST_FILES.add(os.path.relpath(t.name, ROOT))
    return os.path.relpath(t.name, ROOT)


def ts_off(code):   # flip THE Turnstile literal (not merely the first `enabled: true` in the code)
    out = H.TS_LITERAL.sub(lambda m: m.group(0).replace('true', 'false'), code, count=1)
    assert H.TS_LITERAL.findall(out) == ['false'], 'the fixture did not flip the Turnstile literal'
    return out


def drift(fake, cid, ref):
    d = H._draft(fake.wfs[cid])
    return H.content_drift(d, ref, H._ccp().placeholder_smap(d, ref))


ok = True
real_api, real_roles, real_tc, real_hb = H.api, H.ROLES_FILE, W.tracked_clean, W.head_blob
TEST_FILES = set()   # the gitignored .wstest exports this test writes: treated as committed, ONLY for the cases that need it
W.tracked_clean = lambda rel: rel in TEST_FILES or real_tc(rel)
W.head_blob = lambda rel: open(os.path.join(ROOT, rel), encoding='utf-8').read() if rel in TEST_FILES else real_hb(rel)


def call(fake, fn, *a, **k):
    """A workflow-step function called directly (the paths the CLI does not expose: a scratch target) → (rc, output)."""
    H.api = fake.api
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            rc = fn(*a, **k)
        except W.ScratchLeft:
            rc = 3
        except W.Refused as e:
            print(f'REFUSED/RED — {e}')
            rc = 1
        except BaseException as e:
            rc = f'escaped {type(e).__name__}'
    return rc, out.getvalue()


def case(label, good, detail):
    global ok
    ok = ok and good
    print(f"{'✓' if good else '✗'} {label}: {detail}")


try:
    H.ROLES_FILE = roles_file()
    tmp.append(H.ROLES_FILE)
    P, R = 'db/copies/purge.json', 'db/copies/reminders.json'
    # The edits under test are SYNTHESISED from the committed exports (an engine change inside the allowlist), so the
    # test does not depend on n8n/staged/, which empties as each edit is promoted.
    def synth(x, code_node, flag_node=None):
        e = json.load(open(os.path.join(ROOT, 'n8n', f'workflow.{x}.copy.sanitized.json'), encoding='utf-8'))
        n = next(n for n in e['nodes'] if n['name'] == code_node)
        n['parameters']['jsCode'] += '\n// the engine edit under test'
        if flag_node:
            f = next(n for n in e['nodes'] if n['name'] == flag_node)
            f['alwaysOutputData'] = not f.get('alwaysOutputData', False)
        return e
    staged_p = synth('purge', 'Build Owner Alert (Purge)', 'Find Old Leads')
    staged_r = synth('reminders', 'Build Owner Alert (Reminders)')
    SP, SR = repo_file(staged_p), repo_file(staged_r)
    CP_EXPORT = 'n8n/workflow.purge.copy.sanitized.json'   # tracked and clean in a committed tree

    # 1. an E1-shaped and an E2-shaped edit: green, read back == the edit
    for spec, sfile, allow, staged in ((P, SP, E1, staged_p), (R, SR, E2, staged_r)):
        x = os.path.splitext(os.path.basename(spec))[0]
        committed, fake, oid, cid = world(x)
        rc, out = run(fake, ['put', spec, cid, sfile, '--allow', *allow])
        dr = drift(fake, cid, staged)
        case(f'{x}: put the staged edit, read back == staged', rc == 0 and fake.puts() == 1 and not dr, f'rc {rc} · PUTs {fake.puts()} · drift {dr[:1]}')

    # 2. put on an ACTIVE copy → refused, 0 PUT
    committed, fake, oid, cid = world(copy_active=True)
    rc, out = run(fake, ['put', P, cid, SP, '--allow', *E1])
    case('put on an ACTIVE copy is refused', rc == 1 and fake.puts() == 0 and 'not INACTIVE' in out, f'rc {rc} · PUTs {fake.puts()}')

    # 3. outside the allowlist: a node left out of --allow · an edge rewired · a flag on an allowed node · settings ·
    #    an OLDER revision of the copy's own export (the temporary trigger comes back)
    committed, live = H._simulated_live_copy(P)
    edge = copy.deepcopy(staged_p)
    src = next(k for k, v in edge['connections'].items() if v.get('main') and v['main'][0])
    edge['connections'][src]['main'][0] = [{'node': 'Verify Leads Purge', 'type': 'main', 'index': 0}]
    flag = copy.deepcopy(staged_p)
    next(n for n in flag['nodes'] if n['name'] == 'Find Old Leads')['onError'] = 'stopWorkflow'
    sett = dict(copy.deepcopy(staged_p), settings=dict(staged_p.get('settings') or {}, executionTimeout=999))
    for label, exp, allow in (('a changed node left out of --allow', SP, [n for n in E1 if n != 'Build Owner Alert (Purge)']), ('an edge rewired', repo_file(edge), E1),
                              ("an allowed node's onError changed", repo_file(flag), E1), ('settings changed', repo_file(sett), E1)):
        committed, fake, oid, cid = world()
        rc, out = run(fake, ['put', P, cid, exp, '--allow', *allow])
        case(f'refused before any PUT: {label}', rc == 1 and fake.puts() == 0 and 'allowlist' in out, f'rc {rc} · PUTs {fake.puts()}')
    old = __import__('subprocess').run(['git', '-C', ROOT, 'log', '--format=%H', '--', CP_EXPORT], capture_output=True,
                                       text=True).stdout.split()
    if len(old) >= 2:
        committed, fake, oid, cid = world()
        rc, out = run(fake, ['put', P, cid, f'{old[-1]}:n8n/workflow.purge.copy.sanitized.json', '--allow', *E1])
        case('an OLDER revision of the export (temporary trigger) is refused', rc == 1 and fake.puts() == 0, f'rc {rc} · {out.strip().splitlines()[-1][:100]}')
    else:
        case('an OLDER revision of the export (temporary trigger) is refused', False, 'the export has no older revision to test with')

    # 3b. an export that is NOT committed (untracked; and the staged file locally edited) is refused before any PUT
    with tempfile.NamedTemporaryFile('w', prefix='.wstest-', suffix='.json', delete=False, dir=os.path.join(ROOT, 'n8n', 'staged')) as t:
        json.dump(staged_p, t)
    tmp.append(t.name)
    committed, fake, oid, cid = world()
    rc, out = run(fake, ['put', P, cid, os.path.relpath(t.name, ROOT), '--allow', *E1])
    case('an UNTRACKED export file is refused', rc == 1 and fake.puts() == 0 and 'untracked' in out, f'rc {rc}')
    H_tc = W.tracked_clean
    W.tracked_clean = lambda rel: False if rel == SP else H_tc(rel)   # the edit file as if locally modified
    committed, fake, oid, cid = world()
    rc, out = run(fake, ['put', P, cid, SP, '--allow', *E1])
    W.tracked_clean = H_tc
    case('a locally modified export file is refused', rc == 1 and fake.puts() == 0, f'rc {rc}')
    if real_tc(CP_EXPORT):
        case('a committed export counts as tracked and clean', True, 'git ls-files + git diff --quiet HEAD')
    else:
        case('a committed export counts as tracked and clean', False, 'it is untracked or modified in this tree')

    # 3c. a schedule trigger in --allow, re-timed, is refused (the scope's only trigger type)
    tr = copy.deepcopy(staged_p)
    ptrig = next(n['name'] for n in tr['nodes'] if str(n['type']).endswith('Trigger'))
    next(n for n in tr['nodes'] if n['name'] == ptrig)['parameters']['rule'] = {'interval': [{'field': 'minutes'}]}
    committed, fake, oid, cid = world()
    rc, out = run(fake, ['put', P, cid, repo_file(tr), '--allow', *E1, ptrig])
    case('a re-timed schedule trigger in --allow is refused', rc == 1 and fake.puts() == 0 and 'trigger' in out, f'rc {rc}')

    # 3d. the copy reads back under ANOTHER name → refused before any write
    committed, fake, oid, cid = world()
    fake.wfs[cid]['name'] = 'Something Else'
    rc, out = run(fake, ['deactivate', P, cid])
    case('a copy that reads back under another name is refused', rc == 1 and not fake.writes(), f'rc {rc}')

    # 4. a PUT whose read-back differs is RED: n8n keeps a flag · changes settings · leaves the copy active · answers 500
    want_flag = next(n for n in staged_p['nodes'] if n['name'] == 'Find Old Leads').get('alwaysOutputData', False)

    def keep_flag(b):   # n8n does not apply the flag change the edit makes
        next(n for n in b['nodes'] if n['name'] == 'Find Old Leads')['alwaysOutputData'] = not want_flag
    for label, kw in (('n8n keeps alwaysOutputData', {'mangle': keep_flag}),
                      ('n8n changes the settings', {'mangle': lambda b: b.__setitem__('settings', dict(b['settings'], callerPolicy='any'))}),
                      ('the copy comes back active', {'mangle': lambda b: b.__setitem__('_active', True)}),
                      ('PUT answers 500', {'put_status': 500})):
        committed, fake, oid, cid = world(**kw)
        rc, out = run(fake, ['put', P, cid, SP, '--allow', *E1])
        case(f'put is RED when {label}', rc == 1, f'rc {rc}')

    # 5. R2b DEPLOY: put keeps a snapshot only of a REVIEWED state — the live copy must equal its committed export.
    #    After an edit the copy holds the (uncommitted-as-copy-export) edit, so a second put is refused; the undo is
    #    `rollback` to the snapshot, never "put the committed export".
    committed, fake, oid, cid = world()
    run(fake, ['put', P, cid, SP, '--allow', *E1])
    rc, out = run(fake, ['put', P, cid, 'HEAD:n8n/workflow.purge.copy.sanitized.json', '--allow', *E1])
    case('R2b: a put while the live copy is NOT its committed export (it holds the edit) → refused, 0 more PUT, no snapshot',
         rc == 1 and fake.puts() == 1 and 'not its committed export' in out and not os.path.exists(run.last_snap),
         f'rc {rc} · {out.strip().splitlines()[-1][:120]}')

    # 6. an unsanitised export (a real-looking chat id where the chat-id placeholder was, in `parameters` of a node put
    #    into --allow, so ONLY the sanitise check can refuse it) is refused before any PUT
    s = json.dumps(staged_p)
    ph = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
    holder = next((n['name'] for n in staged_p['nodes'] if ph in json.dumps(n.get('parameters'))), None)
    committed, fake, oid, cid = world()
    if holder:
        rc, out = run(fake, ['put', P, cid, repo_file(json.loads(s.replace(ph, '987654321'))), '--allow', *E1, holder])
        case('an unsanitised export is refused by the sanitise check', rc == 1 and fake.puts() == 0 and 'not sanitised' in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:90]}')
    else:
        case('an unsanitised export is refused by the sanitise check', False, f'no {ph} in the staged Purge export to test with')

    # 7. ROLES declares the ORIGINAL live → every command refused, no write
    H.ROLES_FILE = roles_file(live='original')
    tmp.append(H.ROLES_FILE)
    for argv in (['deactivate', P, 'CP'], ['put', P, 'CP', SP, '--allow', *E1], ['activate', P, 'CP']):
        committed, fake, oid, cid = world()
        rc, out = run(fake, argv)
        case(f'{argv[0]} refused when ROLES declares the original live', rc == 1 and not fake.writes(), f'rc {rc}')
    H.ROLES_FILE = roles_file()
    tmp.append(H.ROLES_FILE)

    # 8. the original not parked · the original's id · a copy of another spec · Main (outside scope) · a spec outside
    #    db/copies · an export outside the repo / another copy's REV:PATH / a stash selector
    committed, fake, oid, cid = world(orig_active=True)
    rc, _ = run(fake, ['put', P, cid, SP, '--allow', *E1])
    case('put refused while the original is active', rc == 1 and fake.puts() == 0, f'rc {rc}')
    committed, fake, oid, cid = world()
    rc, _ = run(fake, ['deactivate', P, oid])
    case("the original's id is refused as a target", rc == 1 and not fake.writes(), f'rc {rc}')
    committed, fake, oid, cid = world()
    rc, _ = run(fake, ['put', R, cid, SP, '--allow', *E1])
    case('a copy of another spec is refused', rc == 1 and fake.puts() == 0, f'rc {rc}')
    committed, fake, oid, cid = world('drill-state')
    rc, out = run(fake, ['deactivate', 'db/copies/drill-state.json', cid])
    case('Drill State is outside the scope (no write)', rc == 1 and not fake.writes() and 'scope' in out, f'rc {rc}')
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as t:   # the staged edit itself, outside the repo
        json.dump(staged_p, t)
    outside = t.name
    tmp.append(outside)
    odir = tempfile.mkdtemp(prefix='.wstest-', dir=os.path.join(ROOT, 'n8n', 'staged'))
    ospec = os.path.join(odir, 'purge.json')
    open(ospec, 'w', encoding='utf-8').write(open(os.path.join(ROOT, P), encoding='utf-8').read())
    tmp.extend([ospec, odir])
    for label, argv in (('a spec outside db/copies', ['put', os.path.relpath(ospec, ROOT), 'CP', SP, '--allow', *E1]),
                        ('a VALID export outside the repo', ['put', P, 'CP', outside, '--allow', *E1]),
                        ("another copy's REV:PATH", ['put', P, 'CP', 'HEAD:n8n/workflow.reminders.copy.sanitized.json', '--allow', *E1]),
                        ('a stash selector', ['put', P, 'CP', 'stash@{0}:n8n/workflow.purge.copy.sanitized.json', '--allow', *E1])):
        committed, fake, oid, cid = world()
        rc, _ = run(fake, argv)
        case(f'refused: {label}', rc == 1 and fake.puts() == 0, f'rc {rc}')

    # 9. deactivate / activate read back; RED when the read-back disagrees; activate RED when published != draft
    committed, fake, oid, cid = world(copy_active=True)
    rc1, _ = run(fake, ['deactivate', P, cid])
    a1 = fake.wfs[cid]['active']
    rc2, _ = run(fake, ['activate', P, cid])
    case('deactivate then activate read back', rc1 == 0 and a1 is False and rc2 == 0 and fake.wfs[cid]['active'] is True, f'rc {rc1}/{rc2}')
    committed, fake, oid, cid = world(copy_active=True, flip_ok=False)
    rc, _ = run(fake, ['deactivate', P, cid])
    case('deactivate is RED when the copy still reads active', rc == 1, f'rc {rc}')
    committed, fake, oid, cid = world(flip_ok=False)
    rc, _ = run(fake, ['activate', P, cid])
    case('activate is RED when the copy still reads inactive', rc == 1, f'rc {rc}')
    committed, fake, oid, cid = world(stale_published=True)
    fake.wfs[cid]['_published'] = {'nodes': fake.wfs[cid]['nodes'][1:], 'connections': fake.wfs[cid]['connections']}
    rc, _ = run(fake, ['activate', P, cid])
    case('activate is RED when published != draft', rc == 1, f'rc {rc}')

    # 11. THE WEBHOOK COPIES (7-2 Tur 2, Option A lifts "Main is not edited before ship"): Main and Owner Actions. The
    #     positive cases use the REAL staged exports and the REAL delta files — the approved deltas (ruling FIXED) — read
    #     through the TEST_FILES seam, so the suite is the same before and after they are committed.
    M = 'db/copies/main.json'
    O = 'db/copies/owner-actions.json'
    SM, DM = 'n8n/staged/workflow.main.copy.sanitized.json', 'n8n/staged/workflow.main.copy.delta.json'
    SO, DO = 'n8n/staged/workflow.owner-actions.copy.sanitized.json', 'n8n/staged/workflow.owner-actions.copy.delta.json'
    TEST_FILES.update({SM, DM, SO, DO})
    em = json.load(open(os.path.join(ROOT, SM), encoding='utf-8'))
    eo = json.load(open(os.path.join(ROOT, SO), encoding='utf-8'))
    TAG = 'Tag Turnstile Unavailable'
    committed, fake, oid, cid = world('main')
    s_before = copy.deepcopy(fake.wfs[cid].get('settings'))
    rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
    dr = drift(fake, cid, em)
    case('Main: put the staged edit with its APPROVED delta file, read back == staged, settings unchanged',
         rc == 0 and fake.puts() == 1 and not dr and 'webhook ids unchanged' in out and fake.wfs[cid].get('settings') == s_before,
         f'rc {rc} · drift {dr[:1]} · {out.strip().splitlines()[-1][:80]}')
    case('Main: the v1 sibling order is printed for both Turnstile failure outputs the tag joins',
         out.count(f'Reject Bot Request [2464, 4064] → {TAG}') == 2, f'{[l for l in out.splitlines() if "sibling" in l][:1]}')
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, SM, '--allow', 'Build Owner Alert'])
    case('Main: the staged edit WITHOUT its delta file (--allow only) is refused', rc == 1 and fake.puts() == 0, f'rc {rc}')
    tp = copy.deepcopy(em)
    next(n for n in tp['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['parameters']['responseMode'] = 'onReceived'
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, repo_file(tp), '--delta-file', DM])
    case('Main: an export that changes the trigger responseMode is refused', rc == 1 and fake.puts() == 0, f'rc {rc}')

    def m_webhook(b):
        next(n for n in b['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['webhookId'] = 'changed-by-n8n'

    def m_turnstile(b):
        lc = next(n for n in b['nodes'] if n['name'] == 'Load Config')['parameters']
        lc['jsCode'] = ts_off(lc['jsCode'])

    def m_retry(b):
        next(n for n in b['nodes'] if n['name'] == 'Build Owner Alert')['retryOnFail'] = True

    def m_setting(b):   # n8n (or a bug of ours) puts a setting on the copy during the edit PUT
        b['settings'] = dict(b.get('settings') or {}, saveDataSuccessExecution='none')

    def m_path(b):
        next(n for n in b['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['parameters']['path'] = 'moved-by-n8n'
    for label, mg in (('n8n changes the webhook id', m_webhook), ('n8n flips the Turnstile literal', m_turnstile),
                      ('n8n sets retryOnFail on a node', m_retry), ('a setting changes across the edit PUT', m_setting),
                      ('n8n moves the webhook path', m_path)):
        committed, fake, oid, cid = world('main', mangle=mg)
        rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
        case(f'Main: put is RED when {label}', rc == 1 and 'READ-BACK RED' in out, f'rc {rc} · {out.strip().splitlines()[-1][:110]}')
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, 'HEAD:n8n/workflow.main.copy.sanitized.json', '--delta-file', DM])
    case('Main: the approved delta against an export that does not carry it (HEAD) is refused, 0 PUT', rc == 1 and fake.puts() == 0, f'rc {rc}')

    # probe: judged on the n8n body
    committed, fake, oid, cid = world('main', copy_active=True)
    real_tp = H.turnstile_probe
    try:
        for res, want in (((True, 403), 0), ((False, 403), 1)):
            H.turnstile_probe = lambda path, o, c, r=res: r
            rc, out = run(fake, ['probe', M, cid])
            case(f'Main probe: dummy-token result {res} → exit {want}', rc == want and not fake.writes(), f'rc {rc}')
    finally:
        H.turnstile_probe = real_tp
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['probe', M, cid])
    case('probe on an INACTIVE copy is refused', rc == 1 and 'not ACTIVE' in out, f'rc {rc}')
    W.PROBE_WAIT_S = 0
    real_wp, env_keys = W.webhook_post, ('OWNER_HMAC_SECRET', 'CF_OWNER_ACCESS_CLIENT_ID', 'CF_OWNER_ACCESS_CLIENT_SECRET')
    saved = {k: os.environ.get(k) for k in env_keys}
    try:
        for k in env_keys:
            os.environ[k] = 'test-only-' + k.lower()
        seen = []

        def fake_post(answers, fake, *runners):
            def wp(path, body, headers):
                sig = headers.get('X-Owner-Signature')
                seen.append(sig == __import__('hmac').new(b'test-only-owner_hmac_secret', body.encode(), __import__('hashlib').sha256).hexdigest() if sig else None)
                assert headers.get('CF-Access-Client-Id') == 'test-only-cf_owner_access_client_id'
                for r in runners:   # the workflow(s) that ran it
                    fake.execs.setdefault(r, []).append('9999-12-31T00:00:00.000Z')
                return answers[1 if sig else 0]
            return wp
        good = ((403, {'error': 'invalid_signature'}), (404, {'error': 'not_found'}))
        for label, answers, want, by_orig in (('unsigned 403 invalid_signature + signed 404 not_found', good, 0, False),
                                              ('signed 503 store_unavailable', ((403, {'error': 'invalid_signature'}), (503, {'ok': False, 'error': 'store_unavailable'})), 0, False),
                                              ("Access's own 403 (no n8n body)", ((403, None), (404, {'error': 'not_found'})), 1, False),
                                              ('a bare 503 on the signed request', ((403, {'error': 'invalid_signature'}), (503, None)), 1, False),
                                              ('the signed request WRITES (200)', ((403, {'error': 'invalid_signature'}), (200, {'ok': True})), 1, False),
                                              ('the right answers, but the ORIGINAL executed them', good, 1, 'orig'),
                                              ('the right answers, executed by the copy AND the original', good, 1, 'both')):
            committed, fake, oid, cid = world('owner-actions', copy_active=True)
            W.webhook_post = fake_post(answers, fake, *{'orig': [oid], 'both': [cid, oid]}.get(by_orig, [cid]))
            rc, out = run(fake, ['probe', O, cid])
            case(f'Owner Actions probe: {label} → exit {want}', rc == want and not fake.writes(), f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
            if '503 store' in label:
                case('Owner Actions probe: a 503 store_unavailable is reported as "signature path alive, store unavailable"',
                     'signature path alive, store unavailable' in out, out.strip().splitlines()[-1][:160])
        case('Owner Actions probe signs the exact body with HMAC-SHA256', seen and all(x in (None, True) for x in seen) and True in seen, f'{seen[:4]}')
        committed, fake, oid, cid = world('owner-actions', copy_active=True)
        W.webhook_post = fake_post(good, fake, cid)
        next(n for n in fake.wfs[cid]['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['parameters']['path'] = 'live-draft-elsewhere'
        n0 = len(seen)
        rc, out = run(fake, ['probe', O, cid])
        case('probe: the path comes from the COMMITTED export; a live draft on another path is refused, nothing posted',
             rc == 1 and 'committed export' in out and len(seen) == n0, f'rc {rc} · posts {len(seen) - n0}')
        os.environ.pop('OWNER_HMAC_SECRET')
        committed, fake, oid, cid = world('owner-actions', copy_active=True)
        rc, out = run(fake, ['probe', O, cid])
        case('Owner Actions probe without its secrets is NOT MEASURED (refused)', rc == 1 and 'NOT MEASURED' in out, f'rc {rc}')
    finally:
        W.webhook_post = real_wp
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    # 12. GATE + the webhook invariants, each checked by put ITSELF before the PUT (ruling 2026-10-26; lane T H1/M3).
    #     `blind` makes diff-workflow-copy.compare return [] — a diff tool that misses the change — so each case shows
    #     that put's OWN check refuses it, not the diff behind it.
    real_compare = H.DIFF.compare

    @contextlib.contextmanager
    def blind():
        H.DIFF.compare = lambda *a, **k: []
        try:
            yield
        finally:
            H.DIFF.compare = real_compare

    def main_export(fn):
        e = json.load(open(os.path.join(ROOT, BASELINE['n8n/workflow.main.copy.sanitized.json']), encoding='utf-8'))
        next(n for n in e['nodes'] if n['name'] == 'Build Owner Alert')['parameters']['jsCode'] += '\n// the engine edit under test'
        return fn(e) or e

    def dfile(d, allow=('Build Owner Alert',)):
        """A delta file (written as a test file) holding `d` — parse_delta's shape."""
        return repo_file({'allow': list(allow), **{k: sorted(v) for k, v in d.items() if k != 'settings'},
                          **({'settings': d['settings']} if d.get('settings') else {})})

    @contextlib.contextmanager
    def approved_as(key, d):
        """APPROVED_DELTAS[key] replaced by `d`: a reviewer who approved a bad delta — what the GATE, kept as defence in
        depth, must still refuse."""
        saved = H.DIFF.APPROVED_DELTAS.get(key)
        H.DIFF.APPROVED_DELTAS[key] = {**{k: set(d.get(k) or ()) for k in H.DIFF.DELTA_KEYS}, 'settings': dict(d.get('settings') or {})}
        try:
            yield
        finally:
            H.DIFF.APPROVED_DELTAS[key] = saved

    def removal(e, name):
        """Remove `name` and its edges, re-wire each predecessor to each successor → that delta (a dict)."""
        E = {f"{s}|{i}|{x['node']}|{x.get('index', 0)}" for s, v in e['connections'].items()
             for i, l in enumerate(v.get('main') or []) for x in l}
        ins, outs = [x for x in E if x.split('|')[2] == name], [x for x in E if x.split('|')[0] == name]
        add = sorted({f"{i.split('|')[0]}|{i.split('|')[1]}|{o.split('|')[2]}|{o.split('|')[3]}" for i in ins for o in outs} - E)
        e['nodes'] = [n for n in e['nodes'] if n['name'] != name]
        e['connections'].pop(name, None)
        for k, v in e['connections'].items():
            for i, l in enumerate(v.get('main') or []):
                if any(x['node'] == name for x in l):
                    l[:] = [x for x in l if x['node'] != name] + [{'node': a.split('|')[2], 'type': 'main', 'index': int(a.split('|')[3])}
                                                                  for a in add if a.startswith(f'{k}|{i}|')]
        return {'remove_nodes': {name}, 'remove_edges': set(ins) | set(outs), 'add_edges': set(add)}

    h1 = main_export(lambda e: None)
    h1_d = removal(h1, 'Load Config')
    H1F, H1D = repo_file(h1), dfile(h1_d)
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, H1F, '--delta-file', H1D])
    case('Main H1: Load Config removed, its edges declared, predecessors re-wired → refused: NOT an approved delta, 0 PUT',
         rc == 1 and fake.puts() == 0 and 'not an approved delta' in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    for label, ctx in (('the diff in place', contextlib.nullcontext), ('even with the diff blind', blind)):
        committed, fake, oid, cid = world('main')
        with ctx(), approved_as('main', h1_d):
            rc, out = run(fake, ['put', M, cid, H1F, '--delta-file', H1D])
        case(f'Main H1, the same delta as if APPROVED → still refused by the GATE before any PUT ({label})',
             rc == 1 and fake.puts() == 0 and 'GATE' in out, f'rc {rc} · PUTs {fake.puts()} · {out.strip().splitlines()[-1][:120]}')
    vt = main_export(lambda e: None)
    vt_d = removal(vt, 'Verify Turnstile')
    VTF, VTD = repo_file(vt), dfile(vt_d)
    for label, argv in (('Verify Turnstile in --allow (unchanged)', ['put', M, '{cid}', SM, '--allow', 'Build Owner Alert', 'Verify Turnstile']),
                        ('Turnstile Valid? in --allow (unchanged)', ['put', M, '{cid}', SM, '--allow', 'Build Owner Alert', 'Turnstile Valid?']),
                        ('the webhook trigger in --allow (unchanged)', ['put', M, '{cid}', SM, '--allow', 'Build Owner Alert', 'Receive Inbound Message']),
                        ('Verify Turnstile removed with its edges declared and re-wired, as if APPROVED', ['put', M, '{cid}', VTF, '--delta-file', VTD])):
        committed, fake, oid, cid = world('main')
        with blind(), approved_as('main', vt_d):
            rc, out = run(fake, [a.replace('{cid}', cid) for a in argv])
        case(f'GATE in put (diff blind): {label} → refused, 0 PUT', rc == 1 and fake.puts() == 0 and 'GATE' in out,
             f'rc {rc} · PUTs {fake.puts()} · {out.strip().splitlines()[-1][:100]}')
    lit = main_export(lambda e: None)
    lc = next(n for n in lit['nodes'] if n['name'] == 'Load Config')['parameters']
    lc['jsCode'] = ts_off(lc['jsCode'])
    tr = main_export(lambda e: None)
    next(n for n in tr['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['parameters']['responseMode'] = 'onReceived'
    for label, exp, needle in (('the Turnstile literal flipped to false', lit, 'Turnstile literal'),
                               ("the trigger's responseMode changed", tr, 'webhook trigger')):
        committed, fake, oid, cid = world('main')
        with blind():
            rc, out = run(fake, ['put', M, cid, repo_file(exp), '--allow', 'Build Owner Alert'])
        case(f'webhook invariant in put (diff blind): {label} → refused, 0 PUT', rc == 1 and fake.puts() == 0 and needle in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    real_ce = H.committed_export

    def off_at_head(path, rev='HEAD'):   # HEAD's Main export as if it already said enabled: false (lane T M3)
        w = real_ce(path, rev)
        if path.endswith('main.copy.sanitized.json'):
            n = next(n for n in w['nodes'] if n['name'] == 'Load Config')['parameters']
            n['jsCode'] = ts_off(n['jsCode'])
        return w
    committed, fake, oid, cid = world('main')
    H.committed_export = off_at_head
    try:
        rc, out = run(fake, ['put', M, cid, 'HEAD:n8n/workflow.main.copy.sanitized.json', '--allow', 'Build Owner Alert'])
    finally:
        H.committed_export = real_ce
    case('M3: the committed export ALREADY says enabled: false — "unchanged" is refused, 0 PUT', rc == 1 and fake.puts() == 0
         and 'Turnstile literal' in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    oa = json.load(open(os.path.join(ROOT, BASELINE['n8n/workflow.owner-actions.copy.sanitized.json']), encoding='utf-8'))
    oa['nodes'].append({'name': 'Load Config', 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': [0, 0],
                        'parameters': {'jsCode': 'return [{json: {turnstile: { enabled: false, mode: "x" }}}];'}})
    oa2 = copy.deepcopy(oa)
    oa2['nodes'][-1]['parameters']['jsCode'] = 'return [{json: {turnstile: { enabled: false }}}];'
    for label, exp, needle in (('a Load Config whose Turnstile literal is not of the exact shape', oa, 'exact Turnstile'),
                               ('a Load Config with an exact Turnstile literal the committed export has none of', oa2, 'does not')):
        committed, fake, oid, cid = world('owner-actions')
        with blind():
            rc, out = run(fake, ['put', O, cid, repo_file(exp), '--allow', 'Respond Owner OK'])
        case(f'webhook invariant in put (diff blind): an Owner Actions export gaining {label} → refused, 0 PUT',
             rc == 1 and fake.puts() == 0 and needle in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')

    # 12b. A LIVE webhookId on a node the edit drops (R3, ruling 2026-10-26). The fake live carries real-shaped ids on the
    #      trigger and every Telegram node (live_hooks). put passes the approved delta's remove_nodes to fill_by_path;
    #      only a NON-trigger node named there may drop its id. Each half is shown by a case that only it can fail.
    committed, fake, oid, cid = world('owner-actions')
    TGX = 'Send Marker Failure Alert (Telegram)'
    kept = {n['name']: n['webhookId'] for n in fake.wfs[cid]['nodes'] if n.get('webhookId') and n['name'] != TGX}
    rc, out = run(fake, ['put', O, cid, SO, '--delta-file', DO])
    after = {n['name']: n.get('webhookId') for n in fake.wfs[cid]['nodes']}
    case(f'R3: Owner Actions put drops {TGX!r} (live webhookId, in the approved remove_nodes) — every other live id kept',
         rc == 0 and fake.puts() == 1 and TGX not in after and all(after.get(k) == v for k, v in kept.items()) and len(kept) == 3,
         f'rc {rc} · kept {len(kept)} · {out.strip().splitlines()[-1][:90]}')
    lo = live_hooks(H._simulated_live_copy(O)[1])
    trig = next(n['name'] for n in lo['nodes'] if n['type'] == 'n8n-nodes-base.webhook')
    tg_other = 'Send Owner Alert (Telegram)'

    def without(wf, *names):
        return dict(copy.deepcopy(wf), nodes=[n for n in copy.deepcopy(wf['nodes']) if n['name'] not in names])
    rm = sorted(H.DIFF.APPROVED_DELTAS['owner-actions']['remove_nodes'])
    for label, exp, removable, want_ok in (
            ('the approved removal of the Telegram node', without(lo, TGX), rm, True),
            ('a Telegram node OUTSIDE the delta dropped', without(lo, TGX, tg_other), rm, False),
            ('the webhook trigger dropped, even when named removable', without(lo, trig), [trig], False),
            ('a Telegram node dropped with no removable list (the helper\'s own callers)', without(lo, TGX), (), False)):
        try:
            H.fill_by_path(lo, exp, removable=removable)
            got = True
        except ValueError as e:   # refused for THIS reason, or the case fails
            got = False if 'webhookId' in str(e) else f'refused for another reason: {str(e)[:60]}'
        case(f'R3 fill_by_path: {label} → {"allowed" if want_ok else "refused"}', got is want_ok,
             f'got {"allowed" if got is True else "refused" if got is False else got}')
    tt = copy.deepcopy(lo)
    next(n for n in tt['nodes'] if n['name'] == TGX)['type'] = 'n8n-nodes-base.telegramTrigger'
    try:
        H.fill_by_path(tt, without(tt, TGX), removable=rm)
        got = True
    except ValueError as e:   # refused for THIS reason, or the case fails
        got = False if 'webhookId' in str(e) else f'refused for another reason: {str(e)[:60]}'
    case('R3 fill_by_path: a Telegram TRIGGER named in remove_nodes → refused (no trigger is removable)', got is False,
         f'got {"allowed" if got is True else "refused" if got is False else got}')
    legacy = sorted(H.DIFF.LEGACY_TRIGGER_TYPES)[0]
    next(n for n in tt['nodes'] if n['name'] == TGX)['type'] = legacy
    try:
        H.fill_by_path(tt, without(tt, TGX), removable=rm)
        got = True
    except ValueError as e:   # refused for THIS reason, or the case fails
        got = False if 'webhookId' in str(e) else f'refused for another reason: {str(e)[:60]}'
    case(f'R3 fill_by_path: a legacy trigger type ({legacy.split(".")[-1]}) named in remove_nodes → refused (diff-workflow-copy\'s '
         'one trigger definition, not a copy)', got is False, f'got {"allowed" if got is True else "refused" if got is False else got}')

    # 13. ids from argv are letters and digits only (lane T M2): refused before ANY call
    committed, fake, oid, cid = world('main')
    for bad in ('SCR/../' + cid, cid + '?x=1', cid + '#', ''):
        for argv in (['scratch-delete', M, bad], ['activate', M, bad], ['put', M, bad, SM, '--allow', 'Build Owner Alert']):
            rc, out = run(fake, argv)
            case(f'id {bad!r} on {argv[0]} → refused, no call', rc in (1, 2) and not fake.calls, f'rc {rc} · calls {len(fake.calls)}')

    # 14. delta files: the two real ones parse and ARE the approved deltas; a bad file, the removed keys (move_nodes,
    #     remove_settings) and an unapproved delta are refused; the CLI takes --allow XOR --delta-file, nothing else
    for f, key in ((DM, 'main'), (DO, 'owner-actions')):
        a, d = H.DIFF.load_delta_file(os.path.join(ROOT, f))
        shape = (isinstance(a, list) and a and set(d) == {*H.DIFF.DELTA_KEYS, 'settings'}
                 and all(isinstance(d[k], set) for k in H.DIFF.DELTA_KEYS) and isinstance(d['settings'], dict))
        case(f'delta file {os.path.basename(f)} parses and IS the approved delta for {key}',
             shape and not H.DIFF.approved_errs(key, d), f'allow {len(a)} · approved_errs {H.DIFF.approved_errs(key, d)[:1]}')
    for label, obj in (('an unknown key', {'allow': ['A'], 'add_node': ['x']}), ('an empty allow', {'allow': []}),
                       ('an edge of the wrong form', {'allow': ['A'], 'add_edges': ['A|B']}), ('a repeated entry', {'allow': ['A', 'A']}),
                       ('a list of non-strings', {'allow': ['A'], 'remove_nodes': [1]}), ('not an object', ['A']),
                       ('move_nodes (removed in R1d)', {'allow': ['A'], 'move_nodes': ['N']}),
                       ('remove_settings (removed in R1d)', {'allow': ['A'], 'remove_settings': ['k']}),
                       ('settings holding an object', {'allow': ['A'], 'settings': {'k': {'x': 1}}}),
                       ('settings holding null', {'allow': ['A'], 'settings': {'k': None}}),
                       ('an empty settings object', {'allow': ['A'], 'settings': {}})):
        try:
            H.DIFF.load_delta_file(os.path.join(ROOT, repo_file(obj)))
            case(f'delta file with {label} is refused', False, 'parsed')
        except ValueError as e:
            case(f'delta file with {label} is refused', True, str(e)[:80])
    allow_m, appr_m = H.DIFF.load_delta_file(os.path.join(ROOT, DM))
    _, appr_o = H.DIFF.load_delta_file(os.path.join(ROOT, DO))
    plus_edge = dict(appr_m, add_edges=appr_m['add_edges'] | {f'{TAG}|0|Check Processed|0'})
    bypass = copy.deepcopy(em)
    bypass['connections'][TAG]['main'][0].append({'node': 'Check Processed', 'type': 'main', 'index': 0})
    for label, spec, exp, d in (('Main: the approved delta + ONE edge between non-gate nodes (T HIGH-1, Turnstile reject → claim)',
                                 M, repo_file(bypass), plus_edge),
                                ('Main: the approved delta minus one approved edge removal', M, SM,
                                 dict(appr_m, remove_edges=set(sorted(appr_m['remove_edges'])[1:]))),
                                ('Owner Actions: the approved delta with a setting added (availableInMCP)', O, SO,
                                 dict(appr_o, settings=dict(appr_o['settings'], availableInMCP=True))),
                                ("Owner Actions: the approved setting with another value ('all')", O, SO,
                                 dict(appr_o, settings={'saveDataSuccessExecution': 'all'})),
                                ('Purge: any delta at all (no approved delta)', P, SP, {'remove_nodes': {'Find Old Leads'}})):
        committed, fake, oid, cid = world(os.path.splitext(os.path.basename(spec))[0])
        rc, out = run(fake, ['put', spec, cid, exp, '--delta-file', dfile(d, allow=('Build Owner Alert',))])
        case(f'FIXED: {label} → refused, NOT an approved delta, 0 PUT', rc == 1 and fake.puts() == 0 and 'not an approved delta' in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    for label, argv in (('--allow and --delta-file', ['--delta-file', DM, '--allow', 'Build Owner Alert']),
                        ('--add-node (removed)', ['--delta-file', DM, '--add-node', TAG]),
                        ('--move-node (removed)', ['--delta-file', DM, '--move-node', 'Reject Bot Request']),
                        ('--remove-edge (removed)', ['--allow', 'Build Owner Alert', '--remove-edge', 'A|0|B|0']),
                        ('--scratch (not on the command line)', ['--delta-file', DM, '--scratch']),
                        ('two delta files', ['--delta-file', DM, '--delta-file', DM]),
                        ('a missing path', ['--delta-file'])):
        committed, fake, oid, cid = world('main')
        rc, out = run(fake, ['put', M, cid, SM, *argv])
        case(f'put: {label} → usage, no call', rc == 2 and not fake.calls, f'rc {rc}')
    UNT = repo_file({'_doc': 'x', 'allow': ['Build Owner Alert'], **{k: sorted(v) for k, v in appr_m.items() if k != 'settings'}})
    TEST_FILES.discard(UNT)
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, SM, '--delta-file', UNT])
    TEST_FILES.add(UNT)
    case('put: an untracked delta file (even with the approved content) is refused before any PUT',
         rc == 1 and fake.puts() == 0 and 'untracked' in out, f'rc {rc}')
    dcli = __import__('subprocess').run([sys.executable, DIFF_SRC, os.path.join(ROOT, BASELINE['n8n/workflow.main.copy.sanitized.json']),
                                         os.path.join(ROOT, SM), '--phase', 'edit', '--delta-file', os.path.join(ROOT, DM), '--allow', 'X'],
                                        capture_output=True, text=True)
    case('diff-workflow-copy CLI: --delta-file mixed with --allow → exit 2', dcli.returncode == 2 and 'mutually exclusive' in dcli.stderr, f'rc {dcli.returncode}')
    dcli = __import__('subprocess').run([sys.executable, DIFF_SRC, os.path.join(ROOT, BASELINE['n8n/workflow.main.copy.sanitized.json']),
                                         os.path.join(ROOT, SM), '--phase', 'edit', '--add-node', TAG, '--allow', 'X'],
                                        capture_output=True, text=True)
    case('diff-workflow-copy CLI: --add-node (removed) → exit 2', dcli.returncode == 2, f'rc {dcli.returncode}')
    dcli = __import__('subprocess').run([sys.executable, DIFF_SRC, os.path.join(ROOT, BASELINE['n8n/workflow.main.copy.sanitized.json']),
                                         os.path.join(ROOT, SM), '--phase', 'edit', '--delta-file', os.path.join(ROOT, DM)], capture_output=True, text=True)
    case('diff-workflow-copy CLI: the staged Main export + its delta file → OK', dcli.returncode == 0, f'rc {dcli.returncode} · {dcli.stdout.strip().splitlines()[-1][:80]}')

    # 15. SNAPSHOT (ruling SNAPSHOT): put keeps the live workflow taken immediately before its PUT — a new 0600 file outside
    #     the repo — and `rollback` restores it, proven GET == snapshot (nodes, credential ids, connections, settings)
    committed, fake, oid, cid = world('main')
    pre = copy.deepcopy(H._draft(fake.wfs[cid]))
    rc1, out1 = run(fake, ['put', M, cid, SM, '--delta-file', DM])
    S1 = run.last_snap
    snap = json.load(open(S1, encoding='utf-8')) if os.path.isfile(S1) else {}
    case('snapshot: the file holds the live workflow as it was immediately before the PUT, mode 0600, outside the repo',
         rc1 == 0 and snap.get('workflow') == pre and snap.get('workflow_id') == cid and snap.get('spec') == 'main'
         and oct(os.stat(S1).st_mode & 0o777) == '0o600' and not S1.startswith(ROOT), f'rc {rc1} · {S1[-30:]}')
    rc2, out2 = run(fake, ['rollback', M, cid, S1])
    after = H._draft(fake.wfs[cid])
    case('rollback: the copy holds the edit; rollback S1 → GET == the pre-edit live workflow EXACTLY (nodes, credential ids, connections, settings)',
         rc2 == 0 and after == pre and fake.puts() == 2 and 'read back == the snapshot' in out2, f'rc {rc2} · {out2.strip().splitlines()[-1][:120]}')
    case('rollback: no placeholder fill and no export is involved — the body sent IS the snapshot',
         'credential id' in out2 and json.dumps(after, sort_keys=True) == json.dumps(snap['workflow'], sort_keys=True), out2.strip()[-80:])
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
    S1 = run.last_snap
    for label, mg, needle in (("n8n changes a node's credential id", lambda b: next(n for n in b['nodes'] if n.get('credentials'))['credentials']
                               .__setitem__(next(iter(next(n for n in b['nodes'] if n.get('credentials'))['credentials'])), {'id': 'other', 'name': 'x'}),
                               'credential ids'),
                              ('n8n drops a setting', lambda b: b.__setitem__('settings', {}), 'settings'),
                              ('n8n reorders an output', lambda b: b['connections']['Turnstile Gate']['main'].reverse(), 'connections')):
        f2 = copy.deepcopy(fake)
        f2.mangle = mg
        rc, out = run(f2, ['rollback', M, cid, S1])
        case(f'rollback is RED when {label} (the snapshot is unchanged, the message says so)',
             rc == 1 and 'ROLLBACK READ-BACK RED' in out and needle in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    f2 = copy.deepcopy(fake)
    f2.put_status = 500
    rc, out = run(f2, ['rollback', M, cid, S1])
    case('rollback: PUT answers 500 → RED, "NOT restored", retry the rollback', rc == 1 and 'NOT restored' in out, f'rc {rc}')
    outside_snap = repo_file({'x': 1})
    other = snap_path()
    json.dump(dict(json.load(open(S1)), workflow_id='CPX'), open(other, 'w'))
    other_spec = snap_path()
    json.dump(dict(json.load(open(S1)), spec='owner-actions'), open(other_spec, 'w'))
    bad_snap = snap_path()
    open(bad_snap, 'w').write('{"workflow": 3}')
    def snap_with(fn):   # S1, changed by fn, as a NEW snapshot file (a leftover / already-wrong snapshot)
        d = json.load(open(S1))
        fn(d['workflow'])
        p_ = snap_path()
        json.dump(d, open(p_, 'w'))
        return p_

    def ts_flip(wf):
        lc = next(n for n in wf['nodes'] if n['name'] == 'Load Config')['parameters']
        lc['jsCode'] = ts_off(lc['jsCode'])

    def path_move(wf):
        next(n for n in wf['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['parameters']['path'] = 'elsewhere'
    ts_snap, path_snap = snap_with(ts_flip), snap_with(path_move)
    for label, path, active in (('the copy is ACTIVE', S1, True), ('a snapshot of another workflow id', other, False),
                                ('a snapshot whose Turnstile literal is off (T-1: a weaker gate)', ts_snap, False),
                                ('a snapshot whose webhook path differs from the committed trigger (T-1)', path_snap, False),
                                ('a snapshot of another spec', other_spec, False), ('a snapshot path inside the repo', outside_snap, False),
                                ('a snapshot that does not exist', snap_path(), False), ('a snapshot that does not hold a workflow', bad_snap, False)):
        f2 = copy.deepcopy(fake)
        f2.wfs[cid]['active'] = active
        f2.calls = []
        rc, out = run(f2, ['rollback', M, cid, path])
        case(f'rollback refused, no write: {label}', rc == 1 and not f2.writes(), f'rc {rc} · {out.strip().splitlines()[-1][:110]}')
    in_repo = os.path.join(ROOT, 'n8n', 'staged', '.wstest-snap.json')
    tmp.append(in_repo)   # a mutant that lets it through must not leave it behind for the next run
    for label, sp_ in (('an existing file (never overwritten)', S1), ('a path inside the repository', in_repo),
                       ('a directory that does not exist', os.path.join(SNAPDIR, 'nope', 's.json'))):
        committed, fake, oid, cid = world('main')
        before = open(S1).read()
        rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM, '--snapshot', sp_])
        case(f'put: the snapshot is {label} → refused, 0 PUT', rc == 1 and fake.puts() == 0 and open(S1).read() == before
             and not os.path.exists(in_repo), f'rc {rc} · {out.strip().splitlines()[-1][:110]}')
    link = os.path.join(SNAPDIR, 'repo-link')
    os.symlink(ROOT, link)
    saved_root = W.ROOT
    W.ROOT = link
    try:
        judged = (W._outside_repo(os.path.join(ROOT, 'n8n', 'x.json')), W._outside_repo(os.path.join(ROOT, '.git', 'x')),
                  W._outside_repo(os.path.join(SNAPDIR, 'x.json')))
    finally:
        W.ROOT = saved_root
    case('snapshot path (T-2): with the repo reached through a symlink, a path in the real repo or its .git is still INSIDE',
         judged == (False, False, True), f'{judged}')
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, SM, '--allow', 'Build Owner Alert', 'Verify Turnstile'])
    case('put refused before the PUT writes no snapshot', rc == 1 and not os.path.exists(run.last_snap), f'rc {rc}')
    committed, fake, oid, cid = world('main', put_status=500)
    rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
    case('put: PUT answers 500 → RED and the message names the snapshot to roll back from', rc == 1 and run.last_snap in out
         and os.path.isfile(run.last_snap), f'rc {rc}')

    # 15a. R2b DEPLOY (Codex R2 deploy HIGH): a gate weakened IN THE LIVE COPY by hand (the Turnstile literal still on)
    #      — put refuses before keeping a snapshot, so no rollback can ever restore it; likewise Owner Actions'
    #      signature check, a setting drifted live, and a live copy that carries a sanitize placeholder.
    def live_gate_true(w):
        n = next(n for n in w['nodes'] if n['name'] == 'Turnstile Valid?')
        n['parameters'] = dict(n['parameters'], conditions={'options': {}, 'conditions': [], 'combinator': 'and'})

    def live_sig_valid(w):
        next(n for n in w['nodes'] if n['name'] == 'Verify Owner Signature')['parameters']['jsCode'] = 'return [{json: {valid: true}}];'

    def live_setting(w):
        w['settings'] = dict(w.get('settings') or {}, saveDataSuccessExecution='none')

    def live_placeholder(w):
        n = next(n for n in w['nodes'] if n.get('credentials'))
        k = next(iter(n['credentials']))
        n['credentials'][k] = dict(n['credentials'][k], id='REPLACE_WITH_POSTGRES_CREDENTIAL_ID')
    for label, spec, exp, df, fn in (("Main: 'Turnstile Valid?' made always-true in the live copy", M, SM, DM, live_gate_true),
                                     ("Owner Actions: 'Verify Owner Signature' made always-valid in the live copy", O, SO, DO, live_sig_valid),
                                     ('Owner Actions: a setting drifted in the live copy', O, SO, DO, live_setting),
                                     ('Main: the live copy carries a sanitize placeholder', M, SM, DM, live_placeholder)):
        committed, fake, oid, cid = world(os.path.splitext(os.path.basename(spec))[0])
        fn(fake.wfs[cid])
        rc, out = run(fake, ['put', spec, cid, exp, '--delta-file', df])
        case(f'R2b put refused, 0 PUT, NO snapshot: {label}', rc == 1 and fake.puts() == 0 and 'committed export' in out
             and not os.path.exists(run.last_snap), f'rc {rc} · {out.strip().splitlines()[-1][:130]}')
    for label, who in (('copy AND original drifted alike (only the committed comparison sees it)', 'both'),
                       ("the ORIGINAL's settings differ from the copy's (only the copy-vs-original comparison sees it)", 'orig')):
        committed, fake, oid, cid = world('main')
        for w in ([fake.wfs[cid], fake.wfs[oid]] if who == 'both' else [fake.wfs[oid]]):
            w['settings'] = dict(w.get('settings') or {}, timezone='Europe/Vienna')
        rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
        case(f'R2b put refused, 0 PUT: settings — {label}', rc == 1 and fake.puts() == 0 and 'settings' in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:130]}')
    committed, fake, oid, cid = world('owner-actions')
    run(fake, ['put', O, cid, SO, '--delta-file', DO])
    live_setting(fake.wfs[cid])   # the edit is live, but a setting moved before the settings step
    n0 = fake.puts()
    rc, out = run(fake, ['settings', O, cid, SO, '--delta-file', DO])
    case('R2b settings refused, 0 PUT, no snapshot: the live settings are not the committed ones before the step',
         rc == 1 and fake.puts() == n0 and 'parity' in out and not os.path.exists(run.last_snap), f'rc {rc} · {out.strip().splitlines()[-1][:130]}')

    # 15b. lane T review (R1d): the behaviours no earlier case pinned
    def applied_but(status, fake):   # n8n applies the PUT and still answers `status`
        real = fake.api

        def api(method, path, body=None):
            r = real(method, path, body)
            return (status, {}) if method == 'PUT' else r
        return api
    committed, fake, oid, cid = world('main')
    run(fake, ['put', M, cid, SM, '--delta-file', DM])
    S1b = run.last_snap
    fake.api = applied_but(502, fake)
    rc, out = run(fake, ['rollback', M, cid, S1b])
    case('rollback: a 502 although n8n applied it → judged on the read-back ("restored"), never a false "NOT restored"',
         rc == 1 and 'restored' in out and 'NOT restored' not in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')

    def cred_swap(b):   # a masked value (a credential id) changed by n8n during the PUT: only the body comparison sees it
        n = next(n for n in b['nodes'] if n.get('credentials'))
        k = next(iter(n['credentials']))
        n['credentials'][k] = dict(n['credentials'][k], id='changed-by-n8n')
    committed, fake, oid, cid = world('main', mangle=cred_swap)
    rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
    case('put is RED when n8n changes a credential id (a masked value: only the read-back == body sent catches it)',
         rc == 1 and 'READ-BACK RED' in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    for label, cmd_fn in (('put', lambda cid: ['put', M, cid, SM, '--delta-file', DM]),):
        committed, fake, oid, cid = world('main', mangle=lambda b: b.__setitem__('_active', True))
        rc, out = run(fake, cmd_fn(cid))
        case(f'{label}: the copy comes back ACTIVE → RED, and the message says ACTIVE and `deactivate` first (never "inactive")',
             rc == 1 and 'ACTIVE' in out and 'deactivate' in out and 'holds what n8n kept, inactive' not in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:140]}')
    committed, fake, oid, cid = world('owner-actions')
    run(fake, ['put', O, cid, SO, '--delta-file', DO])
    fake.mangle = lambda b: b.__setitem__('_active', True)
    rc, out = run(fake, ['settings', O, cid, SO, '--delta-file', DO])
    case('settings: the copy comes back ACTIVE → RED, message says ACTIVE', rc == 1 and 'ACTIVE' in out and 'READ-BACK RED' in out,
         f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world('main')
    run(fake, ['put', M, cid, SM, '--delta-file', DM])
    S1c = run.last_snap
    for label, mg, needle in (('comes back ACTIVE', lambda b: b.__setitem__('_active', True), 'ACTIVE'),
                              ('changes the name', lambda b: b.__setitem__('name', 'Renamed'), 'name')):
        f2 = copy.deepcopy(fake)
        f2.mangle = mg
        rc, out = run(f2, ['rollback', M, cid, S1c])
        case(f'rollback is RED when n8n {label}', rc == 1 and 'ROLLBACK READ-BACK RED' in out and needle in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world('owner-actions')
    run(fake, ['put', O, cid, SO, '--delta-file', DO])
    S1o = run.last_snap
    run(fake, ['settings', O, cid, SO, '--delta-file', DO])
    fake.mangle = lambda b: b['settings'].__setitem__('saveDataSuccessExecution', 'none')   # n8n MERGES settings
    rc, out = run(fake, ['rollback', O, cid, S1o])
    case('rollback is RED when n8n merges settings instead of replacing them (the T-4 key would stay live)',
         rc == 1 and 'settings differ' in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world('owner-actions')
    rc, out = run(fake, ['settings', O, cid, 'HEAD:n8n/workflow.owner-actions.copy.sanitized.json', '--delta-file', DO])
    case('settings with EXPORT = the committed export on an UNEDITED copy → refused (EXPORT is not the approved edit), 0 PUT',
         rc == 1 and fake.puts() == 0 and 'not the approved edit' in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world()
    rc, out = run(fake, ['settings', P, cid, SP, '--delta-file', dfile({'settings': {'executionOrder': 'v0'}}, allow=E1)])
    case('settings: a settings-ONLY delta on a copy with no approved delta (Purge) → refused, 0 PUT',
         rc == 1 and fake.puts() == 0 and 'not an approved' in out, f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world('main')
    real_g, seen = fake.api, []

    def flip_after_first_read(method, path, body=None):   # the copy is activated between put's first read and its PUT
        r = real_g(method, path, body)
        if method == 'GET' and path == f'/workflows/{cid}':
            seen.append(1)
            if len(seen) == 1:
                fake.wfs[cid]['active'] = True
        return r
    fake.api = flip_after_first_read
    rc, out = run(fake, ['put', M, cid, SM, '--delta-file', DM])
    case('put re-reads the copy IMMEDIATELY before the PUT: activated in between → refused, 0 PUT, no snapshot',
         rc == 1 and fake.puts() == 0 and 'immediately before the PUT' in out and not os.path.exists(run.last_snap),
         f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    in_repo_snap = repo_file(json.load(open(S1c)))   # a VALID snapshot, placed inside the repo
    committed, fake, oid, cid = world('main')
    run(fake, ['put', M, cid, SM, '--delta-file', DM])
    fake.calls = []
    rc, out = run(fake, ['rollback', M, cid, in_repo_snap])
    case('rollback refused, no write: a VALID snapshot that sits inside the repo (refused for WHERE it is)',
         rc == 1 and not fake.writes() and 'outside the repository' in out, f'rc {rc} · {out.strip().splitlines()[-1][:110]}')

    # 16. T-4 (ruling T-4): put NEVER carries a setting; `settings` applies exactly the approved one, LAST — refused before
    #     the edit is live — and its read-back keeps every node, connection and other setting
    KEY = 'saveDataSuccessExecution'
    committed, fake, oid, cid = world('owner-actions')
    s0 = copy.deepcopy(fake.wfs[cid].get('settings') or {})
    rc, out = run(fake, ['settings', O, cid, SO, '--delta-file', DO])
    case('settings BEFORE the edit is live → refused ("applied LAST"), 0 PUT', rc == 1 and fake.puts() == 0 and 'LAST' in out, f'rc {rc}')
    rc1, out1 = run(fake, ['put', O, cid, SO, '--delta-file', DO])
    case('Owner Actions put with the approved delta (which declares the setting): green, the setting NOT sent',
         rc1 == 0 and (fake.wfs[cid].get('settings') or {}) == s0 and KEY not in (fake.wfs[cid].get('settings') or {}),
         f'rc {rc1} · {out1.strip().splitlines()[-1][:100]}')
    S1 = run.last_snap
    nodes_before = copy.deepcopy(fake.wfs[cid]['nodes'])
    rc2, out2 = run(fake, ['settings', O, cid, SO, '--delta-file', DO])
    S2 = run.last_snap
    case('settings after the edit: exactly saveDataSuccessExecution "none" set, nodes and other settings unchanged',
         rc2 == 0 and fake.wfs[cid]['settings'] == dict(s0, **{KEY: 'none'}) and fake.wfs[cid]['nodes'] == nodes_before,
         f'rc {rc2} · {out2.strip().splitlines()[-1][:110]}')
    rc3, out3 = run(fake, ['rollback', O, cid, S1])
    case('rollback to the PRE-EDIT snapshot undoes the edit AND the setting (the key reads back absent)',
         rc3 == 0 and KEY not in (fake.wfs[cid].get('settings') or {}), f'rc {rc3}')
    for label, kw, needle in (('n8n does not keep the value', {'mangle': lambda b: b['settings'].pop(KEY, None)}, 'settings'),
                              ('n8n changes a node during the settings PUT', {'mangle': lambda b: b['nodes'].pop()}, 'nodes')):
        committed, fake, oid, cid = world('owner-actions')
        run(fake, ['put', O, cid, SO, '--delta-file', DO])
        fake.mangle = kw['mangle']
        rc, out = run(fake, ['settings', O, cid, SO, '--delta-file', DO])
        case(f'settings is RED when {label}', rc == 1 and 'READ-BACK RED' in out and needle in out, f'rc {rc} · {out.strip().splitlines()[-1][:110]}')
    for label, spec, exp, df in (('the Main delta (no setting)', M, SM, DM),
                                 ("an unapproved setting value ('all')", O, SO, dfile(dict(appr_o, settings={KEY: 'all'}))),
                                 ('an extra setting key', O, SO, dfile(dict(appr_o, settings={KEY: 'none', 'availableInMCP': True})))):
        x = os.path.splitext(os.path.basename(spec))[0]
        committed, fake, oid, cid = world(x)
        run(fake, ['put', spec, cid, exp, '--delta-file', DM if x == 'main' else DO])
        n0 = fake.puts()
        rc, out = run(fake, ['settings', spec, cid, exp, '--delta-file', df])
        case(f'settings refused, 0 PUT: {label}', rc == 1 and fake.puts() == n0, f'rc {rc} · {out.strip().splitlines()[-1][:100]}')
    committed, fake, oid, cid = world('owner-actions', copy_active=True)
    rc, out = run(fake, ['settings', O, cid, SO, '--delta-file', DO])
    case('settings on an ACTIVE copy → refused, 0 PUT', rc == 1 and fake.puts() == 0 and 'not INACTIVE' in out, f'rc {rc}')
    committed, fake, oid, cid = world('owner-actions')
    rc, out = run(fake, ['settings', O, cid, SO, '--allow', 'Respond Owner OK'])
    case('settings without a delta file → usage', rc == 2 and not fake.calls, f'rc {rc}')

    # 17. scratch: create → edit → rollback on the scratch; never activated; ROLES ids refused as scratch
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['scratch-create', M, cid])
    sid = next((k for k in fake.wfs if k.startswith('SCR')), None)
    case('scratch-create: an INACTIVE "SCRATCH — " copy of the live draft, its id printed MASKED', rc == 0 and sid and fake.wfs[sid]['active'] is False
         and fake.wfs[sid]['name'].startswith('SCRATCH — ') and W.mask_id(sid) in out and sid not in out, f'rc {rc} · {out.strip().splitlines()[-1][:160]}')
    SS = snap_path()
    rc, out = call(fake, W.put, M, sid, SM, allow_m, appr_m, SS, scratch=True)
    case('put on the scratch: green, the production copy untouched', rc == 0 and fake.puts() == 1
         and not any(p == f'/workflows/{cid}' for m, p in fake.calls if m == 'PUT'), f'rc {rc} · {out.strip().splitlines()[-1][:180]}')
    rc, out = call(fake, W.rollback, M, sid, SS, scratch=True)
    case('rollback on the scratch: green', rc == 0, f'rc {rc}')
    for argv, label in ((['activate', M, sid], 'activate a scratch'), (['probe', M, sid], 'probe a scratch')):
        w0 = fake.writes()
        rc, out = run(fake, argv)
        case(f'refused: {label}', rc == 1 and fake.writes() == w0, f'rc {rc}')
    w0 = fake.writes()
    rc, out = call(fake, W.put, M, cid, SM, allow_m, appr_m, snap_path(), scratch=True)
    case('refused: a ROLES copy used as a scratch', rc == 1 and fake.writes() == w0, f'rc {rc}')
    w0 = fake.writes()
    rc, out = run(fake, ['activate', M, sid])
    case('activate reads the live name back: a "SCRATCH — " workflow is refused AS A SCRATCH', rc == 1 and fake.writes() == w0
         and 'is a SCRATCH' in out, out.strip().splitlines()[-1][:120])
    fake.wfs[sid]['active'] = True
    rc, out = call(fake, W.put, M, sid, SM, allow_m, appr_m, snap_path(), scratch=True)
    case('put on an ACTIVE scratch is refused', rc == 1, f'rc {rc}')
    w0 = fake.writes()
    rc, out = run(fake, ['scratch-delete', M, sid])
    case('scratch-delete of an ACTIVE scratch is refused (a scratch is never activated)', rc == 1 and fake.writes() == w0, f'rc {rc}')
    fake.wfs[sid]['active'] = False
    nm = fake.wfs[cid]['name']
    fake.wfs[cid]['name'] = 'SCRATCH — ' + nm          # a production copy wearing the scratch name
    w0 = fake.writes()
    rc, out = run(fake, ['scratch-delete', M, cid])
    case('a ROLES copy named like a scratch is still refused as a scratch', rc == 1 and fake.writes() == w0 and 'ROLES' in out, f'rc {rc}')
    w0 = fake.writes()
    rc, out = run(fake, ['activate', M, cid])
    case('activate: a ROLES copy whose live name starts with "SCRATCH — " is refused as a scratch', rc == 1 and fake.writes() == w0
         and 'is a SCRATCH' in out, out.strip().splitlines()[-1][:120])
    fake.wfs[cid]['name'] = nm
    for mode in ('keep', 500, 403, 0):
        fake.delete_mode, fake.broken = mode, {}
        rc, out = run(fake, ['scratch-delete', M, sid])
        case(f'scratch-delete: a follow-up GET of {mode if mode != "keep" else "200 (still there)"} is NOT deletion → exit 3, '
             'masked id, "may still exist"', rc == 3 and 'MAY STILL EXIST' in out and W.mask_id(sid) in out and sid not in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:110]}')
    fake.delete_mode, fake.broken = 'gone', {}
    rc, out = run(fake, ['scratch-delete', M, sid])
    case('scratch-delete: DELETE, read back exactly 404', rc == 0 and sid not in fake.wfs, f'rc {rc}')

    # 18. rehearse-rollback, end to end: scratch from the live copy → put (S0) → settings (Owner Actions only) → rollback to
    #     S0, proven equal → scratch deleted in `finally` (404) and the snapshots removed
    def scratches(fake):
        return [k for k in fake.wfs if k.startswith('SCR')]
    real_mkdtemp, made = tempfile.mkdtemp, []

    def mk(*a, **k):
        d = real_mkdtemp(*a, **k)
        made.append(d)
        return d
    tempfile.mkdtemp = mk
    try:
        for spec, exp, df, want_puts, steps in ((M, SM, DM, 2, ('step 1', 'step 3')), (O, SO, DO, 3, ('step 1', 'step 2', 'step 3'))):
            x = os.path.splitext(os.path.basename(spec))[0]
            committed, fake, oid, cid = world(x)
            graveyard = {}
            real_fapi = fake.api

            def api(method, path, body=None, fake=fake, real_fapi=real_fapi, graveyard=graveyard):   # the scratch as it was at its DELETE
                m_ = re.fullmatch(r'/workflows/(SCR\w+)', path)
                if method == 'DELETE' and m_ and m_.group(1) in fake.wfs:
                    graveyard[m_.group(1)] = copy.deepcopy(fake.wfs[m_.group(1)])
                return real_fapi(method, path, body)
            fake.api = api
            live_before = copy.deepcopy(H._draft(fake.wfs[cid]))
            rc, out = run(fake, ['rehearse-rollback', spec, cid, exp, '--delta-file', df])
            sids = sorted(fake.deleted)
            gone = next(iter(graveyard.values()), {})
            case(f'rehearse-rollback {x}: create → edit{" → settings" if want_puts == 3 else ""} → rollback (== S0) → delete (404); '
                 'never activated, production untouched, snapshots removed',
                 rc == 0 and fake.puts() == want_puts and len(sids) == 1 and not scratches(fake) and all(st in out for st in steps)
                 and not any(m == 'POST' and p.endswith('/activate') for m, p in fake.calls)
                 and not any(p == f'/workflows/{cid}' for m, p in fake.calls if m == 'PUT') and sids[0] not in out
                 and H._draft(fake.wfs[cid]) == live_before and made and not os.path.exists(made[-1]),
                 f'rc {rc} · PUTs {fake.puts()} · {out.strip().splitlines()[-1][:120]}')
            case(f'rehearse-rollback {x}: the scratch ended EXACTLY as built from the live copy (settings included)',
                 gone and dict(H._draft(gone), name=live_before['name']) == live_before, f"{(gone.get('settings') or {})}")
    finally:
        tempfile.mkdtemp = real_mkdtemp
    for label, kw, want_puts in (('the edit PUT answers 500', {'put_status': 500}, 1),
                                 ('the scratch reads back wrong after its POST', {'create_mangle': lambda w: w.__setitem__('nodes', w['nodes'][1:])}, 0)):
        committed, fake, oid, cid = world('main', **kw)
        rc, out = run(fake, ['rehearse-rollback', M, cid, SM, '--delta-file', DM])
        case(f'rehearse-rollback: {label} → exit 1 and the scratch is STILL deleted (404)', rc == 1 and fake.puts() == want_puts
             and len(fake.deleted) == 1 and not scratches(fake), f'rc {rc} · deleted {len(fake.deleted)} · {out.strip().splitlines()[-1][:100]}')
    committed, fake, oid, cid = world('main')
    fake_put = fake.api

    def keep_after_edit(method, path, body=None):   # the rollback PUT is not kept: n8n answers 200 and holds the edit
        if method == 'PUT' and sum(1 for m, _ in fake.calls if m == 'PUT') >= 1:
            fake.calls.append((method, path))
            return 200, {}
        return fake_put(method, path, body)
    fake.api = keep_after_edit
    rc, out = run(fake, ['rehearse-rollback', M, cid, SM, '--delta-file', DM])
    case('rehearse-rollback: a rollback n8n does not keep → RED (GET != snapshot), scratch still deleted',
         rc == 1 and 'ROLLBACK READ-BACK RED' in out and len(fake.deleted) == 1, f'rc {rc} · {out.strip().splitlines()[-2][:120] if out.strip() else ""}')
    committed, fake, oid, cid = world('main')
    real_rb = W.rollback

    def rollback_crash(*a, **k):
        raise RuntimeError('a bug in the middle of the rehearsal')
    W.rollback = rollback_crash
    try:
        rc, out = run(fake, ['rehearse-rollback', M, cid, SM, '--delta-file', DM])
    finally:
        W.rollback = real_rb
    case('rehearse-rollback: an unexpected exception mid-way still deletes the scratch (finally)',
         str(rc).startswith('escaped') and len(fake.deleted) == 1 and not scratches(fake), f'rc {rc} · deleted {len(fake.deleted)}')
    committed, fake, oid, cid = world('main', delete_mode=500)
    rc, out = run(fake, ['rehearse-rollback', M, cid, SM, '--delta-file', DM])
    left = scratches(fake)
    case('rehearse-rollback: a delete that does not read back 404 → DISTINCT exit 3, masked id printed, never the full id',
         rc == 3 and len(left) == 1 and W.mask_id(left[0]) in out and left[0] not in out and 'MAY STILL EXIST' in out,
         f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['rehearse-rollback', M, cid, SM, '--delta-file', DM, '--snapshot', snap_path()])
    case('rehearse-rollback --snapshot → usage (its snapshots are its own), no call', rc == 2 and not fake.calls, f'rc {rc}')

    # 19. GATE (R1c ruling), defence in depth: the G1 scenarios A–D and the Owner Actions signature node — A/B/OA through
    #     --allow; C/D and a non-ruled edge from Verify Turnstile through a delta file: refused as NOT APPROVED, and, with
    #     the delta made "approved" and the diff blind, refused by the GATE — all 0 PUT
    def g1(fn):
        return repo_file(main_export(fn))

    def g1_a(e):
        next(n for n in e['nodes'] if n['name'] == 'Turnstile Gate')['parameters']['conditions']['conditions'][0]['leftValue'] = '={{ false }}'

    def g1_b(e):
        next(n for n in e['nodes'] if n['name'] == 'Normalize Inbound')['parameters']['jsCode'] += '\n// admit everything'

    def g1_c(e):
        e['connections']['Turnstile Valid?']['main'][1] = [{'node': 'Validate Payload', 'type': 'main', 'index': 0}]

    def g1_d(e):
        e['connections']['Normalized OK?']['main'][0] = [{'node': 'Validate Payload', 'type': 'main', 'index': 0}]

    def g1_rb(e):
        e['connections']['Reject Bot Request'] = {'main': [[{'node': 'Check Processed', 'type': 'main', 'index': 0}]]}
    oa_sig = json.load(open(os.path.join(ROOT, BASELINE['n8n/workflow.owner-actions.copy.sanitized.json']), encoding='utf-8'))
    next(n for n in oa_sig['nodes'] if n['name'] == 'Verify Owner Signature')['parameters']['jsCode'] = 'return [{json: {valid: true}}];'
    nr = main_export(lambda e: None)
    nr['nodes'].append({'name': 'Tag Test', 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': [2464, 4256],
                        'parameters': {'jsCode': 'return [];'}})
    nr['connections']['Verify Turnstile']['main'][1].append({'node': 'Tag Test', 'type': 'main', 'index': 0})
    for label, spec, exp, allow in (('G1-A: Turnstile Gate in --allow, constant-false condition', M, g1(g1_a), ['Build Owner Alert', 'Turnstile Gate']),
                                    ('G1-B: Normalize Inbound in --allow, rewritten', M, g1(g1_b), ['Build Owner Alert', 'Normalize Inbound']),
                                    ('OA: Verify Owner Signature in --allow, made always-valid', O, repo_file(oa_sig), ['Verify Owner Signature'])):
        for mode, ctx in (('diff in place', contextlib.nullcontext), ('diff blind', blind)):
            committed, fake, oid, cid = world(os.path.splitext(os.path.basename(spec))[0])
            with ctx():
                rc, out = run(fake, ['put', spec, cid, exp, '--allow', *allow])
            case(f'GATE {label} → refused, 0 PUT ({mode})', rc == 1 and fake.puts() == 0 and 'GATE' in out,
                 f'rc {rc} · PUTs {fake.puts()} · {out.strip().splitlines()[-1][:110]}')
    for label, exp, d in (("G1-C: declared edge 'Turnstile Valid?|1|Validate Payload|0'", g1(g1_c),
                           {'add_edges': {'Turnstile Valid?|1|Validate Payload|0'}, 'remove_edges': {'Turnstile Valid?|1|Reject Bot Request|0'}}),
                          ('G1-D: declared re-wire around Turnstile Gate', g1(g1_d),
                           {'add_edges': {'Normalized OK?|0|Validate Payload|0'}, 'remove_edges': {'Normalized OK?|0|Turnstile Gate|0'}}),
                          ('a declared edge from Verify Turnstile that is NOT a ruled edge', repo_file(nr),
                           {'add_nodes': {'Tag Test'}, 'add_edges': {'Verify Turnstile|1|Tag Test|0'}}),
                          ("a declared edge 'Reject Bot Request|0|Check Processed|0' (onward after the reject reply)", g1(g1_rb),
                           {'add_edges': {'Reject Bot Request|0|Check Processed|0'}})):
        DF_ = dfile(d)
        committed, fake, oid, cid = world('main')
        rc, out = run(fake, ['put', M, cid, exp, '--delta-file', DF_])
        case(f'{label} → refused: NOT an approved delta, 0 PUT', rc == 1 and fake.puts() == 0 and 'not an approved delta' in out,
             f'rc {rc} · {out.strip().splitlines()[-1][:110]}')
        for mode, ctx in (('diff in place', contextlib.nullcontext), ('diff blind', blind)):
            committed, fake, oid, cid = world('main')
            with ctx(), approved_as('main', d):
                rc, out = run(fake, ['put', M, cid, exp, '--delta-file', DF_])
            case(f'GATE {label}, as if APPROVED → refused, 0 PUT ({mode})', rc == 1 and fake.puts() == 0 and 'GATE' in out,
                 f'rc {rc} · PUTs {fake.puts()} · {out.strip().splitlines()[-1][:110]}')
    ug = main_export(lambda e: e['connections']['Turnstile Gate']['main'].reverse())
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, repo_file(ug), '--allow', 'Build Owner Alert'])
    case("GATE: an UNDECLARED change of a gate node's connections (Turnstile Gate's outputs swapped) → refused, 0 PUT",
         rc == 1 and fake.puts() == 0 and 'Turnstile Gate' in out, f'rc {rc} · {out.strip().splitlines()[-1][:110]}')

    # 20. M-c, the position lock: the staged Main export moves nothing; a move is refused (no delta declares one)
    cm = H.committed_export('n8n/workflow.main.copy.sanitized.json')
    errs = H.DIFF.compare(cm, em, set(json.load(open(os.path.join(ROOT, DM)))['allow']), phase='edit', delta=appr_m)
    case('M-c: the staged Main export + its approved delta pass, nothing moved', not errs, f'{errs[:2]}')
    mv = copy.deepcopy(em)
    next(n for n in mv['nodes'] if n['name'] == 'Reject Bot Request')['position'] = [2464, 4400]
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, repo_file(mv), '--delta-file', DM])
    case('M-c put: Reject Bot Request moved below the tag → refused, 0 PUT', rc == 1 and fake.puts() == 0 and 'node moved' in out, f'rc {rc}')
    ty = copy.deepcopy(em)   # Codex R2 deploy MEDIUM, its exact case: the approved delta unchanged, one edge's type changed
    ty['connections']['Turnstile Valid?']['main'][0][0]['type'] = 'ai_tool'
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['put', M, cid, repo_file(ty), '--delta-file', DM])
    case("R2b put: 'Turnstile Valid?' output 0 changed main → ai_tool with the approved delta → refused, 0 PUT",
         rc == 1 and fake.puts() == 0 and 'type=ai_tool' in out, f'rc {rc} · {out.strip().splitlines()[-1][:130]}')
    for spec_, exp_, df_, src_ in ((M, em, DM, 'Turnstile Valid?'), (O, eo, DO, 'Write Verified?')):   # Codex R2b: both its cases
        nt = copy.deepcopy(exp_)
        del nt['connections'][src_]['main'][0][0]['type']
        committed, fake, oid, cid = world(os.path.splitext(os.path.basename(spec_))[0])
        rc, out = run(fake, ['put', spec_, cid, repo_file(nt), '--delta-file', df_])
        case(f"R3 TYPE put: '{src_}' output 0 with its type key DELETED, approved delta → refused, 0 PUT",
             rc == 1 and fake.puts() == 0 and 'type=missing' in out, f'rc {rc} · {out.strip().splitlines()[-1][:130]}')

    # 21. M-b: a POST that returns no usable id (none · malformed · curl's 0) is exit 3 with the find-by-name instruction,
    #     no DELETE, and never "deleted"; a rehearsal refused before the POST says no scratch was created.
    for label, answer in (('no id', (200, {})), ('a malformed id', (200, {'id': '../evil?x=1'})), ('curl status 0', (0, None))):
        for cmd in ('scratch-create', 'rehearse-rollback'):
            committed, fake, oid, cid = world('main', create_answer=answer)
            argv = ['scratch-create', M, cid] if cmd == 'scratch-create' else ['rehearse-rollback', M, cid, SM, '--delta-file', DM]
            rc, out = run(fake, argv)
            case(f'M-b {cmd}: POST answered {label} → exit 3, find by name, no DELETE, never "deleted"',
                 rc == 3 and 'MAY EXIST' in out and 'SCRATCH — ' in out and 'deleted' not in out.replace('NOT PROVEN DELETED', '')
                 and not any(m == 'DELETE' for m, _ in fake.calls) and '../evil' not in out,
                 f'rc {rc} · {out.strip().splitlines()[-1][:120]}')
    committed, fake, oid, cid = world('main', orig_active=True)
    rc, out = run(fake, ['rehearse-rollback', M, cid, SM, '--delta-file', DM])
    case('M-b rehearse-rollback refused before the POST → exit 1, "no scratch was created", never "deleted"',
         rc == 1 and 'no scratch was created' in out and 'was deleted' not in out and not fake.writes(), f'rc {rc} · {out.strip().splitlines()[-1][:120]}')

    # 22. REV (T MED-3): REV:PATH takes HEAD or a commit SHA only
    head_sha = __import__('subprocess').run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    tree_sha = __import__('subprocess').run(['git', '-C', ROOT, 'rev-parse', 'HEAD^{tree}'], capture_output=True, text=True).stdout.strip()
    for rev, want in (('HEAD', 0), (head_sha, 0), (head_sha[:12], 0), ('main', 1), ('origin/main', 1), ('FETCH_HEAD', 1),
                      ('stash@{0}', 1), ('HEAD~0', 1), (tree_sha, 1), ('0' * 40, 1)):
        committed, fake, oid, cid = world()
        rc, out = run(fake, ['put', P, cid, f'{rev}:n8n/workflow.purge.copy.sanitized.json', '--allow', *E1])
        case(f'REV {rev[:14]!r}: {"accepted" if want == 0 else "refused, 0 PUT"}', rc == want and fake.puts() == (1 if want == 0 else 0),
             f'rc {rc} · {out.strip().splitlines()[-1][:100]}')

    # 23. M-a: content comes from git HEAD with literal pathspecs — proven in a throwaway git repo (W.ROOT pointed at it,
    #     the real tracked_clean/head_blob, not the TEST_FILES seam).
    import shutil
    import subprocess as sp
    grepo = tempfile.mkdtemp(prefix='wstest-git-')
    g = lambda *a: sp.run(['git', '-C', grepo, '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', '-c',
                           'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', *a], capture_output=True, check=True)

    def wr(rel, obj):
        os.makedirs(os.path.dirname(os.path.join(grepo, rel)) or grepo, exist_ok=True)
        with open(os.path.join(grepo, rel), 'w', encoding='utf-8') as f:
            json.dump(obj, f)
    g('init', '-q')
    for rel, obj in (('n8n/staged/delta1.json', {'allow': ['TRACKED']}), ('lit/delta[1].json', {'allow': ['LIT']}),
                     ('lit/delta1.json', {'allow': ['OTHER']}), ('au.json', {'allow': ['HEAD']}),
                     ('ex.json', {'v': 'head'}), ('mod.json', {'allow': ['HEAD']})):
        wr(rel, obj)
    g('add', '-A')
    g('commit', '-q', '-m', 'fixture')
    for rel in ('n8n/staged/delta[1].json', 'n8n/staged/delta?.json', 'n8n/staged/d*1.json'):
        wr(rel, {'allow': ['UNTRACKED']})
    wr('lit/delta1.json', {'allow': ['MODIFIED']})                  # the glob twin of lit/delta[1].json, locally modified
    wr('mod.json', {'allow': ['WORKTREE']})
    g('update-index', '--assume-unchanged', 'au.json', 'ex.json')   # an edit `git diff` cannot see
    wr('au.json', {'allow': ['WORKTREE']})
    wr('ex.json', {'v': 'worktree'})
    saved_root, saved = W.ROOT, (W.tracked_clean, W.head_blob)
    W.ROOT, W.tracked_clean, W.head_blob = os.path.realpath(grepo), real_tc, real_hb

    def ld(rel):
        try:
            return W.load_delta_file(rel)[0]
        except W.Refused as e:
            return f'refused: {e}'
    try:
        for rel in ('n8n/staged/delta[1].json', 'n8n/staged/delta?.json', 'n8n/staged/d*1.json'):
            r = ld(rel)
            case(f'M-a: an UNTRACKED glob-named delta file {rel.split("/")[-1]!r} (a tracked delta1.json beside it) → refused',
                 isinstance(r, str) and r.startswith('refused'), str(r)[:90])
        r = ld('lit/delta[1].json')
        case('M-a: a TRACKED, clean "delta[1].json" whose glob twin delta1.json is modified → accepted (literal pathspec)',
             r == ['LIT'], str(r)[:90])
        r = ld('mod.json')
        case('M-a: a tracked file modified in the working tree → refused', isinstance(r, str) and 'differs from HEAD' in r, str(r)[:90])
        r = ld('au.json')
        case('M-a: an edit git cannot see (assume-unchanged): the HEAD content is what is used, not the working tree',
             r == ['HEAD'], str(r)[:90])
        try:
            v = W.load_export('ex.json', M).get('v')
        except W.Refused as e:
            v = f'refused: {e}'
        case('M-a: load_export reads the export from HEAD, not the working tree', v == 'head', str(v)[:90])
    finally:
        W.ROOT, (W.tracked_clean, W.head_blob) = saved_root, saved
        shutil.rmtree(grepo, ignore_errors=True)

    # 10. usage → exit 2, no call
    committed, fake, oid, cid = world()
    for argv in (['put', P, cid, SP], ['put', P, cid, SP, '--allow'], ['activate', P], ['put', P, cid, SP, '--force', 'x'], ['nuke', P, cid],
                 ['rollback', P, cid], ['rollback', P, cid, 'x', 'y'], ['rollback', P, cid, '--snapshot']):
        rc, _ = run(fake, argv)
        case(f"usage {' '.join(argv[:1] + [a for a in argv[3:] if a.startswith('-') or len(argv) != 4])} → exit 2", rc == 2 and not fake.calls, f'rc {rc}')
    for argv in (['put', P, cid, SP, '--allow', *E1], ['settings', P, cid, SP, '--delta-file', 'x']):
        rc, _ = run(fake, argv, snap=False)
        case(f'usage: {argv[0]} WITHOUT --snapshot → exit 2', rc == 2 and not fake.calls, f'rc {rc}')
finally:
    H.api, H.ROLES_FILE, W.tracked_clean, W.head_blob = real_api, real_roles, real_tc, real_hb
    __import__('shutil').rmtree(SNAPDIR, ignore_errors=True)
    for p in tmp:
        with contextlib.suppress(OSError):
            os.rmdir(p) if os.path.isdir(p) else os.unlink(p)

print(f"workflow-step: {'OK' if ok else 'FAILED'}")
sys.exit(0 if ok else 1)
