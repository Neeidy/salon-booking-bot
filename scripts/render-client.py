#!/usr/bin/env python3
"""render-client.py — Phase 8: one client's five workflows, produced from its config and its secret inputs alone.

Why (docs/PHASE-8-PLAN.md): the committed exports are the demo client's workflows, and four kinds of per-client value
sit inside their nodes. A new client used to mean editing those nodes by hand; this fills them from the client's files
instead, so the code every client runs stays the committed code. It is the n8n counterpart of the site's
`web/site/scripts/build-config.mjs`. Offline: it reads files and writes files, and calls nothing.

THE SLOTS — the only places a rendered workflow differs from the committed export (measured 2026-10-28):
  1–3  the three inline config literals — Main `Load Config`, `Load Config (Reminders)`, `Load Config (Purge)` —
       rewritten as JSON from the client's config, projected onto the committed literal's OWN key tree: the committed
       literal is the key list, so a config that lacks one of its keys is refused by name, and a value of another type
       is refused; a list element is projected onto the committed first element's keys. Keys the literal does not hold
       are not carried, except the ones a workflow reads with a code fallback (OPTIONAL: Main's `cancelRetry`,
       `dryRunNoChange`), which go in when the config gives them as non-empty text (given empty or null: refused);
       every number must be finite and inside the JS safe-integer range;
  4–8  the owner's Telegram chat id: `chatId` of the five Telegram nodes (Main 1, Owner Actions 2, Purge 1, Reminders 1);
  9    the Turnstile secret: Main `Verify Turnstile`'s `secret` body parameter;
  10   `Build LLM Request`'s few-shot examples: `"serviceId":"haircut"` ×2 and "a haircut" ×2, rendered from the client's
       FIRST service (ruling 2026-10-28), at fixed anchors with an expected count.
  Slots 4–9 come from the --secrets file (0600, owned by this user; keys `telegramChatId`, `turnstileSecret`). A key the
  file does not give, or no file, leaves the committed `REPLACE_WITH_…` placeholder. Every slot count is checked: an
  export whose count differs from the measured one is refused — the template moved, so re-measure; do not guess.
A RECORDED BOUND (owner's ruling 2026-10-28, Codex CRT #14 M1): the prompt carries a fixed example that hair colouring
  is not offered; a client offering it gets a contradicting prompt until a Main edit. Quality only: `Merge Slots` and
  `Slot Gate` refuse a service id the config does not hold. The example is not rewritten, only watched (its two phrases
  once each, and its `(not in services)` marker once, so a second such example is refused — one written without that
  marker is not seen).
BOUNDS of the refusals above, recorded (R2b review, the owner's convergence ruling): a list nested about a thousand deep
  ends in a Python recursion traceback, not a named refusal (nothing is written: it fails before the render); an
  integer of more than 4300 digits (Python's own parsing limit) is refused, but as "cannot be read as JSON", not by
  name; a template given only spaces is taken as text, so the customer gets a blank reply (the node's fallback does not
  answer it).
NOT slots: the credential references (per-instance links: they stay placeholders and are linked in the new instance),
  and the comments and `messageTemplates` fallback strings that hold demo text (tests/unit/render-client.test.py keeps
  them on the A-leak scan's allowlist, one entry per hit).

Output: a directory that does NOT exist yet, OUTSIDE this repository (refused inside it, through a link or `..` alike —
the output can carry secrets). It is created 0700 and re-checked after creation; each file, `workflow.<key>.json`, is
created 0600 without following links. Everything is rendered in memory first, so a refusal before writing writes
nothing; a write that fails part-way says so (its files are 0600 in the new 0700 directory). Prints node names and
counts, never a value. "This repository" is found from the script's REAL path, so a symlink to it is fine; a COPY of
the script elsewhere, or a hard link to it from elsewhere, guards the directory it sits in instead (a bound: run it
from the repository).

Usage: python3 scripts/render-client.py --config FILE --out DIR [--secrets FILE] [--exports DIR]
Exit: 0 rendered · 1 refused (the message says whether anything was written) · 2 usage.
"""
import argparse
import copy
import json
import math
import os
import re
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))   # realpath: a link to the script must not move the repo
KEYS = ('drill-state', 'main', 'owner-actions', 'purge', 'reminders')
LITERALS = {'main': 'Load Config', 'reminders': 'Load Config (Reminders)', 'purge': 'Load Config (Purge)'}
HEAD = 'const config = '
TAIL = ';\nreturn [{ json: { ...$json, config } }];'
TELEGRAM = 'n8n-nodes-base.telegram'
CHAT_COUNT = {'drill-state': 0, 'main': 1, 'owner-actions': 2, 'purge': 1, 'reminders': 1}
CHAT_PLACEHOLDER = 'REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID'
TURNSTILE_NODE = 'Verify Turnstile'
TURNSTILE_PLACEHOLDER = 'REPLACE_WITH_TURNSTILE_SECRET'
FEWSHOT_NODE = 'Build LLM Request'
SERVICE_ID = re.compile(r'^[a-z0-9_]+$')                            # = the service id pattern in the config schema
SERVICE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &+'.,()/-]{0,59}$")  # lands inside a JS template literal: no ` $ \ "
SECRET_SHAPES = {'telegramChatId': re.compile(r'^-?[0-9]{1,20}$'),
                 'turnstileSecret': re.compile(r'^[A-Za-z0-9._-]{16,256}$')}


