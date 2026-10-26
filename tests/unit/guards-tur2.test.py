#!/usr/bin/env python3
"""Repository-guard tests for 7-2 Tur 2 R1, lane G — every case is built from a scenario in docs/codex/7-2/4.md.

Each test reproduces what Codex measured against the guards at f1a47eb (a value that passed, a push that was not
scanned) and asserts the guard now refuses it, plus the controls that must stay green (code text, expressions,
placeholders, the committed exports). Offline: synthetic values only, built at RUN time so this file itself carries no
value any guard matches; throwaway git repos under $TMPDIR with the global and system git config switched off; no
hook is installed anywhere a real push from THIS repo would use it: installer cases run a COPY of the installer placed
inside a temp repo (install_into(), which refuses a path under this repo), so it can only write that temp repo's own
.git/hooks. (R1c: the old case passed PRE_PUSH_TARGET, which the confined installer ignores by design; run against the
canonical path it installed into this repo's .git/hooks once, was moved out, and the case was rewritten.)
R1d: the installer and the drift check work from HEAD, so every installer and drift case first COMMITS the gate scripts
inside its own throwaway repo (stage_scripts(), with the same refusal of any path under this repo) and runs the copy
there; the t_r1d_* cases cover M-A, M-B, --diff-merges, the hooks-path redirect and LOW-2/3/4.

R2b (Codex 7-2 R2, target 4): a key CONTAINING a run of x (AWS- and OpenAI-shaped, built at run time) is blocked on
a real push with the installed hook, and whole placeholder tokens still pass; the second-remote case (g5) sets a nested
remote name through config, so it runs on a newer git (which refuses `git remote add origin/side`) as on an older one.

GUARDS_ROOT (default: this repo) points every script path at another tree, so the same cases can be run against the
pre-fix scripts (red) and against a mutant of a fix (red) as well as the fixed tree (green).

Run: python3 tests/unit/guards-tur2.test.py [-k SUBSTRING ...] [-v]
"""
import copy
import contextlib
import glob
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GROOT = os.path.abspath(os.environ.get('GUARDS_ROOT', REPO))
SCAN = os.path.join(GROOT, 'scripts', 'secret-scan.sh')
PREPUSH = os.path.join(GROOT, 'scripts', 'pre-push.sh')
INSTALL = os.path.join(GROOT, 'scripts', 'install-pre-push.sh')
HOSTLEAK = os.path.join(GROOT, 'scripts', 'check-no-host-leak.sh')
DRIFT = os.path.join(GROOT, 'scripts', 'check-hook-drift.sh')
CCP_PATH = os.path.join(GROOT, 'scripts', 'check-content-parity.py')
STAGED_TEST = os.path.join(GROOT, 'tests', 'unit', 'staged-sanitised.test.py')
MAIN_EXPORT = os.path.join(REPO, 'n8n', 'workflow.sanitized.json')
STAGED_EXPORT = os.path.join(REPO, 'n8n', 'staged', 'workflow.main.copy.sanitized.json')
HOOK_PAYLOAD = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'git push'}})
ZERO = '0' * 40


# ---- synthetic values (assembled here so no source line matches a rule) -------------------------------------
def syn_sender():
    return 'widget:w-' + 'synthetic' + '-'.join(['0a1b2c3d', '4e5f', '6a7b', '8c9d', '0e1f2a3b4c5d'])


def syn_event():
    return (syn_sender() + '|2026-01-01|10:00|cut').encode().hex()


def syn_anthropic():
    return 'sk-' + 'ant-' + 'api03-' + 'Q1w2E3r4T5y6' * 4


def syn_openai_proj():
    return 'sk-' + 'proj-' + 'Zx9_Cv8-Bn7' * 6


def syn_aws_xrun():   # R2b XRUN: Codex's AWS-shaped case — a run of X INSIDE a valid-length key
    return 'AK' + 'IA' + 'ABCD' + 'XX' + 'XX' + 'EFGH1234'


def syn_openai_xrun():   # and its OpenAI-shaped case: 33 key characters, four of them a run of x — the old strip left
    return 'sk' + '-' + 'Ab1Cd2Ef3Gh4' + 'xx' + 'xx' + 'Ij5Kl6Mn7Op8Qr9St'   # 29, below the rule's 32 (review R2b L2)


def syn_placeholders():   # documentation placeholders: every one is a WHOLE placeholder token, and must pass
    return ['AK' + 'IA' + 'X' * 16, 'sk-' + 'ant-' + 'x' * 24, 'sk-' + 'proj-' + 'x' * 24, 'gh' + 'p_' + 'x' * 36,
            'app' + 'X' * 14]


def syn_hex(n):
    return ('0123456789abcdef' * 8)[:n]


def syn_host():
    return 'synthetic-host' + '.invalid'


# ---- helpers ---------------------------------------------------------------------------------------------------
def git_env():
    env = dict(os.environ, GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0',
               GIT_AUTHOR_NAME='guards', GIT_AUTHOR_EMAIL='guards@t.invalid',
               GIT_COMMITTER_NAME='guards', GIT_COMMITTER_EMAIL='guards@t.invalid')
    for k in ('N8N_HOST', 'SECRET_SCAN_INSTALLED', 'PRE_PUSH_INSTALLED', 'PRE_PUSH_TARGET', 'GIT_DIR', 'GIT_WORK_TREE'):
        env.pop(k, None)
    return env


def run(cmd, cwd, stdin='', env=None, timeout=120):
    p = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, env=env or git_env(),
                       timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def git(cwd, *args):
    rc, out = run(['git', *args], cwd)
    if rc != 0:
        raise RuntimeError('git %s failed: %s' % (' '.join(args), out[-300:]))
    return out.strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def commit(work, rel, text, msg):
    write(os.path.join(work, rel), text)
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-m', msg)
    return git(work, 'rev-parse', 'HEAD')


def mkrepo(tmp, scanner=True):
    """A bare remote plus a clone with one pushed commit and an upstream; the scanner copied in UNTRACKED."""
    remote, work = os.path.join(tmp, 'remote.git'), os.path.join(tmp, 'work')
    git(tmp, 'init', '-q', '--bare', '-b', 'main', remote)
    git(tmp, 'init', '-q', '-b', 'main', work)
    write(os.path.join(work, '.gitignore'), 'scripts/\n')
    commit(work, 'README.md', 'base\n', 'base')
    git(work, 'remote', 'add', 'origin', remote)
    git(work, 'push', '-q', '-u', 'origin', 'main')
    if scanner and os.path.exists(SCAN):
        os.makedirs(os.path.join(work, 'scripts'), exist_ok=True)
        shutil.copy(SCAN, os.path.join(work, 'scripts', 'secret-scan.sh'))
    return remote, work


def hook_scan(work):
    """secret-scan.sh in its Claude Code hook mode, exactly as the PreToolUse payload reaches it."""
    return run(['bash', SCAN], work, stdin=HOOK_PAYLOAD)


def prepush(work, lines, remote='origin', url='synthetic-url', hook=None):
    hook = hook or PREPUSH
    if not os.path.exists(hook):
        return 127, '%s does not exist' % hook
    return run(['bash', hook, remote, url], work, stdin=''.join(l + '\n' for l in lines))


def revs_scan(work, *revs, env=None):
    return run(['bash', SCAN, '--revs', *revs], work, env=env)


def manual_scan(work):
    """Manual mode: no hook payload on stdin (an empty pipe, as `</dev/null` gives it)."""
    return run(['bash', SCAN], work, stdin='')


GATE_FILES = ('pre-push.sh', 'secret-scan.sh', 'secret-scan-ignore', 'install-pre-push.sh', 'check-hook-drift.sh')


def outside_this_repo(work):
    real_work = os.path.realpath(work)
    if real_work == os.path.realpath(REPO) or real_work.startswith(os.path.realpath(REPO) + os.sep):
        raise RuntimeError('refusing a path inside this repository: %s' % work)


def stage_scripts(work, commit=True, push=True):
    """Copy the gate scripts into <work>/scripts (gitignored by mkrepo) and, by default, COMMIT them there (force-added
    in THAT throwaway repo) and push that commit with --no-verify as setup: since R1d the installer and the drift check
    take every canonical file from HEAD. Never this repository: see the module docstring."""
    outside_this_repo(work)
    sd = os.path.join(work, 'scripts')
    os.makedirs(sd, exist_ok=True)
    rels = []
    for n in GATE_FILES:
        if os.path.exists(os.path.join(GROOT, 'scripts', n)):
            shutil.copy(os.path.join(GROOT, 'scripts', n), os.path.join(sd, n))
            rels.append('scripts/' + n)
    if commit:
        git(work, 'add', '-f', '--', *rels)
        if git(work, 'status', '--porcelain', '--', 'scripts'):
            git(work, 'commit', '-q', '-m', 'gate scripts')
        if push and 'origin' in git(work, 'remote').split():
            git(work, 'push', '-q', '--no-verify', 'origin', 'HEAD')
    return sd


def install_into(work, *args, env=None, commit=True):
    """Stage (and commit) the gate scripts in <work> and run THAT installer, so the only hooks directory it can reach is
    <work>/.git/hooks. Never the canonical path: see the module docstring."""
    sd = stage_scripts(work, commit=commit)
    return run(['bash', os.path.join(sd, 'install-pre-push.sh'), *args], work, env=env)


def hooks_of(work):
    return os.path.join(work, '.git', 'hooks')


def key_file(work, rel, extra=''):
    """A file whose LAST line carries a synthetic key (never passed on a command line)."""
    write(os.path.join(work, rel), extra + 'k=%s\n' % syn_anthropic())


def msg_file(tmp, text):
    p = os.path.join(tmp, 'msg-%d.txt' % len(os.listdir(tmp)))
    write(p, text)
    return p


