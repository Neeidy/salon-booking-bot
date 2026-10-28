#!/usr/bin/env python3
"""scripts/render-client.py, offline (Phase 8, CRT #14 — client render isolation). No network, no n8n: the render reads
the committed exports and writes into temporary directories outside the repo.

The proofs (docs/PHASE-8-PLAN.md):
  1  render(example) equals the committed five exports: every node byte-equal except the three config literals, whose
     text around the literal is byte-equal and whose literal EVALUATES (node) to the committed literal's value;
     `Build LLM Request` byte-identical (the tenth slot is the identity for the demo's own first service).
  2  render(example-b): the nodes that differ from the committed export are exactly the slot set; the few-shot carries
     B's first service; the chat id and Turnstile secret carry the synthetic secret input, or the placeholder without
     one. And because example-b SHARES many values with the demo (the calendar id, the Purge policy …), a third,
     synthetic config is rendered whose every leaf the literals read DIFFERS from the demo's: each literal must
     evaluate to that config's value at every key, and to none of the demo's (review 2026-10-28, H1).
  3  the A-leak scan: no string distinct to client A appears in render(B) outside the allowlist — one entry per hit,
     node + text + reason, never a pattern; every entry must still hit (a stale entry is red). Positive control: the
     same scan finds every probe in render(A). Negative control: an A literal planted outside the slots turns it red.
  4  behaviour: `Answer FAQ` and `Build LLM Request` run (node) on render(B)'s own Load Config — B's prices, hours,
     services and examples come out, A's do not.
  5  the existing guards run on render(B) and are green (`check-config-schema`, `check-cancel-validation-parity`, the
     deploy tool's Turnstile-literal pattern) — and the parity guard is shown to READ the rendered literal: a timezone
     split between render(B)'s Main and Reminders turns it red.
  6  the drill matrix: no secret input → placeholders · --out inside the repo → refused, nothing written · a missing
     config key → refused by name · secrets file of the wrong mode / an unknown key / a wrong shape → refused, the value
     never printed · a service name that would break the template literal → refused · an anchor count that moved →
     refused · an export set nobody measured → refused · a list element without the committed element's keys, a value
     of another kind, an empty template, NaN, a trailing newline → refused · an existing output path, a link or `..`
     into the repo, a secrets path inside the repo → refused.
Mutants: tests/unit/render-client-mutants.py runs each against a copy of the script (RENDER_CLIENT=<path>); every one
must turn this test red. Not in check-all (it re-runs this test once per mutant).

Run: python3 tests/unit/render-client.test.py
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A_CFG = os.path.join(ROOT, 'config', 'client.config.example.json')
B_CFG = os.path.join(ROOT, 'config', 'client.config.example-b.json')
EXPORTS = os.path.join(ROOT, 'n8n')
LUXON = os.path.join(ROOT, 'scripts', 'node_modules', 'luxon')
LITERAL_NODES = {('main', 'Load Config'), ('reminders', 'Load Config (Reminders)'), ('purge', 'Load Config (Purge)')}
FEWSHOT_NODE = ('main', 'Build LLM Request')
SECRET_NODES = {('main', 'Send Owner Alert (Telegram)'), ('owner-actions', 'Send Owner Alert (Telegram)'),
                ('owner-actions', 'Send Release Failure Alert (Telegram)'), ('purge', 'Send Owner Alert (Purge)'),
                ('reminders', 'Send Owner Alert (Reminders)'), ('main', 'Verify Turnstile')}
# The A-leak allowlist (ruling 2026-10-28): one entry per hit — (workflow, node, the A text) → why it is not a slot.
ALLOW = {
    ('main', 'Build LLM Request', 'Europe/Vienna'):
        'a code comment beside `cfg.business.timezone`; the value itself is read from the config',
    ('main', 'Resolve Date', 'haircut'):
        'a code comment ("haircut friday", an example sentence); never sent anywhere',
    ('main', 'Build Booked State', "You're booked: {service}, {date} {time}. See you then!"):
        'the fallback after `t.bookingConfirmed ||`; unreachable: the render refuses the key missing or empty',
    ('main', 'Build Mirror-Failed State', "You're booked: {service}, {date} {time}. See you then!"):
        'the fallback after `t.bookingConfirmed ||`; unreachable: the render refuses the key missing or empty',
    ('main', 'Build Dry-Run Booked State', "You're booked: {service}, {date} {time}. See you then!"):
        'the fallback after `t.bookingConfirmed ||`; unreachable: the render refuses the key missing or empty',
    ('main', 'Build Cancelled State', 'Done — your {service} on {when} is cancelled.'):
        'the fallback after `cfg.messageTemplates.cancelDone ||`; unreachable: the render refuses the key missing or empty',
}
JS = r"""
const fs = require('fs');
const { DateTime } = require(process.argv[3]);
const p = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const stub = (refs) => (name) => {
  if (!(name in refs)) throw new Error('Referenced node is unexecuted: ' + name);
  return { first: () => ({ json: refs[name] }), all: () => [{ json: refs[name] }] };
};
let out;
if (p.mode === 'literal') out = new Function('$json', p.code)({})[0].json.config;
if (p.mode === 'faq') out = new Function('$', '$json', p.code)(stub({ 'Load Config': { config: p.config } }), { slots: p.slots })[0].json.computed_reply;
if (p.mode === 'llm') out = new Function('$', '$json', '$now', p.code)(stub({ 'Load Config': { config: p.config } }), p.item, DateTime.now())[0].json.request;
process.stdout.write(JSON.stringify(out));
"""


def load_script():
    path = os.environ.get('RENDER_CLIENT', os.path.join(ROOT, 'scripts', 'render-client.py'))
    spec = importlib.util.spec_from_file_location('render_client_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = ROOT
    return mod


def run(mod, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = mod.main(['render-client.py', *argv])
    return rc, out.getvalue()


def node_eval(payload):
    fd, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(payload, f)
    try:
        r = subprocess.run(['node', '-', path, LUXON], input=JS, capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    return json.loads(r.stdout)


def nodes_of(wf):
    return {n['name']: n for n in wf['nodes']}


def code_of(wf, name):
    return nodes_of(wf)[name]['parameters']['jsCode']


def leaves(o, p=''):
    if isinstance(o, dict):
        for k, v in o.items():
            if not k.startswith('$comment'):
                yield from leaves(v, f'{p}.{k}' if p else k)
    else:
        yield p, o


def committed():
    return {k: json.load(open(os.path.join(EXPORTS, f'workflow.{k}.sanitized.json'), encoding='utf-8'))
            for k in ('drill-state', 'main', 'owner-actions', 'purge', 'reminders')}


def rendered(out):
    return {f[len('workflow.'):-len('.json')]: json.load(open(os.path.join(out, f), encoding='utf-8'))
            for f in os.listdir(out)}


def diff_nodes(a, b):
    """{(key, node)} whose node object differs between two renders, plus any top-level difference."""
    d = set()
    for k in a:
        if {x: y for x, y in a[k].items() if x != 'nodes'} != {x: y for x, y in b[k].items() if x != 'nodes'}:
            d.add((k, '<workflow fields>'))
        na, nb = nodes_of(a[k]), nodes_of(b[k])
        d |= {(k, n) for n in set(na) | set(nb) if na.get(n) != nb.get(n)}
    return d


def all_leaves(o, p=''):
    """Like leaves(), but into lists too (services[0].id …): the probes need every string, not every key."""
    if isinstance(o, list):
        for i, v in enumerate(o):
            yield from all_leaves(v, f'{p}[{i}]')
    elif isinstance(o, dict):
        for k, v in o.items():
            if not k.startswith('$comment'):
                yield from all_leaves(v, f'{p}.{k}' if p else k)
    else:
        yield p, o


def a_probes():
    """Every string of client A (5+ characters) that B's config does not hold anywhere. `site.*` is left out: it is the
    site's page copy, and no workflow literal carries it (asserted in main())."""
    A, B = json.load(open(A_CFG, encoding='utf-8')), json.load(open(B_CFG, encoding='utf-8'))
    bvals, btext = dict(all_leaves(B)), json.dumps(B, ensure_ascii=False)
    return sorted({v for p, v in all_leaves(A) if isinstance(v, str) and len(v) >= 5 and not p.startswith('site.')
                   and bvals.get(p) != v and v not in btext})