class Refused(Exception):
    def __init__(self, msg, wrote=False):
        super().__init__(msg)
        self.wrote = wrote          # True when something may already be on disk (a directory or part of the output)


def _article(name):
    return 'an' if name[:1].lower() in 'aeio' else 'a'      # approximate: few-shot grammar only, never a value


FEWSHOT = (     # (anchor in the committed export, expected count, its rendering from the client's first service)
    ('"serviceId":"haircut"', 2, lambda s: f'"serviceId":"{s["id"]}"'),
    ("I'd like a haircut on", 1, lambda s: f"I'd like {_article(s['name'])} {s['name'].lower()} on"),
    ('How much is a haircut?', 1, lambda s: f"How much is {_article(s['name'])} {s['name'].lower()}?"),
)
KEY_RE = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*(?=\s*:)')
# The prompt's fixed "not offered" example (Codex CRT #14, M1; a recorded bound): not rewritten, only watched, so a
# moved or added example stops the render instead of passing unseen.
NOT_OFFERED = ("Do you do hair coloring? I'm interested", 'asked about hair coloring (not in services)')
NOT_OFFERED_MARK = '(not in services)'
JS_SAFE = 2 ** 53 - 1                   # beyond it a JS number no longer holds the integer exactly
# Keys a workflow READS that its committed literal does not hold, each read with a code fallback (Codex CRT #14, M2):
# carried into the literal when the config gives them (non-empty text); absent, the node's own fallback text answers.
OPTIONAL = {'main': {'messageTemplates': ('cancelRetry', 'dryRunNoChange')}}


# ── the config literal (pure) ────────────────────────────────────────────────────────────────────────────────
def js_literal(src):
    """The committed literal's object, read WITHOUT executing it: line comments dropped, bare keys quoted, the rest
    parsed as JSON. Anything outside that shape (another quote style, a block comment, a trailing comma) is refused."""
    out, last, i = [], '', 0
    while i < len(src):
        c = src[i]
        if c == '"':
            j = i + 1
            while j < len(src) and src[j] != '"':
                j += 2 if src[j] == '\\' else 1
            out.append(src[i:j + 1])
            last, i = '"', j + 1
        elif src.startswith('//', i):
            nl = src.find('\n', i)
            i = len(src) if nl < 0 else nl
        elif c in "'`" or src.startswith('/*', i):
            raise Refused('a config literal holds a form this reader does not take (a quote other than ", or /*)')
        else:
            m = KEY_RE.match(src, i) if last in ('{', ',') else None
            if m:
                out.append(json.dumps(m.group()))
                last, i = '"', m.end()
            else:
                out.append(c)
                if not c.isspace():
                    last = c
                i += 1
    try:
        return json.loads(''.join(out))
    except ValueError:
        raise Refused('a config literal is not an object this reader can take')


def _kind(v):
    if isinstance(v, bool):
        return 'a boolean'
    if isinstance(v, (int, float)):
        return 'a number'
    return {str: 'a string', list: 'a list', dict: 'an object', type(None): 'null'}[type(v)]


def _take(want, got, p):
    """`got`, checked against `want` and returned as it goes into the literal: same kind; a string the demo fills may
    not be empty (an empty template would fall through to the code's fallback text); each list element shaped like the
    committed list's first element — an object element PROJECTED onto its keys, so a field the workflows never read is
    not carried in (Codex CRT #14, L5)."""
    if _kind(got) != _kind(want):
        raise Refused(f'{p} must be {_kind(want)}, not {_kind(got)}')
    if isinstance(want, str) and want and not got:
        raise Refused(f'{p} must not be empty')
    if isinstance(want, list) and want:
        out = []
        for i, el in enumerate(got):
            if isinstance(want[0], dict):
                if not isinstance(el, dict):
                    raise Refused(f'{p}[{i}] must be an object')
                out.append(project(want[0], el, f'{p}[{i}]'))
            else:
                out.append(_take(want[0], el, f'{p}[{i}]'))
        return out
    return got