def ccp():
    spec = importlib.util.spec_from_file_location('ccp_g', CCP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sanitised(wf):
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            ccp().check_sanitised(wf)
        return True, ''
    except SystemExit as e:
        return not e.code, ' '.join(out.getvalue().split())[:300]


def main_wf():
    return json.load(open(MAIN_EXPORT, encoding='utf-8'))


def node(wf, name):
    return next(n for n in wf['nodes'] if n['name'] == name)


def first_exec(wf):
    return next(n for n in wf['nodes'] if n.get('type') != 'n8n-nodes-base.stickyNote')


def must_fail(wf, label):
    ok, msg = sanitised(wf)
    return (not ok), ('%s: check_sanitised %s %s' % (label, 'REFUSED' if not ok else 'ACCEPTED', msg))


def must_pass(wf, label):
    ok, msg = sanitised(wf)
    return ok, ('%s: check_sanitised %s %s' % (label, 'accepted' if ok else 'REFUSED', msg))


# ---- 1 · 4-H1 (a) top-level staticData / pinData ---------------------------------------------------------------
def t_h1a_static_data_with_sender_keys():
    wf = main_wf()
    wf['staticData'] = {'global': {'alertThrottle': {'class:' + syn_sender(): 1767225600000}}}
    return must_fail(wf, 'top-level staticData carrying a full sender key')


def t_h1a_pin_data_under_removed_node():
    wf = main_wf()
    wf['pinData'] = {'A Node That No Longer Exists': [{'json': {'sender_key': syn_sender()}}]}
    return must_fail(wf, 'top-level pinData under a removed node name')


def t_h1a_empty_static_and_pin_allowed():
    wf = main_wf()
    wf['staticData'], wf['pinData'] = None, {}
    return must_pass(wf, 'staticData null + pinData {}')


def t_h1a_negative_control_code_text():
    wf = main_wf()
    code = json.dumps(node(wf, 'Build Owner Alert').get('parameters'))
    if "$getWorkflowStaticData('global')" not in code:
        return False, 'negative control is void: Build Owner Alert no longer contains the static-data call text'
    return must_pass(wf, 'unmodified Main export (Build Owner Alert jsCode calls $getWorkflowStaticData)')


# ---- 1 · 4-H1 (b) bearer identifiers by KEY NAME ---------------------------------------------------------------
def t_h1b_param_object_keys():
    wf = main_wf()
    first_exec(wf)['parameters']['pastedSample'] = {'sender_key': syn_sender(), 'gcal_event_id': syn_event()}
    return must_fail(wf, 'pasted execution sample in a node parameter')


def t_h1b_param_json_string():
    wf = main_wf()
    first_exec(wf)['parameters']['jsonBody'] = json.dumps({'_alert_sender': syn_sender()})
    return must_fail(wf, 'execution sample as a JSON string parameter')


def t_h1b_param_name_value_pair():
    wf = main_wf()
    first_exec(wf)['parameters']['assignments'] = {'assignments': [
        {'id': 'x', 'name': 'gcal_event_id', 'type': 'string', 'value': syn_event()}]}
    return must_fail(wf, 'Set-node {name, value} assignment with a literal event id')


def t_h1b_param_expression_allowed():
    wf = main_wf()
    first_exec(wf)['parameters']['pastedSample'] = {'sender_key': '={{ $json.sender_key }}',
                                                    'gcal_event_id': '={{ $json.gcal_event_id }}'}
    return must_pass(wf, 'n8n expressions under the same key names')


def t_h1b_sticky_identifiers_and_pii():
    wf = main_wf()
    st = node(wf, 'Sticky Note')
    st['parameters']['content'] += ('\n\nsample from a live run: sender_key: %s · gcal_event_id = %s · '
                                    'customer: Synthetic Person, +43 000 0000000' % (syn_sender(), syn_event()))
    return must_fail(wf, 'sticky note carrying a pasted sender_key / gcal_event_id')


def t_h1b_staged_test_functions():
    """Codex: the identifiers added to an existing sticky passed the exact staged-test functions with zero errors."""
    spec = importlib.util.spec_from_file_location('staged_g', STAGED_TEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    wf = json.load(open(STAGED_EXPORT, encoding='utf-8'))
    node(wf, 'Sticky Note')['parameters']['content'] += '\n_alert_sender: %s' % syn_sender()
    with tempfile.TemporaryDirectory(prefix='guards-staged-') as d:
        p = os.path.join(d, os.path.basename(STAGED_EXPORT))
        json.dump(wf, open(p, 'w', encoding='utf-8'))
        errs = mod.check(p)
    return bool(errs), 'staged-sanitised.check() on a staged export with a pasted identifier: %d error(s)' % len(errs)


# ---- 2 · 4-M1 representation gaps ------------------------------------------------------------------------------
def t_m1_telegram_chat_id_number():
    wf = main_wf()
    node(wf, 'Send Owner Alert (Telegram)')['parameters']['chatId'] = 100200300
    return must_fail(wf, 'Telegram chatId as a JSON number')


def t_m1_calendar_single_quoted():
    wf = main_wf()
    lc = node(wf, 'Load Config')['parameters']
    real = 'synthetic.owner' + '@' + 'gmail.com'
    lc['jsCode'] = lc['jsCode'].replace('"REPLACE_WITH_CALENDAR_ID@group.calendar.google.com"', "'%s'" % real)
    if real not in lc['jsCode']:
        return False, 'fixture void: the calendar literal was not found in Load Config'
    return must_fail(wf, 'primary calendar address in a single-quoted config literal')


def t_m1_airtable_id_in_array():
    wf = main_wf()
    first_exec(wf)['parameters']['recordIds'] = ['app' + 'Q7w8E9r0T1y2U3']
    return must_fail(wf, 'Airtable-format id directly inside an array')


# ---- 3 · 4-M2 placeholder predicate ----------------------------------------------------------------------------
def t_m2_airtable_id_containing_xxxx():
    wf = main_wf()
    first_exec(wf)['parameters']['url'] = 'https://api.airtable.com/v0/' + 'app' + 'K7XXXXB9nRt4Ls'
    return must_fail(wf, 'real-format Airtable id containing XXXX')


def t_m2_credential_id_containing_xxxx():
    wf = main_wf()
    n = next(x for x in wf['nodes'] if x.get('credentials'))
    cred = next(iter(n['credentials'].values()))
    cred['id'] = 'aB3d' + 'XXXX' + 'kLm9PqR2'
    return must_fail(wf, 'real-format credential id containing XXXX')


def t_m2_every_committed_export_passes():
    # Exports only (`*.sanitized.json`): n8n/staged/ also holds each edit's declared delta, which is not a workflow.
    paths = sorted(glob.glob(os.path.join(REPO, 'n8n', '*.sanitized.json')) + glob.glob(os.path.join(REPO, 'n8n', 'staged', '*.sanitized.json')))
    bad = []
    for p in paths:
        ok, msg = sanitised(json.load(open(p, encoding='utf-8')))
        if not ok:
            bad.append('%s: %s' % (os.path.relpath(p, REPO), msg))
    return (not bad and len(paths) > 0), ('%d committed export(s) sanitise-clean' % len(paths)) if not bad else '; '.join(bad)


# ---- 4 · 4-H2 excluded markers strip tokens, never lines -------------------------------------------------------
def _h2_case(tmp, line):
    _, work = mkrepo(tmp)
    commit(work, 'conf.txt', line + '\n', 'add conf')
    rc, out = hook_scan(work)
    leaked = syn_anthropic() in out
    return rc, out, leaked


def t_h2_marker_beside_secret():
    key = syn_anthropic()
    lines = ['PLACEHOLDER_A=1 key=%s' % key,
             'REPLACE_WITH_THING then %s' % key,
             'base=${API_BASE} key=%s' % key,
             'url=process.env.SOME_URL k=%s' % key,
             'see https://api.example.com/v1 k=%s' % key,
             json.dumps({'nodes': [{'credentials': {'x': {'id': 'REPLACE_WITH_X_CREDENTIAL_ID'}},
                                    'parameters': {'k': key}}]})]
    fails = []
    for i, line in enumerate(lines):
        with tempfile.TemporaryDirectory(prefix='guards-h2-') as tmp:
            rc, out, leaked = _h2_case(tmp, line)
            if rc == 0 or leaked:
                fails.append('case %d rc=%d leaked=%s' % (i, rc, leaked))
    return not fails, ('all %d marker+key lines BLOCKED, key never echoed' % len(lines)) if not fails else '; '.join(fails)


def t_h2_markers_alone_pass():
    with tempfile.TemporaryDirectory(prefix='guards-h2ok-') as tmp:
        _, work = mkrepo(tmp)
        commit(work, 'conf.txt', 'id=REPLACE_WITH_X_CREDENTIAL_ID host=${N8N_HOST} url=https://example.com/a\n'
                                 + 'sk-' + 'ant-' + 'x' * 24 + '\n'
                                 + 'secret: process.env.RELEASE_SIGNING_SECRET_FOR_THE_DASHBOARD,\n'
                                 + "api_key = os.environ['ANTHROPIC_API_KEY_FOR_THE_BOT_RUNTIME']\n", 'placeholders only')
        rc, out = hook_scan(work)
    return rc == 0, 'placeholder-only commit: exit %d %s' % (rc, out.strip()[-160:])


# ---- 5 · 4-H3 every commit's patch, merges included -------------------------------------------------------------
def t_h3_secret_added_then_removed():
    with tempfile.TemporaryDirectory(prefix='guards-h3-') as tmp:
        _, work = mkrepo(tmp)
        commit(work, 'a.txt', 'k=%s\n' % syn_anthropic(), 'A adds')
        commit(work, 'a.txt', 'k=gone\n', 'B removes')
        rc, out = hook_scan(work)
    return rc != 0, 'commit A adds a key, commit B removes it, both unpushed: hook-mode exit %d' % rc


def _evil_merge(work):
    """A merge whose RESOLUTION introduces the key, removed again by a later commit: only `-m` sees it."""
    git(work, 'checkout', '-q', '-b', 'side')
    commit(work, 'side.txt', 'side\n', 'side work')
    git(work, 'checkout', '-q', 'main')
    commit(work, 'main.txt', 'main\n', 'main work')
    git(work, 'merge', '-q', '--no-ff', '--no-commit', 'side')
    write(os.path.join(work, 'merge.txt'), 'k=%s\n' % syn_anthropic())
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-m', 'merge side')
    commit(work, 'merge.txt', 'k=gone\n', 'clean up')


def t_h3_evil_merge():
    with tempfile.TemporaryDirectory(prefix='guards-h3m-') as tmp:
        _, work = mkrepo(tmp)
        _evil_merge(work)
        rc, out = hook_scan(work)
    return rc != 0, 'key introduced only by a merge resolution, then removed: hook-mode exit %d' % rc


# ---- 6 · 4-H5 provider and header shapes -----------------------------------------------------------------------
def _blocked_line(prefix, line, rel='x.txt'):
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        _, work = mkrepo(tmp)
        commit(work, rel, line, 'add')
        return hook_scan(work)


def t_h5_openai_project_key():
    rc, out = _blocked_line('guards-h5a-', 'const k = "%s";\n' % syn_openai_proj())
    return rc != 0 and syn_openai_proj() not in out, 'project-scoped OpenAI key: exit %d' % rc


def t_h5_bearer_hex_header():
    rc, out = _blocked_line('guards-h5b-', 'curl -H "Authorization: Bearer %s" https://api.invalid\n' % syn_hex(40))
    return rc != 0, 'hexadecimal Bearer header value: exit %d' % rc


def t_h5_bearer_ignores_expressions():
    lines = ['"value": "=Bearer {{ $json.accessToken }}"',
             'Authorization: Bearer ={{ $json.accessTokenFromStateOfTheRun }}',
             'Authorization: Bearer ${apiTokenFromTheEnvironmentAtRuntime}',
             'Authorization: Bearer <paste-your-own-token-here-please>']
    rc, out = _blocked_line('guards-h5c-', '\n'.join(lines) + '\n')
    return rc == 0, 'Bearer followed by ={{ / ${ / < : exit %d %s' % (rc, out.strip()[-200:])


def t_h5_n8n_header_pair_json():
    wf = {'nodes': [{'name': 'Call API', 'type': 'n8n-nodes-base.httpRequest', 'parameters': {
        'headerParameters': {'parameters': [{'name': 'Authorization', 'value': 'Bearer ' + syn_hex(16)}]}}}]}
    rc, out = _blocked_line('guards-h5d-', json.dumps(wf, indent=2) + '\n', rel='n8n/wf.json')
    return rc != 0, 'n8n {name: Authorization, value: <16-hex bearer>} pretty-printed JSON: exit %d' % rc


def t_h5_n8n_header_pair_expression_ok():
    wf = {'nodes': [{'name': 'Call API', 'type': 'n8n-nodes-base.httpRequest', 'parameters': {
        'headerParameters': {'parameters': [{'name': 'Authorization', 'value': '=Bearer {{ $json.token }}'},
                                            {'name': 'X-API-Key', 'value': 'REPLACE_WITH_API_KEY'}]}}}]}
    rc, out = _blocked_line('guards-h5e-', json.dumps(wf, indent=2) + '\n', rel='n8n/wf.json')
    return rc == 0, 'header pairs holding an expression / placeholder: exit %d %s' % (rc, out.strip()[-160:])


# ---- 7 · 4-M3 host-leak quoting and case -----------------------------------------------------------------------
def _host_repo(tmp, decl_value, tracked_text):
    work = os.path.join(tmp, 'work')
    git(tmp, 'init', '-q', '-b', 'main', work)
    write(os.path.join(work, '.gitignore'), 'CLAUDE.local.md\n')
    write(os.path.join(work, 'CLAUDE.local.md'), 'notes\nSYNTHETIC_HOST=%s\n' % decl_value)
    commit(work, 'docs/page.md', tracked_text, 'page')
    return run(['bash', HOSTLEAK], work)


def t_m3_quoted_declaration():
    fails = []
    for q in ('"', "'"):
        with tempfile.TemporaryDirectory(prefix='guards-m3q-') as tmp:
            rc, out = _host_repo(tmp, q + syn_host() + q, 'api: https://%s/webhook\n' % syn_host())
            if rc != 1 or syn_host() in out.lower():
                fails.append('quote %s -> exit %d' % (q, rc))
    return not fails, 'quoted declarations find the host in a URL (exit 1, masked)' if not fails else '; '.join(fails)


def t_m3_case_variant():
    with tempfile.TemporaryDirectory(prefix='guards-m3c-') as tmp:
        rc, out = _host_repo(tmp, syn_host(), 'api: HTTPS://%s/webhook\n' % syn_host().upper())
    leaked = syn_host() in out.lower()
    return rc == 1 and not leaked, 'upper-case host in a tracked file: exit %d, printed unmasked=%s' % (rc, leaked)


def t_m3_clean_tree_passes():
    with tempfile.TemporaryDirectory(prefix='guards-m3ok-') as tmp:
        rc, out = _host_repo(tmp, '"%s"' % syn_host(), 'nothing to see\n')
    return rc == 0, 'no occurrence: exit %d' % rc


# ---- 8 · pre-push hook: `<local sha> [^<remote sha>] [--not --remotes=<target>]`, merges included ---------------
def t_pp_unpushed_range_blocked():
    with tempfile.TemporaryDirectory(prefix='guards-pp1-') as tmp:
        _, work = mkrepo(tmp)
        base = git(work, 'rev-parse', 'HEAD')
        commit(work, 'a.txt', 'k=%s\n' % syn_anthropic(), 'A adds')
        head = commit(work, 'a.txt', 'k=gone\n', 'B removes')
        rc, out = prepush(work, ['refs/heads/main %s refs/heads/main %s' % (head, base)])
    return rc not in (0, 127), 'pre-push over A(adds)+B(removes): exit %d' % rc


def t_pp_merge_included():
    with tempfile.TemporaryDirectory(prefix='guards-pp2-') as tmp:
        _, work = mkrepo(tmp)
        base = git(work, 'rev-parse', 'HEAD')
        _evil_merge(work)
        head = git(work, 'rev-parse', 'HEAD')
        rc, out = prepush(work, ['refs/heads/main %s refs/heads/main %s' % (head, base)])
    return rc not in (0, 127), 'pre-push over an evil merge: exit %d' % rc


def t_pp_clean_and_deleted_ref_pass():
    with tempfile.TemporaryDirectory(prefix='guards-pp3-') as tmp:
        _, work = mkrepo(tmp)
        base = git(work, 'rev-parse', 'HEAD')
        head = commit(work, 'a.txt', 'ordinary text\n', 'clean')
        rc1, o1 = prepush(work, ['refs/heads/main %s refs/heads/main %s' % (head, base)])
        rc2, o2 = prepush(work, ['(delete) %s refs/heads/gone %s' % (ZERO, base)])
        rc3, o3 = prepush(work, [])
    return (rc1, rc2, rc3) == (0, 0, 0), 'clean push %d · deleted ref %d · empty stdin %d %s' % (rc1, rc2, rc3, (o1 + o2 + o3)[-200:])


def t_pp_already_on_a_remote_not_rescanned():
    with tempfile.TemporaryDirectory(prefix='guards-pp4-') as tmp:
        _, work = mkrepo(tmp)
        old = commit(work, 'a.txt', 'k=%s\n' % syn_anthropic(), 'already public')
        git(work, 'push', '-q', 'origin', 'main')
        git(work, 'checkout', '-q', '-b', 'feature')
        head = commit(work, 'b.txt', 'ordinary\n', 'new work')
        rc, out = prepush(work, ['refs/heads/feature %s refs/heads/feature %s' % (head, ZERO)])
    return rc == 0, 'new branch whose only new commit is clean (older key already on the remote): exit %d %s' % (rc, out[-160:])


def t_pp_missing_scanner_fails_closed():
    # R1c: the hook runs the scanner BESIDE itself, so "absent" means a hook directory holding pre-push alone — and the
    # working tree's scripts/secret-scan.sh, present here, must NOT be used as a fallback.
    with tempfile.TemporaryDirectory(prefix='guards-pp5-') as tmp:
        _, work = mkrepo(tmp, scanner=True)
        lone = os.path.join(tmp, 'lone-hooks', 'pre-push')
        os.makedirs(os.path.dirname(lone))
        shutil.copy(PREPUSH, lone)
        base = git(work, 'rev-parse', 'HEAD')
        head = commit(work, 'a.txt', 'ordinary\n', 'x')
        rc, out = prepush(work, ['refs/heads/main %s refs/heads/main %s' % (head, base)], hook=lone)
    return rc not in (0, 127), 'pre-push with no secret-scan.sh beside it (working-tree copy present): exit %d' % rc


def t_pp_install_and_real_push():
    if not os.path.exists(INSTALL):
        return False, 'scripts/install-pre-push.sh does not exist'
    with tempfile.TemporaryDirectory(prefix='guards-pp6-') as tmp:
        remote, work = mkrepo(tmp)
        rc_i, out_i = install_into(work)
        target = os.path.join(hooks_of(work), 'pre-push')
        if rc_i != 0 or not os.path.exists(target):
            return False, 'installer exit %d: %s' % (rc_i, out_i[-200:])
        before = git(remote, 'rev-parse', 'main')
        commit(work, 'a.txt', 'k=%s\n' % syn_anthropic(), 'A adds')
        commit(work, 'a.txt', 'k=gone\n', 'B removes')
        rc_p, out_p = run(['git', 'push', '-q', 'origin', 'main'], work)
        after = git(remote, 'rev-parse', 'main')
        git(work, 'reset', '-q', '--hard', 'origin/main')
        commit(work, 'c.txt', 'ordinary\n', 'clean')
        rc_ok, out_ok = run(['git', 'push', '-q', 'origin', 'main'], work)
        write(target, '#!/bin/sh\necho someone elses hook\n')
        rc_r, out_r = install_into(work)
    ok = rc_p != 0 and before == after and rc_ok == 0 and rc_r != 0
    return ok, ('real push with the installed hook: dirty push exit %d (remote moved=%s) · clean push exit %d · '
                'installer over a foreign hook exit %d' % (rc_p, before != after, rc_ok, rc_r))


# ---- R2b · XRUN: the placeholder strip removes a WHOLE placeholder token, never part of a key --------------------
def t_r2b_xrun_key_with_x_run_blocked_on_real_push():
    res = {}
    for label, key in (('AWS-shaped', syn_aws_xrun()), ('OpenAI-shaped', syn_openai_xrun())):
        with tempfile.TemporaryDirectory(prefix='guards-r2bx-') as tmp:
            remote, work = mkrepo(tmp)
            rc_i, out_i = install_into(work)
            if rc_i != 0:
                return False, 'installer exit %d: %s' % (rc_i, out_i[-200:])
            before = git(remote, 'rev-parse', 'main')
            commit(work, 'cfg.txt', 'value: %s\n' % key, 'adds a key with an x run')
            rc, out = run(['git', 'push', '-q', 'origin', 'main'], work)
            res[label] = (rc != 0, git(remote, 'rev-parse', 'main') == before, key not in out)
    return all(all(v) for v in res.values()), 'a key CONTAINING a run of x, real push with the installed hook ' \
        '(blocked, remote unchanged, value not printed): %s' % res


def t_r2b_xrun_whole_placeholders_pass_real_push():
    with tempfile.TemporaryDirectory(prefix='guards-r2bp-') as tmp:
        remote, work = mkrepo(tmp)
        rc_i, out_i = install_into(work)
        if rc_i != 0:
            return False, 'installer exit %d: %s' % (rc_i, out_i[-200:])
        commit(work, 'docs.md', ''.join('example: %s\n' % p for p in syn_placeholders()), 'documents placeholders')
        rc, out = run(['git', 'push', '-q', 'origin', 'main'], work)
        moved = git(remote, 'rev-parse', 'main') == git(work, 'rev-parse', 'HEAD')
    return rc == 0 and moved, 'whole placeholder tokens (AWS, Anthropic, OpenAI project, GitHub, Airtable), real push: ' \
        'exit %d, remote moved=%s · %s' % (rc, moved, out.strip()[-160:])


# ---- 9 · check-hook-drift covers the pre-push hook -------------------------------------------------------------
IGNORE = os.path.join(GROOT, 'scripts', 'secret-scan-ignore')


def _drift_repo(tmp):
    """A throwaway repo whose HEAD holds the gate scripts: check-hook-drift.sh compares against HEAD since R1d."""
    d = os.path.join(tmp, 'drepo')
    if not os.path.isdir(d):
        git(tmp, 'init', '-q', '-b', 'main', d)
        stage_scripts(d)
    return d


def _drift(tmp, prepush_installed, extra_env=None):
    d = _drift_repo(tmp)
    cc = os.path.join(tmp, 'cc-hook.sh')
    shutil.copy(SCAN, cc)
    env = dict(git_env(), SECRET_SCAN_INSTALLED=cc, PRE_PUSH_INSTALLED=prepush_installed, **(extra_env or {}))
    return run(['bash', os.path.join(d, 'scripts', 'check-hook-drift.sh')], d, env=env)


def _hookdir(tmp, pre_push=True, scanner=True, mode=0o755, ignore=True):
    """A hooks directory as the installer leaves it: pre-push + secret-scan.sh (executable) + secret-scan-ignore."""
    d = os.path.join(tmp, 'hooks')
    os.makedirs(d, exist_ok=True)
    for want, src, name, m in ((pre_push, PREPUSH, 'pre-push', mode), (scanner, SCAN, 'secret-scan.sh', mode),
                               (ignore, IGNORE, 'secret-scan-ignore', 0o644)):
        if want and os.path.exists(src):
            shutil.copy(src, os.path.join(d, name))
            os.chmod(os.path.join(d, name), m)
    return os.path.join(d, 'pre-push')


def t_hd_prepush_drift_detected():
    with tempfile.TemporaryDirectory(prefix='guards-hd1-') as tmp:
        pp = _hookdir(tmp)
        write(pp, '#!/bin/sh\nexit 0\n')
        os.chmod(pp, 0o755)
        rc, out = _drift(tmp, pp)
    return rc == 1, 'installed pre-push differs from scripts/pre-push.sh: exit %d' % rc


def t_hd_prepush_match_and_not_installed():
    with tempfile.TemporaryDirectory(prefix='guards-hd2-') as tmp:
        rc1, o1 = _drift(tmp, _hookdir(tmp))
        rc2, o2 = _drift(tmp, os.path.join(tmp, 'absent', 'pre-push'))
    ok = (rc1 == 0 and o1.count('hook drift check: OK') == 4 and rc2 == 0 and o2.count('NOT INSTALLED') == 3
          and 'pre-push' in o2)
    return ok, 'all four identical (+executable) exit %d (%d OK lines) · absent exit %d (%s)' % (
        rc1, o1.count('hook drift check: OK'), rc2, ' '.join(o2.split())[:160])


# ---- R1c · 3 · the hook runs ITS OWN installed scanner copy; drift compares all three files --------------------------
def t_g3_hook_runs_its_installed_copy():
    with tempfile.TemporaryDirectory(prefix='guards-g3a-') as tmp:
        remote, work = mkrepo(tmp)
        rc_i, out_i = install_into(work)
        if rc_i != 0:
            return False, 'installer exit %d: %s' % (rc_i, out_i[-200:])
        # a NEUTERED working-tree scanner that carries every API marker a hook might check
        write(os.path.join(work, 'scripts', 'secret-scan.sh'),
              '#!/usr/bin/env bash\nSECRET_SCAN_API=2\nSECRET_SCAN_API=3\nexit 0\n')
        before = git(remote, 'rev-parse', 'main')
        key_file(work, 'a.txt')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'adds a key')
        rc, out = run(['git', 'push', '-q', 'origin', 'main'], work)
        after = git(remote, 'rev-parse', 'main')
    return rc != 0 and before == after, ('working-tree scanner neutered after install, key pushed: exit %d, remote '
                                         'moved=%s' % (rc, before != after))


def t_hd_g3_scanner_copy_drift_and_missing():
    with tempfile.TemporaryDirectory(prefix='guards-hd3-') as tmp:
        pp = _hookdir(tmp)
        write(os.path.join(tmp, 'hooks', 'secret-scan.sh'), '#!/usr/bin/env bash\nexit 0\n')
        rc1, o1 = _drift(tmp, pp)
        os.remove(os.path.join(tmp, 'hooks', 'secret-scan.sh'))
        rc2, o2 = _drift(tmp, pp)
    return (rc1, rc2) == (1, 1), 'scanner beside the hook differs: exit %d · missing (hook present): exit %d' % (rc1, rc2)


# ---- R1c · 7 · installed executable ---------------------------------------------------------------------------------
def t_hd_g7_not_executable_fails():
    res = []
    for which in ('pre-push', 'secret-scan.sh'):
        with tempfile.TemporaryDirectory(prefix='guards-hd4-') as tmp:
            pp = _hookdir(tmp)
            os.chmod(os.path.join(tmp, 'hooks', which), 0o644)
            res.append(_drift(tmp, pp)[0])
    return res == [1, 1], 'identical but chmod 644: pre-push exit %d · scanner copy exit %d' % tuple(res)


def t_g7_installer_sets_and_verifies_exec():
    with tempfile.TemporaryDirectory(prefix='guards-g7-') as tmp:
        _, work = mkrepo(tmp)
        rc, out = install_into(work)
        h = hooks_of(work)
        files = {'pre-push': (PREPUSH, True), 'secret-scan.sh': (SCAN, True), 'secret-scan-ignore': (IGNORE, False)}
        state = {}
        for name, (src, need_x) in files.items():
            t = os.path.join(h, name)
            state[name] = (os.path.isfile(t) and not os.path.islink(t) and (os.access(t, os.X_OK) or not need_x)
                           and open(t, 'rb').read() == open(src, 'rb').read())
    return rc == 0 and all(state.values()), 'installer exit %d · executable byte-identical copies: %s' % (rc, state)


# ---- R1c · 8 · the installer writes only into this repo's own .git/hooks -----------------------------------------
def t_g8_installer_confined():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-g8a-') as tmp:      # (a) the old free-form override
        _, work = mkrepo(tmp)
        outside = os.path.join(tmp, 'outside', 'pre-push')
        install_into(work, env=dict(git_env(), PRE_PUSH_TARGET=outside))
        res['PRE_PUSH_TARGET ignored'] = not os.path.exists(outside)
    with tempfile.TemporaryDirectory(prefix='guards-g8b-') as tmp:      # (b) a global core.hooksPath
        _, work = mkrepo(tmp)
        gh = os.path.join(tmp, 'global-hooks')
        os.makedirs(gh)
        gcfg = os.path.join(tmp, 'gitconfig')
        write(gcfg, '[core]\n\thooksPath = %s\n' % gh)
        rc, _ = install_into(work, env=dict(git_env(), GIT_CONFIG_GLOBAL=gcfg))
        res['global hooksPath refused'] = (rc != 0 and not os.listdir(gh)
                                           and not os.path.exists(os.path.join(hooks_of(work), 'pre-push')))
    with tempfile.TemporaryDirectory(prefix='guards-g8c-') as tmp:      # (c) .git/hooks is a symlink
        _, work = mkrepo(tmp)
        elsewhere = os.path.join(tmp, 'elsewhere')
        os.makedirs(elsewhere)
        shutil.rmtree(hooks_of(work))
        os.symlink(elsewhere, hooks_of(work))
        rc, _ = install_into(work)
        res['symlinked hooks dir refused'] = rc != 0 and not os.listdir(elsewhere)
    with tempfile.TemporaryDirectory(prefix='guards-g8d-') as tmp:      # (d) the target is a symlink, even with --force
        _, work = mkrepo(tmp)
        victim = os.path.join(tmp, 'victim.txt')
        write(victim, 'victim\n')
        os.makedirs(hooks_of(work), exist_ok=True)
        os.symlink(victim, os.path.join(hooks_of(work), 'pre-push'))
        rc, _ = install_into(work, '--force')
        res['symlinked target refused'] = rc != 0 and open(victim).read() == 'victim\n'
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


# ---- R1c · 1 · python3 -I: a json.py in the cwd (or on PYTHONPATH) cannot replace the rule engine ------------------
PLANT = 'import os\nos._exit(0)\n'


def t_g1_repo_root_json_py_cannot_bypass():
    with tempfile.TemporaryDirectory(prefix='guards-g1-') as tmp:
        _, work = mkrepo(tmp)
        key_file(work, 'a.txt')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'adds a key')
        write(os.path.join(work, 'json.py'), PLANT)
        rc1, _ = hook_scan(work)
        rc2, _ = revs_scan(work, 'HEAD', '--not', '--remotes=origin')
        os.remove(os.path.join(work, 'json.py'))
        pp = os.path.join(tmp, 'pp')
        write(os.path.join(pp, 'json.py'), PLANT)
        rc3, _ = revs_scan(work, 'HEAD', '--not', '--remotes=origin', env=dict(git_env(), PYTHONPATH=pp))
    return 0 not in (rc1, rc2, rc3), ('json.py that exits 0 — in cwd, hook mode %d · in cwd, --revs %d · on PYTHONPATH '
                                      '%d' % (rc1, rc2, rc3))


