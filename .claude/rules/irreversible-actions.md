# irreversible-actions

**Purpose:** the control that replaces the permission prompt. Since 2026-09-11 this machine runs in
`bypassPermissions` (`.claude/settings.local.json`, gitignored — deliberately NOT in the committed
settings, because the repo is PUBLIC and a resellable template). The prompt is gone; this file is what
stands in its place, and it is stricter in the only way that matters.

## Why the prompt was removed rather than kept
**Yigitcan cannot evaluate the commands it showed him.** A gate whose only realistic answer is "Yes" does
not filter anything — it manufactures consent and spends attention. And it cost real evidence: in the
6b CRT #13 round `security-auditor` was judging `scripts/secret-scan.sh` and **could not read the guard's
body** because the permission layer denied it, so its verdict rested on behaviour measurement alone and
said so. That is not friction, it is a hole in the audit.

What Yigitcan CAN evaluate is the **effect**. So the gate moves from the command to the consequence.

## The rule
**Before ANY action in the list below: ask in chat, in TURKISH, in this exact shape, and wait for written
approval. Do not paste the command — the thing to be judged is the EFFECT, not the syntax.**

```
⚠ ONAY GEREKİYOR
Ne yapacağım:      <tek cümle, Türkçe, sade>
Neden:             <tek cümle>
Yanlışsa ne olur:  <tek cümle — neyi kaybederiz>
Geri alınabilir mi:<evet/hayır + nasıl>
```

**The list — ask first, every time:**
- `git reset --hard` · `git restore .` / `git checkout -- .` · `git rebase` · `git filter-branch` · any
  rewriting of history · `git push --force`
- **`git clean -fdx` / `-fdX`, and any wipe of IGNORED files.** This does not look like `rm -rf` and is the
  most dangerous line here. Measured 2026-09-11: it would destroy `CLAUDE.local.md` — the **sole copy of the
  production host** that `check-no-host-leak.sh` reads — plus `web/site/.env.local`,
  `.claude/settings.local.json`, and **51 files under `n8n/.snapshots/`**. OPS-1 was recovered from exactly
  such a backup. One command removes both the secret and the way back.
- **`git stash -a` / `git stash --include-untracked`, and `git stash drop` on such a stash.** It reads as a
  save, and it is a REMOVAL: `-a` takes ignored and untracked files OUT of the working tree, which here
  means `CLAUDE.local.md` (the sole copy of the production host) and `web/site/.env.local`; a later `drop`
  destroys the only remaining copy. Same blast radius as `git clean -fdx`, with none of its warning signs
  (added 2026-09-12 after `security-auditor` measured the removal — the list named `clean -fdx` but not this).
- `git add -f` (force-adding an ignored file — the gitignore is a secret/PII boundary here)
- `rm -rf`, and any deletion that cannot be undone
- **WRITING to the live n8n workflow** — adding or editing a node, publishing, touching `activeVersion` —
  and separately **ACTIVATING/DEACTIVATING a workflow or re-opening the Zernio webhook**, which is
  deliberately CLOSED for spend-safety; re-opening it costs money and exposure, and is its own API call.
- **Editing or deleting n8n Credentials.**
- **Airtable DELETE or bulk update — and deleting a FIELD**, which is not a row but a whole column
  (`appointments.calendar_id` and `conversations.cancel_target_id` were added by hand; they can go the same way).
- **Google Calendar event deletion — and CREATING a real event on the production calendar.**
- **Any OUTBOUND message to a real recipient** (WhatsApp/Zernio). A sent message cannot be recalled and it
  reaches a THIRD PARTY, which nothing else on this list does.
- **Writing outside the repo root** — and specifically **overwriting `~/.claude/hooks/secret-scan.sh`**, the
  installed push guard itself (`check-hook-drift.sh` exists because that file can drift).
- **Changing the git identity** (`user.name` / `user.email`)

**Everything else is NOT asked, and asking anyway is its own failure mode** — it re-creates the prompt this
replaced: reading, greps, guards, tests, builds, scratchpad work, ordinary commits.

⚠ **PUSH IS NOT ON EITHER SIDE OF THAT LINE, and an earlier version of this file wrongly listed it as
exempt.** In a PUBLIC repo a push is the single most irreversible act available — `git-github.md` says so
itself: *"git history is permanent and worldwide — a leaked secret survives a later delete."* Push already
has its own two gates and they are untouched by this file: **Yigitcan asks for it** (`git-github.md`), and
**the pre-push `security-auditor` run is mandatory** (`git-github.md`, `CLAUDE.md`). What the line above
means is only that a push does not need a SECOND `⚠ ONAY GEREKİYOR` block on top of those two. It is not an
exemption, and writing it as one — in the file whose subject is irreversibility — was the exact mistake this
file exists to prevent.

## Why this list and not a longer one
Every entry is either **irreversible** (a deleted calendar event, a rewritten history, a dropped Airtable
row) or **invisible after the fact** (a force-added ignored file in a public repo, a changed git identity).
Reversible and visible actions do not need a gate; they need a good report, which `reporting.md` already
requires. A list that grows past what it must contain gets ignored wholesale — see `make-the-error-cheap`.

## Related
`git-github.md` (commit/push only when asked; author is Yigitcan only) · `security-secrets.md` (the
gitignore is a secret boundary, which is why `git add -f` is on the list) · `n8n-conventions.md` (the live
workflow is production) · `docs/OPERATIONAL-INCIDENTS.md` (what went wrong when these were not gated).