def project(shape, cfg, path=''):
    """cfg cut to `shape`'s key tree, in shape's key order; a missing key or a value of another kind is refused, and
    so is a list element without the committed first element's keys."""
    out = {}
    for k, want in shape.items():
        p = f'{path}.{k}' if path else k
        if not isinstance(cfg, dict) or k not in cfg:
            raise Refused(f'the config lacks {p}')
        got = cfg[k]
        if isinstance(want, dict):
            if not isinstance(got, dict):
                raise Refused(f'{p} must be an object')
            out[k] = project(want, got, p)
        else:
            if isinstance(want, list) and not want:     # an empty demo list (a closed day): take a filled sibling's shape
                want = next((v for v in shape.values() if isinstance(v, list) and v), want)
            out[k] = _take(want, got, p)
    return out


def split_literal(code, where):
    if code.count(HEAD) != 1 or not code.endswith(TAIL):
        raise Refused(f"{where}: the literal is not where it was measured ('{HEAD}…' once, ending in the return line)")
    start = code.index(HEAD) + len(HEAD)
    return code[:start], code[start:len(code) - len(TAIL)], TAIL


BARE = re.compile(r'^[A-Za-z_$][A-Za-z0-9_$]*$')


def _scalar(v):
    return json.dumps(v, ensure_ascii=False).replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def js_object(v, pad=''):
    """`v` written in the committed literal's own style — bare keys, small objects and lists on one line — because
    the repo's tools read that style: the deploy tool's `turnstile: { enabled: … }` pattern and the parity script's
    `timezone: "…"` / `ownerAlert: { … }` patterns do not match JSON's quoted keys (they would find nothing, and a
    parity check that finds nothing on both sides passes)."""
    if isinstance(v, dict):
        items = [f"{k if BARE.fullmatch(k) else _scalar(k)}: {js_object(x, pad + '  ')}" for k, x in v.items()]
        one = '{ ' + ', '.join(items) + ' }' if items else '{}'
        if len(pad) + len(one) <= 110 and '\n' not in one:
            return one
        return '{\n' + ',\n'.join(pad + '  ' + it for it in items) + '\n' + pad + '}'
    if isinstance(v, list):
        items = [js_object(x, pad + '  ') for x in v]
        one = '[' + ', '.join(items) + ']'
        if len(pad) + len(one) <= 110 and '\n' not in one:
            return one
        return '[\n' + ',\n'.join(pad + '  ' + it for it in items) + '\n' + pad + ']'
    return _scalar(v)


def render_literal(code, cfg, where, optional=None):
    before, literal, after = split_literal(code, where)
    body = project(js_literal(literal), cfg, '')
    for section, keys in (optional or {}).items():
        for k in keys:
            if k not in cfg[section]:            # `project` above already refused the section missing or not an object
                continue
            v = cfg[section][k]
            if not isinstance(v, str) or not v:  # null too: given means text, absent means the node's fallback
                raise Refused(f'{section}.{k} must be non-empty text when given')
            body[section][k] = v
    return before + js_object(body) + after, len(body)


# ── the inputs (pure apart from reading them) ────────────────────────────────────────────────────────────────
def _no_constant(name):
    raise ValueError(name)                       # NaN / Infinity: not JSON, and NaN compares false with everything