# ---- R1c · 2 · extraction flags and pinned config ------------------------------------------------------------------
def t_g2_attributes_binary_and_nul_cannot_blind():
    cases = {'* -diff': ('.gitattributes', '* -diff\n', ''), '*.txt binary': ('.gitattributes', '*.txt binary\n', ''),
             'NUL byte': (None, None, 'head\x00tail\n')}
    res = {}
    for name, (ga, gtext, prefix) in cases.items():
        with tempfile.TemporaryDirectory(prefix='guards-g2a-') as tmp:
            _, work = mkrepo(tmp)
            if ga:
                write(os.path.join(work, ga), gtext)
            key_file(work, 'a.txt', extra=prefix)
            git(work, 'add', '-A')
            git(work, 'commit', '-q', '-m', 'adds')
            res[name] = hook_scan(work)[0]
    return all(rc != 0 for rc in res.values()), 'hook-mode exit per case: %s' % res


def t_g2_manual_mode_textconv_and_minus_diff():
    res = {}
    for name, attr, cfg in (('textconv prints nothing', 'a.txt diff=hide\n', ('diff.hide.textconv', 'true')),
                            ('-diff', 'a.txt -diff\n', None)):
        with tempfile.TemporaryDirectory(prefix='guards-g2b-') as tmp:
            _, work = mkrepo(tmp)
            write(os.path.join(work, '.gitattributes'), attr)
            commit(work, 'a.txt', 'ordinary\n', 'tracked file')
            git(work, 'push', '-q', 'origin', 'main')
            if cfg:
                git(work, 'config', *cfg)
            key_file(work, 'a.txt', extra='ordinary\n')     # uncommitted change to a TRACKED file
            rc, out = manual_scan(work)
            # the RULE must fire: a pre-fix run saw nothing and answered NOT MEASURED (also exit 2) for a dirty tree
            res[name] = (rc, 'possible secret' in out)
    return all(rc == 2 and hit for rc, hit in res.values()), 'manual-mode (exit, rule fired) per case: %s' % res


