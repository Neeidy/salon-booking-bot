# security-secrets

**Purpose:** the repo is **PUBLIC** — keep every secret AND every piece of customer PII out of git.

**Where secrets live (never in git):**
- Production secrets → **n8n Credentials** and **Vercel env**. The repo holds only `.env.example` (names + fake placeholders).
- Local dev → `.env` (gitignored). Copy from `.env.example`, fill locally, never commit.
- Rotate immediately on any suspected leak.

**PII is treated like a secret (this is a PUBLIC repo):**
- Customer names, phone numbers, and message content are **never committed** — not in exports, not in
  screenshots, not in test fixtures. Use fake/test data only.
- n8n exports: commit **only** `n8n/workflow.sanitized.json` — pinned/test data and credentials stripped
  (see [../commands/sanitize.md](../commands/sanitize.md)).
- Real per-client `config/client.config.json` is gitignored; only `client.config.example.json` (mock) is committed.

**Two identifier classes that look harmless and are NOT (measured, 2026-09-11):**
- **A full widget `sender_key` is a BEARER CREDENTIAL, not PII.** `Find Booking` looks appointments up by
  `sender_key`, and on the widget it derives from the client-supplied `sessionId` — "session-token strength,
  not a verified identity". Anyone holding the full value can POST it as their own `sessionId` and reach that
  conversation's cancel/reschedule. **Never commit a full one.** A prefix is fine: `w-` is a fixed literal in
  `chatClient.ts`, so `widget:w-…` leaks zero entropy.
- **A full `gcal_event_id` is the same secret wearing a different coat.** It is `hex(sender_key|date|time|
  serviceId)` — a **UTF-8 hex encoding, not a hash** — so it reverses to the `sender_key` with one command.
  Treat a full event id exactly like a full `sender_key`. Decoding one INSIDE a report re-exposes it.
- Airtable record ids are redacted to a bare `rec…` (ruling `4a29c2c`): a partial id is unusable without the
  base id and a PAT, so keeping three characters buys the reader nothing and costs pure exposure.

## What the deny glob actually does — MEASURED, not assumed

The `Read(.env.*)` deny glob also blocks `.env.example`, the one `.env`-family file that is **committed,
public, and placeholder-only**. It blocks Claude AND the `security-auditor` agent — the same class of gap
that left a guard's own body unreadable during the 6b CRT #13 round.

**The blanket deny STAYS (Yigitcan's ruling, 2026-09-12).** Narrowing it means enumerating exceptions, and
the next `.env.staging` would be born unprotected. The risk of missing one real secret outweighs the cost
of not being able to open one example file.

**The correct route to a committed file is `git show HEAD:<path>`**. The deny rule protects a FILESYSTEM PATH, where a
real `.env` with real values may sit. What git holds is what was PUT there — usually only what was committed, but `git stash -a` puts an uncommitted, ignored file in with one command, so "not in git" is a statement about today, not a property of the file.

### ⚠ The deny layer is ANTI-ACCIDENT. It is NOT a boundary against a determined reader.

*Written 2026-09-12 after `security-auditor` demolished the first draft of this section, which claimed an
uncommitted `.env` stays "unreadable by every route… measured, not assumed". It WAS measured — on one
command shape — and then generalised into an absolute, in the file whose subject is that a claim must
equal its measurement.*

**What was measured, both directions:** a LITERAL path to a denied file is refused — through `Read` and
through Bash alike, including via `git diff --no-index`. A **glob-shaped** path to the same file is **not**
refused, and the content is reachable that way. The exact command shape is deliberately not written here
(see the note below). The mechanism was also mis-attributed in the first draft: the deny list in
`~/.claude/settings.json` holds only `Read(...)` rules, and the one Bash-side hook returns 0 without running
any rule on a non-`git push` invocation — the Bash refusals come from the harness inspecting the command
STRING, which is why a differently-shaped path walks past them.

**Therefore: the file is the boundary, not this layer.** Secrets live in `.env` / n8n Credentials, mode
**0600** (verified), and are **kept out of git** — a discipline, not a property of the files, per the
`git stash -a` note below. Treat the deny glob as a guard against a careless `cat`, never
as proof that a secret cannot be read.

> **The instruction this section exists to give, and the only one:** **do not deliberately route around a
> deny rule.** If a read you believe is legitimate is blocked, say so and stop — do not go looking for a
> shape that gets through. The measurement above was taken to CORRECT a false claim in this file, under an
> explicit instruction, with the content never printed; that is the only circumstance in which it is
> appropriate, and even then the working command is not recorded. A rule file that documents a bypass makes
> that bypass reachable by memory rather than by intent — and this file is read at the start of every session.

### Reading a file out of git history — the bound

`git show <rev>:<path>` is the correct route to a **committed, deliberately-public, placeholder-only** file
(`git show HEAD:.env.example` is the standard example — the deny glob blocks that file even though it is
committed, public and carries only `REPLACE_ME` values).

Two conditions are checkable BEFORE you read, and both are required:

1. **`git merge-base --is-ancestor <rev> origin/<branch>` is green** — the content really is already public.
   A local commit ahead of `origin` is not world-readable; "committed" is not "pushed".
2. **`<path>` is a deliberately public file at that rev** — not gitignored today, not a secret committed by
   mistake and later removed.

⚠ **A third property — "the target carries placeholders, not real values" — CANNOT be checked in advance,
and an earlier draft of this section listed it as if it could.** You only learn it by reading. This repo has
a live counterexample that satisfies both checkable conditions and still yields real data: masking is
**forward-only** — a later commit that masks a value does not remove it from earlier revisions, so a file
that is public today can still yield unmasked values at a revision from before the masking commit. This
repo has done exactly that (`docs/ROADMAP.md`, the Airtable record-id masking ruling).

**So the real control is what you do at the moment of discovery:** if the content looks like a real
credential or real customer data — **STOP.** Do not print it, do not quote it, do not summarise it. The
action is **rotate + report** ("Rotate immediately on any suspected leak", above). Discovering a leak is the
finding; continuing to read it is not.

This bound is about READING A BLOB FROM HISTORY, not about one command. `git log -p`, `git cat-file -p`,
`git grep <rev>`, `git diff <rev>` and `git stash show -p` reach the same objects and are covered by the
same rule — naming only `git show` would repeat, in reverse, the single-command over-generalisation that
this section was rewritten to remove.

⚠ `git stash -a` is **destructive**, not a read: it REMOVES ignored and untracked files from the working
tree, and in this repo those are `CLAUDE.local.md` (the sole copy of the production host) and
`web/site/.env.local`. It is on the gated list in
[irreversible-actions.md](irreversible-actions.md) for that reason. It is mentioned here only because it
also puts such a file into git, where the history rule above then applies.

**Before every commit:** run `/sanitize` and the `security-auditor` agent (pre-push secret + PII scan).

**Why:** one leaked token or one real customer number in a public repo is a real-world breach, not a demo bug.