def _numbers(o, p=''):
    """Every number must survive the trip into a JS literal (Codex CRT #14, M4): a float that overflows (1e999) parses
    to infinity without any NaN/Infinity token, and an integer past the safe range (10**400 is one) is written out in
    full and read by JS as a different number or as Infinity."""
    if isinstance(o, dict):
        for k, v in o.items():
            _numbers(v, f'{p}.{k}' if p else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _numbers(v, f'{p}[{i}]')
    elif isinstance(o, float) and not math.isfinite(o):
        raise Refused(f'{p} is not a finite number')
    elif isinstance(o, int) and not isinstance(o, bool) and abs(o) > JS_SAFE:
        raise Refused(f'{p} is outside the JS safe-integer range (±{JS_SAFE})')


def load_config(path):
    try:
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f, parse_constant=_no_constant)
    except (OSError, ValueError):
        raise Refused('the config file cannot be read as JSON (NaN and Infinity are refused)')
    if not isinstance(cfg, dict):
        raise Refused('the config is not a JSON object')
    _numbers(cfg)
    svc = cfg.get('services')
    if not isinstance(svc, list):
        raise Refused(f'services must be a list, not {_kind(svc)}' if 'services' in cfg else 'the config lacks services')
    first = svc[0] if svc and isinstance(svc[0], dict) else None
    if not first:
        raise Refused('the config lacks services[0] (the few-shot examples are rendered from it)')
    if not isinstance(first.get('id'), str) or not SERVICE_ID.fullmatch(first['id']):
        raise Refused(f'services[0].id must match {SERVICE_ID.pattern}')
    if not isinstance(first.get('name'), str) or not SERVICE_NAME.fullmatch(first['name']):
        raise Refused('services[0].name must be plain text (letters, digits, spaces and & + \' . , ( ) / -; at most 60)')
    return cfg


def _inside_repo(real):
    root = os.path.realpath(ROOT)
    return real == root or real.startswith(root + os.sep)


def load_secrets(path):
    if path is None:
        return {}
    if _inside_repo(os.path.realpath(path)):
        raise Refused('the secrets file is inside this repository; keep it outside')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)  # a link is refused here; a FIFO cannot block
    except OSError:
        raise Refused('the secrets file cannot be opened (a link is not followed)')
    try:                                         # every check on the open descriptor, before it becomes a file object
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Refused('the secrets file must be a regular file')
        if st.st_mode & 0o077:
            raise Refused('the secrets file must be mode 0600 (no group or other access)')
        if st.st_uid != os.getuid():
            raise Refused('the secrets file must belong to this user')
        if st.st_nlink != 1:
            raise Refused('the secrets file has another hard link (a second name could sit inside the repository)')
    except Refused:
        os.close(fd)
        raise
    with os.fdopen(fd, encoding='utf-8') as f:
        try:
            data = json.load(f, parse_constant=_no_constant)
        except (OSError, ValueError):
            raise Refused('the secrets file is not JSON')              # no detail: the parser could quote it
    if not isinstance(data, dict):
        raise Refused('the secrets file is not a JSON object')
    stray = set(data) - set(SECRET_SHAPES)
    if stray:                                    # counted, not named: a secret pasted as a key must not be printed
        raise Refused(f'the secrets file has {len(stray)} key(s) this tool does not take '
                      f'(it takes {sorted(SECRET_SHAPES)})')
    for k, v in data.items():
        if not isinstance(v, str) or not SECRET_SHAPES[k].fullmatch(v):
            raise Refused(f'{k} in the secrets file has the wrong shape (the value is not shown)')
    return data


def out_dir(out):
    if _inside_repo(os.path.realpath(out)):
        raise Refused('the output directory is inside this repository; the output can carry secrets')
    if os.path.lexists(out):
        raise Refused('the output path exists; give a directory that does not exist yet')
    return out


def load_exports(exports):
    found = sorted(f[len('workflow.'):-len('.sanitized.json')] for f in os.listdir(exports)
                   if f.startswith('workflow.') and f.endswith('.sanitized.json'))
    if tuple(found) != KEYS:
        raise Refused(f'the exports are {found}, not the measured {list(KEYS)}: a workflow nobody measured for slots')
    out = {}
    for k in KEYS:
        with open(os.path.join(exports, f'workflow.{k}.sanitized.json'), encoding='utf-8') as f:
            out[k] = json.load(f)
    return out


# ── the render (pure) ────────────────────────────────────────────────────────────────────────────────────────
def _one(nodes, name, where):
    hits = [n for n in nodes if n.get('name') == name]
    if len(hits) != 1:
        raise Refused(f"{where}: {len(hits)} nodes named '{name}' (exactly one was measured)")
    return hits[0]