def t_g2_root_commit_under_showroot_false():
    with tempfile.TemporaryDirectory(prefix='guards-g2c-') as tmp:
        work = os.path.join(tmp, 'work')
        git(tmp, 'init', '-q', '-b', 'main', work)
        git(work, 'config', 'log.showRoot', 'false')
        key_file(work, 'a.txt')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'root')
        rc, out = revs_scan(work, 'HEAD')
    return rc != 0, 'root commit carrying a key, log.showRoot=false, --revs HEAD: exit %d' % rc


def t_g2_diff_relative_from_subdir():
    with tempfile.TemporaryDirectory(prefix='guards-g2d-') as tmp:
        _, work = mkrepo(tmp)
        write(os.path.join(work, 'sub', 'keep.txt'), 'x\n')
        key_file(work, 'a.txt')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'adds')
        git(work, 'config', 'diff.relative', 'true')
        rc, out = hook_scan(os.path.join(work, 'sub'))
    return rc != 0, 'diff.relative=true, hook run from sub/, key outside it: exit %d' % rc


def t_g2_quotepath_json_header_pair():
    wf = {'nodes': [{'name': 'Call API', 'type': 'n8n-nodes-base.httpRequest', 'parameters': {
        'headerParameters': {'parameters': [{'name': 'Authorization', 'value': 'Bearer ' + syn_hex(16)}]}}}]}
    rc, out = _blocked_line('guards-g2e-', json.dumps(wf, indent=2) + '\n', rel='n8n/w\u00f6rk.json')
    return rc != 0 and 'n8n header pair' in out, 'header pair in a non-ASCII-named JSON file: exit %d, header-pair ' \
                                                 'rule fired=%s' % (rc, 'n8n header pair' in out)


