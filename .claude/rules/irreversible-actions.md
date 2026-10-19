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
- **Any of these on a workflow that uses a database credential: CREATING it (including a brand-new one
  that touches no existing workflow) · ACTIVATING it · EDITING it, ACTIVE OR INACTIVE · EXECUTING it BY
  HAND (a manual or test run, with chosen input or pinned data), ACTIVE OR INACTIVE.**
  *"Active or inactive" is written out deliberately. The item above says "the live n8n workflow" in the
  singular, and an earlier version of this line leaned on it for active ones; that reading was never
  written down, so it was not a boundary.*
  *(Added 2026-10-19 as the implementation of migration ruling Q6; widened the same day by ruling Q12.)*
  **What "EXECUTING it BY HAND" means, and the stricter rule on top of it (ruling Q13, 2026-10-19,
  Yigitcan: "elle bir şey çalışmasın, mümkünse hiç manuel olmasın"):**
  - It means n8n's OWN manual/test execution: "execute" from the editor or the API, starting from a node,
    or running with pinned data. **During the migration phase this is NOT USED AT ALL**, so approval is
    not the default way forward. Schedule-triggered copies are tested through a DECLARED TEMPORARY WEBHOOK
    trigger (spike S7's fallback). If a manual execution ever looks unavoidable: **STOP and ask
    Yigitcan.**
  - **The temporary webhook trigger has two binding conditions:**
    - it lives **only on a path behind Access**. Purge deletes, so an unprotected trigger would let anyone
      fire a deletion, which makes the Access-coverage spike (S6) its precondition;
    - it is **removed before the swap**, and its absence is proven by the copy-diff tool.
    Adding it to a copy is an EDIT of a workflow that uses a database credential, so it falls under this
    item.
  - It does NOT cover drill requests sent to the NORMAL trigger (webhook or schedule) of an approved,
    active workflow. Those are governed by the Turnstile window protocol, the `mig-` seed and the call
    budget, not by this item. **A temporary test trigger is NOT a normal trigger,** and this exception never
    covers it.
  Under Q6, Claude is given only the read-only DB role, from D2, so it cannot write to the database
  directly, unless a write credential reaches it some other way (OPS-6). But the n8n API key lets it
  build, change or run a workflow that writes through the app credential. That path has no technical
  barrier; **its only boundary is this line.** A boundary that exists only in a plan is not a boundary.
  **Why the two later verbs are named:** the first version named creating and activating only, and the
  pre-push audit found two routes it left open. An approved, inactive D3 copy could later have its query
  changed from SELECT to DELETE, and an inactive copy could be run by hand without ever being activated.
  Both are named now.
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