def render(exports, cfg, secrets):
    """{key: rendered workflow}, plus a log of what each slot received (names and counts, never a value)."""
    first = cfg['services'][0]
    out, log = {}, []
    for key in KEYS:
        wf = copy.deepcopy(exports[key])
        nodes = wf.get('nodes') or []
        if key in LITERALS:
            n = _one(nodes, LITERALS[key], key)
            n['parameters']['jsCode'], count = render_literal(n['parameters'].get('jsCode', ''), cfg, f"{key} · {LITERALS[key]}",
                                                              OPTIONAL.get(key))
            log.append(f"{key} · {LITERALS[key]}: literal from the config ({count} top-level keys)")
        tg = [n for n in nodes if n.get('type') == TELEGRAM]
        if len(tg) != CHAT_COUNT[key] or any((n.get('parameters') or {}).get('chatId') != CHAT_PLACEHOLDER for n in tg):
            raise Refused(f'{key}: {len(tg)} Telegram nodes, or a chatId that is not the placeholder '
                          f'(measured: {CHAT_COUNT[key]}, each {CHAT_PLACEHOLDER})')
        for n in tg:
            n['parameters']['chatId'] = secrets.get('telegramChatId', CHAT_PLACEHOLDER)
        if tg:
            log.append(f"{key}: chatId ×{len(tg)} — {'from the secrets file' if 'telegramChatId' in secrets else 'placeholder'}")
        if key == 'main':
            n = _one(nodes, TURNSTILE_NODE, key)
            ps = [p for p in ((n['parameters'].get('bodyParameters') or {}).get('parameters') or []) if p.get('name') == 'secret']
            if len(ps) != 1 or ps[0].get('value') != TURNSTILE_PLACEHOLDER:
                raise Refused(f"main · {TURNSTILE_NODE}: the secret body parameter is not the one measured placeholder")
            ps[0]['value'] = secrets.get('turnstileSecret', TURNSTILE_PLACEHOLDER)
            log.append(f"main · {TURNSTILE_NODE}: secret — {'from the secrets file' if 'turnstileSecret' in secrets else 'placeholder'}")
            n = _one(nodes, FEWSHOT_NODE, key)
            code = n['parameters'].get('jsCode', '')
            for anchor, want, _ in FEWSHOT:
                if code.count(anchor) != want:
                    raise Refused(f"main · {FEWSHOT_NODE}: the anchor {anchor!r} occurs {code.count(anchor)}×, measured {want}×")
            for fixed in (*NOT_OFFERED, NOT_OFFERED_MARK):
                if code.count(fixed) != 1:
                    raise Refused(f"main · {FEWSHOT_NODE}: the fixed example {fixed!r} occurs {code.count(fixed)}×, measured 1×")
            for anchor, _, make in FEWSHOT:
                code = code.replace(anchor, make(first))
            n['parameters']['jsCode'] = code
            log.append(f"main · {FEWSHOT_NODE}: few-shot ×{sum(w for _, w, _ in FEWSHOT)} from services[0]")
        out[key] = wf
    return out, log


def write(out, rendered):
    """mkdir (never into an existing path or through a link at the leaf), re-check where it landed, then create each
    file inside it by directory fd without following links — so a link swapped in after out_dir() cannot steer the
    output into the repository."""
    try:
        os.mkdir(out, 0o700)
    except OSError:
        raise Refused('the output directory could not be created new')
    try:
        dfd = os.open(out, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise Refused('the output directory changed right after it was created (an empty directory may remain)', wrote=True)
    try:
        real = os.path.realpath(out)
        here, there = os.fstat(dfd), os.stat(real)
        if _inside_repo(real) or (here.st_dev, here.st_ino) != (there.st_dev, there.st_ino):
            ours = (here.st_dev, here.st_ino) == (there.st_dev, there.st_ino)
            if ours:
                os.rmdir(real)                           # ours, still empty: remove it
            raise Refused('the output directory moved or landed inside this repository after it was checked' +
                          (' (the empty directory it created was removed)' if ours else
                           ' (an empty directory it created may remain where the path pointed)'), wrote=not ours)
        os.fchmod(dfd, 0o700)
        for key, wf in rendered.items():
            fd = os.open(f'workflow.{key}.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(wf, f, indent=2, ensure_ascii=False)
                f.write('\n')
    except OSError:
        raise Refused('writing the output failed part-way (files written so far are 0600 inside the new 0700 directory)',
                      wrote=True)
    finally:
        os.close(dfd)


def main(argv):
    ap = argparse.ArgumentParser(prog='render-client.py', description='Render one client\'s workflows from its config.')
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--secrets')
    ap.add_argument('--exports', default=os.path.join(ROOT, 'n8n'))
    try:
        a = ap.parse_args(argv[1:])
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        out = out_dir(a.out)
        rendered, log = render(load_exports(a.exports), load_config(a.config), load_secrets(a.secrets))
        write(out, rendered)
    except Refused as e:
        print(f'render-client: REFUSED — {e}' + ('' if e.wrote else ' (nothing written)'))
        return 1
    for line in log:
        print('  ' + line)
    print(f'render-client: OK — {len(rendered)} workflows written to the output directory (0700, files 0600)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