def t_g2_log_output_encoding_pinned():
    with tempfile.TemporaryDirectory(prefix='guards-g2f-') as tmp:
        _, work = mkrepo(tmp)
        write(os.path.join(work, 'a.txt'), 'ordinary\n')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-F', msg_file(tmp, 'note %s\n' % syn_anthropic()))
        git(work, 'config', 'i18n.logOutputEncoding', 'UTF-16')
        rc, out = hook_scan(work)
    return rc != 0, 'key in a commit message, i18n.logOutputEncoding=UTF-16: exit %d' % rc


# ---- R1c · 4 · extraction fails closed ------------------------------------------------------------------------------
def _shim(d, tool, token):
    real = shutil.which(tool)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, tool)
    cond = 'hit=1' if token is None else 'for a in "$@"; do [ "$a" = "%s" ] && hit=1; done' % token
    write(p, '#!/bin/sh\nhit=0\n%s\nif [ "$hit" = 1 ]; then echo "shim: simulated %s failure" >&2; exit 128; fi\n'
             'exec %s "$@"\n' % (cond, tool, real))
    os.chmod(p, 0o755)
    return d


def t_g4_extraction_failure_blocks():
    header_wf = json.dumps({'nodes': [{'name': 'Call API', 'parameters': {'headerParameters': {'parameters': [
        {'name': 'Authorization', 'value': 'Bearer ' + syn_hex(16)}]}}}]}, indent=2) + '\n'
    # R1d: committed patches are split by the rule engine itself (it needs their commit and path), so the added-line
    # filter runs only on the manual-mode WORKING TREE — that stage is driven there (an awk state machine since R4, which
    # keeps a content line starting with `++`; it was a grep pair). Every stage must name the extraction failure, not
    # merely block: a key the rules find would block too, and prove nothing about the stage.
    stages = {   # stage -> (tool, token, where the ONLY detectable secret sits)
        'git log -p': ('git', '-p', 'content'), 'git log %B': ('git', '--format=%B', 'message'),
        'git log --name-only': ('git', '--name-only', 'header'), 'git cat-file': ('git', 'cat-file', 'header'),
        'awk (manual-mode working tree)': ('awk', None, 'worktree')}
    res = {}
    for stage, (tool, token, where) in stages.items():
        with tempfile.TemporaryDirectory(prefix='guards-g4-') as tmp:
            _, work = mkrepo(tmp)
            if where == 'content':
                key_file(work, 'a.txt')
            elif where == 'worktree':
                write(os.path.join(work, 'a.txt'), 'ordinary\n')
            elif where == 'header':
                write(os.path.join(work, 'n8n', 'wf.json'), header_wf)
            else:
                write(os.path.join(work, 'a.txt'), 'ordinary\n')
            git(work, 'add', '-A')
            git(work, 'commit', '-q', '-F', msg_file(tmp, ('note %s\n' % syn_anthropic()) if where == 'message'
                                                     else 'ordinary\n'))
            if where == 'worktree':
                git(work, 'push', '-q', 'origin', 'main')
                key_file(work, 'a.txt', extra='ordinary\n')     # uncommitted change to a TRACKED file
            shim = _shim(os.path.join(tmp, 'shim'), tool, token)
            rc, out = run(['bash', SCAN], work, stdin='' if where == 'worktree' else HOOK_PAYLOAD,
                          env=dict(git_env(), PATH=shim + os.pathsep + os.environ['PATH']))
            res[stage] = (rc, 'could not extract' in out)
    return all(rc != 0 and b for rc, b in res.values()), 'simulated failure per stage -> (exit, extraction ' \
                                                         'failure named): %s' % res


def t_g4_truncated_write_blocks():
    with tempfile.TemporaryDirectory(prefix='guards-g4t-') as tmp:
        _, work = mkrepo(tmp)
        key_file(work, 'big.txt', extra=''.join('ordinary line number %06d of padding\n' % i for i in range(12000)))
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'big file, key on its last line')
        rc, out = run(['bash', '-c', 'ulimit -f 128; exec bash "$0" --revs HEAD --not --remotes=origin', SCAN], work)
    return rc != 0, 'file-size limit 128 KiB under a ~450 KB patch whose key is at the end: exit %d %s' % (
        rc, ' '.join(out.split())[-160:])


# ---- R1c · 5 · exclude only what the TARGET remote already has ------------------------------------------------------
def _key_on_second_remote(tmp, name):
    remote, work = mkrepo(tmp)
    other = os.path.join(tmp, 'other.git')
    git(tmp, 'init', '-q', '--bare', '-b', 'main', other)
    if '/' in name:
        # A nested remote name is set up through config: `git remote add origin/side` is refused by newer git (measured
        # in the audit container: "a subset of existing remote"), while a configured one still pushes and still gets
        # tracking refs under refs/remotes/origin/side/ — the state this case needs, on every git version (R2b: g5 on the
        # host's git and the container's newer one).
        git(work, 'config', 'remote.%s.url' % name, other)
        git(work, 'config', 'remote.%s.fetch' % name, '+refs/heads/*:refs/remotes/%s/*' % name)
    else:
        git(work, 'remote', 'add', name, other)
    base = git(work, 'rev-parse', 'HEAD')
    key_file(work, 'a.txt')
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-m', 'adds a key')
    git(work, 'push', '-q', name, 'main')
    head = commit(work, 'b.txt', 'ordinary\n', 'clean on top')
    return work, base, head


def t_g5_commit_on_other_remote_still_scanned():
    res = {}
    for name in ('backup', 'origin/side'):    # 'origin/side': its tracking refs also match --remotes=origin
        with tempfile.TemporaryDirectory(prefix='guards-g5a-') as tmp:
            work, base, head = _key_on_second_remote(tmp, name)
            res[name] = prepush(work, ['refs/heads/main %s refs/heads/main %s' % (head, base)])[0]
    return all(rc not in (0, 127) for rc in res.values()), 'key only on a second remote, push to origin: %s' % res


def t_g5_url_push_and_remote_sha():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-g5b-') as tmp:
        remote, work = mkrepo(tmp)
        key_file(work, 'a.txt')
        git(work, 'add', '-A')
        git(work, 'commit', '-q', '-m', 'adds a key')
        git(work, 'push', '-q', 'origin', 'main')
        tip = git(work, 'rev-parse', 'HEAD')
        head = commit(work, 'b.txt', 'ordinary\n', 'clean on top')
        line = 'refs/heads/main %s refs/heads/main %s'
        res['URL, new ref: whole range scanned (blocked)'] = prepush(work, [line % (head, ZERO)], remote=remote,
                                                                     url=remote)[0] not in (0, 127)
        res['URL, remote sha excluded (passes)'] = prepush(work, [line % (head, tip)], remote=remote, url=remote)[0] == 0
        git(work, 'update-ref', '-d', 'refs/remotes/origin/main')       # stale tracking refs: only ^<remote sha> helps
        res['named, no tracking ref, remote sha excluded (passes)'] = prepush(work, [line % (head, tip)])[0] == 0
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


# ---- R1c · 6 · annotated tags ------------------------------------------------------------------------------------
def _tag_repo(tmp):
    _, work = mkrepo(tmp)
    return work


def t_g6_annotated_tag_message_scanned():
    with tempfile.TemporaryDirectory(prefix='guards-g6a-') as tmp:
        work = _tag_repo(tmp)
        git(work, 'tag', '-a', 'v1', '-F', msg_file(tmp, 'release %s\n' % syn_anthropic()))
        tag = git(work, 'rev-parse', 'v1')
        rc, out = prepush(work, ['refs/tags/v1 %s refs/tags/v1 %s' % (tag, ZERO)])
    return rc not in (0, 127) and syn_anthropic() not in out, 'annotated tag (on a pushed commit) whose message ' \
                                                             'carries a key: exit %d' % rc


def t_g6_tag_chain_followed():
    with tempfile.TemporaryDirectory(prefix='guards-g6b-') as tmp:
        work = _tag_repo(tmp)
        git(work, 'tag', '-a', 't1', '-F', msg_file(tmp, 'inner %s\n' % syn_anthropic()))
        git(work, '-c', 'advice.nestedTag=false', 'tag', '-a', 't2', 't1', '-m', 'outer, clean')
        tag = git(work, 'rev-parse', 't2')
        rc, out = prepush(work, ['refs/tags/t2 %s refs/tags/t2 %s' % (tag, ZERO)])
    return rc not in (0, 127), 'clean tag t2 -> tag t1 (key in message) -> commit: exit %d' % rc


def t_g6_tag_on_blob_or_tree_refused():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-g6c-') as tmp:
        work = _tag_repo(tmp)
        blob, tree = git(work, 'rev-parse', 'HEAD:README.md'), git(work, 'rev-parse', 'HEAD^{tree}')
        git(work, 'tag', 'lw-blob', blob)
        git(work, 'tag', '-a', 'an-tree', tree, '-m', 'tree tag')
        for ref in ('lw-blob', 'an-tree'):
            sha = git(work, 'rev-parse', ref)
            rc, out = prepush(work, ['refs/tags/%s %s refs/tags/%s %s' % (ref, sha, ref, ZERO)])
            res[ref] = (rc, 'does not peel to a commit' in out)
    return all(rc not in (0, 127) and m for rc, m in res.values()), 'tag on a blob / tree -> (exit, refused): %s' % res


def t_g6_clean_annotated_tag_passes():
    with tempfile.TemporaryDirectory(prefix='guards-g6d-') as tmp:
        work = _tag_repo(tmp)
        git(work, 'tag', '-a', 'v1', '-m', 'release one')
        tag = git(work, 'rev-parse', 'v1')
        rc, out = prepush(work, ['refs/tags/v1 %s refs/tags/v1 %s' % (tag, ZERO)])
    return rc == 0, 'clean annotated tag on a pushed commit: exit %d %s' % (rc, out[-160:])


