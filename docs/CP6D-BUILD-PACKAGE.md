# CP 6d — build package (ONE editor session)

> **Who does what.** Yigitcan builds these nodes in the n8n editor, generates the secret and publishes.
> Claude Code builds the dashboard client, the test harness and the docs, and **does every measurement**.
> "I built it" is not a measurement — the drills in `tests/run-d11.sh` are.
>
> **Two jobs are in here on purpose:** the D11 owner write path and the `leads` TTL branch. Both are n8n
> work; splitting them across two sessions would cost an extra editor round for nothing.
>
> ⚠ **No literal host anywhere below.** `<n8n-host>` is a placeholder; the real value lives in
> `CLAUDE.local.md` and is never typed into a file or a shown command (`.claude/rules/remote-operator.md`).

---

## STEP 0 — the shared secret (Yigitcan, before touching the editor)

```
openssl rand -hex 32
```

That one value goes in **two places and nowhere else**:

| Where | How |
|---|---|
| **n8n** | Credentials → new *Header Auth* or a workflow-level variable named `OWNER_HMAC_SECRET` |
| **the dashboard** | `web/dashboard/.env.local` → `OWNER_HMAC_SECRET=<value>` |

⚠ **It must never take a `NEXT_PUBLIC_` prefix.** That prefix inlines the value into the browser bundle,
and an HMAC secret in a browser makes the signature decorative — anyone could forge a release request.
The dashboard reaches it only from server code, the same discipline `lib/airtable.ts` uses for the PAT.

Also into `web/dashboard/.env.local` (names are in `.env.example`):
`OWNER_ACTION_URL` · `CF_OWNER_ACCESS_CLIENT_ID` · `CF_OWNER_ACCESS_CLIENT_SECRET`.
The two `CF_OWNER_*` values already exist in `~/.n8n-api.env` from CP 6d-0 — copy, do not regenerate.

---

## PART A — the D11 owner write path (11 nodes, new workflow *or* a new trigger in the main one)

Path: **`/webhook/owner-release`**. It sits inside the `owner-*` Access application built in CP 6d-0,
which was measured: unauthenticated **403**, service-token **404** (reaches n8n). Access answers *which
machine*; HMAC answers *which request*. Both are required — if the service token ever leaks, the signature
is the only thing left.

### A1 · `Receive Owner Action` — Webhook
`POST` · path `owner-release` · **Response Mode: Using 'Respond to Webhook'** · **Raw Body: ON**.
*Why raw:* the HMAC is computed over the exact bytes. If n8n parses and re-serialises the JSON, key order
and spacing change and the signature will not match.
*Skip it and:* signatures fail intermittently and the cause is invisible — this was already paid for once
on the Zernio inbound signature (CP5d).

### A2 · `Verify Owner Signature` — Code
Compute `HMAC-SHA256(raw_body, OWNER_HMAC_SECRET)`; compare to header `X-Owner-Signature` with
**`crypto.timingSafeEqual`**.
*Why constant-time:* `===` leaks the signature one byte at a time to anyone who can measure latency.
*Skip it and:* the endpoint is effectively unsigned, and the Access token becomes a single point of failure.
⚠ **This n8n instance blocks `require()`** (measured, all modules). `crypto` is available as a **global** —
do not write `require('crypto')`.

### A3 · `Owner Request Fresh?` — Code + IF  ⟵ replay window
The signed body carries `ts` (unix seconds). Reject if `abs(now - ts) > 300`.
*Why:* a captured request stays valid forever without it. A stolen POST could be replayed months later.
*Skip it and:* the signature proves authorship but not recency — a replay is indistinguishable from a
fresh click.
Fail → `Reject Owner Request` with **401**.

### A4 · `Signature Valid?` — IF
false → **`Reject Owner Request`** — Respond to Webhook, **403**, `{ok:false,error:"invalid_signature"}`.
*Why a named node:* `n8n-conventions.md` — a refusal must be VISIBLE on the canvas, not an implicit
fall-through.

### A5 · `Validate Owner Action` — Code  ⟵ **the allow-list**
Accept **exactly** `action === "release_handoff"`. Anything else → **400**.
*Why:* this is `prompt-injection.md`'s "there is no other write action, so there is nothing to escalate
into", expressed in the engine. It is also the reason CRT #11 can be audited at all — the surface is one
verb.
*Skip it and:* the endpoint becomes a general write proxy the day someone adds a second verb, and every
guarantee in the audit lapses silently.

### A6 · `Find Target Conversation` — Airtable (get by record id)
Table `conversations`, **`record_id` from the signed body** — not `sender_key`.

⚠ **THIS CHANGED BEFORE ANYTHING RAN, and the reason is the design rule catching the design.** The first
draft of this guide said `sender_key`. The dashboard does not have one and must not: E2's rule is *a field
that is not displayed is not fetched*, and a full widget `sender_key` is a **bearer credential** — anyone
holding it can post it as their own `sessionId` and reach that conversation's cancel/reschedule
(`security-secrets.md`). `airtable.ts` therefore fetches only the masked form.
A record id is already on every queue row, costs nothing, and **cannot be replayed into the widget lane**:
it is useless without the base id and a PAT. Strictly better, and it only surfaced because the client was
written against the data that actually exists rather than the data the design assumed.

### A7 · `Validate Release Target` — Code  ⟵ **target validation**
Three conditions, all required: the record **exists** · `stage === 'handoff'` · it was updated within the
last N days. Otherwise **404** (missing) or **409** (not locked).
*Why:* a correct signature still does not say WHICH conversation. `ARCH-DEC:147` names the threat exactly —
*"an unsigned owner-action endpoint would let anyone unlock any conversation"* — and a signed one with no
target check has the same hole for anyone holding the secret. `Validate Cancel Target` exists in the
booking flow for this identical reason (CP3).
*Skip it and:* one valid signature unlocks arbitrary conversations, including ones never in handoff.

