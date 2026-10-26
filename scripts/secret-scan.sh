#!/usr/bin/env bash
# Secret scan — ONE rule set, three entry points:
#   1. git pre-push hook (THE GATE since 7-2 Tur 2): scripts/pre-push.sh, installed by scripts/install-pre-push.sh
#      TOGETHER WITH A COPY OF THIS FILE in the repo's own .git/hooks, calls this copy with
#      `--revs <local sha> [^<remote sha>] [--not --remotes=<the remote being pushed to>]` for every pushed ref.
#   2. Claude Code PreToolUse hook (a first line, no longer the gate): a `git push` command seen on the Bash tool.
#   3. By hand, before a commit: unpushed commits + the working tree.
#
# ── INSTALL ────────────────────────────────────────────────────────────────────────────────────────────────
#   git pre-push hook:      bash scripts/install-pre-push.sh      (installs pre-push.sh, this file and secret-scan-ignore
#                           into .git/hooks FROM HEAD — the commit, never the working tree; it refuses while any of the
#                           three is untracked or differs from HEAD, so commit them first)
#   Claude Code hook:       git cat-file blob HEAD:scripts/secret-scan.sh > ~/.claude/hooks/secret-scan.sh && chmod +x ~/.claude/hooks/secret-scan.sh
#     and wire it in ~/.claude/settings.json as a PreToolUse hook for the Bash tool:
#     {"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[
#       {"type":"command","command":"/home/<you>/.claude/hooks/secret-scan.sh"}]}]}}
#     (it reads its exceptions from ~/.claude/hooks/secret-scan-ignore; absent = no exceptions, the strict direction)
# Verify no installed copy has drifted from the copy committed at HEAD:  bash scripts/check-hook-drift.sh
#
# WHY THIS LIVES IN THE REPO (2026-09-03): a security control that exists only on one machine cannot be
# REVIEWED — Codex cannot see it, Cowork reviews from git and cannot see it, and it disappears with the
# machine. That is precisely how this hook stayed broken for the entire project: nobody could look at it,
# so nobody noticed it was scanning nothing.
#
# WHY THIS SHAPE — three defects found by drilling it, 2026-09-03:
#  1. SCOPE. v1 scanned `git diff --cached` — the STAGED area. By push time you have already committed,
#     so that area is empty: separate `git commit` and `git push` commands bypassed the hook entirely.
#     It was decor. A guard's scope must match the moment it runs → scan `<upstream>..HEAD`.
#  2. NOISE. v1 matched bare words (api_key|secret|password|bearer), so honest prose — "no secret found",
#     "NON-SECRET config" — blocked pushes. A guard that cries wolf gets switched off, and a switched-off
#     guard is worse than none because you think you are covered → match VALUE SHAPES, not words.
#  3. SILENT BREAKAGE. `grep -E '^\+'` is GNU-safe but ugrep (the grep on this machine) rejects it; the
#     pipeline errored, `|| true` swallowed it, and the hook approved everything while scanning nothing.
#     → portable character classes, plus a self-check that FAILS LOUD if the scan comes back empty while
#     commits are pending. (Since 7-2 Tur 2 R1c every extraction step is checked on its own — see 9.)
# Payload goes to a temp FILE, not a shell variable: re-piping ~1MB through bash printf once per rule
# took 15s for a single commit and timed out on five (measured) — and a slow hook is disabled like a
# noisy one.
#  4. UNEARNED PASS (2026-09-13). Two modes were being conflated. As a HOOK the scope `@{u}..HEAD` is
#     exactly right — it is what leaves the machine. But the same file is also run BY HAND as a pre-commit
#     gate, and then that scope is EMPTY: `rev-list --count` is 0, nothing is extracted, and it exits 0.
#     Worse, invoked with no hook payload at all it never even reached the scan — line "[[ $tool == Bash ]]
#     || exit 0" returned success. A gate reporting a pass it did not earn is the `check-listeners` dead
#     `exit 1` again: green, and measuring nothing. Manual mode below scans the WORKING TREE too, and
#     returns 2 NOT MEASURED — never 0 — when there is genuinely nothing to look at.
#
# FOUR MORE, from Codex 7-2 target 4 (docs/codex/7-2/4.md), each reproduced by tests/unit/guards-tur2.test.py:
#  5. A WHOLE LINE WAS DROPPED for carrying an excluded marker (`PLACEHOLDER`, `REPLACE_WITH_`, an env reference),
#     so a real key on the same line was never looked at. Exclusions now STRIP the excluded token alone and the
#     rest of the line is still scanned.
#  6. THE ENDPOINT DIFF hid intermediate commits: A adds a key, B removes it, `git diff base..HEAD` shows neither,
#     and both commits are published. Every commit's patch is scanned now — `git log -p`, merges included (each merge
#     diffed against every parent: `--diff-merges=separate` since R1d, see 14; it was `-m` until then).
#  7. COMMAND-FORM PARSING is not a gate: `git -C <dir> push` and `git -c k=v push` never matched `*"git push"*`.
#     The gate moved to git's own pre-push hook, which git runs for every form; the substring test below stays
#     only as the Claude Code first line.
#  8. SHAPES MISSED: project-scoped OpenAI keys (`sk-proj-…`), a bare `Bearer <token>` header value, and n8n
#     header pairs `{"name": "Authorization", "value": "…"}` — the last read by PARSING the JSON files a commit
#     touches, because pretty-printed JSON puts the name and the value on different lines.
#
# SIX MORE, from the R1 reviews (7-2 Tur 2 R1c; each reproduced by tests/unit/guards-tur2.test.py, t_g*):
#  9. EXTRACTION FAILS CLOSED. A git error, a write error (full disk, file-size limit) or a grep exit above 1 on
#     the extraction path used to be swallowed by `|| true` / `2>/dev/null`, and the scan approved what it had not
#     read. Every step now writes to a file and its exit code is checked; any failure is BLOCKED (exit 2).
# 10. WHAT GIT SHOWS IS PINNED. `--text` (a `.gitattributes` `-diff`/`binary` line, or one NUL byte, turned a file
#     into "Binary files differ"), `--no-textconv`/`--no-ext-diff` (a textconv driver can print nothing), `--root`
#     and `grep -a` (ugrep prints "binary file matches" instead of the lines). Config pinned on every extracting git
#     call: core.quotePath=false (a non-ASCII path came out quoted and its JSON was skipped), diff.relative=false
#     (from a sub-directory it hid every change outside it), log.showRoot=true (the root commit's patch),
#     i18n.logOutputEncoding=UTF-8 (a UTF-16 setting re-encoded every commit message out of the rules' reach).
# 11. `python3 -I`: plain `python3 -` puts the CURRENT DIRECTORY first on the import path, so a `json.py` at the
#     repo root ran instead of the rule engine on every push — and could simply exit 0.
# 12. TAGS. An annotated tag's MESSAGE leaves with the push and was never scanned (the tag pointed at an
#     already-public commit, so the range was empty and the scan exited 0). In `--revs` mode every positive tip
#     that is a tag is followed tag by tag and each tag's text is scanned. A tip that does not end in a commit (a
#     tag or ref on a blob or a tree) is REFUSED rather than scanned: `rev-list` counts it as 0 commits, nothing
#     here reads trees, and a refusal is visible and recoverable (push without that ref) while a partial scan is
#     neither. This repo has never published such a ref.
# 13. THE example.com EXEMPTION IS GONE. Its pattern ran from the domain to the next space or quote, so
#     `https://example.com/cb?token=<key>` or `https://example.com/<key>` lost the key with the URL. Measured
#     before removing it: across the full history (every ref, 150 844 patch + message lines) removing it added
#     ZERO hits, while an injected `example.com/cb?token=<key>` line went from 0 to 2 — it suppressed no false
#     positive this repo has, only keys.
#
# FIVE MORE, from the R1c reviews (7-2 Tur 2 R1d; each reproduced by tests/unit/guards-tur2.test.py, t_r1d_*):
# 14. MERGE DIFFS ARE PINNED. `-m` takes its format from `log.diffMerges`, and `log.diffMerges=off` made it print
#     NOTHING for a merge — a key added only in a merge resolution left unscanned, on the patch AND on the JSON name
#     listing. Both now say `--diff-merges=separate` explicitly; a flag beats the setting (measured for off,
#     first-parent, combined, remerge and unset).
# 15. FINGERPRINT EXCEPTIONS. A push to a new or empty remote, or to a URL, has nothing to exclude, so the whole history
#     is scanned from the root — and it blocked forever on one known historical test fixture. secret-scan-ignore, read
#     from BESIDE THIS FILE (never the repo's working tree when this runs as the installed hook), lists exceptions as
#     `<full 40-hex commit>:<path>:<rule name>`: an exact string, no pattern syntax at all, so the same line in another
#     commit, another path in that commit, or another rule on that line is still a hit. Only committed patch lines carry
#     that provenance (a `@@C <commit>` marker per commit, the path from the `+++ ` header of each file); commit
#     messages, tag text and the manual-mode working tree carry none and can never be excepted. Absent file = no
#     exceptions (strict); a malformed, symlinked or non-regular one is BLOCKED. The first three remaining hits per rule
#     are printed with their fingerprint next to the masked text (the rest as "… and N more"), so an exception can be
#     written without anyone seeing the value.
# 16. PATH PREFIXES ARE PINNED for that provenance: `diff.dstPrefix=Z/` printed `+++ Z/<path>` and `diff.noprefix=true`
#     printed `+++ <path>` on `git log -p` (measured), so a correct exception stopped matching. The extraction passes
#     `--src-prefix=a/ --dst-prefix=b/` and pins diff.noprefix/diff.mnemonicPrefix off; with them both settings print
#     `+++ b/<path>` again (measured; diff.mnemonicPrefix changed nothing on `git log -p` and is pinned as a precaution).
#     A wrong path only ever fails strict — the hit stays a hit — so this is about a correct exception still matching.
# 17. THE TEMP DIRECTORY IS CHECKED. `tmp="$(mktemp -d)"` had no exit-code check: a failing mktemp left `$tmp` empty, so
#     every path became `/raw`, `/patch` (refused later only because a non-root user cannot write there), and a mktemp
#     that printed a directory and still failed was simply used (measured with a shim: the scan ran and passed). Its exit
#     code and the directory are checked now; a failure is BLOCKED (exit 2).
# 18. THE RULE ENGINE IS A FILE in that temp directory, run with `python3 -I <file>`: the ignore file is validated by the
#     SAME code that applies it, before anything is extracted, so a malformed exception is visible even when there is
#     nothing to scan. `-I` keeps the script's own directory and the current directory off the import path, as 11 did.
set -uo pipefail
SECRET_SCAN_API=3   # scripts/pre-push.sh refuses a scanner without this marker (API 3: --revs + tag messages + R1c)
: "$SECRET_SCAN_API"