# ---- R1c · 9 · example.com no longer exempts anything ------------------------------------------------------------
def t_g9_example_com_cannot_swallow_a_key():
    k = syn_anthropic()
    lines = ['callback https://example.com/cb?token=%s' % k, 'see https://example.com/%s' % k,
             'see https://example.com/#%s' % k, 'mail %s@example.com' % k]
    res = []
    for line in lines:
        rc, out = _blocked_line('guards-g9-', line + '\n')
        res.append(rc != 0 and k not in out)
    return all(res), 'example.com + key, blocked and masked per line: %s' % res


# ---- R1c · end to end: real `git push` through the installed hook --------------------------------------------------
def t_g_e2e_real_push_matrix():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-e2e-') as tmp:
        remote, work = mkrepo(tmp)
        other = os.path.join(tmp, 'other.git')
        git(tmp, 'init', '-q', '--bare', '-b', 'main', other)
        git(work, 'remote', 'add', 'backup', other)
        rc_i, out_i = install_into(work)
        if rc_i != 0:
            return False, 'installer exit %d: %s' % (rc_i, out_i[-200:])

        def push(*a):
            before = git(remote, 'for-each-ref', '--format=%(objectname) %(refname)')
            rc, out = run(['git', 'push', '-q', *a], work)
            return rc, before != git(remote, 'for-each-ref', '--format=%(objectname) %(refname)')

        def reset():
            git(work, 'reset', '-q', '--hard', 'origin/main')
            for f in ('json.py',):
                if os.path.exists(os.path.join(work, f)):
                    os.remove(os.path.join(work, f))

        seq = []

        def add_key(extra_files=()):
            for rel, text in extra_files:
                write(os.path.join(work, rel), text)
            seq.append(1)       # a distinct commit every time, so a push that wrongly passes cannot make the next empty
            key_file(work, 'a.txt', extra='round %d\n' % len(seq))
            git(work, 'add', '-A')
            git(work, 'commit', '-q', '-m', 'adds a key')

        add_key()
        rc, moved = push('origin', 'main')
        res['dirty push blocked'] = rc != 0 and not moved
        reset()
        add_key()
        write(os.path.join(work, 'json.py'), PLANT)           # untracked, at the root git runs the hook from
        rc, moved = push('origin', 'main')
        res['root json.py does not bypass'] = rc != 0 and not moved
        reset()
        add_key([('.gitattributes', '* -diff\n')])
        rc, moved = push('origin', 'main')
        res['* -diff does not blind'] = rc != 0 and not moved
        reset()
        add_key()
        git(work, 'push', '-q', '--no-verify', 'backup', 'main')   # setup only: put the key commit on the 2nd remote
        commit(work, 'b.txt', 'ordinary\n', 'clean on top')
        rc, moved = push('origin', 'main')
        res['commit on a second remote still scanned'] = rc != 0 and not moved
        reset()
        git(work, 'tag', '-a', 'v1', '-F', msg_file(tmp, 'release %s\n' % syn_anthropic()))
        rc, moved = push('origin', 'v1')
        res['annotated tag with a key blocked'] = rc != 0 and not moved
        git(work, 'tag', '-d', 'v1')
        commit(work, 'c.txt', 'ordinary\n', 'clean')
        rc, moved = push('origin', 'main')
        res['clean push passes'] = rc == 0 and moved
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


# ---- R1d · M-A · the installer and the drift check work from HEAD, never the working tree ----------------------------
HOOK_NAMES = ('pre-push', 'secret-scan.sh', 'secret-scan-ignore')


def _installed(work):
    return [n for n in HOOK_NAMES if os.path.lexists(os.path.join(hooks_of(work), n))]


def t_r1d_ma_installer_refuses_unless_tracked_and_at_head():
    res = {}
    for case in ('untracked', 'modified', 'staged', 'exception file untracked'):
        with tempfile.TemporaryDirectory(prefix='guards-ma1-') as tmp:
            _, work = mkrepo(tmp)
            if case == 'untracked':
                rc, out = install_into(work, commit=False)
            else:
                sd = stage_scripts(work)
                if case == 'exception file untracked':
                    git(work, 'rm', '-q', '--cached', 'scripts/secret-scan-ignore')
                    git(work, 'commit', '-q', '-m', 'untrack the exceptions')
                else:
                    with open(os.path.join(sd, 'secret-scan.sh'), 'a', encoding='utf-8') as f:
                        f.write('# an unreviewed local edit\n')
                    if case == 'staged':
                        git(work, 'add', '-f', 'scripts/secret-scan.sh')
                rc, out = run(['bash', os.path.join(sd, 'install-pre-push.sh')], work)
            res[case] = (rc, _installed(work))
    return all(rc != 0 and not w for rc, w in res.values()), 'installer (exit, files written) per case: %s' % res


def t_r1d_ma_installer_writes_the_head_blob_not_smudged_bytes():
    """A smudge filter makes the working-tree bytes differ while `git diff` (which cleans first) calls them identical —
    the case where reading the working tree and reading the blob part ways."""
    with tempfile.TemporaryDirectory(prefix='guards-ma2-') as tmp:
        _, work = mkrepo(tmp)
        sd = stage_scripts(work)
        marker = '# SMUDGED-INTO-THE-WORKING-TREE'
        git(work, 'config', 'filter.inject.smudge', "sed '$a %s'" % marker)
        git(work, 'config', 'filter.inject.clean', "sed '/^%s$/d'" % marker)
        write(os.path.join(work, '.git', 'info', 'attributes'), 'scripts/secret-scan.sh filter=inject\n')
        os.remove(os.path.join(sd, 'secret-scan.sh'))
        git(work, 'checkout', '--', 'scripts/secret-scan.sh')
        smudged = marker in open(os.path.join(sd, 'secret-scan.sh'), encoding='utf-8').read()
        clean = run(['git', 'diff', '--quiet', 'HEAD', '--', 'scripts/secret-scan.sh'], work)[0] == 0
        if not (smudged and clean):
            return False, 'fixture void: smudged=%s, git diff quiet=%s' % (smudged, clean)
        rc, out = run(['bash', os.path.join(sd, 'install-pre-push.sh')], work)
        inst = open(os.path.join(hooks_of(work), 'secret-scan.sh'), 'rb').read() if rc == 0 else b''
        blob = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:scripts/secret-scan.sh'], cwd=work, env=git_env(),
                              capture_output=True).stdout
    return rc == 0 and inst == blob, ('smudged working tree, clean diff: installer exit %d, installed == HEAD blob: %s, '
                                      'smudge marker installed: %s' % (rc, inst == blob, marker.encode() in inst))


def t_r1d_ma_drift_compares_head_not_working_tree():
    with tempfile.TemporaryDirectory(prefix='guards-ma3-') as tmp:
        pp = _hookdir(tmp)
        rc0, o0 = _drift(tmp, pp)
        canon = os.path.join(_drift_repo(tmp), 'scripts', 'secret-scan.sh')
        with open(canon, 'a', encoding='utf-8') as f:
            f.write('# an uncommitted edit\n')
        rc1, o1 = _drift(tmp, pp)            # installed copies still equal HEAD: OK, plus a note
        shutil.copy(canon, os.path.join(tmp, 'hooks', 'secret-scan.sh'))   # installed == working tree != HEAD
        os.chmod(os.path.join(tmp, 'hooks', 'secret-scan.sh'), 0o755)
        rc2, o2 = _drift(tmp, pp)
    ok = rc0 == 0 and rc1 == 0 and 'uncommitted changes' in o1 and rc2 == 1 and 'HOOK DRIFT' in o2
    return ok, ('baseline exit %d · canonical edited, installed == HEAD: exit %d (note=%s) · installed == the edited '
                'working tree: exit %d' % (rc0, rc1, 'uncommitted changes' in o1, rc2))


# ---- R1d · M-B · fingerprint exceptions -------------------------------------------------------------------------------
RULE_A = 'anthropic key'


def _fp_scanner(tmp, ignore_text=None):
    """A scanner copy with its OWN exception file beside it — the scanner never reads the repo's working tree."""
    d = os.path.join(tmp, 'scanner')
    os.makedirs(d, exist_ok=True)
    shutil.copy(SCAN, os.path.join(d, 'secret-scan.sh'))
    if ignore_text is not None:
        write(os.path.join(d, 'secret-scan-ignore'), ignore_text)
    return os.path.join(d, 'secret-scan.sh')


def _fp_repo(tmp, a_text=None, a_msg='A adds a fixture', extra=None):
    """Root commit, then A (a.txt carries the fixture key), then B (removes it). Returns (work, A)."""
    work = os.path.join(tmp, 'work')
    git(tmp, 'init', '-q', '-b', 'main', work)
    commit(work, 'README.md', 'base\n', 'base')
    write(os.path.join(work, 'a.txt'), a_text or 'k=%s\n' % syn_anthropic())
    for rel, text in (extra or {}).items():
        write(os.path.join(work, rel), text)
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-F', msg_file(tmp, a_msg + '\n'))
    a = git(work, 'rev-parse', 'HEAD')
    commit(work, 'a.txt', 'gone\n', 'B removes it')
    return work, a


def _full(work, scanner):
    return run(['bash', scanner, '--revs', 'HEAD'], work)     # from the root: what a push to an empty remote scans


def _entry(fp):
    return '# synthetic fixture, test only\n%s\n' % fp


def t_r1d_mb_fixture_blocks_then_its_fingerprint_passes():
    with tempfile.TemporaryDirectory(prefix='guards-mb1-') as tmp:
        work, a = _fp_repo(tmp)
        fp = '%s:a.txt:%s' % (a, RULE_A)
        rc0, o0 = _full(work, _fp_scanner(tmp))                      # no exception file: strict
        os.remove(os.path.join(tmp, 'scanner', 'secret-scan.sh'))
        rc1, o1 = _full(work, _fp_scanner(tmp, _entry(fp)))
        git(work, 'config', 'diff.dstPrefix', 'Z/')          # a setting that changes `+++ b/<path>` (16); NOT
        rc2, _ = _full(work, os.path.join(tmp, 'scanner', 'secret-scan.sh'))   # with noprefix, which overrides it
    ok = (rc0 == 2 and ('fingerprint ' + fp) in o0 and syn_anthropic() not in o0
          and rc1 == 0 and '1 hit(s) excepted by fingerprint' in o1 and rc2 == 0)
    return ok, ('full history, no exception file: exit %d (fingerprint printed=%s, key echoed=%s) · its fingerprint '
                'listed: exit %d (count line=%s) · same, under diff.dstPrefix=Z/: exit %d' % (
                    rc0, ('fingerprint ' + fp) in o0, syn_anthropic() in o0, rc1,
                    '1 hit(s) excepted by fingerprint' in o1, rc2))