def scan(wfs, probes):
    hits = set()
    for k, wf in wfs.items():
        for n in wf['nodes']:
            text = json.dumps(n.get('parameters'), ensure_ascii=False)
            for v in probes:
                if json.dumps(v, ensure_ascii=False)[1:-1] in text:
                    hits.add((k, n['name'], v))
    return hits


def copy_exports(dst):
    """Only the five committed exports — never `n8n/.snapshots/` (gitignored live snapshots) or anything else."""
    os.makedirs(dst)
    for f in os.listdir(EXPORTS):
        if f.startswith('workflow.') and f.endswith('.sanitized.json'):
            shutil.copy(os.path.join(EXPORTS, f), dst)
    return dst


def perturb(v, path=''):
    """A value of the same kind that differs from `v`: the synthetic client whose every leaf differs from the demo."""
    if isinstance(v, dict):
        return {k: (x if k.startswith('$comment') else perturb(x, f'{path}.{k}' if path else k)) for k, x in v.items()}
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return [perturb(x, path) for x in v]
        return [perturb(x, path) for x in v] if v else ['05:05-06:06']
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 1
    if isinstance(v, str):
        if path.endswith('services.name'):
            return v + ' C'
        return v + '_c'
    return v


def main():
    mod = load_script()
    ok = True
    tmp = tempfile.mkdtemp(prefix='render-client-test-')

    def case(label, good, detail=''):
        nonlocal ok
        ok = ok and bool(good)
        print(f"{'✓' if good else '✗'} {label}" + ('' if good or not detail else f'\n    {str(detail)[:400]}'))

    def render_to(name, cfg=A_CFG, extra=()):
        out = os.path.join(tmp, name)
        rc, txt = run(mod, ['--config', cfg, '--out', out, *extra])
        return rc, txt, out

    def secrets_file(name, data, mode=0o600):
        path = os.path.join(tmp, name)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
        os.chmod(path, mode)
        return path

    try:
        C = committed()
        # ── 0. the literal reader against the truth (node evaluates the committed literal) ─────────────────────
        for k, name in sorted(LITERAL_NODES):
            code = code_of(C[k], name)
            _, lit, _ = mod.split_literal(code, name)
            case(f'reader: {name} read without executing equals node\'s evaluation of it',
                 mod.js_literal(lit) == node_eval({'mode': 'literal', 'code': code}))

        # ── 1. render(example) equals the committed exports ──────────────────────────────────────────────────
        rc, txt, outA = render_to('A')
        RA = rendered(outA)
        case('render(example): exit 0, five workflows', rc == 0 and sorted(RA) == sorted(C), txt[-300:])
        d = diff_nodes(C, RA)
        case(f'render(example): only the three literal nodes differ in text ({sorted(d)})', d <= LITERAL_NODES)
        for k, name in sorted(LITERAL_NODES):
            cc, rc_ = code_of(C[k], name), code_of(RA[k], name)
            cb, _, ca = mod.split_literal(cc, name)
            rb, _, ra = mod.split_literal(rc_, name)
            case(f'render(example): {name} — the code around the literal byte-equal, the literal evaluates equal',
                 cb == rb and ca == ra and node_eval({'mode': 'literal', 'code': cc}) == node_eval({'mode': 'literal', 'code': rc_}))
        case('render(example): Build LLM Request byte-identical (the tenth slot is the identity for the demo)',
             code_of(C['main'], 'Build LLM Request') == code_of(RA['main'], 'Build LLM Request'))

        # ── 2. render(example-b): the difference set is the slot set, and every slot holds B's value ─────────────
        rc, txt, outB = render_to('B', B_CFG)
        RB = rendered(outB)
        case('render(example-b): exit 0', rc == 0, txt[-300:])
        d = diff_nodes(C, RB)
        case('render(example-b), no secret input: the differing nodes are exactly the literals + the few-shot',
             d == LITERAL_NODES | {FEWSHOT_NODE}, sorted(d))
        Bcfg = json.load(open(B_CFG, encoding='utf-8'))
        bflat = dict(leaves(Bcfg))
        for k, name in sorted(LITERAL_NODES):
            want = dict(leaves(node_eval({'mode': 'literal', 'code': code_of(C[k], name)})))
            got = dict(leaves(node_eval({'mode': 'literal', 'code': code_of(RB[k], name)})))
            case(f'render(example-b): {name} evaluates to B\'s value at every committed key ({len(want)} keys)',
                 set(got) == set(want) and all(got[p] == bflat[p] for p in want),
                 [p for p in want if got.get(p) != bflat.get(p)][:5])
        first = Bcfg['services'][0]
        fs = code_of(RB['main'], 'Build LLM Request')
        case(f"render(example-b): the few-shot carries B's first service ({first['id']}) at all four anchors",
             fs.count(f'"serviceId":"{first["id"]}"') == 2 and fs.count(f"a {first['name'].lower()}") >= 2 and 'haircut' not in fs)
        chat, ts = str(secrets.randbelow(10 ** 9) + 10 ** 9), '0xTEST' + secrets.token_hex(12)
        sf = secrets_file('s-ok.json', {'telegramChatId': chat, 'turnstileSecret': ts})
        rc, txt, outBS = render_to('BS', B_CFG, ['--secrets', sf])
        Acfg0 = json.load(open(A_CFG, encoding='utf-8'))
        C_CFG = os.path.join(tmp, 'c-synthetic.json')
        json.dump(perturb(Acfg0), open(C_CFG, 'w', encoding='utf-8'))
        Cflat = dict(leaves(json.load(open(C_CFG, encoding='utf-8'))))
        rc_c, txt_c, outC = render_to('C', C_CFG)
        RC = rendered(outC)
        case('render(synthetic C, every leaf differs from the demo): exit 0', rc_c == 0, txt_c[-300:])
        for k, name in sorted(LITERAL_NODES):
            demo = dict(leaves(node_eval({'mode': 'literal', 'code': code_of(C[k], name)})))
            got = dict(leaves(node_eval({'mode': 'literal', 'code': code_of(RC[k], name)})))
            same = [p for p in demo if got.get(p) == demo[p]]
            wrong = [p for p in demo if got.get(p) != Cflat.get(p)]
            case(f"render(C): {name} — all {len(demo)} keys carry C's value and none the demo's", not same and not wrong
                 and set(got) == set(demo), f'demo value kept at {same[:5]} · not C at {wrong[:5]}')
        RBS = rendered(outBS)
        d = diff_nodes(C, RBS)
        case('render(example-b) with the secret input: the difference set adds exactly the 5 chat ids + the Turnstile secret',
             rc == 0 and d == LITERAL_NODES | {FEWSHOT_NODE} | SECRET_NODES, sorted(d))
        tg = [n['parameters']['chatId'] for wf in RBS.values() for n in wf['nodes'] if n['type'] == 'n8n-nodes-base.telegram']
        vt = nodes_of(RBS['main'])['Verify Turnstile']['parameters']['bodyParameters']['parameters']
        case('the secret input lands in all five chatId fields and the Turnstile secret, and is never printed',
             tg == [chat] * 5 and [p['value'] for p in vt if p['name'] == 'secret'] == [ts] and chat not in txt and ts not in txt)
        case('the output directory is 0700 and every file 0600',
             oct(os.stat(outBS).st_mode & 0o777) == '0o700'
             and all(oct(os.stat(os.path.join(outBS, f)).st_mode & 0o777) == '0o600' for f in os.listdir(outBS)))

        # ── 3. the A-leak scan, with its controls ─────────────────────────────────────────────────────────────
        probes = a_probes()
        case("no workflow literal carries the site's page copy (why the probes leave `site.*` out)",
             not any('site' in node_eval({'mode': 'literal', 'code': code_of(C[k], name)}) for k, name in LITERAL_NODES))
        in_a = scan(RA, probes)
        case(f'A-leak positive control: every one of the {len(probes)} A probes is found in render(A)',
             probes and {v for _, _, v in in_a} == set(probes), sorted(set(probes) - {v for _, _, v in in_a}))
        hits = scan(RB, probes)
        case('A-leak scan on render(example-b): every hit is on the allowlist', hits <= set(ALLOW), sorted(hits - set(ALLOW)))
        case('A-leak allowlist: every entry still hits (none stale)', set(ALLOW) <= hits, sorted(set(ALLOW) - hits))
        planted = os.path.join(tmp, 'exports-planted')
        copy_exports(planted)
        pm = json.load(open(os.path.join(planted, 'workflow.main.sanitized.json'), encoding='utf-8'))
        nodes_of(pm)['Answer FAQ']['parameters']['jsCode'] += '\n// planted: Demo Barber Co.'
        json.dump(pm, open(os.path.join(planted, 'workflow.main.sanitized.json'), 'w', encoding='utf-8'))
        rc, txt, outP = render_to('P', B_CFG, ['--exports', planted])
        extra = scan(rendered(outP), probes) - set(ALLOW)
        case('A-leak negative control: an A literal planted outside the slots is caught',
             rc == 0 and ('main', 'Answer FAQ', 'Demo Barber Co.') in extra, sorted(extra))

        # ── 4. behaviour on render(B)'s own Load Config ───────────────────────────────────────────────────────
        cfgB = node_eval({'mode': 'literal', 'code': code_of(RB['main'], 'Load Config')})
        Acfg = json.load(open(A_CFG, encoding='utf-8'))
        a_names = [s['name'] for s in Acfg['services'] if s['name'] not in json.dumps(Bcfg)]
        price = node_eval({'mode': 'faq', 'code': code_of(RB['main'], 'Answer FAQ'), 'config': cfgB, 'slots': {'faqTopic': 'price'}})
        case("Answer FAQ (price) on render(B): every B service and price, no A service",
             all(f"{s['name']} €{s['priceEUR']}" in price for s in Bcfg['services']) and not any(n in price for n in a_names), price)
        hours = node_eval({'mode': 'faq', 'code': code_of(RB['main'], 'Answer FAQ'), 'config': cfgB, 'slots': {'faqTopic': 'hours'}})
        case("Answer FAQ (hours) on render(B): B's days", all(
            (f"{d.capitalize()}: {', '.join(h)}" if h else f"{d.capitalize()}: closed") in hours
            for d, h in Bcfg['workingHours'].items()), hours)
        req = json.dumps(node_eval({'mode': 'llm', 'code': code_of(RB['main'], 'Build LLM Request'), 'config': cfgB,
                                    'item': {'channel': 'widget', 'text': 'hi', 'state': {}}}), ensure_ascii=False)
        case("Build LLM Request on render(B): B's name and every B service id in the prompt; no A name, no 'haircut'",
             Bcfg['business']['name'] in req and all(s['id'] in req for s in Bcfg['services'])
             and Acfg['business']['name'] not in req and 'haircut' not in req)

        # ── 5. the existing guards on render(B), and one shown to read the rendered literal ─────────────────
        env = dict(os.environ, CONFIG_EXAMPLE=B_CFG, SANITIZED_PATH=os.path.join(outB, 'workflow.main.json'))
        r = subprocess.run(['node', os.path.join(ROOT, 'scripts', 'check-config-schema.cjs')], env=env, cwd=ROOT,
                           capture_output=True, text=True)
        case('check-config-schema on render(B) (example-b + its rendered Main Load Config): green', r.returncode == 0, r.stdout[-300:])
        par = lambda d: subprocess.run(
            [sys.executable, os.path.join(ROOT, 'scripts', 'check-cancel-validation-parity.py'), os.path.join(d, 'workflow.main.json')],
            env=dict(os.environ, REMINDERS_SANITIZED=os.path.join(d, 'workflow.reminders.json'),
                     PURGE_SANITIZED=os.path.join(d, 'workflow.purge.json')), cwd=ROOT, capture_output=True, text=True)
        r = par(outB)
        case('check-cancel-validation-parity on render(B): green', r.returncode == 0, r.stdout[-300:])
        split = os.path.join(tmp, 'B-split')
        shutil.copytree(outB, split)
        rp = os.path.join(split, 'workflow.reminders.json')
        rw = json.load(open(rp, encoding='utf-8'))
        n = nodes_of(rw)['Load Config (Reminders)']
        n['parameters']['jsCode'] = n['parameters']['jsCode'].replace(Bcfg['business']['timezone'], 'Pacific/Auckland', 1)
        json.dump(rw, open(rp, 'w', encoding='utf-8'))
        r = par(split)
        case('…and it READS the rendered literal: a timezone split between render(B)\'s Main and Reminders turns it red',
             r.returncode != 0 and 'SHARED-KEY DRIFT' in r.stdout, r.stdout[-300:])
        spec = importlib.util.spec_from_file_location('deploy_helper', os.path.join(ROOT, 'scripts', 'deploy-workflow-copy.py'))
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        case("the deploy tool's Turnstile-literal pattern finds exactly one literal in render(B)'s Load Config",
             len(helper.TS_LITERAL.findall(code_of(RB['main'], 'Load Config'))) == 1)

        # ── 6. the drill matrix ──────────────────────────────────────────────────────────────────────────────
        ph = [n['parameters']['chatId'] for wf in RB.values() for n in wf['nodes'] if n['type'] == 'n8n-nodes-base.telegram']
        case('no secret input: every chatId and the Turnstile secret stay the committed placeholder',
             ph == ['REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'] * 5 and 'REPLACE_WITH_TURNSTILE_SECRET' in json.dumps(RB['main']))
        inside = os.path.join(ROOT, 'n8n', 'render-test-must-not-exist')

        def into_repo(label, out):
            """A case whose --out resolves to `inside`. A broken render writes there: remove exactly what this case
            made (it did not exist before), then fail the case — a mutant must not leave the repo dirty for the next."""
            existed = os.path.lexists(inside)
            rc, txt = run(mod, ['--config', B_CFG, '--out', out])
            wrote = not existed and os.path.lexists(inside)
            if wrote:
                shutil.rmtree(inside)
            # refused by the PRE-check (before any render): the re-check in write() is the race backstop, and a
            # refusal from it alone would hide a pre-check that resolves paths wrongly
            case(label, not existed and rc == 1 and 'the output directory is inside this repository' in txt and not wrote, txt)

        into_repo('--out inside the repository: refused, nothing written', inside)
        rc, txt, _ = render_to('A', B_CFG)
        case('--out an existing directory: refused (only a new one is taken)', rc == 1 and 'exists' in txt, txt)
        os.mkdir(os.path.join(tmp, 'empty'))
        rc, txt, _ = render_to('empty', B_CFG)
        case('--out an existing EMPTY directory: refused too', rc == 1 and 'exists' in txt, txt)
        lk = os.path.join(tmp, 'link-into-repo')
        os.symlink(os.path.join(ROOT, 'n8n'), lk)
        into_repo('--out through a link into the repository: refused, nothing written', os.path.join(lk, 'render-test-must-not-exist'))
        into_repo('--out with `..` that resolves into the repository: refused, nothing written',
                  tmp + '/x/' + '../' * (tmp.count('/') + 1) + inside.lstrip('/'))
        miss = os.path.join(tmp, 'b-missing.json')
        bm = json.load(open(B_CFG, encoding='utf-8'))
        del bm['messageTemplates']['cancelDone']
        json.dump(bm, open(miss, 'w', encoding='utf-8'))
        rc, txt, out = render_to('M', miss)
        case('a config key missing: refused by name, nothing written',
             rc == 1 and 'messageTemplates.cancelDone' in txt and not os.path.exists(out), txt)
        bt = os.path.join(tmp, 'b-type.json')
        bm = json.load(open(B_CFG, encoding='utf-8'))
        bm['bot']['maxTurnsPerConversation'] = '12'
        json.dump(bm, open(bt, 'w', encoding='utf-8'))
        rc, txt, _ = render_to('T', bt)
        case('a config value of another kind: refused by name', rc == 1 and 'bot.maxTurnsPerConversation' in txt, txt)
        for label, mutate in (('a backtick', 'Skin `Fade'), ('a template placeholder', 'Skin ${x}'), ('a double quote', 'Skin "Fade"')):
            bn = os.path.join(tmp, f'b-name-{len(label)}.json')
            bm = json.load(open(B_CFG, encoding='utf-8'))
            bm['services'][0]['name'] = mutate
            json.dump(bm, open(bn, 'w', encoding='utf-8'))
            rc, txt, _ = render_to(f'N{len(label)}', bn)
            case(f'a first service name with {label} (it lands inside a JS template literal): refused', rc == 1 and 'services[0].name' in txt, txt)
        loose = secrets_file('s-loose.json', {'telegramChatId': chat}, mode=0o644)
        rc, txt, _ = render_to('L', B_CFG, ['--secrets', loose])
        case('a secrets file readable by group/other: refused', rc == 1 and '0600' in txt, txt)
        pasted = 'pasted-' + secrets.token_hex(6)
        stray = secrets_file('s-stray.json', {'telegramChatId': chat, pasted: 'x'})
        rc, txt, _ = render_to('S', B_CFG, ['--secrets', stray])
        case('a secrets file with an unknown key: refused, counted — the key is not printed (it may be a pasted secret)',
             rc == 1 and '1 key(s)' in txt and pasted not in txt, txt)
        nl = secrets_file('s-nl.json', {'telegramChatId': '12345\n'})
        rc, txt, _ = render_to('NL', B_CFG, ['--secrets', nl])
        case('a secret with a trailing newline: refused (the shape is matched in full)', rc == 1 and 'telegramChatId' in txt, txt)
        rc, txt = run(mod, ['--config', B_CFG, '--out', os.path.join(tmp, 'SR'), '--secrets', os.path.join(ROOT, 'n8n', 'no-such-secrets.json')])
        case('a secrets path inside the repository: refused before it is opened', rc == 1 and 'inside this repository' in txt, txt)
        for label, mutate, needle in (
                ('a list element without the committed element\'s key', lambda c: c['services'][1].pop('priceEUR'), 'services[1].priceEUR'),
                ('a list element value of another kind', lambda c: c['services'][1].__setitem__('priceEUR', '28'), 'services[1].priceEUR'),
                ('an empty template', lambda c: c['messageTemplates'].__setitem__('bookingConfirmed', ''), 'messageTemplates.bookingConfirmed'),
                ('a first service id with a trailing newline', lambda c: c['services'][0].__setitem__('id', 'skin_fade\n'), 'services[0].id')):
            bc = json.load(open(B_CFG, encoding='utf-8'))
            mutate(bc)
            path = os.path.join(tmp, f'b-{len(label)}-{needle[:8]}.json')
            json.dump(bc, open(path, 'w', encoding='utf-8'))
            rc, txt, out = render_to(f'D{len(label)}{needle[:4]}', path)
            case(f'{label}: refused by name, nothing written', rc == 1 and needle in txt and not os.path.exists(out), txt)
        bs = json.load(open(B_CFG, encoding='utf-8'))
        empty_day = next(d for d, h in json.load(open(A_CFG, encoding='utf-8'))['workingHours'].items() if not h)
        bs['workingHours'][empty_day] = [42]
        path = os.path.join(tmp, 'b-emptyday.json')
        json.dump(bs, open(path, 'w', encoding='utf-8'))
        rc, txt, _ = render_to('ED', path)
        case(f"a value under a day the demo leaves empty ({empty_day}) is checked against a filled day's shape: refused",
             rc == 1 and f'workingHours.{empty_day}[0]' in txt, txt)
        fifo = os.path.join(tmp, 's-fifo')
        os.mkfifo(fifo, 0o600)
        try:
            # in a child process (a blocking open would hang this one), loading the script under test with ROOT pinned
            # to this repo — a mutant copy lives in a temp dir, and its own ROOT would make every temp path "the repo"
            child = ('import importlib.util, sys; s = importlib.util.spec_from_file_location("m", sys.argv[1]); '
                     'm = importlib.util.module_from_spec(s); s.loader.exec_module(m); m.ROOT = sys.argv[2]; '
                     'sys.exit(m.main(["render-client.py"] + sys.argv[3:]))')
            r = subprocess.run([sys.executable, '-c', child, mod.__file__, ROOT, '--config', B_CFG, '--out',
                                os.path.join(tmp, 'FF'), '--secrets', fifo], capture_output=True, text=True, timeout=20)
            ff = (r.returncode, r.stdout)
        except subprocess.TimeoutExpired:
            ff = (None, 'timed out — the open blocked on the FIFO')
        case('a secrets path that is a FIFO: refused at once, never blocks', ff[0] == 1 and 'regular file' in ff[1], ff)
        held = os.path.join(tmp, 'held')
        os.symlink(tmp, held)
        try:
            mod.write(held, {})
            case('write(): a leaf that became a link before mkdir is refused', False)
        except mod.Refused as e:
            case('write(): a leaf that became a link before mkdir is refused', 'created new' in str(e), str(e))
        # the re-check after mkdir, shown with a stand-in repository: the parent is swapped for a link into it AFTER
        # out_dir() passed — the write must refuse, write no file there, and remove the empty directory it made
        fake = os.path.join(tmp, 'fake-repo')
        os.mkdir(fake)
        parent = os.path.join(tmp, 'parent')
        os.mkdir(parent)
        target = os.path.join(parent, 'out')
        saved_root = mod.ROOT
        mod.ROOT = fake
        try:
            mod.out_dir(target)
            os.rename(parent, parent + '-moved')
            os.symlink(fake, parent)
            try:
                mod.write(target, {'main': {'nodes': []}})
                refused = ''
            except mod.Refused as e:
                refused = str(e)
        finally:
            mod.ROOT = saved_root
        case('write(): a parent swapped for a link into the repository after the check is refused, nothing left there',
             'moved or landed inside' in refused and os.listdir(fake) == [], refused or 'not refused')
        nan = os.path.join(tmp, 'b-nan.json')
        open(nan, 'w').write(open(B_CFG, encoding='utf-8').read().replace('"llmCostCapUsd": 10.0', '"llmCostCapUsd": NaN', 1))
        rc, txt, _ = render_to('NAN', nan)
        case('a config holding NaN: refused', rc == 1 and 'NaN' in txt, txt)
        bad = 'not-a-chat-id-' + secrets.token_hex(4)
        shape = secrets_file('s-shape.json', {'telegramChatId': bad})
        rc, txt, _ = render_to('W', B_CFG, ['--secrets', shape])
        case('a secret of the wrong shape: refused, and the value is not printed', rc == 1 and 'telegramChatId' in txt and bad not in txt, txt)
        link = os.path.join(tmp, 's-link.json')
        os.symlink(sf, link)
        rc, txt, _ = render_to('K', B_CFG, ['--secrets', link])
        case('a secrets path that is a symlink: refused (opened without following it)', rc == 1 and 'link is not followed' in txt, txt)
        moved = os.path.join(tmp, 'exports-moved')
        copy_exports(moved)
        mm = json.load(open(os.path.join(moved, 'workflow.main.sanitized.json'), encoding='utf-8'))
        nodes_of(mm)['Build LLM Request']['parameters']['jsCode'] += '\n// "serviceId":"haircut"'
        json.dump(mm, open(os.path.join(moved, 'workflow.main.sanitized.json'), 'w', encoding='utf-8'))
        rc, txt, out = render_to('MV', B_CFG, ['--exports', moved])
        case('a few-shot anchor count that moved (3 instead of 2): refused, nothing written',
             rc == 1 and 'occurs 3' in txt and not os.path.exists(out), txt)
        extra_wf = os.path.join(tmp, 'exports-extra')
        copy_exports(extra_wf)
        shutil.copy(os.path.join(extra_wf, 'workflow.purge.sanitized.json'), os.path.join(extra_wf, 'workflow.new.sanitized.json'))
        rc, txt, _ = render_to('X', B_CFG, ['--exports', extra_wf])
        case('an export set with a workflow nobody measured: refused', rc == 1 and 'nobody measured' in txt, txt)
        mt = os.path.join(tmp, 'exports-tg')
        copy_exports(mt)
        pw = json.load(open(os.path.join(mt, 'workflow.purge.sanitized.json'), encoding='utf-8'))
        next(n for n in pw['nodes'] if n['type'] == 'n8n-nodes-base.telegram')['parameters']['chatId'] = '12345'
        json.dump(pw, open(os.path.join(mt, 'workflow.purge.sanitized.json'), 'w', encoding='utf-8'))
        rc, txt, _ = render_to('TG', B_CFG, ['--exports', mt])
        case('an export whose chatId is not the placeholder (a live value): refused', rc == 1 and 'purge' in txt and '12345' not in txt, txt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('render-client:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
