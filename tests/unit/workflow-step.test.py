#!/usr/bin/env python3
"""Offline test for scripts/workflow-step.py (7-F1 Round B, final shape): a fake n8n behind the deploy helper's `api`
(an UNEXPECTED call raises, so a case cannot pass on a 404 it did not ask for), fake ids in a fixture ROLES file, and
live copies simulated from the committed exports.

What it proves: put refuses an ACTIVE copy, an edit outside its allowlist (a node not named, an edge, a flag, a
setting, an older revision that brings the temporary trigger back), an export that is not sanitised, a copy ROLES does
not declare live, an original that is not parked, a copy of another spec, a spec outside db/copies, an export outside
the repo or not this copy's own REV:PATH, and Main (outside the tool's scope) — each before any PUT; a PUT whose
read-back differs from the export, whose settings or active flag come back changed, or that answers non-200 is RED;
the staged E1 and E2 edits read back == staged; the restore (the committed export put over an edited copy) reads back
== committed; deactivate and activate are RED when their read-back disagrees, activate also when published != draft.
What it does NOT prove: n8n's real behaviour on PUT (the live read-back proves that, every run).
Run: python3 tests/unit/workflow-step.test.py [path/to/workflow-step.py]
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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'scripts', 'workflow-step.py')
_spec = importlib.util.spec_from_file_location('workflow_step', SRC)
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)
H = W.H

E1 = ['Aggregate Leads Total', 'Build Owner Alert (Purge)', 'Count Leads After', 'Count Leads Total', 'Find Old Leads',
      'Leads Purge Sane?', 'Verify Leads Purge']
E2 = ['Build Owner Alert (Reminders)']
IDS = {'purge': ('OP', 'CP'), 'reminders': ('OR', 'CR'), 'main': ('OM', 'CM')}


class FakeN8n:
    def __init__(self, wfs, mangle=None, flip_ok=True, stale_published=False, put_status=200):
        self.wfs, self.mangle, self.calls = wfs, mangle, []
        self.flip_ok, self.stale_published, self.put_status = flip_ok, stale_published, put_status

    def api(self, method, path, body=None):
        self.calls.append((method, path))
        m = re.fullmatch(r'/workflows/(\w+)(?:/(activate|deactivate))?', path)
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


def world(spec='purge', copy_active=False, orig_active=False, **fake_kw):
    committed, live = H._simulated_live_copy(f'db/copies/{spec}.json')
    oid, cid = IDS[spec]
    orig = dict(copy.deepcopy(live), name='original', active=orig_active)
    cp = dict(copy.deepcopy(live), active=copy_active)
    return committed, FakeN8n({oid: orig, cid: cp}, **fake_kw), oid, cid


def run(fake, argv):
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


def drift(fake, cid, ref):
    d = H._draft(fake.wfs[cid])
    return H.content_drift(d, ref, H._ccp().placeholder_smap(d, ref))


ok = True
real_api, real_roles, real_tc = H.api, H.ROLES_FILE, W.tracked_clean
TEST_FILES = set()   # the gitignored .wstest exports this test writes: treated as committed, ONLY for the cases that need it
W.tracked_clean = lambda rel: rel in TEST_FILES or real_tc(rel)


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

    # 5. restore: the copy holds the edit; put the COMMITTED export (REV:PATH) → read back == committed
    committed, fake, oid, cid = world()
    run(fake, ['put', P, cid, SP, '--allow', *E1])
    rc, out = run(fake, ['put', P, cid, 'HEAD:n8n/workflow.purge.copy.sanitized.json', '--allow', *E1])
    dr = drift(fake, cid, committed)
    case('restore from the committed export reads back == committed', rc == 0 and fake.puts() == 2 and not dr, f'rc {rc} · drift {dr[:1]}')

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
    committed, fake, oid, cid = world('main')
    rc, out = run(fake, ['deactivate', 'db/copies/main.json', cid])
    case('Main is outside the scope (no write)', rc == 1 and not fake.writes() and 'scope' in out, f'rc {rc}')
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

    # 10. usage → exit 2, no call
    committed, fake, oid, cid = world()
    for argv in (['put', P, cid, SP], ['put', P, cid, SP, '--allow'], ['activate', P], ['put', P, cid, SP, '--force', 'x'], ['nuke', P, cid]):
        rc, _ = run(fake, argv)
        case(f"usage {' '.join(a for a in argv if a.startswith('-') or a in ('put', 'activate', 'nuke'))} → exit 2", rc == 2 and not fake.calls, f'rc {rc}')
finally:
    H.api, H.ROLES_FILE, W.tracked_clean = real_api, real_roles, real_tc
    for p in tmp:
        with contextlib.suppress(OSError):
            os.rmdir(p) if os.path.isdir(p) else os.unlink(p)

print(f"workflow-step: {'OK' if ok else 'FAILED'}")
sys.exit(0 if ok else 1)