def t_r1d_mb_exception_is_pinned_to_commit_path_and_rule():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-mb2a-') as tmp:      # the SAME line, re-added by a NEW commit
        work, a = _fp_repo(tmp)
        c = commit(work, 'a.txt', 'k=%s\n' % syn_anthropic(), 'C re-adds the same line')
        rc, out = _full(work, _fp_scanner(tmp, _entry('%s:a.txt:%s' % (a, RULE_A))))
        res['same line, new commit'] = rc == 2 and ('fingerprint %s:a.txt:%s' % (c, RULE_A)) in out
    with tempfile.TemporaryDirectory(prefix='guards-mb2b-') as tmp:      # same commit, another path
        work, a = _fp_repo(tmp, extra={'b.txt': 'k=%s\n' % syn_anthropic()})
        rc, out = _full(work, _fp_scanner(tmp, _entry('%s:a.txt:%s' % (a, RULE_A))))
        res['same commit, other path'] = rc == 2 and ('fingerprint %s:b.txt:%s' % (a, RULE_A)) in out
    with tempfile.TemporaryDirectory(prefix='guards-mb2c-') as tmp:      # same commit and path, another rule
        work, a = _fp_repo(tmp, a_text='k=%s p=%s\n' % (syn_anthropic(), syn_openai_proj()))
        rc, out = _full(work, _fp_scanner(tmp, _entry('%s:a.txt:%s' % (a, RULE_A))))
        res['same line, other rule'] = rc == 2 and ('fingerprint %s:a.txt:openai project/service key' % a) in out
    with tempfile.TemporaryDirectory(prefix='guards-mb2d-') as tmp:      # the key in A's MESSAGE: no provenance
        work, a = _fp_repo(tmp, a_msg='A adds a fixture %s' % syn_anthropic())
        rc, out = _full(work, _fp_scanner(tmp, _entry('%s:a.txt:%s' % (a, RULE_A))))
        res['commit message never excepted'] = rc == 2 and 'cannot be excepted' in out
    return all(res.values()), ' · '.join('%s blocked=%s' % kv for kv in res.items())


def t_r1d_mb_malformed_or_linked_exception_file_blocks():
    a = '0123456789abcdef0123456789abcdef01234567'
    bad = {'short commit': '%s:a.txt:%s' % (a[:12], RULE_A), 'no rule': '%s:a.txt' % a,
           'rule wildcard': '%s:a.txt:*' % a, 'path wildcard': '%s:*.txt:%s' % (a, RULE_A),
           'upper-case hex': '%s:a.txt:%s' % (a.upper(), RULE_A), 'trailing space': '%s:a.txt:%s ' % (a, RULE_A),
           'inline comment': '%s:a.txt:%s # why' % (a, RULE_A), 'CRLF': '%s:a.txt:%s\r' % (a, RULE_A)}
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-mb3-') as tmp:
        work, real_a = _fp_repo(tmp)
        for name, line in bad.items():
            shutil.rmtree(os.path.join(tmp, 'scanner'), ignore_errors=True)
            sc = _fp_scanner(tmp, '# ok comment\n\n%s\n' % line)
            rc1, o1 = _full(work, sc)
            rc2, o2 = run(['bash', sc, '--revs', 'HEAD', '^HEAD'], work)    # nothing to scan: still refused
            res[name] = rc1 == 2 and rc2 == 2 and 'malformed' in o1 and 'malformed' in o2
        # a symlink (to a VALID file that would except the fixture) and a directory: refused, never followed
        good = os.path.join(tmp, 'good-ignore')
        write(good, _entry('%s:a.txt:%s' % (real_a, RULE_A)))
        shutil.rmtree(os.path.join(tmp, 'scanner'))
        sc = _fp_scanner(tmp)
        os.symlink(good, os.path.join(tmp, 'scanner', 'secret-scan-ignore'))
        rc, out = _full(work, sc)
        res['symlink'] = rc == 2 and 'symlink' in out
        os.remove(os.path.join(tmp, 'scanner', 'secret-scan-ignore'))
        os.makedirs(os.path.join(tmp, 'scanner', 'secret-scan-ignore'))
        rc, out = _full(work, sc)
        res['directory'] = rc == 2 and 'not a regular file' in out
    return all(res.values()), 'refused per shape: %s' % res


def t_r1d_mb_committed_exception_file_shape():
    """Every entry in the committed file passes the scanner's own validation and has its reason directly above it."""
    if not os.path.exists(IGNORE):
        return False, 'scripts/secret-scan-ignore does not exist'
    lines = open(IGNORE, encoding='utf-8').read().split('\n')
    entries, unexplained = 0, []
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        entries += 1
        if i == 0 or not lines[i - 1].lstrip().startswith('#'):
            unexplained.append(i + 1)
    with tempfile.TemporaryDirectory(prefix='guards-mb4-') as tmp:
        work = os.path.join(tmp, 'work')
        git(tmp, 'init', '-q', '-b', 'main', work)
        commit(work, 'README.md', 'base\n', 'base')
        rc, out = run(['bash', SCAN, '--revs', 'HEAD', '^HEAD'], work)
    ok = entries > 0 and not unexplained and rc == 0
    return ok, '%d entr(y/ies), without a comment above: %s, scanner validation exit %d %s' % (
        entries, unexplained or 'none', rc, ' '.join(out.split())[-160:] if rc else '')


def t_r1d_mb_real_history_needs_exactly_the_listed_fingerprints():
    """This repo's own history from the root (what a push of HEAD to an empty remote scans): it passes WITH the
    committed exception file, and is blocked by the same scanner WITHOUT it — so no listed entry is dead weight."""
    rc1, o1 = run(['bash', SCAN, '--revs', 'HEAD'], REPO)
    with tempfile.TemporaryDirectory(prefix='guards-mb5-') as tmp:
        rc2, o2 = run(['bash', _fp_scanner(tmp), '--revs', 'HEAD'], REPO)
    listed = sum(1 for l in open(IGNORE, encoding='utf-8') if l.strip() and not l.lstrip().startswith('#')) \
        if os.path.exists(IGNORE) else 0
    remaining = o2.count('      fingerprint ')
    ok = rc1 == 0 and 'excepted by fingerprint' in o1 and rc2 == 2 and remaining == listed
    return ok, ('HEAD from the root: with the committed exceptions exit %d · without them exit %d, %d fingerprint(s) '
                'printed for %d listed' % (rc1, rc2, remaining, listed))


# ---- R1d · --diff-merges=separate: a log.diffMerges setting cannot hide a merge ----------------------------------------
def _evil_merge_json(work):
    """As _evil_merge, but the merge resolution adds an n8n header pair only the JSON check can see."""
    wf = {'nodes': [{'name': 'Call API', 'parameters': {'headerParameters': {'parameters': [
        {'name': 'Authorization', 'value': 'Bearer ' + syn_hex(16)}]}}}]}
    git(work, 'checkout', '-q', '-b', 'side')
    commit(work, 'side.txt', 'side\n', 'side work')
    git(work, 'checkout', '-q', 'main')
    commit(work, 'main.txt', 'main\n', 'main work')
    git(work, 'merge', '-q', '--no-ff', '--no-commit', 'side')
    write(os.path.join(work, 'n8n', 'wf.json'), json.dumps(wf, indent=2) + '\n')
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-m', 'merge side')
    git(work, 'rm', '-q', 'n8n/wf.json')
    git(work, 'commit', '-q', '-m', 'clean up')


def t_r1d_dm_evil_merge_under_every_log_diffmerges():
    res = {}
    for builder in (_evil_merge, _evil_merge_json):
        for v in (None, 'off', 'first-parent', 'combined', 'remerge', 'separate'):
            with tempfile.TemporaryDirectory(prefix='guards-dm-') as tmp:
                _, work = mkrepo(tmp)
                builder(work)
                if v:
                    git(work, 'config', 'log.diffMerges', v)
                rc, out = revs_scan(work, 'HEAD', '--not', '--remotes=origin')
                res['%s/%s' % ('line' if builder is _evil_merge else 'json', v or 'unset')] = rc
    return all(rc == 2 for rc in res.values()), 'evil merge, exit per log.diffMerges: %s' % res


# ---- R1d · drift: where git actually runs hooks from (security MEDIUM-3) ---------------------------------------------
def t_r1d_hd_hookspath_redirect_is_drift():
    with tempfile.TemporaryDirectory(prefix='guards-hp-') as tmp:
        _, work = mkrepo(tmp)
        rc_i, out_i = install_into(work)
        if rc_i != 0:
            return False, 'installer exit %d: %s' % (rc_i, out_i[-200:])
        drift = os.path.join(work, 'scripts', 'check-hook-drift.sh')
        cc = os.path.join(tmp, 'cc-hook.sh')
        shutil.copy(SCAN, cc)
        env = dict(git_env(), SECRET_SCAN_INSTALLED=cc)
        res = {'installed, no redirect': run(['bash', drift], work, env=env)[0] == 0}
        empty = os.path.join(tmp, 'empty-hooks')
        os.makedirs(empty)
        git(work, 'config', 'core.hooksPath', empty)
        rc, out = run(['bash', drift], work, env=env)
        res['local hooksPath -> empty dir'] = rc == 1 and 'core.hooksPath' in out
        git(work, 'config', 'core.hooksPath', os.path.join(work, '.git', 'hooks'))
        rc, out = run(['bash', drift], work, env=env)
        res['local hooksPath naming .git/hooks'] = rc == 1 and 'core.hooksPath' in out
        rc, out = run(['bash', os.path.join(work, 'scripts', 'install-pre-push.sh')], work)
        res['installer refuses that too'] = rc != 0 and 'core.hooksPath is set' in out
        git(work, 'config', '--unset', 'core.hooksPath')
        gcfg = os.path.join(tmp, 'gitconfig')
        write(gcfg, '[core]\n\thooksPath = %s\n' % empty)
        rc, out = run(['bash', drift], work, env=dict(env, GIT_CONFIG_GLOBAL=gcfg))
        res['global hooksPath'] = rc == 1 and 'core.hooksPath' in out
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


# ---- R1d · LOW-2 · the installer's backup name cannot be a pre-placed link ---------------------------------------------
def t_r1d_low2_backup_name_link_refused_nothing_written():
    res = {}
    for kind in ('symlink to a file', 'dangling symlink'):
        with tempfile.TemporaryDirectory(prefix='guards-l2-') as tmp:
            _, work = mkrepo(tmp)
            rc0, _ = install_into(work)
            h = hooks_of(work)
            write(os.path.join(h, 'pre-push'), '#!/bin/sh\nexit 0\n')        # a different hook: --force backs it up
            victim = os.path.join(tmp, 'victim.txt')
            if kind == 'symlink to a file':
                write(victim, 'victim\n')
            now = int(time.time())
            for e in range(now - 2, now + 120):
                os.symlink(victim, os.path.join(h, 'pre-push.bak.%d' % e))
            before = {n: os.lstat(os.path.join(h, n)).st_ino for n in os.listdir(h)}
            rc, out = run(['bash', os.path.join(work, 'scripts', 'install-pre-push.sh'), '--force'], work)
            after = {n: os.lstat(os.path.join(h, n)).st_ino for n in os.listdir(h)}
            victim_ok = (open(victim).read() == 'victim\n') if kind == 'symlink to a file' else not os.path.exists(victim)
            res[kind] = rc0 == 0 and rc != 0 and victim_ok and before == after
    return all(res.values()), '--force with every backup name pre-linked -> refused, victim intact, nothing written: ' \
                              '%s' % res