mode=hook
REVARGS=()
input=""
cmd=""
if [[ "${1:-}" == "--revs" ]]; then
  mode=revs; shift; REVARGS=("$@")
  [[ ${#REVARGS[@]} -gt 0 ]] || { echo "secret-scan: --revs needs revision arguments" >&2; exit 2; }
else
  manual=1
  if [[ ! -t 0 ]]; then
    input="$(cat)"
    tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null || echo '')"
    cmd="$(printf  '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || echo '')"
    [[ -n "$tool" ]] && manual=0
  fi
  [[ "$manual" -eq 1 ]] && mode=manual
fi

if [[ "$mode" == hook ]]; then
  # CLAUDE CODE HOOK — a first line only (see 7 above); git's pre-push hook is the gate.
  [[ "$cmd" == *"git push"* ]] || exit 0
fi
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  # The pre-push entry runs inside git; anywhere else "not a repository" is a pass-through, as before.
  [[ "$mode" == revs ]] && { echo "BLOCKED: secret-scan --revs ran outside a git repository" >&2; exit 2; }
  exit 0
fi
command -v python3 >/dev/null 2>&1 || {
  echo "BLOCKED: secret-scan needs python3 for its rule engine — it will not approve content it did not scan." >&2
  exit 2; }

# (17) A failed mktemp must not leave `$tmp` empty: every path below would then sit at the filesystem root.
if ! tmp="$(mktemp -d)" || [[ -z "$tmp" || ! -d "$tmp" || -L "$tmp" ]]; then
  echo "BLOCKED: secret-scan could not create its temp directory (mktemp -d, TMPDIR=${TMPDIR:-unset}) — it will not" >&2
  echo "  approve content it had nowhere to extract to." >&2
  exit 2
fi
trap 'rm -rf "$tmp"' EXIT

# ── EXTRACTION: added lines + messages of EVERY commit in the range, merges included (6) ──────────────
# Fails CLOSED (9): every step writes to a file and its exit code is checked — nothing on this path is piped into
# `|| true` or has its stderr thrown away. git's own message reaches stderr, and the push is refused.
fail_extract() {
  echo "BLOCKED: secret-scan could not extract the content to scan ($1) — it will not approve content it did not read." >&2
  exit 2
}
mkdir -p "$tmp/json" || fail_extract "creating $tmp/json"
: > "$tmp/raw" || fail_extract "creating $tmp/raw"
: > "$tmp/patch" || fail_extract "creating $tmp/patch"

# (15) The exception file sits BESIDE THIS FILE — the installed hook's own copy, never the repo's working tree.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || fail_extract "locating the scanner's own directory"
IGNORE_FILE="$SELF_DIR/secret-scan-ignore"
if [[ -L "$IGNORE_FILE" ]] || { [[ -e "$IGNORE_FILE" ]] && [[ ! -f "$IGNORE_FILE" ]]; }; then
  echo "BLOCKED: $IGNORE_FILE is a symlink or not a regular file — exceptions are read only from a regular file" >&2
  echo "  installed beside the scanner (re-run scripts/install-pre-push.sh)." >&2
  exit 2
fi

# ── THE RULE SET (one, for every entry point) ─────────────────────────────────────────────────────────
# Written to a file and run as `python3 -I <file>` (18): checked once here against the exception file, before
# anything is extracted, and run again at the end over what was extracted.
cat > "$tmp/engine.py" <<'PY' || fail_extract "writing the rule engine"
import json, os, re, sys

# EXCLUSIONS — shapes that look secret-ish but are not; each is a real FP from this repo. They are STRIPPED as
# whole tokens and the remainder of the line is still scanned (5). Case-sensitive, as the old line filter was.
# KNOWN LIMIT, measured 2026-10-26: an env reference is stripped WITH its name, so `process.env.X_SECRET = '<literal>'`
# loses its keyword and is not caught (it was not caught before either — the whole line was dropped). Keeping the
# name was tried and fired on the dashboard tests' `test-…` fixtures, which a push of that file would then block.
STRIP = [(re.compile(p), r) for p, r in (
    (r'"integrity"\s*:\s*"[^"]*"', ' '),
    (r'"resolved"\s*:\s*"[^"]*"', ' '),
    (r'sha(?:512|384|256|1)-[A-Za-z0-9+/]+=*', ' '),
    (r'REPLACE_WITH_[A-Za-z0-9_]*(?:@[A-Za-z0-9.-]+)?', ' '),
    (r'[A-Za-z0-9_]*PLACEHOLDER[A-Za-z0-9_]*', ' '),
    (r'__REDACTED__', ' '),
    (r'process\.env\.[A-Za-z_][A-Za-z0-9_]*', ' '),
    (r'os\.environ(?:\.get)?\s*[\[(]\s*[\'"][A-Za-z_][A-Za-z0-9_]*[\'"]\s*[\])]?', ' '),
    (r'\$\{?[A-Z_][A-Z0-9_]{2,}\}?', ' '),
    (r'\$credentials(?:\.[A-Za-z0-9_]+)*', ' '),
    (r'<your-[^>\s]*>?', ' '),
)]
# A run of four or more x's is the placeholder filler (`sk-ant-xxxx…`). It is removed WITHOUT a separator, so a
# real value that merely contains such a run is rejoined and still has to clear the rules.
XRUN = re.compile(r'x{4,}|X{4,}')


def strip(line):
    for rx, repl in STRIP:
        line = rx.sub(repl, line)
    return XRUN.sub('', line)


# RULES — value SHAPES, case-insensitive (as `grep -i` was).
RULES = [(n, re.compile(p, re.I)) for n, p in (
    ('anthropic key', r'sk-ant-[A-Za-z0-9_-]{20,}'),
    ('openai key', r'(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9]{32,}'),
    ('openai project/service key', r'sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}'),
    ('github token', r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}'),
    ('aws access key', r'AKIA[0-9A-Z]{16}'),
    ('google api key', r'AIza[0-9A-Za-z_-]{35}'),
    ('slack token', r'xox[baprs]-[A-Za-z0-9-]{10,}'),
    ('airtable pat', r'pat[A-Za-z0-9]{14}\.[0-9a-f]{64}'),
    ('telegram bot token', r'[0-9]{8,10}:AA[A-Za-z0-9_-]{32,}'),
    ('private key block', r'BEGIN [A-Z ]*PRIVATE KEY'),
    ('jwt', r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    # The value class has no `=`, `{`, `$` or `<`, so `Bearer ={{ … }}`, `Bearer ${…}` and `Bearer <…>` cannot match.
    ('bearer token', r'\bbearer\s+[A-Za-z0-9._~+/-]{20,}=*'),
    ('secret assigned a real value',
     r'(?:api[_-]?key|secret|token|password|passwd|auth[_-]?key)["\' ]*[:=]["\' ]*[A-Za-z0-9/+_-]{24,}'),
)]


def mask(line, span):
    s = line[:span[0]] + '<redacted>' + line[span[1]:]
    return re.sub(r'[A-Za-z0-9_-]{12,}', '<redacted>', s[:80])


RULE_NAMES = {n for n, _ in RULES}


# FINGERPRINT EXCEPTIONS (15) — `<full 40-hex commit>:<path>:<rule name>`. The rule name is what follows the LAST colon
# (no rule name has one), the path is everything between. Matching is exact string equality: there is no wildcard,
# glob or prefix syntax to misuse. Only a LINE-rule hit on a committed patch line can be excepted — never a commit
# message, tag text, a working-tree line or a JSON header-pair hit, none of which carries a commit AND a path.
FP_LINE = re.compile(r'([0-9a-f]{40}):(.+):([^:]+)')


def bad_ignore(path, n, why):
    print('secret-scan: %s line %d is malformed — %s. Exceptions are exact fingerprints; fix or remove the line.'
          % (path, n, why), file=sys.stderr)
    sys.exit(4)


def load_ignore(path):
    """The exception set. Absent file = no exceptions (strict). The first malformed line exits 4 (BLOCKED, visible).
    The line itself is never printed: nothing here should hold a value, but a mistake should not be echoed either."""
    if not os.path.lexists(path):
        return set()
    with open(path, 'rb') as f:
        data = f.read()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        bad_ignore(path, 0, 'the file is not UTF-8')
    out = set()
    for n, line in enumerate(text.split('\n'), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line != line.strip():
            bad_ignore(path, n, 'leading or trailing whitespace (a CR from a CRLF file counts)')
        m = FP_LINE.fullmatch(line)
        if not m:
            bad_ignore(path, n, 'not `<full 40-hex commit>:<path>:<rule name>`')
        if '*' in m.group(2) or '?' in m.group(2):
            # it could never match anything but a file literally named so — refused, so nobody believes it is a glob
            bad_ignore(path, n, 'the path looks like a wildcard; there is no pattern syntax, only exact paths')
        if m.group(3) not in RULE_NAMES:
            bad_ignore(path, n, 'unknown rule name; one of: %s' % ', '.join(sorted(RULE_NAMES)))
        out.add(line)
    return out


MARK = re.compile(rb'@@C ([0-9a-f]{40,64})')


def patch_lines(path):
    """(commit, path, line) for every ADDED line of the committed patches. The filter is the one added_lines() applies
    in bash — a line starting with `+`, minus EVERY line starting with `+++` — on `\n` boundaries, as grep sees them.
    The commit comes from the `@@C` marker; the path from the `+++ ` header between `diff --git` and the first `@@`."""
    commit = fpath = None
    header = False
    with open(path, 'rb') as f:
        for raw in f:
            b = raw[:-1] if raw.endswith(b'\n') else raw
            m = MARK.fullmatch(b)
            if m:
                commit, fpath, header = m.group(1).decode('ascii'), None, False
                continue
            if b.startswith(b'diff --git '):
                fpath, header = None, True
                continue
            if header:
                if b.startswith(b'+++ '):
                    p = b[4:].decode('utf-8', 'replace')
                    fpath = p[2:] if p.startswith('b/') else (None if p == '/dev/null' else p)
                elif b.startswith(b'@@'):
                    header = False
                continue
            if b.startswith(b'+') and not b.startswith(b'+++'):
                yield commit, fpath, b.decode('utf-8', 'replace')


def universal_lines(s):
    """Split as the old raw-file read did (universal newlines: \\r, \\n, \\r\\n), so a CR inside a patch line
    splits it exactly as before."""
    parts = s.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if len(parts) > 1 and parts[-1] == '':
        parts.pop()
    return parts


# n8n HEADER PAIRS — parsed, not pattern-matched (8).
AUTH_NAMES = {'authorization', 'proxy-authorization', 'x-api-key', 'api-key', 'apikey', 'x-auth-token',
              'x-access-token', 'x-n8n-api-key'}


def literal_header(v):
    if not isinstance(v, str):
        return False
    s = v.strip()
    s = re.sub(r'^(?:bearer|basic|token)\s+', '', s, flags=re.I)
    if not s or s.startswith(('=', '${', '<', '{{')):
        return False
    return len(re.sub(r'\s', '', strip(s))) >= 8


def walk(o, label, out):
    if isinstance(o, dict):
        nm = o.get('name')
        if isinstance(nm, str) and nm.strip().lower() in AUTH_NAMES and literal_header(o.get('value')):
            out.append(('n8n header pair (%s)' % nm.strip(), label))
        for v in o.values():
            walk(v, label, out)
    elif isinstance(o, list):
        for v in o:
            walk(v, label, out)


def main(argv):
    if argv[0] == 'check-ignore':
        load_ignore(argv[1])
        return 0
    raw_path, json_dir, patch_path, ignore_path = argv[1:5]
    ignore = load_ignore(ignore_path)
    hits = []          # (rule, where, fingerprint or None)
    count = {'lines': 0, 'excepted': 0}

    def check(text, origin):
        count['lines'] += 1
        cand = strip(text)
        for name, rx in RULES:
            m = rx.search(cand)
            if not m:
                continue
            fp = '%s:%s:%s' % (origin[0], origin[1], name) if origin and origin[0] and origin[1] else None
            if fp is not None and fp in ignore:
                count['excepted'] += 1
                continue
            hits.append((name, mask(cand, m.span()), fp))

    # Unlabelled: commit messages, tag text, the manual-mode working tree. Never excepted.
    with open(raw_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            check(line.rstrip('\n'), None)
    # Labelled: every added line of every committed patch, with its commit and path.
    for c, p, line in patch_lines(patch_path):
        for piece in universal_lines(line):
            check(piece, (c, p))

    parsed = unparsed = 0
    pairs = []
    for fn in sorted(os.listdir(json_dir)):
        if fn.endswith('.label'):
            continue
        p = os.path.join(json_dir, fn)
        label = open(p + '.label', encoding='utf-8').read().strip() if os.path.exists(p + '.label') else fn
        try:
            doc = json.load(open(p, encoding='utf-8'))
        except (ValueError, UnicodeDecodeError):
            unparsed += 1
            continue
        parsed += 1
        walk(doc, label, pairs)
    hits.extend((name, where, None) for name, where in pairs)

    shown = {}
    for name, where, fp in hits:
        shown.setdefault(name, []).append((where, fp))
    for name, items in shown.items():
        for where, fp in items[:3]:
            print('  ✗ %s: %s' % (name, where), file=sys.stderr)
            print('      fingerprint %s' % fp if fp else
                  '      no fingerprint (a commit message, tag text, working-tree line or JSON header pair) — cannot be '
                  'excepted', file=sys.stderr)
        if len(items) > 3:
            print('    … and %d more hit(s) of this rule' % (len(items) - 3), file=sys.stderr)
    if ignore:
        print('secret-scan: %d hit(s) excepted by fingerprint (%d exception(s) listed in %s).'
              % (count['excepted'], len(ignore), ignore_path), file=sys.stderr)
    if unparsed:
        print('secret-scan: note — %d .json file(s) did not parse; the header-pair check was not applied to them '
              '(the line rules were).' % unparsed, file=sys.stderr)
    with open(os.path.join(os.path.dirname(raw_path), 'stats'), 'w') as f:
        f.write('%d line(s) + %d JSON file(s)%s' % (count['lines'], parsed, ' (%d hit(s) excepted by fingerprint)'
                                                    % count['excepted'] if count['excepted'] else ''))
    return 1 if hits else 0


try:
    sys.exit(main(sys.argv[1:]))
except SystemExit:
    raise
except Exception as e:   # never 1 (that means "hits"): an engine fault must read as a fault. Type only — no content.
    print('secret-scan: rule engine error (%s).' % type(e).__name__, file=sys.stderr)
    sys.exit(3)
PY
if ! python3 -I "$tmp/engine.py" check-ignore "$IGNORE_FILE"; then
  echo "BLOCKED: $IGNORE_FILE could not be used (see above) — no push is approved on a broken exception list." >&2
  exit 2
fi

# Config that changes WHAT git prints is pinned here or overridden by an explicit flag on the call itself (10, 14, 16).
# That is a claim about the settings measured and named in this header — not about every setting git has.
gitx() { git -c core.quotePath=false -c diff.relative=false -c log.showRoot=true -c i18n.logOutputEncoding=UTF-8 \
             -c diff.noprefix=false -c diff.mnemonicPrefix=false "$@"; }
# Keep a patch's added lines, minus its `+++ <file>` headers. grep exit 1 = no line matched (fine); above 1 = error.
# Used for the manual-mode WORKING TREE only, whose lines carry no commit and so are never excepted (15). Committed
# patches go to the rule engine whole and are split there with the SAME `+`/`+++` filter, plus their provenance.
added_lines() {   # <patch file>
  local rc
  grep -a -E '^[+]' "$1" > "$tmp/added"; rc=$?
  [[ "$rc" -le 1 ]] || fail_extract "grep for added lines, exit $rc"
  grep -a -v -E '^[+][+][+]' "$tmp/added" >> "$tmp/raw"; rc=$?
  [[ "$rc" -le 1 ]] || fail_extract "grep dropping file headers, exit $rc"
}
extract_revs() {
  # `@@C <commit>` starts each commit's patch (no patch line can begin with it: content lines begin with ' ', '+', '-'
  # or '\', and git's own hunk headers with '@@ ' or '@@@ ').
  gitx log -p --diff-merges=separate --root --text --no-color --no-ext-diff --no-textconv -U0 \
       --src-prefix=a/ --dst-prefix=b/ --format='@@C %H' "$@" > "$tmp/patch" \
    || fail_extract "git log -p, exit $?"
  gitx log --format='%B' "$@" >> "$tmp/raw" || fail_extract "git log commit messages, exit $?"
  # the JSON files each commit adds or modifies, read whole at that commit, for the header-pair check (8)
  gitx log --diff-merges=separate --no-renames --diff-filter=AM --name-only --format='@@C %H' "$@" > "$tmp/names" \
    || fail_extract "git log file list, exit $?"
  local sha="" line i=0
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    if [[ "$line" == @@C\ * ]]; then sha="${line#@@C }"; continue; fi
    [[ -n "$sha" && "$line" == *.json ]] || continue
    i=$((i + 1))
    git cat-file -p "$sha:$line" > "$tmp/json/$i" || fail_extract "git cat-file ${sha:0:12}:$line, exit $?"
    printf '%s:%s\n' "${sha:0:12}" "$line" > "$tmp/json/$i.label" || fail_extract "writing a label"
  done < "$tmp/names"
}
# (12) Follow every positive tip that is a TAG down to its commit, scanning each tag's text on the way. Arguments
# after the first `--not`, `^x` exclusions, `a..b` ranges and options are not tips. A tip ending in a blob or a tree
# is refused (reason in the header).
tagged=0
scan_tag_chains() {
  local a obj t key
  for a in "${REVARGS[@]}"; do
    [[ "$a" == --not ]] && break
    [[ "$a" == -* || "$a" == ^* || "$a" == *..* ]] && continue
    obj="$a"
    while :; do
      t="$(git cat-file -t "$obj")" || fail_extract "git cat-file -t $obj, exit $?"
      case "$t" in
        commit) break ;;
        tag)
          git cat-file tag "$obj" > "$tmp/tag" || fail_extract "git cat-file tag $obj, exit $?"
          cat "$tmp/tag" >> "$tmp/raw" || fail_extract "writing a tag's text"
          tagged=1
          IFS=' ' read -r key obj < "$tmp/tag"   # its first line is `object <id>`; checked just below
          [[ "$key" == object && -n "$obj" ]] || fail_extract "tag $a has no object line"
          ;;
        *)
          echo "BLOCKED: $a does not peel to a commit (it ends in a $t). Only commits and the tags on them are" >&2
          echo "  scanned; push this ref only after scanning its content another way." >&2
          exit 2 ;;
      esac
    done
  done
}

base=""
if [[ "$mode" == revs ]]; then
  scan_tag_chains
  ahead="$(git rev-list --count "${REVARGS[@]}" 2>/dev/null)" || {
    echo "BLOCKED: secret-scan could not resolve the revisions to scan: ${REVARGS[*]}" >&2; exit 2; }
  if [[ "${ahead:-0}" -eq 0 && "$tagged" -eq 0 ]]; then
    echo "secret-scan: nothing new to scan in ${REVARGS[*]} (every commit is already on the target)." >&2
    exit 0
  fi
  extract_revs "${REVARGS[@]}"
  scope="${REVARGS[*]}"
else
  # ── SCOPE: exactly what is about to leave this machine ────────────────────────
  if up="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" && [[ -n "$up" ]] \
     && git rev-parse --verify -q "$up" >/dev/null 2>&1; then
    base="$up"
  elif git rev-parse --verify -q 'HEAD~1' >/dev/null 2>&1; then
    base="HEAD~1"
  fi
  if [[ -n "$base" ]]; then
    extract_revs "$base..HEAD"
    ahead="$(git rev-list --count "$base..HEAD" 2>/dev/null || echo 0)"
  else
    extract_revs -1 HEAD
    ahead=1
  fi
  scope="${base:-HEAD}..HEAD"
fi

# MANUAL MODE also scans what is NOT yet committed — the whole reason a person runs this before a commit.
# Untracked files go through `--exclude-standard`, so gitignored secrets (.env, CLAUDE.local.md) are not read.
if [[ "$mode" == manual ]]; then
  # NOT MEASURED is decided on the REAL question — is there anything under review? — and not on whether
  # $tmp/raw happens to be empty. `git log --format=%B` always yields a commit message, so a check on raw
  # alone could never reach this branch: dead code wearing a guard's clothes, which is the defect this
  # whole file keeps paying for.
  # `ahead` is set to 1 by the no-upstream fallback above, so it cannot answer this question. Ask it
  # directly: is anything unpushed, and is the tree dirty?
  unpushed=0
  if git rev-parse --verify -q '@{u}' >/dev/null 2>&1; then
    unpushed="$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
  fi
  if [[ "${unpushed:-0}" -eq 0 ]] && [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "secret-scan: NOT MEASURED — no unpushed commits and a clean working tree; there was nothing to scan." >&2
    echo "  (a pass here would be a pass this gate did not earn)" >&2
    exit 2
  fi
  gitx diff -U0 --text --no-color --no-ext-diff --no-textconv HEAD > "$tmp/wpatch" \
    || fail_extract "git diff HEAD, exit $?"
  added_lines "$tmp/wpatch"
  git ls-files --others --exclude-standard > "$tmp/untracked" || fail_extract "git ls-files, exit $?"
  gitx diff --name-only HEAD -- '*.json' > "$tmp/wjson" || fail_extract "git diff --name-only, exit $?"
  n=10000
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    sed -e 's/^/+/' -- "$f" >> "$tmp/raw" || fail_extract "reading untracked $f"
    if [[ "$f" == *.json ]]; then
      n=$((n + 1)); cp -- "$f" "$tmp/json/$n" || fail_extract "copying untracked $f"
      printf 'untracked:%s\n' "$f" > "$tmp/json/$n.label" || fail_extract "writing a label"
    fi
  done < "$tmp/untracked"
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    n=$((n + 1)); cp -- "$f" "$tmp/json/$n" || fail_extract "copying $f"
    printf 'worktree:%s\n' "$f" > "$tmp/json/$n.label" || fail_extract "writing a label"
  done < "$tmp/wjson"
fi

# Self-check: commits pending but nothing extracted = the scan itself broke. Never approve unscanned.
if [[ ! -s "$tmp/raw" && ! -s "$tmp/patch" ]]; then
  if [[ "${ahead:-0}" -gt 0 ]] && [[ -n "$(git log -1 --format=%H 2>/dev/null)" ]]; then
    echo "BLOCKED: secret-scan could not read the ${ahead} commit(s) being pushed — it will not approve" >&2
    echo "a push it did not actually scan. Fix the hook; do not bypass it." >&2
    exit 2
  fi
  # Nothing committed AND nothing in the working tree. For the hook that is a legitimate no-op; for a
  # person running this as a gate it is indistinguishable from a broken scan, so it is NOT MEASURED.
  if [[ "$mode" == manual ]]; then
    echo "secret-scan: NOT MEASURED — nothing to scan (no unpushed commits and a clean working tree)." >&2
    exit 2
  fi
  exit 0
fi

python3 -I "$tmp/engine.py" scan "$tmp/raw" "$tmp/json" "$tmp/patch" "$IGNORE_FILE"
rc=$?
if [[ "$rc" -eq 1 ]]; then
  echo "BLOCKED: possible secret(s) in the scanned content (see above)." >&2
  echo "Scope scanned: ${scope}$([[ "$mode" == manual ]] && printf ' + working tree'). Remove it, ROTATE it if it ever left this machine, then push." >&2
  exit 2
elif [[ "$rc" -ne 0 ]]; then
  echo "BLOCKED: the secret-scan rule engine failed (exit $rc) — it will not approve content it did not scan." >&2
  exit 2
fi
[[ "$mode" != hook ]] && echo "secret-scan: OK — ${scope}$([[ "$mode" == manual ]] && printf ' + working tree'): $(cat "$tmp/stats" 2>/dev/null) scanned against one rule set (line rules + n8n header pairs)." >&2
exit 0