### A8 · `Check Owner Replay` — Airtable (search) on `processed_messages` by `messageId`
*Why:* `booking-integrity.md` item 1 — the same click twice must produce one write.
⚠ **Known, measured bound — write it on the sticky, do not claim more:** `Record Processed` writes at the
**END** of a turn, so a replay that arrives while the first is still in flight finds nothing and proceeds.
On the booking path a deterministic Calendar event id absorbs that collision; **here there is no such
backstop.** What makes it safe is that the write itself is idempotent — setting `stage='new'` twice is the
same as once. Accept that deliberately; do not write "deduplicated" on the canvas.

### A9 · `Release Handoff Lock` — Airtable (update)
⚠ **`stage` → `'new'` AND `last_intent` → empty, together.**
*Why both:* learned on 2026-09-09f when the manual release was performed for real and written into
`docs/DATA-MODEL.md` — **two escalation ladders read `last_intent`**. Clearing only `stage` leaves the
conversation half-armed.
*Skip the second field and:* the lock opens, then the next uncertain turn re-locks it immediately and the
owner believes the feature is broken.
Error handling: `onError` → **`continueRegularOutput`** plus a `<Node> Errored?` IF. **Do not use
`alwaysOutputData` + `continueErrorOutput`** — that combination caused the double-run measured in exec 1361
and was removed from six nodes in CP5e.

### A10 · `Re-read Released Conversation` — Airtable (get)  ⟵ **write-then-verify**
Read the record back; assert `stage === 'new'`.
*Why:* Airtable and the engine share no transaction. A write that returned 200 is not a write you have
confirmed — `booking-integrity.md` requires the re-read on every mutation path.
*Skip it and:* a silently-failed update reports success to the owner.

### A11 · `Build Owner Alert (Release)` — Code → existing `Send Owner Alert (Telegram)`
New alert class `handoff_released`, and `Record Alert Class` stamps it.
*Why:* the dashboard reads that class; an owner-initiated write that leaves no trace is the one kind of
write nobody can audit later.
⚠ The delivery-failure leaf stays **terminal** — an alert about a failed alert is an infinite loop
(Codex INVARIANT #1).

### A12 · `Respond Owner OK` — Respond to Webhook — **200**
Body: `{ok:true}` — and nothing else.
⚠ **Do not echo the sender, masked or not, and do not echo the record id.** The caller already knows which
row it asked about; a response body ends up in logs, and the only thing a log needs from this endpoint is
that it succeeded.

---

## PART B — the `leads` TTL branch (a NEW branch in the EXISTING purge workflow)

Do **not** create a new workflow. `Load Config (Purge)` already fans out to two branches
(`Compute Purge Cutoff` → processed_messages, `Compute PII Cutoff` → conversations). This is the **third**
fan-out from the same node.

⚠ **This is a DELETE loop — criterion 1, irreversible.** Every guard below exists because one wrong cutoff
sweeps a table.

### B1 · `Compute Leads Cutoff` — Code (from `Load Config (Purge)`)
Cutoff = now − `leadsRetentionDays` (read from config; do **not** hard-code).
*Skip the config read and:* the retention period becomes invisible to the client config that is supposed
to drive everything.

### B2 · `Find Old Leads` — Airtable (search)
`leads`, filter `created_at < cutoff`. **Return only the fields needed to delete and count** — not the
phone, not the name.
*Why:* the rows are about to be destroyed for being PII; pulling that PII into execution data and owner
alerts on the way out defeats the purpose. `leads` is exactly the table the public-deploy gate names.

### B3 · `Leads Purge Sane?` — IF  ⟵ **THE CANDIDATE CAP**
If `candidates > 20% of the table` (or `> 200` rows, whichever is smaller) → **do not delete**. Route to
the alert branch with `leads_purge_capped`.
*Why:* a mis-computed cutoff is a single arithmetic slip, and without a cap its cost is the whole table.
With a cap its cost is one Telegram message. **This is the single most important node in Part B.**
*Skip it and:* the first timezone or unit mistake in B1 is unrecoverable — Airtable has no undo.

### B4 · `Count Leads Before` — Airtable (search, count only)
### B5 · `Delete Old Leads` — Airtable (deleteRecord), **batched at 25 per request**
⚠ **25, not 10.** This repo wrote 10 once, from a brief, and budgeted the calls wrongly on that basis.
### B6 · `Count Leads After` — Airtable (search, count only)
### B7 · `Verify Leads Purge` — Code: assert `before − after === deleted`; mismatch → alert branch.
*Why B4/B6/B7:* arithmetic proof. A delete that reports success and removes nothing, or removes more than
it listed, is otherwise invisible.

### B8 · errors → the existing `Build Owner Alert (Purge)`
Reuse it; do not add a second alert path. The message carries **counts only, never a row's contents**.

⚠ **CALL BUDGET, declared before the first run** (criterion 2 — the free Airtable plan stopped this
project once): one search + one count + ⌈n/25⌉ deletes + one count. For n ≤ 25 that is **4 calls per
run**, daily. Write that number on the sticky next to the branch.

---

## After publishing

Tell Claude Code. The seven cases in `tests/run-d11.sh` then run against the live path, and each one is
only evidence if the control and the treatment **differ** — a case where both return the same status is a
broken measurement, not a pass. That distinction is not pedantry: in CP 6d-0 a token-bearing request and an
unauthenticated one both returned 404 while the application was inert, and it had been written down as a
pass before being retracted.