# ---- R1d · LOW-3 · a symlinked installed copy is drift, and the hook refuses one ---------------------------------------
def t_r1d_low3_drift_flags_symlinked_installed_copies():
    res = {}
    canon = {'pre-push': 'pre-push.sh', 'secret-scan.sh': 'secret-scan.sh', 'secret-scan-ignore': 'secret-scan-ignore'}
    for which in HOOK_NAMES + ('claude code copy',):
        with tempfile.TemporaryDirectory(prefix='guards-l3d-') as tmp:
            pp = _hookdir(tmp)
            d = _drift_repo(tmp)
            target = os.path.join(d, 'scripts', canon.get(which, 'secret-scan.sh'))   # identical to HEAD
            os.chmod(target, 0o755)
            if which == 'claude code copy':
                link = os.path.join(tmp, 'cc-link.sh')
                os.symlink(target, link)
                d_rc, out = run(['bash', os.path.join(d, 'scripts', 'check-hook-drift.sh')], d,
                                env=dict(git_env(), SECRET_SCAN_INSTALLED=link, PRE_PUSH_INSTALLED=pp))
            else:
                p = os.path.join(tmp, 'hooks', which)
                os.remove(p)
                os.symlink(target, p)
                d_rc, out = _drift(tmp, pp)
            res[which] = (d_rc, 'SYMLINK' in out)
    return all(rc == 1 and m for rc, m in res.values()), 'linked to a HEAD-identical file -> (exit, SYMLINK): %s' % res


def t_r1d_low3_prepush_refuses_symlinked_scanner_exceptions_and_itself():
    res = {}
    for which in ('secret-scan.sh', 'secret-scan-ignore', 'the hook itself'):
        with tempfile.TemporaryDirectory(prefix='guards-l3p-') as tmp:
            _, work = mkrepo(tmp)
            pp = _hookdir(tmp)
            elsewhere = os.path.join(tmp, 'elsewhere')
            os.makedirs(elsewhere)
            if which == 'the hook itself':
                ld = os.path.join(tmp, 'linkhooks')
                os.makedirs(ld)
                for n in ('secret-scan.sh', 'secret-scan-ignore'):
                    shutil.copy(os.path.join(tmp, 'hooks', n), os.path.join(ld, n))
                hook = os.path.join(ld, 'pre-push')
                os.symlink(pp, hook)
                want = 'running through a symlink'
            else:
                src = os.path.join(elsewhere, which)
                shutil.move(os.path.join(tmp, 'hooks', which), src)
                os.symlink(src, os.path.join(tmp, 'hooks', which))
                hook, want = pp, 'is a symlink; the gate runs only regular files'
            base = git(work, 'rev-parse', 'HEAD')
            head = commit(work, 'a.txt', 'ordinary\n', 'clean')
            rc, out = prepush(work, ['refs/heads/main %s refs/heads/main %s' % (head, base)], hook=hook)
            res[which] = (rc, want in out)
    return all(rc not in (0, 127) and m for rc, m in res.values()), 'clean push, linked file -> (exit, refused by ' \
                                                                    'pre-push): %s' % res


# ---- R1d · LOW-4 · a failed mktemp is BLOCKED --------------------------------------------------------------------------
def t_r1d_low4_mktemp_failure_blocks():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-l4-') as tmp:
        _, work = mkrepo(tmp)
        commit(work, 'a.txt', 'ordinary\n', 'clean')
        args = ('HEAD', '--not', '--remotes=origin')
        res['control: clean range passes'] = revs_scan(work, *args)[0] == 0
        rc, out = revs_scan(work, *args, env=dict(git_env(), TMPDIR=os.path.join(tmp, 'no-such-dir')))
        res['TMPDIR does not exist'] = rc == 2 and 'temp directory' in out
        existing = os.path.join(tmp, 'pre-existing-dir')
        os.makedirs(existing)
        for name, body in (('exit 1 after printing an existing dir', 'echo %s\nexit 1\n' % existing),
                           ('exit 0, no such dir', 'echo %s\nexit 0\n' % os.path.join(tmp, 'never-made'))):
            shim = os.path.join(tmp, 'shim-%d' % len(res))
            write(os.path.join(shim, 'mktemp'), '#!/bin/sh\n' + body)
            os.chmod(os.path.join(shim, 'mktemp'), 0o755)
            rc, out = revs_scan(work, *args, env=dict(git_env(), PATH=shim + os.pathsep + os.environ['PATH']))
            res[name] = rc == 2 and 'temp directory' in out
            os.makedirs(existing, exist_ok=True)
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


# ---- R4 · the CONVERGE fixes ruled "fix now" (product secret types; the `++` line; the hook's bypass refusals) -------
def syn_n8n_key():
    return 'N8N_' + 'ENCRYPTION_KEY=' + 'Q1w2E3r4T5y6' * 2


def syn_pg_url():
    return 'postgres' + 'ql://' + 'drill' + ':' + 'Zx9Cv8Bn7Lk' + '@' + 'db.invalid:5432/salon'


def _hook(work, command):
    return run(['bash', SCAN], work, stdin=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}}))


def t_r4_plusplus_line_committed():
    rc, out = _blocked_line('guards-r4a-', '++ %s\n' % syn_anthropic())
    return rc != 0 and syn_anthropic() not in out, 'a committed line whose content starts with ++: exit %d' % rc


def t_r4_plusplus_line_worktree():
    with tempfile.TemporaryDirectory(prefix='guards-r4b-') as tmp:
        _, work = mkrepo(tmp)
        commit(work, 'notes.txt', 'line\n', 'base2')
        git(work, 'push', '-q')
        write(os.path.join(work, 'notes.txt'), 'line\n++%s\n' % syn_anthropic())
        rc, out = manual_scan(work)
    return rc == 2 and 'possible secret' in out, 'a working-tree line starting with ++ (manual mode): exit %d' % rc


def t_r4_plusplus_header_not_content():
    # control: a normal commit's `+++ b/<path>` header is still a header, not scanned as content (no false block)
    rc, out = _blocked_line('guards-r4c-', 'plain text\n', rel='keys/ordinary.txt')
    return rc == 0, 'an ordinary commit (its +++ header must not be read as content): exit %d %s' % (rc, out.strip()[-120:])


def t_r4_n8n_encryption_key():
    res = {}
    for label, line, want_block in (('env assignment', syn_n8n_key(), True),
                                    ('json config key', '{"encryption' + 'Key": "%s"}' % ('Ab12Cd34Ef56' * 2), True),
                                    ('.env.example placeholder', 'N8N_' + 'ENCRYPTION_KEY=REPLACE_ME', False),
                                    ('env reference', 'N8N_' + 'ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}', False)):
        rc, out = _blocked_line('guards-r4d-', line + '\n')
        res[label] = (rc != 0) == want_block and 'Q1w2E3r4T5y6' not in out
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


def t_r4_postgres_url_with_credentials():
    res = {}
    for label, line, want_block in (('postgresql URL with a password', syn_pg_url(), True),
                                    ('postgres URL with a password', syn_pg_url().replace('ql://', '://'), True),
                                    ('URL without credentials', 'postgres' + '://db.invalid:5432/salon', False),
                                    ('password from the environment', 'postgres' + '://drill:${PGPASSWORD}@db.invalid/salon', False)):
        rc, out = _blocked_line('guards-r4e-', 'DATABASE_URL=%s\n' % line)
        res[label] = (rc != 0) == want_block and 'Zx9Cv8Bn7Lk' not in out
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


def t_r4_hook_refuses_bypasses():
    res = {}
    with tempfile.TemporaryDirectory(prefix='guards-r4f-') as tmp:
        _, work = mkrepo(tmp)
        for label, command, want in (('push --no-verify', 'git push --no-verify origin main', 2),
                                     ('push --no-verif (git accepts the abbreviation)', 'git push --no-verif origin main', 2),
                                     ('quoted "--no-verify"', 'git push "--no-verify" origin main', 2),
                                     ('--no-verify then ;', 'git push --no-verify; echo done', 2),
                                     ('-c core.hooksPath', 'git -c core.hooksPath=/dev/null push', 2),
                                     ('quoted -c', "git -c 'core.hooksPath=/x' push", 2),
                                     ('-c with an empty value', 'git -c core.hooksPath= push', 2),
                                     ('-c in another case', 'git -C . -c Core.HooksPATH=/tmp push origin main', 2),
                                     ('--config-env', 'git --config-env=core.hooksPath=HP push', 2),
                                     ('GIT_CONFIG_KEY_0', 'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/x git push', 2),
                                     ('git config sets it, then push', 'git config core.hooksPath /dev/null && git push', 2),
                                     ('plain push (scanned, nothing ahead)', 'git push origin main', 0),
                                     ('commit --no-verify (not a push)', 'git commit --no-verify -m x', 0),
                                     ('commit --no-verify && push (two segments)', 'git commit --no-verify -m x && git push origin main', 0),
                                     ('a commit message naming both', "git commit -m 'push --no-verify and -c core.hooksPath= are refused'", 0),
                                     ('grep -c core.hooksPath (not git)', 'grep -c core.hooksPath notes.txt', 0),
                                     ('git config --get core.hooksPath (a read)', 'git config --get core.hooksPath', 0),
                                     ('a command naming neither', 'git status', 0)):
            rc, out = _hook(work, command)
            res[label] = rc == want and (want == 0 or 'BLOCKED' in out)
    return all(res.values()), ' · '.join('%s=%s' % kv for kv in res.items())


TESTS = [(n[2:], f) for n, f in sorted(globals().items(), key=lambda kv: kv[0]) if n.startswith('t_') and callable(f)]


def main(argv):
    keys = [argv[i + 1] for i, a in enumerate(argv) if a == '-k' and i + 1 < len(argv)]
    verbose = '-v' in argv
    sel = [(n, f) for n, f in TESTS if not keys or any(k in n for k in keys)]
    if not sel:
        print('guards-tur2: no test matches %s' % keys)
        return 2
    bad = 0
    for name, fn in sel:
        try:
            ok, detail = fn()
        except Exception as e:   # a crashed case is a failed case, never a skipped one
            ok, detail = False, 'CRASH %s: %s' % (type(e).__name__, str(e)[:300])
        bad += not ok
        if verbose or not ok:
            print(('  ✓ ' if ok else '  ✗ ') + name + ' — ' + detail)
    print('guards-tur2: %s (%d/%d passed; scripts from %s)' % ('OK' if not bad else 'FAILED', len(sel) - bad, len(sel),
                                                             'this repo' if GROOT == REPO else GROOT))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
