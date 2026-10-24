# Migration phase — Airtable → self-hosted Postgres · PLAN (D1)

> **Status:** **APPROVED by Yigitcan, 2026-10-19** ("onaylıyorum", with Cowork's recommendations), with the
> rulings in §11 and three corrections applied in place (the race drill row, n8n image pinning as D2's first
> step, the Q6 wording). Derived against `3196ecb`; rulings applied on top of `a9ab867`. **Nothing is built
> yet.** D2a (preparation) is in the chat report of 2026-10-19.
> The build starts only on Yigitcan's written "approved" (`.claude/rules/plan-gate.md`).
> **Why this file exists:** the ruling (ARCHITECTURE-DECISIONS 2026-10-19) made the migration an interim
> phase before Phase 7. A plan that is not in the repo is a memory, and Phase 7's v2 plan evaporated that
> way (`governance-sync.md` §2).
> **Inputs:** the migration cost report (chat, 2026-10-18), re-measured where this plan relies on a
> number. **Evidence labels:** *measured* = a command was run against the repo, the live instance or the
> D0 backup · *quoted* = from the node schema or the official docs, quoted · *not measured → spike* = needs
> a live write, so it is planned as a D2 spike rather than assumed.

---

## 1 · Goal (one sentence)

**The bot, its owner path and the dashboard read and write a self-hosted Postgres that is unreachable
from outside the host, through parameterized queries and least-privilege roles, with behaviour
mechanically shown to be unchanged apart from the data layer — and Airtable is no longer on any
runtime path.**

## 2 · Scope · NOT-build

**In scope:** the five live workflows' data layer (34 Airtable nodes) · the dashboard's read path ·
the tests and tools that assume Airtable · a Postgres service, roles and schema · the backup of the new
store · the shutdown of the Airtable runtime path.

**NOT built in this phase:**
- ✗ **Behaviour changes riding along with the swap.** The copy differs from the original ONLY in its
  data-layer nodes (§4). **This rule has no exceptions:** the claim-first fix for CRT 1a's race went to
  Phase 7 (ruling Q5), so the equivalence proof stays clean.
- ✗ The Customers table (Yigitcan's separate decision). It is not migrated, not created in Postgres, and
  not deleted from Airtable by this phase.
- ✗ Migrating existing Airtable rows. The record shows every bot row is drill or test data (cost report
  §B5), so Postgres starts empty plus a mock seed. Confirm or overrule: **Q1**.
- ✗ Moving n8n's OWN database (SQLite) to Postgres. That is a different change, with its own restore
  story.
- ✗ Exposing Postgres on any non-loopback interface, or putting it behind the tunnel.
- ✗ A generic "data adapter" layer of sub-workflows (§3c).
- ✗ Any Phase 7 work. Phase 7 is ⏸; its premises are listed (§8), not re-derived.
- ✗ Re-opening the Zernio webhook, or sending to any real recipient.

## 3 · The phase map — re-derived

The candidate map from chat (D2 infra · D3 small workflows · D4 Main · D5 dashboard · D6 acceptance +
backup + Airtable shutdown · D7 close) is **kept in shape but changed in one place, and the change is
the main design finding of this plan.**

**What does not hold in the candidate: "copy → test → swap" PER WORKFLOW.** All five workflows and the
dashboard read and write ONE shared store. Every swap before the last one creates a split brain.
Measured examples:
- **Owner Actions on Postgres while the dashboard reads Airtable.** The dashboard hands the release
  button an Airtable record id (`airtable.ts:222` → `ReleaseButton` → owner-actions `RECORD_ID()`). That
  id does not exist in Postgres, so the release fails.
- **Drill State Read on Postgres while Main writes Airtable.** `run-d11.sh` then reads a state that never
  changes, so every assertion of CRT #11 measures the wrong store.
- **Reminders on Postgres while Main writes Airtable.** Reminders reads `appointments`, which Main writes.

**Re-derived rule: test per workflow, swap per store.** Each copy is built and drilled on its own, on
a test path, against a seeded Postgres. All of them switch together in ONE coordinated cutover. There is
a single exception: **Processed Purge is the only workflow whose swap is store-independent.** It reads
and deletes only its own aged rows, so swapping it alone leaves no split brain. That makes it the
"re-activate the old one" rehearsal the D0 ruling scheduled for "D3's first swap". The rehearsal stays in
D3 and runs on the one workflow where it is harmless.

| Step | Content | Exit gate |
|---|---|---|
| **D0** ✅ | Restore point (tag `pre-migration`, out-of-repo backup, two copies, restore-tested) | closed 2026-10-19 |
| **D1** | This plan | Yigitcan's written "approved" |
| **D2** | **Foundations + spikes.** **D2a ✅ 2026-10-19: image pinned by digest (§3m) · credential-decryption precondition PASSED with that image (§3k) · duplicate HMAC line removed (§3i).** **D2b-1 ✅ 2026-10-19 (offline): schema files, three gates, sanitizer test, operator commands (§3n).** **D2b-2 ✅ (operator) · D2b-3 ⚠ partial: network, Q15, deny rule, ro-negatives 26/26, S6, S8 done; STOPPED at S2 on a design-changing answer, Q17 (§3o).** **D2b-3 remainder (2026-10-20) ⚠ partial: Q17 ✅ ruled (a) and its premise measured · migrator role check (operator) · S3 ✅ · S5 measured; STOPPED at S5 on a design-changing answer, Q18 (§3p).** **D2b-3 close-out (2026-10-20): Q18 ✅ ruled · S1 ✅ · contract run ✅ on seeded rows, control red (§3q). ✅ D2 CLOSED 2026-10-20: exit gate met.** Then: Postgres service, roles and schema; the three committed gates (SQL-parameter gate · copy-diff tool · contract-shape test), each mutation-tested; sanitizer support for Postgres credentials; spikes S1–S9 | every gate shown able to go red · every spike answered or its design branch chosen |
| **D3** | **The four small workflows as copies:** Drill State Read → Owner Actions → Reminders → Processed Purge. Each is an inactive copy, with mechanical diff, contract test and drills on a test path. **Purge rehearsal:** swap → verify → re-activate the original → verify → leave the copy inactive. **Plan APPROVED 2026-10-20 with rulings K-1 to K-7 (§3r); D3e needs its own go-ahead.** **S10 ✅ · D3a ✅ · D3b ⚠ (Q17 race gap, evidence accepted) · D3c ⛔ waiting for the operator's binaryMode step · D3d not started (§3r) — status as of 2026-10-20, superseded by the line that follows.** *Status 2026-10-22: D3a ✅ · D3b ⚠ (accepted) · **D3c ✅** (error paths in D4's M7 window) · D3d ✅ · **D3e ✅ (daytime form)** · K-3 closed for D3a/D3b/D3d · settings-parity built. D3 is complete apart from D3c's error paths, which move to D4.* *Status 2026-10-23: ✅ D3 fully closed; D3c's error paths were drilled in D4's M7 window.* | 4 copies green · rehearsal measured in both directions |
| **D4** | **Main as a copy:** 17 nodes, 8 filter formulas (18 across all five), 43 `fields` references kept byte-identical by the contract shape. **Plan APPROVED 2026-10-23 with rulings D4-1 to D4-9 (§3s). D4a ✅ 2026-10-23 (offline build). D4b ✅ CLOSED 2026-10-23 (live drills; D4-5 cleared by a canary). D4c (the M7 window) ✅ 2026-10-23. D4-3 ruled (a). ✅ D4 CLOSED 2026-10-23.** | diff + contract + drills green; Turnstile window protocol on the COPY |
| **D5** | **Dashboard + tools:** `airtable.ts` → a read-only Postgres client · `run-d11.sh` PAT route · parity masks · `.env.example`. **Plan (with D6a and D6b) APPROVED 2026-10-23, §3t; built offline first; live check ✅ 2026-10-24 (round 2); the dashboard's live switch inside D6b; Codex CRT #10 on `store.ts` ruled (Round 3b); the dashboard reads Postgres in production since D6b (2026-10-24).** | CRT #10's boundary re-proven against Postgres |
| **D6** | **a) Pre-cutover gate:** `pg_dump` in the nightly job plus a restore test (§3j). **✅ D6a CLOSED 2026-10-24** (operator run: restore equal on 107 rows, both negatives red; the nightly call added, §3t). **b) Coordinated cutover + acceptance window.** **✅ D6b CLOSED 2026-10-24** (cutover 14:15–14:18 UTC; acceptance A1–A5 and A7–A9 green; A6, Purge's first trigger-mode tick, and the first nightly Postgres backup log are soak items; §3t Round 3c). **Phase 7's premise re-check happens at D6b's acceptance, and Phase 7 starts right after it** (ruling 2026-10-20). **c) Soak, then the Airtable shutdown** behind the export gate (§7). The 7-day soak runs in the BACKGROUND; only D6c's revocations wait for it (speed plan 2026-10-22: D7's close no longer waits). **d) Permanent off-server target** (moved to the final security pass, speed plan 2026-10-22). **e) Decided in D6b's plan (ruling 2026-10-22):** the O3 question, i.e. whether D6b PUTs each copy's nodes onto its original's id. It is measured first on a throwaway with routes R1, R2 and R3 (settings-parity plan, §3r). With it: `staticData` (Reminders' `reminderRunAt` concurrency guard and the `ownerAlerts` throttles, absent on every copy) and Main's tags. | acceptance suite green · rollback trigger list armed · export taken before any revoke |
| **D7** | Close: governance surfaces (rules, DATA-MODEL, MASTER-BRIEF stack, README), test-data cleanup, resume point. *(The Phase 7 premise list moved to D6b's acceptance, ruling 2026-10-20.)* Does not wait for the soak (speed plan 2026-10-22; it used to). | DoD |

*Why D6 carries the shutdown and not D7: the D0 rulings already attach the Airtable export gate and the
off-server target to D6 (ARCHITECTURE-DECISIONS 2026-10-19). Moving them would have contradicted a recorded
ruling, so they stayed. The soak sits inside D6 so that the rollback target outlives the cutover.*
**Re-ruled 2026-10-22 (speed plan):** the off-server target (D6d) moved to the final security pass by a new
ruling; the export gate stays in D6.

## 3a · Cutover method

**Options:** (i) edit the live workflows in place; (ii) copies, swapped one workflow at a time; (iii)
copies built and tested per workflow, swapped per store (all at once).
**Evidence:** the shared-store split-brain above (*measured* from the dashboard → owner-actions id
path and from the readers of `appointments`/`conversations`). n8n's public API creates workflows
inactive and has activate/deactivate endpoints, which earlier rounds used. **Whether two active
workflows can hold the same production webhook path: measured in S1 (2026-10-20, §3q): NO, for the same method
+ path.** The second
activation is refused with 409 ("There is a conflict with one of the webhooks") and the workflow stays
inactive; the first keeps serving the path.
**Recommendation: (iii).**
- Originals are never edited and stay as they are. Copies live on **test paths** while they are tested.
- At cutover: deactivate the original → PUT the copy's path to the production path → activate the copy
  → measure. One workflow at a time, inside one window.
- This order never asks two workflows to hold one path, so the design is safe **whatever S1 finds**. S1
  still tells us whether n8n would refuse loudly if the order were broken: **it does (409), measured §3q**,
  so activating the copy before deactivating the original fails visibly instead of splitting traffic.
- **Rollback is the same steps reversed: deactivate the copy, re-activate the original.**
- ⚠ **Honest limit of that rollback while OPS-5 lasts:** the originals run on Airtable, which is
  quota-blocked. Rolling back restores the CODE path to a known state whose data layer is down until the
  quota resets or the plan changes. Rows written to Postgres after the cutover are not in Airtable. Today
  they are test rows, so that is acceptable; after real traffic it would not be.
**Yigitcan rules on:** (iii) versus (ii) — **Q2**.

## 3b · Contract preservation

**The question:** if a Postgres query returns Airtable's shape, do the 49 `fields` references and the
downstream logic stay byte-identical?
**Measured:**
- The 49 references sit in 11 nodes (Main 7 nodes / 43 refs · Owner Actions 2/4 · Reminders 1/1 ·
  Drill State 1/1). The strict pattern `\.fields\b` is used, the same as in the cost report.
- **None of the 11 distinguishes "key absent" from "key null".** A static scan for `=== undefined`,
  `in`, `hasOwnProperty`, `Object.keys/entries/values` and `...fields` spread found zero hits. `typeof`
  has 2 hits: `typeof f.stage === 'string'` in `Validate Release Target` (a direct field access), and one
  on `turnCt`, a stored field carried through `Merge State`, whose `??` already treats absent and null
  alike. A typeof test treats absent and null the same, so the conclusion holds. The
  one `=== null` (in `Eval Spend`) compares the CAP, not a field; the field itself goes through
  `Number()` and then `Number.isFinite`. *(The `typeof` count was first written as zero; the pre-push
  audit measured 2. Corrected.)*
- **`Merge State`** decides "found" by `!!rec.id`, and its own comment documents the new-customer item
  as `{}` (that is `alwaysOutputData`). 15 of the 34 Airtable nodes set `alwaysOutputData`.
- **`createdTime`** is read once (Main).
- **A real Airtable output IS recorded, and the D0 backup keeps it permanently.** Processed Purge's
  `Count Leads Total` holds **114 record items whose top-level keys are exactly `{createdTime, fields,
  id}`**. The same backup holds 0-row items as `{}` (`Find Old Leads`, with `alwaysOutputData`) and
  error items carrying `error` + `message` alongside the input's own keys.
- **Measured from the D0 SQLite copy; keys and counts only, no values.** *A first scan of this
  history reported "no Airtable output" and "only Reminders runs". Both were wrong: its node list did
  not include `Count Leads Total`, and the same copy holds 14 Purge runs next to the Reminders runs.
  Its empty result described the instrument, not the data. The audit found the records,
  and they were then re-measured here.*
- **Still NOT measurable: whether Airtable omits EMPTY fields.** Every recorded item requests a single
  field, so no record shows an absent field. Absent-versus-null therefore rests on the static scan
  above, which found the consumers indifferent to it.

**Design:** every data-layer read builds the Airtable shape **in SQL**, so the types are ours rather
than the driver's:
```
SELECT id,
       to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS "createdTime",
       jsonb_strip_nulls(jsonb_build_object(
         'sender_key', NULLIF(sender_key, ''),
         'turn_count', turn_count,
         'reminded',   CASE WHEN reminded THEN true END,   -- false is omitted, like Airtable
         'last_updated', to_char(last_updated AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
         …)) AS fields
FROM …  WHERE … = $1
```
Nulls, empty strings and `false` are omitted; timestamps come out in Airtable's ISO form; numbers come
out as JSON numbers. **How the node returns a `jsonb` column (parsed object or string), and what a
0-row result looks like with and without `alwaysOutputData`: *not measured → spike S2*.** That spike
decides whether the shape holds by construction or needs an adjustment, and it is the first thing D2
measures.

**Record id: keep the `rec` + 14 alphanumeric format.** The primary key is
`text DEFAULT 'rec' || <14 random [A-Za-z0-9]>`, generated in the database.
**Places that change if the format changes instead (measured):**
- owner-actions `Validate Owner Action` allow-list regex
- drill-state signature/allow-list regex
- `tests/run-d11.sh` fixtures (2)
- `web/dashboard/lib/ownerAction.test.ts` fixture (1)
- `scripts/check-content-parity.py` id masks, which also stop masking ids in exports: a **sanitizer
  regression**, against the redaction ruling `4a29c2c`
- the 3 `RECORD_ID()` filter formulas (these change regardless)

The dashboard has no id validation of its own.
**Recommendation: keep `rec`+14.** It costs one SQL function and keeps the allow-list, the fixtures and
the export masks working unchanged. A collision across 62¹⁴ is negligible, and the PK rejects one
anyway. **Yigitcan rules on: Q3.**

**One existing quirk the contract must keep:** the dashboard builds rows as `{ id: r.id, ...r.fields }`,
so for `leads` the autonumber `fields.id` overwrites the record id. Postgres keeps an identity column
exposed as `fields.id`, so the behaviour is identical. *Recorded, not fixed.*

## 3c · Data adapter

| | Full adapter (sub-workflows per table, called from every workflow) | 1:1 node swap + contract shape |
|---|---|---|
| Diff size | 34 Airtable nodes → 34 Execute-Workflow calls plus ~5–10 new sub-workflows; **connections change** | 34 nodes change type and parameters in place, **same names, same connections** |
| Risk | every `$('Load State')`-style reference has to survive a new node; a new failure mode (sub-workflow errors) on every call; CRT #6's error branches are re-wired | error branches and node references untouched; the mechanical diff can prove "only these 34 nodes differ" |
| Cost of the NEXT store swap | low: only the sub-workflows change | medium: 34 nodes again, but with a proven diff tool and contract test |

**Recommendation: the 1:1 swap.** It is the only option where "no new bug" can be proven mechanically:
same node names and the same connection graph, so the diff tool can assert that everything outside the
34 nodes is byte-identical. The adapter optimises for a hypothetical next migration and pays for it now
with a re-wired error topology. That is `make-the-error-cheap` in reverse.

## 3d · Schema

Five tables. **Customers is NOT created.** Every table has
`id text PRIMARY KEY DEFAULT gen_rec_id()` and `created_at timestamptz NOT NULL DEFAULT now()`.

| Table | Columns (type · constraint) | Uniqueness (= today's upsert / dedupe key, measured) |
|---|---|---|
| `conversations` | sender_key text NOT NULL · stage text NOT NULL DEFAULT 'new' **CHECK (the 9 values in DATA-MODEL)** · slot_service/slot_date/slot_time text · last_updated **timestamptz NOT NULL** · turn_count int NOT NULL DEFAULT 0 · last_intent, recent_messages, gcal_event_id, cancel_target_id, confirm_turn, computed_reply, last_alert_class text · last_alert_at timestamptz · **sender_masked text GENERATED ALWAYS AS (…) STORED** | **UNIQUE (sender_key)**, from `Save State` upsert matchingColumns `['sender_key']` |
| `appointments` | sender_key NOT NULL · service · start_utc/end_utc **timestamptz NOT NULL** · gcal_event_id text NOT NULL · calendar_id · channel · customer_name · status text NOT NULL **CHECK (booked, cancelled)** · reminded **boolean NOT NULL DEFAULT false** · reminder_sent timestamptz | **UNIQUE (gcal_event_id)**, from `Write Appointment` upsert `['gcal_event_id']` · index (sender_key, status) · index (status, start_utc) |
| `leads` | **lead_no bigint GENERATED ALWAYS AS IDENTITY** (exposed as `fields.id`) · name, phone, message text · source **CHECK (whatsapp, widget, instagram)** · status **CHECK (new, contacted, converted)** DEFAULT 'new' | — |
| `processed_messages` | message_id text NOT NULL · sender_key · channel · created_at **timestamptz NOT NULL** (today it is TEXT; this is the blank-timestamp fix) | **UNIQUE (message_id)**, global as today (`Check Processed` filters on message_id alone) |
| `bot_metrics` | period_key text NOT NULL · cost_usd numeric(12,6) NOT NULL DEFAULT 0 · updated_at timestamptz | **UNIQUE (period_key)**, from `Record LLM Spend` upsert `['period_key']` |

- **The stage CHECK turns a silent new value into a visible error.** In D2, every `stage` value Main can
  write is listed, so the CHECK does not reject a value the flow legitimately produces. *Measured statically at D4
  planning (2026-10-23, §3s): every stage literal Main writes (9) is in the list; every other write passes the stored
  value back. Owner Actions writes only 'new'.*
- **`sender_masked`:** the Airtable formula's two measured defects are fixed (ROADMAP, 592 rows). A
  generated column keeps the dashboard's field. Its expression is derived in D2 from the fixed formula's
  described behaviour. `HandoffQueue` already re-masks as a fallback, so a mismatch fails safe, never
  open.
- **`cancel_target_id`:** plain `text`, **no foreign key.** Today the flow writes it as an empty string
  and as a dangling id, and `Validate Cancel Target` re-reads and refuses a bad one. An FK would turn
  those writes into errors, which is a behaviour change. A FK `ON DELETE SET NULL` after Phase 7 is a
  possible follow-up, not part of this phase.
- **The blank-timestamp class closes structurally:** `timestamptz NOT NULL` cannot hold `''`, and a write
  of `''` fails the cast and goes to the error branch, where it is visible. The three `!= ""` guards
  disappear because the condition cannot occur, not because they were deleted for convenience.

## 3e · Atomicity

| Node (today) | Postgres form | Closes |
|---|---|---|
| `Record Processed` (create) | `INSERT … ON CONFLICT (message_id) DO NOTHING RETURNING id` | duplicate dedupe rows: impossible by the UNIQUE |
| `Record Owner Action Processed` (owner replay marker) | **Q17 (a), ruled 2026-10-20:** `INSERT … ON CONFLICT (message_id) DO UPDATE SET message_id = EXCLUDED.message_id RETURNING id`. On a conflict the no-op update returns the EXISTING row's id, so `Marker Written?` (`!$json.error && !!$json.id`) takes the "written" path as on Airtable (the returned id is measured, §3p; the IF's routing follows from its expression and was not run). *Not `DO NOTHING`: that returns `{success: true}` and no id, with or without `alwaysOutputData`, and routes the race to "marker failure".* | duplicate replay markers (one row where Airtable made two) |
| `Save State` / `Save State (Post-Write)` (upsert) | `INSERT … ON CONFLICT (sender_key) DO UPDATE` | two first-contact rows for one sender: impossible |
| `Write Appointment` (upsert) | `INSERT … ON CONFLICT (gcal_event_id) DO UPDATE` | duplicate mirror rows for one event |
| `Record LLM Spend` (upsert) | `INSERT … ON CONFLICT (period_key) DO UPDATE SET cost_usd = EXCLUDED.cost_usd, updated_at = EXCLUDED.updated_at` (1:1, absolute; both mapped columns, D4-4) | duplicate period rows |

**Quoted** (n8n-mcp's bundled node database, node version 2.7; see §3f): the node's batching modes are "Single Query: A single query for all incoming items" ·
"Independent: Execute one query per incoming item of the run" · "Transaction: Execute all queries in a
transaction, if a failure occurs, all changes are rolled back". **There is no transaction across
nodes.** Atomicity therefore comes only from single statements plus constraints.
**How `RETURNING` rows come back, and what a conflict with 0 rows looks like: measured in S2 and the Q17
probe (§3o, §3p).** `RETURNING` hands back its rows; a write that returns 0 rows gives `{success: true}`, with
or without `alwaysOutputData`. **Batching modes under a partial failure: measured in S5 (§3p). Q18 ✅ ruled 2026-10-20:
`independently` for the four multi-item write nodes** (`Delete Old Processed`, `Scrub Recent Messages`, `Delete Old
Leads`, `Stamp Reminded`); every other node keeps the default `single`, which with one item is per-item.

**What the migration does NOT close, stated so that nobody believes it does:**
- **CRT 1a's race:** `Check Processed` (read) → processing → `Record Processed` (write, after the
  response). Two copies of the same message arriving inside that window are both processed. The UNIQUE
  makes the second `Record Processed` a no-op; it does **not** stop the second processing. The fix
  (claim-first, with a release on failure so provider retries still work) is a behaviour change.
  **Ruled (Q5): Phase 7.** The migration's rule is "behaviour does not change".
- **CRT 1b:** Google Calendar plus the store have no common transaction. Write-then-verify stays
  exactly as it is.
- **The spend meter's read-then-write TOCTOU** across concurrent turns stays (1:1). An atomic increment
  is possible, but it changes the node's input semantics (a delta instead of an absolute value). It is
  listed for Phase 7, not done.
- **Concurrent turns of one sender:** `Save State` remains last-write-wins, as on Airtable.

## 3f · Injection

**Quoted (docs):** *"n8n sanitizes data in query parameters, which prevents SQL injection."*
**Quoted (node schema, `query`):** *"You can use n8n expressions and $1, $2, $3, etc to refer to the
'Query Parameters'"*. *(The schema quotes in this plan come from n8n-mcp's bundled node database, node
version 2.7, not from this instance; this instance's available typeVersion is spike S2.)* **The node
therefore accepts both. Inference, on the safe side: only the parameters are sanitized, and expression
text is not.**
**Quoted (schema, `queryReplacement`):** *"Comma-separated list of the values you want to use as query
parameters."*
The docs do not say what happens to a string value that contains a comma; their only array example is
`{{ [ 'users', $json.email ] }}`. **Whether an array expression keeps a comma-, quote-, `$2`- or
newline-bearing value as ONE parameter: *not measured → spike S3*. Until S3 answers, no design depends
on the comma-separated string form.**

**Committed gate — `scripts/check-sql-params.py`** (D2, wired into `check-all`). Over every committed
workflow export it fails on any Postgres node where:
- `operation` ≠ `executeQuery` (no table-builder operations, so there is one review surface), or
- `query` is an expression (starts with `=`) or contains `{{`, or
- a `$N` in the query has no matching parameter, or parameters exist that are never referenced, or
- `queryReplacement` is present but is not an array expression (pending S3), or
- an identifier placeholder (`$N:name`) is used.

**Mutation-tested before any claim is written:** inject `{{ $json.x }}` into one query → red · drop a
parameter → red · switch one node to `insert` → red · clean → green. Live is covered by the existing
content-parity guard (committed == live).

**This closes an open input-validation finding.** On the public path's dedupe lookup, one
client-supplied identifier reaches an Airtable formula without a strict character allow-list.
- **Its impact has not been drilled, and it is NOT assumed to be limited to the sender's own message.**
  The lookup runs over the whole dedupe table, and its outcome is observable to the client, so it is
  treated as a potential read of other senders' rows. *(The migration cost report called it
  self-limited; the pre-push audit showed, from the committed graph, why that was too narrow.
  Corrected here.)*
- **Today it is dormant only because the Airtable path is down (OPS-5).** It becomes live again the
  moment the quota returns.
- On Postgres the lookup is a parameterized equality. **It closes at D4's cutover and is evidenced by
  the hostile-identifier drill (§4).**
- **Interim mitigation, ruled NOW (Q10), and BEFORE Main's copy is taken.** It is a strict character
  class on that identifier in the payload validator, the same shape as the owner path's fix of
  2026-09-13.
  - Patching the original while no copy exists keeps the diff base intact: D4 copies the PATCHED
    original, so the patch is never part of the data-layer diff.
  - **✅ APPLIED 2026-10-19** (approved by Yigitcan; measured by Claude). One condition was added to
    `Validate Payload`: `message_id` must match `^[A-Za-z0-9._:=+/-]{1,128}$`.
    - **The base was the PUBLISHED graph.** The draft carried two unpublished sticky-note moves, and a
      raw PUT publishes the draft. Those two cosmetic moves were discarded so that the running graph
      changed by this condition alone.
    - **Only that one condition changed:** the published graph before and after differs in exactly that
      condition (checked by a tool shown to catch an added change), and published == draft afterwards.
    - **Drilled inside a Turnstile window on Main only** (open 49 s, restored and measured both ways):
      - **7 hostile ids → 400**; `Check Processed` did NOT run, per the execution records.
      - **3 clean ids → 503** (store down, OPS-5); `Check Processed` DID run.
      - No LLM node ran.
    - After the window, the live graph is structurally identical to the post-patch graph. Only meta and
      the runtime `staticData` values differ.
    - **Drift guard:** `tests/unit/message-id-guard.test.cjs` is in `check-all` and was red on 5 of 5
      mutants.
    - **Rollback:** the pre-patch snapshot is kept, gitignored and untracked.
    - **D4 copies THIS patched original.**
  - ⚠ **Precondition for opening the WhatsApp/Zernio channel:** a REAL Zernio `message_id` must pass
    this class. The `=+/` in it rest on a base64 assumption, and no real Zernio id was available. Without
    that check, real WhatsApp messages could get 400. *(The ship gate has no item for opening that
    channel; where to put this is open, see the D2a/Q10 report.)*

## 3g · Roles (least privilege)

| Role | Can | Cannot | Negative test (D2; must FAIL with "permission denied") |
|---|---|---|---|
| `salon_owner` (owns the schema; NOLOGIN after setup) | DDL | log in during normal operation | a login attempt is refused |
| `salon_migrator` (applies migrations) | DDL on the schema | DML on data outside migrations (by convention, audited) | — (used only by Yigitcan's migration command) |
| `salon_app` (the n8n credential) | SELECT/INSERT/UPDATE/DELETE on the 5 tables, USAGE on sequences | `CREATE`/`DROP`/`ALTER`/`TRUNCATE`; reach any other database | `CREATE TABLE x()` · `DROP TABLE leads` · `TRUNCATE leads` · `ALTER TABLE …` → all refused |
| `salon_ro` (dashboard + Claude's verification) | SELECT on the 5 tables | any write | `INSERT`/`UPDATE`/`DELETE` on each table → refused |

- **CRT #10's boundary today rests on a read-only Airtable PAT.** It moves to `salon_ro`, which preserves
  it. The dashboard has no write credential to the data store at all; its one write goes through the
  owner path (CRT #11), unchanged.
- **Ruled (Q6): Claude holds only `salon_ro`. DDL is applied by Yigitcan's one command** (the schema
  files are committed, and he runs them).
- **What that does and does not guarantee, stated exactly:**
  - **Claude cannot write to the database DIRECTLY.** It holds no write credential. This holds only
    as long as no DB write credential is visible to it some other way (OPS-6 records one such case on
    this host).
  - **It CAN cause an INDIRECT write.** With the n8n API key it can create or edit a workflow that
    uses the `salon_app` credential.
  - **That path is held by a PROCEDURAL boundary, not a technical one:** the approval gate in
    `irreversible-actions.md`.
  - **The gate names the whole path:** `irreversible-actions.md` lists, for any workflow that uses a
    database credential: creating it · activating it · editing it, active or inactive · executing it by
    hand, active or inactive.
  - It was added 2026-10-19 for Q6 with the first two verbs. **The audit found the last two routes open,
    and ruling Q12 widened the rule the same day.** The rule's text now says so, which is the only basis
    on which this plan calls the gap closed.
  - *(The proposal said this keeps "agent never holds prod write credentials" literally true. That was
    too strong; this paragraph replaces it.)*
- The cost: every schema change needs one turn from Yigitcan.

## 3h · Network

**Measured:**
- n8n's compose service publishes only on `127.0.0.1` and uses the project's default network; no
  custom network is declared.
- The dashboard runs on the HOST as `next start -H 127.0.0.1` (from `package.json`), not in compose.
- The tunnel daemon runs on the host, not in compose.

**Options:** (A) publish Postgres on `127.0.0.1:5432` only; n8n reaches it by service name on the
default network, and the dashboard reaches it over loopback. (B) Move the dashboard into compose so
Postgres publishes nothing.
**Recommendation: (A).** It repeats the pattern n8n already uses (loopback publish), leaves how the
dashboard runs unchanged, and needs no tunnel change. (B) changes the dashboard's deployment, its
tunnel target and its env handling inside a data-layer phase, which is scope creep.
**Verification:**
- `ss -ltn` shows `127.0.0.1:5432` and **no** `0.0.0.0:5432` / `[::]:5432`.
- An external probe from Yigitcan's machine to the origin on 5432 times out. This is a behavioural
  check, because the bind address is the control being verified.
- `check-listeners.sh` stays green.

**Yigitcan rules on: Q7.**

## 3i · Secrets

- **The DB passwords are generated by Yigitcan, on the server, into the root-owned compose env.**
  Claude never generates or sees them (`remote-operator.md`). They are written straight into the file
  (e.g. `openssl rand` → `sudo tee -a`), never echoed.
- **The n8n Postgres credential is created by Yigitcan in the n8n UI.** The instance has the `postgres`
  credential type (*measured*: `GET /credentials/schema/postgres` → 200, with fields host, database,
  user, password, port, ssl, …). He reads the password on his own terminal; it never passes through an
  agent transcript. Claude verifies by BEHAVIOUR only (spike S8: a SELECT through n8n succeeds; a
  `CREATE` with the same credential is refused).
- **`salon_ro` for Claude's verification** lives in a new mode-600 file outside the repo, which gets a
  **new deny rule in the same change** (the operator API env file's lesson: deny globs stop at the repo
  root).
- **Duplicate `OWNER_HMAC_SECRET`: ✅ removed 2026-10-19 (D2a, by Yigitcan).**
  - **Before deleting, compared without printing a value or a hash** (*operator statement, Yigitcan's
    terminal output; not re-measurable now*): both lines held the SAME value, and the last one equals
    the value n8n reads from the compose env file. The earlier line was deleted; the count is now 1 and
    the file mode stays 600.
  - **After deleting, measured by behaviour, both directions** (*measured by Claude*): a drill-state read signed with the
    remaining value passed the signature gate (200), while the same request signed with a wrong key was
    refused (403, `REFUSED`).
  - The deletion's backup file held the value and fell outside the deny rule, which is bound to the
    exact path. It was deleted without being read, and its absence was measured. **The gap itself is
    open: backups of a secret file fall outside the deny scope.** It joins the final security pass, and
    the new DB credential file (above) gets a deny pattern that covers its backups.

## 3j · Backup

- **Design (D1) · applied in D6a, BEFORE the cutover**, so the store is backed up before it holds anything
  that matters. One step is added to the nightly job: `pg_dump -Fc` from inside the Postgres container
  (the job already uses the container pattern) → `pg_restore --list` non-empty → **restore into a
  scratch database, compare row counts per table, drop the scratch database.** A dump that has never
  been restored proves nothing.
  *Corrected 2026-10-23 (decision 3, §3t): the restore goes into a `--network none` throwaway container started from
  the running Postgres image, not into a scratch database in the live cluster; the comparison is per-table counts plus
  an ordered md5, and both the dump and the restore check run nightly (decision 5).*
- **Negative control:** a dump with a flipped byte must fail `pg_restore`, and the checksum must go red
  (D0's lessons: `integrity_check` and `bundle verify` both checked less than assumed).
- **The nightly job lives outside the repo**, so editing it needs Yigitcan's approval
  (`irreversible-actions.md`, writing outside the repo root).
- **Permanent off-server target: decided in D6, not now (ruling Q8).** *Re-ruled 2026-10-22: moved to the final
  security pass (speed plan).* Recommendation on the table: a
  client-side-encrypted `restic` repository.

## 3k · Credential-decryption test (precondition of D2)

Proves that the D0 backup's encryption key decrypts the D0 backup's credentials **without one value
leaving the container.** Run by Yigitcan (root + docker), on COPIES, never on the live volume:
```
T=$(sudo mktemp -d) && sudo cp <D0>/n8n/<db>.sqlite "$T/database.sqlite" \
 && sudo tar -C "$T" -xzf <D0>/n8n/<config>.tar.gz config && sudo chown -R 1000:1000 "$T"
sudo docker run --rm --network none --entrypoint sh -v "$T":/home/node/.n8n <the digest-pinned image, §3m> -c \
 'n8n export:credentials --all --decrypted --output=/tmp/c.json >/dev/null 2>&1;
  node -e "const c=require(\"/tmp/c.json\");console.log(\"total\",c.length,\"decrypted\",c.filter(x=>x.data&&Object.keys(x.data).length).length)"'
```
- *`--entrypoint sh` corrected 2026-10-19:* without it, the image's entrypoint hands `sh -c …` to
  `n8n` as arguments, and the test never runs.
- **Pass:** total = decrypted = the credential count recorded in D0's MANIFEST.
- **Negative control (required):** the same run with a config whose key has been altered must NOT
  decrypt them; an error or a decrypted count of 0 is expected.
- Afterwards: `sudo rm -rf "$T"`.
- **✅ PASSED 2026-10-19 (D2a, run by Yigitcan with the digest-pinned image; *operator statement*):**
  - `total 6 decrypted 6`. The six match D0's MANIFEST.
  - The negative control with a wrong key gave `export failed (no file)`. ⚠ **That message is generic.**
    A wrong mount or a typo would print the same thing, and the failure class (a key mismatch) was not
    captured. The red direction is shown, but its specificity is not.
  - Both temporary copies were removed, and a search found no leftovers.
  - **What this proves:** level B's key ↔ database pairing, on the pinned image. **What it does NOT
    prove:** a full n8n restore. n8n was never started serving from the backup, and no workflow ran
    on it.
  - *(The first attempt did not run, because the block was pasted while the previous command was still
    sleeping and the running command swallowed it. Every command block from now on carries a
    "do not paste the next block before the prompt returns" line.)*
- **Quoted (n8n CLI docs):** `n8n export:credentials --all --decrypted --output=…`, *"Exports the
  credentials in a plain text format"*, *"All sensitive information is visible in the files"*. That
  warning is why the file never leaves a `--network none` container that is deleted on exit.

## 3l · Rollback per step

| Step | Trigger | Exactly how |
|---|---|---|
| D2 | n8n behaviour changes after the compose edit (health, its port, a workflow fails) | restore compose + env from D0 (`RESTORE.md`, level B-4); remove the Postgres service; **keep its volume** |
| D3 / D4 | a copy misbehaves | deactivate or delete the copy. **Originals were never touched.** |
| D3 (rehearsal) | — (the rehearsal IS a rollback) | Purge: deactivate the copy → re-activate the original → measure the original's next run |
| D5 | the dashboard is wrong on Postgres | `git revert` + restore the dashboard's env from D0 (the dashboard is local and not public) |
| D6b | any acceptance assertion red · an error-branch alert class not seen before · a parity guard red · Turnstile not restored | §3a's steps reversed for every swapped workflow + dashboard env back. ⚠ This lands on Airtable, which is quota-blocked (§3a) |
| D6c | — | the Airtable shutdown runs only after the soak, and **only the revocations run, never a deletion** (§7). A revoked PAT is reversible by issuing a new one |

## 3m · n8n image pinning (D2's first step) — measured 2026-10-19

- **The running n8n version was read** from the running process's own `package.json`, without the
  docker CLI. *(The value lives in D0's private copy, not here: an exact version of a public-facing
  service turns CVE matching into one step, and it goes stale at the first upgrade.)*
- **The compose file in force pins that same version TAG, not `:latest`.** Read from D0's copy of the compose directory,
  which the operator verified byte-equal to live on 2026-10-18. The same directory holds an older
  `.bak` file that still names `:latest`. *(A premise in the D1 approval brief said the compose file
  names `:latest`. The measurement says that is the `.bak`, not the file in force. The conclusion
  stands either way: a tag is mutable.)*
- **What is NOT pinned is the DIGEST.** A tag can be re-pointed upstream, so a clean machine pulling
  the same tag later could get different bytes.
- **D2's first step:**
  1. Measure the running container's image id and the digest behind it.
  2. Pin compose to `n8nio/n8n:<tag>@sha256:<digest>`.
  3. Restart, and prove that the running image IS the pinned one.
  4. Run §3k with that SAME reference.
- The restore procedures (`docs/RESTORE-PROCEDURE.md`, and the canonical copy inside D0) record that
  **the pinned image is part of the restore.**
- **✅ DONE 2026-10-19 (D2a, by Yigitcan; *operator statement*).** Compose and the running container
  both reference the tag plus digest. The proof is "new container == pinned image == previous image":
  the restart changed the reference and not the bytes.
- Recovery measured afterwards (*measured by Claude*): API read 200 · webhook GET 404 · all 5 workflows active, with node
  counts, versionId and activeVersionId equal to D0's · `check-exports-parity` 0 · `check-live-parity` 0.
- *The exact version and digest are not written here (an exact version of a public-facing service
  turns CVE matching into one step). They live in the compose file and D0's private copy.*
- **Who changed the tag on 2026-10-13: most likely the operator, NOT VERIFIED.** Yigitcan does not
  remember. An optional check (the host's shell history and docker events around that date) was offered
  and not run.

## 3n · D2b-1 (2026-10-19): schema files, gates, operator commands, offline only

**Postgres version: major 18.** It is the newest supported release, and the official versioning page lists
version 18 with its final release on **November 14, 2030**. Quoted: *"The PostgreSQL Global Development Group
supports a major version for 5 years after its initial release."* The image is pinned by DIGEST in the
compose file. The digest was read from the registry's own API, without the docker CLI, and the operator's
pull re-checks it. Exact tag and digest stay out of this public file. Postgres 18's image also moved its
volume, and the official image page says so: *"The defined `VOLUME` was changed in 18 and above to
`/var/lib/postgresql`."*

**`db/schema/001_init.sql`:** the five tables of §3d, schema `salon`, the `rec`+14 id generator (no
extension: built from `gen_random_uuid()` bytes), and `salon.at_ts()` for Airtable's timestamp text.
- **`stage` CHECK: the nine values Main can WRITE, measured from the committed export** (executable nodes
  only; sticky notes excluded):
  - `booked`, `cancel_confirming`, `cancelled`, `handoff`, `new`: literal writes;
  - `confirming`, `reschedule_confirming`: assignments;
  - `collecting`, `ready`: Slot Gate's ternary.
  - Owner Actions writes only `new`.
  - This closes §3d's "not yet measured". *Still open:* whether any path writes an EMPTY stage. Merge
    State defaults it to `new`; D4's drills decide.
- **`sender_masked`:** a generated column carrying the FIXED formula. With Postgres, `left(s, n)` and a
  NEGATIVE `n` return all but the last |n| characters, so the length is clamped with `GREATEST(…, 0)`.
  Without the clamp, a very short key would come back almost whole, which is exactly the defect the
  formula was fixed for.

**`db/schema/002_roles.sql`:** `salon_owner` (NOLOGIN) · `salon_migrator` · `salon_app` · `salon_ro`, as
§3g. **Passwords: no literal, and never on a command line** (OPS-6: argv is readable by every local
account, including argv inside a container).
- They live in a root-only roles file that is **never** given to the container as an env file, so they
  are not in its lasting environment, where `docker inspect` would show them.
- The operator's root shell loads that file and runs `docker compose exec -e NAME …`. With `-e NAME` and no
  value, only the NAME reaches the command line; the value reaches that one psql process, which reads it
  with `\getenv`. The SQL itself arrives on STDIN.
- The script fails with a real error on a missing or short password. It keeps error text terse, and it
  raises `log_min_error_statement` for its session, because a failed `CREATE ROLE` would otherwise put
  the password in the server log.
- **Neither file has BEGIN/COMMIT:** the runner wraps both in ONE transaction, first as a dry run ending
  in ROLLBACK (Postgres rolls back `CREATE ROLE` too), then for real.
- ⚠ **Not executed:** there is no Postgres in reach. The dry run is the first execution.

**Gates (all in `check-all`, each shown red):**
- `scripts/check-sql-params.py`: 14 fixtures, and the selftest checks that each bad fixture fails FOR ITS
  OWN reason.
  - Each of its rules was disabled in turn without crashing the tool: executeQuery only · no expression in
    the SQL · every $N has a parameter · every parameter is used · array form only · no formatting
    filter or named placeholder (`$N^`, `$N#`, `${…}` included) · the query is a string. Each disabled
    rule turned the selftest red.
  - It counts the `postgresTool` type too, with its own fixture.
  - On the committed exports it reports "0 Postgres nodes checked", which is stated as such.
  - *Before the pre-push audit, the array-form rule could be switched off with the selftest staying
    green, because its fixture also failed another rule. The reason check closed that.*
- `scripts/diff-workflow-copy.py`: 18 cases built from the committed Drill State export. Each of its 11
  checks, disabled, turns the selftest red. The checks:
  - added node · removed node · a node outside the data layer · connections · a data node's non-data keys
    · settings;
  - the temporary trigger left in at the swap · the trigger path at the swap;
  - type (only airtable → postgres) · `pinData` · an `--allow` node that was not a data-layer node in the
    original (the pre-push audit showed a non-data node could otherwise be rewritten freely).
- `tests/contract/`: key/type/format fixtures from D0 (114 records, the 0-row `{}`, the error-item shape;
  no values). Each of the checker's 10 rules, and a fixture mutation, turn it red. The run against the
  real database is in D2b-3.
- `tests/unit/sanitize-postgres.test.cjs`: a fake Postgres credential block. A real-looking id is a
  SANITISE FAILURE, the placeholder passes, and with the sanitizer's credential walk disabled the test is
  red.

**Deny rule:** the project settings deny `~/.salon-db-ro.env` and `~/.salon-db-ro.env*`, the second
covering its backups (the D2a gap). Measured from a subagent once the file exists (D2b-3).

**Raised for a ruling (both block the operator's commands):**
- **Q14: the DB passwords go in SEPARATE files, not in n8n's own env file.**
  - The D2b-1 brief named n8n's own env file. **Measured:** n8n's compose service loads that file as its
    `env_file` (from D0's copy of the compose file), and workflows read the environment (Owner Actions and
    Drill State read `$env.OWNER_HMAC_SECRET`).
  - Every DB password there, the superuser's included, would be readable by any workflow, and so,
    indirectly, by anything that can edit workflows.
  - Two files keep them out of n8n entirely:
    - the Postgres service's env file holds only the bootstrap superuser's password (residual: it stays in
      that container's environment, root-visible);
    - a root-only roles file, never mounted anywhere, holds the three role passwords.
  - n8n gets the app password only through its credential.
  - *Declared deviation: the commands are written for the separate file; not run.*
- **Q16: `salon_ro` can read EVERY column**, including the bearer-credential `sender_key`, message content
  and lead PII, and every future table by default. Claude would hold it (Q6).
  - Postgres allows column grants, so a split is possible:
    - a dashboard role with exactly the columns the dashboard renders;
    - a verification role for Claude with only non-PII columns and counts.
  - That changes Q6's security model, so it is **proposed, not applied**.
  - Recommendation: split before D5. Until then, D2b-3 uses only counts and shapes through `salon_ro`.
  - *Re-ruled 2026-10-22 (speed plan):* the split moves to the final security pass, not before D5. Until
    then the same rule holds: Claude reads only counts and shapes through `salon_ro`.
- **Q15: how Claude reaches Postgres as `salon_ro` in D2b-3.** There is no client on the host (no psql,
  no driver). Recommendation: the `pg` package, pinned, as a dashboard dependency, because D5 needs it
  anyway. The alternative is read-only probes through temporary workflows only.

### D2b-3 measurement plan (written now, run later; every workflow named here needs approval, Q12)
- **Network:**
  - `ss -ltn` shows `127.0.0.1:5432` and NO `0.0.0.0:5432` / `[::]:5432`;
  - `check-listeners.sh` stays green;
  - the operator's external probe times out, with a positive control on port 22.
- **S8:** a temporary workflow, triggered only by a temporary webhook behind Access. It uses the
  `salon_app` credential:
  - a SELECT on `salon.conversations` must return rows;
  - `CREATE TABLE`, `DROP TABLE salon.leads`, `TRUNCATE salon.leads` and `ALTER TABLE` must each return
    "permission denied". `onError` is `continueRegularOutput`, so every outcome comes back in one
    response.
- **`salon_ro` negatives** (through the Q15 route): INSERT / UPDATE / DELETE on each table, and
  `CREATE TEMP TABLE`, must each return "permission denied". The same TEMP check runs for `salon_app` (in
  S8), and connecting to the `postgres` database must be refused for both.
- **Operator-side role checks:**
  - `salon_owner` cannot log in;
  - `salon_migrator` can `SET ROLE salon_owner`;
  - nobody else can.
- **S1–S6:** each runs as a throwaway workflow behind a temporary Access-covered webhook.
  - S1: two workflows on one throwaway path, activating both.
  - S2: return shapes on `mig-` seed rows: rows, 0 rows, `RETURNING`, `ON CONFLICT DO NOTHING RETURNING`
    with 0 rows, jsonb, timestamptz, and the available typeVersion.
  - S3: hostile values through an array `queryReplacement`, echoed back byte for byte.
  - S4: the error-item shape of an SQL error. An auth failure needs a deliberately wrong credential,
    which is the operator's to create.
  - S5: batching modes with 3 items.
  - S6: a credential-less request to the temporary path is refused at the edge.
  - **No manual execution (Q13).** Each workflow is deleted at the end, and its absence is measured with
    a 404 on GET.
- **Contract run:** the Airtable-shape SQL for each table, run through `salon_ro` and checked by
  `tests/contract/shape.cjs`.
- **Seed hygiene:** every row uses the `mig-` prefix, and the prefix-guarded cleanup runs at the end.
- **S9:** D6c.

## 3o · D2b-2 (operator) and D2b-3 (measurements), 2026-10-19: STOPPED at S2 on a design-changing answer

**D2b-2: operator statements (Yigitcan's terminal output, not verified by Claude except where noted):**
- **(a)** the image was pulled and its digest verified.
- **(b)** two files exist (Q14), holding 4 passwords of ≥32 characters, mode 600.
- **(c)** Postgres is healthy and bound only to loopback. The n8n container's id and start time are
  unchanged, and the volume was created. Cowork added three guards to the block before it ran.
- **(d)** the dry run (ROLLBACK) and the COMMIT both passed. ⚠ *The block's check line was a false red:
  casting a boolean to text in Postgres gives `true`/`false`, not `t`/`f`, and the expected string was
  wrong (it existed only in the chat command, never in this repo). Re-measured with the right spelling:
  5 tables, the roles as designed.* Cowork checked with `git diff` that the SQL applied is the committed
  one.
- **(e)** the n8n Postgres credential, with its connection limit lowered to 10.
  - ⚠ **Measured: the credential's name on the instance is "Postgres account", not the one reported.** The
    name is cosmetic.
  - What matters was measured by S8: it connects as `salon_app` to `salon`.
- **(f)** the read-only file exists, mode 600, 5 lines.
- **(g)** from the operator's machine, port 22 succeeded (the control) and 5432 timed out, in two runs.

**D2b-3: measured by Claude:**
- **Network, two layers:**
  - the bind address: `ss` shows `127.0.0.1:5432` and no wildcard 5432; `check-listeners` is green;
  - the firewall: the operator's external probe timed out (*operator statement*).
- **Q15 done:** `pg` is pinned to an exact version, installed as a dashboard dependency, and recorded in
  the lockfile (only pg's own dependency tree was added).
- **The deny rule works.** A subagent's Read of the read-only DB file was refused, both by absolute path
  and in `~/` form.
- **`salon_ro` negatives: 26/26** (`tests/db/ro-negatives.cjs`, which prints SQLSTATE codes only and
  makes every attempt unable to change data: `WHERE false`, or a rolled-back transaction for TRUNCATE and
  CREATE):
  - controls: the connection as `salon_ro`, and SELECT on all 5 tables;
  - refused with 42501: INSERT, UPDATE and DELETE on every table, TRUNCATE, CREATE TABLE, CREATE TEMP
    TABLE, and connecting to `postgres`;
  - catalog: `salon_owner` has `rolcanlogin = false`.
- **S6 ✅ · S8 ✅ · S2 measured · S4 partly answered.** See the S-table.
- **Clean-up was measured:** the prefix-guarded delete removed exactly the seeded rows (2/1/1/1/1). Counts
  were all zero before and all zero after.
  - The three temporary workflows were deleted, each confirmed by a 404.
  - The live instance is back to 5 workflows, and both parity guards are green.
  - The clean-up trigger was added to the S2 workflow itself, as §3n planned, so no workflow outside the
    approved list was created.

**THE ANSWER THAT CHANGES THE DESIGN (S2), and why D2b-3 stopped there:**
- §3e prescribed (before Q17) `INSERT … ON CONFLICT DO NOTHING RETURNING` for the owner replay marker (`Record Owner
  Action Processed`).
- S2 measured that on a conflict this returns `{success: true}` with `alwaysOutputData`. That node has no
  `alwaysOutputData`. *Corrected 2026-10-20: this bullet first went on "and NOTHING without it". That case
  was never run: S2 tested "without `alwaysOutputData`" on a 0-row SELECT only, and the write case was
  inferred from it. Measured on 2026-10-20 (§3p): a 0-row write returns `{success: true}` WITHOUT
  `alwaysOutputData` too.*
- Its consumer, `Marker Written?`, tests `!$json.error && !!$json.id`.
- So in the race the marker guards (two identical owner requests at once), Airtable would have created a
  second marker, returned its id and taken the "written" path. Postgres routes to "marker failure" (no
  `id`). *The first version also said it might "stop the flow silently"; that rested on the unmeasured
  half above and is removed.* **That breaks "behaviour does not change."**
- `Record Processed` in Main is unaffected: nothing reads its success output.
- **The general rule this exposes, for D3/D4:** a 0-row WRITE does not return `{}`. Every update/upsert
  node whose target can be missing needs its consumer checked one by one.

**Q17 ✅ ruled 2026-10-20 by Yigitcan: (a).** `Record Processed` (Main) stays `DO NOTHING`. The premise
was measured before it was recorded (§3p). The question was how the owner marker keeps Airtable's
observable behaviour:
- **(a)** `ON CONFLICT (message_id) DO UPDATE SET message_id = EXCLUDED.message_id RETURNING id`. A no-op
  update returns the EXISTING row's id, so `Marker Written?` takes the same path as on Airtable; there is
  one marker row instead of Airtable's two.
- **(b)** `DO NOTHING` (with or without `alwaysOutputData`, as measured afterwards). A race then raises a
  "marker failure" alert, which is a behaviour change.
- **(c)** change `Marker Written?`. That is outside the data layer, so it is forbidden in the copy by the
  diff rule.
- **Recommendation: (a).** S3, S5, S1 and the contract run against the database were NOT run on
  2026-10-19; S3 and S5 ran on 2026-10-20 (§3p).

## 3p · D2b-3 remainder (2026-10-20): Q17 measured, S3 ✅, STOPPED at S5 on a design-changing answer (Q18)

**Recorded:**
- **Operator statement (Yigitcan, 2026-10-20), not verified by Claude:** `salon_migrator` → `SET ROLE
  salon_owner` returned `salon_owner`; the control, `salon_app` → `SET ROLE salon_owner`, returned
  "permission denied to set role". This closes §3n's operator-side role checks, together with the catalog
  check in §3o (`salon_owner` cannot log in).
- **Credential name (ruling, 2026-10-20):** it stays "Postgres account". The plan uses the measured name.
- **Turnstile:** published `enabled: true` and a dummy token refused with 403, measured at the start and at
  the end of the round.

**Q17 premise, measured** (the S2 pattern: a temporary workflow, a temporary Access-covered webhook, `mig-`
rows, the statement parameterised through an array `queryReplacement`, NO `alwaysOutputData`).
**Where it ran, declared:** in **"S2b"**, S2's workflow from the approved list (§3n) RE-CREATED for this
round, because S2's own was deleted on 2026-10-19 and the brief's step 1 named "the S2 pattern". Besides
the Q17 chain, it held two more triggers: the contract seed (never triggered) and the prefix-guarded
clean-up (§3o's S2 workflow held a clean-up trigger the same way). No workflow outside S2 · S3 · S5 was created.

| Step | Returned | Meaning |
|---|---|---|
| first insert of `mig-q17-a` | 1 item, id X (`rec`+14) | the row is created |
| the same `message_id` again | **1 item, the same id X; `created_at` unchanged** | the no-op update hands back the existing row |
| control: a fresh `message_id` | 1 item, a new id ≠ X | the probe can tell a new row from an old one |
| row count for `mig-q17-a` | 1 | no duplicate row |
| contrast: `DO NOTHING` on `mig-q17-a`, no `alwaysOutputData` | 1 item, `{success: true}`, no `id` | what option (b) gives; it corrects §3o |

**S3 ✅ (`queryReplacement`):**
- **The array form keeps every value whole.** 14 values went through one array expression and came back
  identical: a comma, a single and a double quote, `$2`, a newline, an injection string, a backslash,
  unicode, `{{ $json.v1 }}`, `${v1} $1:raw $1^`, an empty string, an object cast to `jsonb`, `null` and a
  number.
  - The values came from a Code node, not from the webhook body, so the probe measured n8n, not Cloudflare's
    WAF.
  - A read afterwards showed `salon.leads` still exists.
  - So an expression or a pg-promise filter INSIDE a value is not evaluated.
- **The control that differs: the string form splits on commas.** The literal `a,b` became two
  parameters.
  - Bound to a query with a single `$1`, the value `a,b` **came back as `a`, silently truncated, with no
    error.**
  - This is the evidence for `check-sql-params.py`'s array-only rule, which was written before S3 and did
    not wait for it.
  - No design changes.

**S5, per-item parameters under each batching mode (3 items):**
- **On the success path all three modes behave the same:** 3 items in, 3 rows deleted, 3 items out, 0
  rows left.
- **When item 2 fails (a cast that fails only on that row), they differ, and none matches what the flow's
  error consumers were written for:**

| Mode | Rows left (of 3) | Items out | Error item | What the alert builders get |
|---|---|---|---|---|
| `single` (the node's default) | 3: the whole batch is undone | 1 | `{error: {…}, message: "<SQL text>"}`, Airtable's keys | the SQL reason, but "failed items: 1" for the whole batch |
| `independently` | 1: items 1 and 3 deleted | 3 | `{error: {…}}`, **no `message`, and no SQL text anywhere in the item** | `[object Object]` as the detail value (rendered `-object Object-`) |
| `transaction` | 3: rolled back | 2 | `{error: {…}}`, no `message` | item 1 is reported as deleted although it was rolled back; item 3 is not reported |

  - **Airtable's error item, read from the live execution history** (types only, no values): `{error:
    object, message: string}`. Three nodes in two workflows show it, with no other keys: `Check Processed`
    (Main), `Read Conversation` and `Count Markers` (Drill State). **All three run `continueRegularOutput`**
    (read from the committed exports). The input-key carry recorded in §3r belongs to
    `continueErrorOutput`, a different mode.
  - **The alert builders read the detail as `(e.error && e.error.message) || e.message || e.error`.** These
    are `Build Owner Alert (Purge)` and `Build Owner Alert (Reminders)`. Postgres's error object has no
    `message` key.
  - **Declared probe fault, fixed:** the first failure probe used `1/0`. Postgres folds a constant at
    plan time, so every item failed in every mode. Measured from the result: under `independently`, 3 of
    3 rows were left. The cast form fails only on its own row. The re-run used fresh `mig-` tags, and both
    runs' rows were in the clean-up.
- **This corrects S4:** "an SQL error is exactly `{error, message}`" holds for the `single` mode only.
  That is the mode S8 ran in, with one item.

**Q18 ✅ ruled 2026-10-20 by Yigitcan: (a) `independently` for all four.** His reason, on record: a stalled
batch re-sends reminders to every customer in it and lets one bad row block the leads TTL indefinitely; a
degraded alert detail line is visible and recoverable. **The alert-detail fix is a MANDATORY Phase 7 item**
(PHASE-7-PLAN, open-items table, PHASE 7 bucket). The question was the batching mode of the four multi-item
WRITE nodes:
- The nodes: `Delete Old Processed`, `Scrub Recent Messages`, `Delete Old Leads` (Purge) and `Stamp
  Reminded` (Reminders).
- Under a partial failure, no mode reproduces what these nodes' consumers were written against. That is
  Q17's class: an edge path where "behaviour does not change" cannot hold as written.
- The single-item nodes are unaffected. With one item, `single` mode IS per-item, and it keeps
  Airtable's error keys.
- **(a) `independently` for the four.** It keeps per-row progress and a true count of failed items. The
  alert's detail value degrades to `[object Object]` (rendered `-object Object-` in the owner's message, after the builders' markdown escape); the alert still fires, with its branch and count.
  The builders cannot be changed in the copy (the diff rule), so the detail fix is a Phase 7 item.
- **(b) `single` (the default).** It keeps the SQL reason in the alert, but one bad row undoes the whole
  batch.
  - For the three purge nodes, that only delays deletion to the next daily run.
  - **For `Stamp Reminded` it means that no appointment in the batch is stamped, so the next Reminders
    run sends the reminder AGAIN to every customer in it.** That is an outbound message to real
    recipients, the most irreversible class this repo names.
- **(c) A mix:** `independently` for `Stamp Reminded`, `single` for the three purge nodes. Each node keeps
  the more important half of its behaviour, at the cost of two rules in one migration.
- **Recommendation: (a).** A degraded detail line is visible and recoverable; a duplicate message to a
  customer is neither. (c) is the fallback if Yigitcan weighs the purge alert's text over uniformity.
- ⚠ **Not measured: Airtable's OWN behaviour when one item in such a batch fails** (per-item or
  batched). These nodes' history holds no partial failure. The ruling is therefore made against the
  consumers' code, which reads per-item error items, not against a recorded Airtable run.

**Not run, because of the stop:** S1 and the contract run. *(Both ran later the same day, after Q18: §3q.)*
- **S1:** two workflows on one throwaway path.
- **The contract run:** the Airtable-shape SQL per table through `salon_ro`. Its seed node was built into
  the S2b workflow and never triggered.
- Both resume after Q18. Neither depends on the answer; the brief's stop rule is unconditional.

**Clean-up (measured):**
- **Counts as `salon_ro`:** all five tables were 0 before the round. Just before clean-up,
  `processed_messages` held 18 rows, all `mig-`. After clean-up, every table is 0.
- **The prefix-guarded delete removed exactly 18** (2 Q17 · 9 from the first S5 run · 7 from the
  re-run), and 0 from the other tables.
- **Three temporary workflows** (S2b, S3, S5) were deleted, and each returns 404 on GET.
- **The live instance holds 5 workflows, and none is temporary.** `check-exports-parity` and
  `check-live-parity` are both 0.
- **Every temporary path was checked with no token first:** five paths (S2b's three triggers, S3, S5),
  each returned 403 before the owner token was used, S5's twice. *Status code only: the two signals S6
  used to place the refusal AT THE EDGE (the Access header, and no execution created) were not re-checked
  this round.*
- **The S5 workflow was edited once (PUT) to fix the probe fault above.** S5 is on the approved list, and
  so is editing it (Q12).

**D2's exit gate: NOT met at this point.** *(Superseded the same day: after Q18, S1 and the contract run, the gate is MET, §3q. The list below is the state at the S5 stop.)* The gate reads "every gate shown able to go red · every spike answered or its
design branch chosen".
- **Gates:** met (D2b-1).
- **Spikes:**
  - S2, S3, S6 and S8 are answered, and S7 and S9 are ruled.
  - S5 needs Q18.
  - S1 and the contract run are not run.
  - S4's auth-failure shape is open.
- **Can D2 close with S4's auth-failure shape open? Yes, if its design branch is named, and the proposed
  branch is:**
  - Every `Errored?` IF tests `!!$json.error`, which any of the measured error shapes satisfies.
  - The connect-time failure shape is measured in D4 by drill M7, which revokes `salon_app`'s CONNECT and
    so uses the EXISTING credential. That measures the same class (the store cannot be reached) without
    the extra credential that is not on the approved list.
  - The residual: M7 produces a refused CONNECT, not a wrong password, so the two messages may differ. The
    alert builders' detail line is the only consumer of the text.
  - **Ruled 2026-10-20 (Yigitcan): accepted.** D2 may close with S4's auth-failure shape open; the branch is
    drill M7 in D4, and its REVOKE/GRANT is an operator step.
- **Last round's declared deviations accepted (Yigitcan, 2026-10-20):** S2b (S2 re-created), the S5 PUT and
  the probe fix.

## 3q · D2b-3 close-out (2026-10-20): S1 ✅, the contract run ✅, D2 CLOSED

**Turnstile:** published `enabled: true` and a dummy token refused with 403, at the start and at the end.

**Edge refusals now carry S6's two signals, not the status alone.** Every temporary path was hit with no
token first, and each returned 403 with a Cloudflare Access header while the workflow's execution count
stayed the same (0 → 0). That held for S1's path and for S2c's two triggers, on both S2c runs.

**S1 ✅: two active workflows cannot hold one path (same method + path, which is what a cutover copy uses; a different method on the same path was not measured).**
- **Setup:** two throwaway workflows, A and B, each a webhook on the same Access-covered throwaway path
  plus a respond node with its own text. Neither uses a database credential.
- **Activating A:** 200.
- **Activating B with A active:** **409**, "There is a conflict with one of the webhooks". B read back
  inactive.
- **Owner-token request:** answered by A. A's executions went 0 → 1, B's stayed 0 → 0.
- **Control:** A deactivated → B activated (200) → the same request was answered by B.
- **Meaning for §3a:** the cutover order (deactivate the original, then activate the copy) is the only
  order n8n allows. A wrong order fails loudly. No design change.

**The contract run ✅** (`tests/db/contract-run.cjs`, as `salon_ro`; counts, rule names and field names only):
- **The instrument was shown to fail on empty tables first.** With no seed it went red on all five
  tables ("EMPTY: … measured nothing"), so a green run cannot come from reading nothing.
- **Seed:** 2 `mig-` rows per table, one full and one sparse. The sparse row carries `''`, `NULL` and a
  `false` checkbox where the table has such a column (`false`: appointments only; `''`: not bot_metrics).
  - They were written through S2c, S2's workflow re-created for the seed and the prefix-guarded clean-up,
    the same accepted pattern as S2b.
  - **Declared:** no other workflow was created.
- **Shaped SQL** (§3b's pattern: `NULLIF`, `jsonb_strip_nulls`, `CASE WHEN … THEN true END`,
  `salon.at_ts`):
  - **0 violations on all five tables.**
  - The full row carries every field key (conversations 16/16 · appointments 12/12 · leads 7/7 ·
    processed_messages 4/4 · bot_metrics 3/3).
  - The sparse rows' empty values were dropped, which is shown by no null, `""` or `false` violation.
  - Every number came out as a JSON number (`turn_count`, `lead_no` as `fields.id`, `cost_usd`).
- **Positive control:** the same rows read through a deliberately MIS-SHAPED query (no `NULLIF`, no
  strip, raw boolean, raw timestamps). On each table the control must catch EVERY rule class the seed can
  trigger there, and it did:
  - conversations, leads and processed_messages: null · `""` · field timestamp · `createdTime`;
  - appointments: the same plus a `false` checkbox;
  - bot_metrics: null · field timestamp · `createdTime`.
- **The control was shown able to fail. Each of the five rules this seed can trigger was switched off in a
  scratch copy of `shape.cjs`, and the run went red every time, naming exactly the rule removed.** The
  checker's other three rules (number, id, top-level keys) cannot be triggered by this mis-shaped query;
  they are shown red offline in `tests/contract/airtable-shape.test.cjs`, so "every number came out as a
  JSON number" above rests on a rule this database run does not turn red.

  | Rule removed | Red tables |
  |---|---|
  | null | 5 |
  | `""` | 4 |
  | `false` | 1 |
  | field timestamp | 5 |
  | `createdTime` | 5 |

  The red-table counts equal the number of tables whose seed exercises that rule.
- ⚠ **Declared script fault, fixed (pre-push audit, MEDIUM):** the first version passed the control on
  "any violation". Its raw `createdTime` (a JS `Date` from the driver) tripped one on every table, so the
  field rules could have been deleted with the run still green. Fixed as above. The run was REPEATED on a
  fresh seed through a second S2c, which was created and deleted like the first. The counts before and
  after are in the clean-up below.
- **Limit:** this proves the SQL PATTERN on every column type the schema has, read through the `pg`
  driver. The n8n node's own handling of the same output (jsonb parsed, ISO-ms-Z) was measured in S2. Each
  of D3's per-node queries is still checked against its consumers when it is written.

**Clean-up (measured):**
- **Counts as `salon_ro`, for each of the two seeds:** every table 0 before, 2 per table after the seed,
  and every table 0 after clean-up.
- **Each prefix-guarded delete removed exactly 2 rows per table.**
- **Four temporary workflows** (S1 A, S1 B, and S2c twice) were deleted, and each returns 404 on GET.
- **The live instance holds 5 workflows**, and none is temporary.
- **Both parity guards are 0.**

**D2 exit gate: MET.** The gate reads "every gate shown able to go red · every spike answered or its
design branch chosen".
- **Gates:** `check-sql-params`, `diff-workflow-copy`, the contract checker and the sanitizer test, each
  shown red (D2b-1). The contract checker is now also red on a mis-shaped query against the real database.
- **Spikes, all answered or with a branch chosen:**
  - **Answered:** S1 ✅ · S2 ✅ (corrected 2026-10-20) · S3 ✅ · S5 ✅ (branch: Q18 `independently`) · S6 ✅ ·
    S8 ✅.
  - **Branch chosen:** S4 (the SQL-error shape is measured; the auth-failure shape's branch is drill M7
    in D4, ruled) · S7 (ruled by Q13) · S9 (ruled by Q4: rides on D6c's export read).
- **Carried, not part of the gate:**
  - Q16 (split `salon_ro`'s column access before D5) *(moved to the final security pass, speed plan 2026-10-22)*;
  - the mandatory Phase 7 alert-detail fix;
  - M7's REVOKE/GRANT, an operator step in D4.

## 3r · D3 plan: APPROVED 2026-10-20 (Yigitcan, plan-gate), with rulings K-1 to K-7

The plan was presented in chat in the full `/plan-flow` format and built from reads of the committed
exports and the live instance at `2c467a5`. This section is its record. **Nothing in it has been built
yet.** Each step below ends in its own commit and verdict, and then stops for Cowork.

**Measured while planning** (live, read-only, 2026-10-20):
- Turnstile is up, and both parity guards are 0.
- **Draft equals published in all five workflows.** This matters for D3e: activating a workflow publishes
  its draft.
- Reminders fired at minute :00 in 60 of its last 60 executions.
- Purge fired at 02:00 UTC in 14 of its last 14.
- `whatsappSendDisabled` is the literal `true` in `Load Config (Reminders)`. Cowork confirmed the
  literal.
- Airtable `search` defaults to `returnAll: true`. This is quoted from n8n-mcp's node database; that
  it is the same on this instance's version was not measured.

**Rulings (Yigitcan, 2026-10-20):**

| | Ruling |
|---|---|
| **K-1** | D3a Drill State → D3b Owner Actions → D3c Reminders → D3d Purge, one copy each, each with its own verdict. **D3e (the Purge rehearsal) is separate, touches LIVE, and starts only on its own written go-ahead. It is NOT part of this round.** |
| **K-2 (widened)** | **S10 runs first.** It measures the Postgres node under `continueErrorOutput`, which ALL FOUR Q18 nodes and all ten Purge/Reminders data nodes use. S4 and S5 measured `continueRegularOutput` only, so **Q18 was unproven for its own configuration** until S10. S10 is the premise check for Q18 itself (below). **✅ S10 confirmed it, 2026-10-20.** |
| **K-3** | The copies' error paths are drilled in ONE operator window at the end of D3d, using a table-level `REVOKE`, then `GRANT`. D3a–D3c's verdicts mark their error paths "pending the shared window". *Recorded risk for D4: `REVOKE CONNECT` (M7) may not cut a pooled connection; a table-level `REVOKE` is checked on every statement.* |
| **K-4** | A schedule-triggered copy is active only during its drill minutes, because activating it for the temporary webhook also arms its schedule. The windows are :05–:50 for Reminders and away from the Purge tick. Executions are measured by mode: the copy must show **no** `trigger` execution. |
| **K-5** | The owner's Telegram chat is a permitted recipient for drill alerts. It is Yigitcan's own chat (§6: "owner alerts from drills, as today"). The NOT-build line "no real recipient" covers customers and third parties. |
| **K-6** | **Accepted as a recorded deviation.** If a row disappears between a node's Find and its write inside one run, `Stamp Reminded`, `Scrub Recent Messages`, `Delete Old Processed` and `Delete Old Leads` return `{success: true}` on Postgres, where Airtable raised an error and an alert. Unreachable as measured: no workflow deletes appointments or conversations, and the deletes run once a day. |
| **K-7** | **(b), daytime only (re-ruled 2026-10-22, speed plan; it was (a)).** *The first ruling was (a), full verification: the copy's scheduled run (`triggerAtHour: 4`), then the original's next scheduled run (two nights).* Now the rehearsal swaps and swaps back in daytime and measures `active` and `versionId`. **Recorded gap:** the copy never fires in trigger mode before the cutover. Its trigger node is identical to the original's, which the diff tool shows. |
| tool | `scripts/build-workflow-copy.py` is checked by `diff-workflow-copy.py` plus ONE selftest. No separate test suite. |
| **Q17 evidence (D3b)** | **ACCEPTED (Yigitcan, 2026-10-20).** The evidence is the true overlap on the pre-fix deploy, plus the race path measured identical node by node, plus S2b. The gap stays recorded, and the race is not re-tried. |
| **run-d11 bodies** | A 200 whose body carries `degraded` is a FAIL (ruling, 2026-10-20). |
| **deploy helper** | **Committed BEFORE D3c**, with its pre-drill checks inside it, automatic and fail-closed (ruling, 2026-10-20). |
| **race script** | Out of scope; not committed (ruling, 2026-10-20). |
| **binaryMode (D3c)** | **(a)** one PUT through `--update`, carrying the original's settings. If the API drops the setting again: **(b)** Yigitcan sets it on the copy in the editor (Workflow Settings), then `--verify`. **(c), accepting the difference, is REJECTED:** the setting's effect is unmeasured (ruling, 2026-10-20). |
| **settings parity** | The parity guards must compare workflow SETTINGS. This is its own small step **BEFORE D4**, not now. D3d is unaffected: Purge has no extra settings (ruling, 2026-10-20). |
| **hidden settings (iii)** | **Ruling (Yigitcan, 2026-10-22): (iii).** Settings an API-created copy loses are a CLASS: 1 on Reminders, 4 on Main including `callerPolicy`. The class is decided ONCE, in the settings-parity step before D4, not per workflow now. Options (i) and (ii) are not applied. **Reason on record:** one mechanism for the class; and (i)'s brake coupling would only hold at deploy time, not at the moment CP4d-2 opens the brake. |
| **settings-parity, first task** | On a THROWAWAY workflow (not a copy), measure which route, if any, preserves a hidden setting: an editor JSON import, or the CLI's `import:workflow`. Then make one class decision for Reminders and Main. **D3c's remaining work resumes after it:** `--verify`, `PAIRS`, the drills, and its error paths in a second, small K-3 window. The Reminders copy stays as it is: inactive, unpaired, 0 executions. |
| **K-3 closed (2026-10-22)** | **Ruling (Yigitcan):** K-3 is CLOSED for D3a, D3b and D3d, on the window's results (the K-3 result below) and the operator's closing evidence. *Operator statements, not Claude's measurements:* the window terminal froze after `baseline OK … Waiting for Claude's go` and showed no later line, so the `RESTORED` line was NOT seen. From a new session: no `k3-window` process running · `~/k3-flags` empty · `k3-window.sh --check` OK · `k3-restore.sh` OK (catalog 20/20, `salon_app` SELECT on all five tables). *Claude's measurement:* after `W2.done` the catalog read through `salon_ro` showed `salon_app` lacking nothing. Why the terminal stopped printing is not known. |
| **The 502 body (2026-10-22)** | **Ruling:** continuing the window past the replaced 502 body was acceptable. The copy behaved as planned inside (node, alert, row unchanged), and the edge layer changes that body for the original too. |
| **Two Phase 7 items (2026-10-22)** | **Ruling:** both are NAMED Phase 7 items, not migration regressions, because both exist in the originals ([PHASE-7-PLAN.md](PHASE-7-PLAN.md) §1, PHASE 7 bucket): (1) a release failure reaches the client as the edge's generic 502, not the `release_failed` JSON; the dashboard must decide on the status code, and where the body is replaced is measured there. (2) A leads READ error also emits a spurious `no_candidates` alert next to the real errors (`alwaysOutputData` leaves an empty item on output 0). |
| **D3e order (2026-10-22)** | **Ruling:** D3e waits. It opens in its own round, after the settings-parity plan is approved. |
| **settings-parity plan APPROVED (2026-10-22)** | **Ruling (Yigitcan, plan-gate), class option O1 (accept by evidence, per key), with amendments:** (i) the `binaryMode` reader search is redone at the source tag matching the running build (the version number is kept out of this public repo), with every reader listed; (ii) only T0 and the five guard mutants run now. **R1 (editor import), R2 (CLI `import:workflow`) and R3 (does a PUT preserve a present hidden setting) are NOT run; they move to D6b's plan as the O3 question.** `availableInMCP`: first measure, read-only, whether this instance's MCP server is enabled; the committed Main export takes the live value ONLY together with the ruling that follows from it. `docs/n8n-rollback.md`'s three contradicted statements are corrected in place. `staticData` and tags move to D6b's plan. Yigitcan does not remember whether Main's `availableInMCP` was turned on; there is no operator statement either way, so the measurement decides. |
| **settings-parity build, step 1: STOPPED (2026-10-22)** | **The instance-level MCP server is ENABLED** *(the response is measured; "enabled" is read against the source tag matching the running build (the version number is kept out of this public repo), and the running build's version was confirmed equal to that tag by the L2 `security-auditor`, read in the running container on 2026-10-22).* Probe on the origin over loopback, no credential: `GET /mcp-server/http` → **401** with `WWW-Authenticate: Bearer realm="n8n MCP Server"` and the body `Unauthorized: Authorization header not sent`. `HEAD` → **401** with the same header and no body. In the source, `mcp.controller.ts` puts `getEnabledMiddleware` FIRST on both routes: GET then runs the auth middleware (`mcp-server-middleware.service.ts`), which sends that 401, and HEAD's own handler sends its 401. With the server disabled, `getEnabledMiddleware` answers both with **404** `{"message": "MCP access is disabled"}`. *Controls:* a nonexistent sibling path returns the editor page (200), so the 401 is route-specific. The public API without a key returns a different 401 (`Unauthorized`, no `WWW-Authenticate`). *The edge:* from the internet every `/mcp-server/*` path is redirected to the Cloudflare Access login (302), with or without the API service token. So an outside MCP client needs an Access identity first; that is a second layer, not the server being off. *Consequence:* Main's `availableInMCP: true` is NOT inert. The brief's stop condition applies, so steps 2–5 were not run and Main's export was not changed. *Observation, cause unknown:* Main's draft `versionId` has differed from its published `activeVersionId` since 2026-10-22 12:49 UTC; nodes are in parity, so the change is not in the nodes. |
| **MCP exposure (2026-10-22)** | **Ruling (Yigitcan):** the instance MCP server STAYS ENABLED. Main's `availableInMCP: true` is recorded as an accepted EXPOSURE, behind two layers (Cloudflare Access at the edge, MCP bearer auth at the origin), and moves to the final security pass ([PHASE-7-PLAN.md](PHASE-7-PLAN.md), security pass list). Main's committed export takes the live value WITH this ruling. A copy's absent `availableInMCP` (that is, `false`, narrower) goes into the copy's allowlist with this ruling as its reference; at the cutover Main becomes less exposed, recorded as accepted. *For D4:* the T0 probe did not send `availableInMCP`, so whether the API keeps it on create is not measured. The D4 plan decides how the Main copy ends up without it. *Decided 2026-10-23 (D4-1, §3s): the deploy helper never sends an allowlisted key, and the guard reds one present on a copy.* |
| **Speed plan (2026-10-22)** | **Ruling (Yigitcan):** (1) the 7-day soak runs in the background and gates ONLY D6c's revocations; nothing else waits on it (D7's close no longer does). (2) **D3e is a DAYTIME-only rehearsal: K-7 changes from (a) to (b)** (D3e section). (3) Reminders' K-3 error-path drills fold into D4's M7 operator window: one window, not two. (4) Q16 (splitting `salon_ro`'s column access) and D6d (the permanent off-server target) move to the final security pass. **Unchanged and NOT cut:** the nightly `pg_dump` plus one restore test before the cutover · the Turnstile window protocol · Airtable is not deleted · drills and gates on every copy. |
| **settings-parity build result (2026-10-22)** | Run after the MCP ruling. **Main's draft vs published:** of 191 nodes, 174 differ ONLY in `position` and 17 are identical; connections, description and `nodeGroups` are equal; `name` is set on the draft and `null` on the published version record. Settings, pinData, meta, `staticData` and tags are not versioned, so they have no draft/published pair. *Declared reading:* a canvas re-layout, behaviour-neutral, so not a stop (the brief's "touches nodes" is read as "changes behaviour"). **`binaryMode` readers at the source tag** (a stream scan of the tagged source archive, 23,717 files, 34 non-test files mention it): every reader treats an absent value as `"separate"`. Core helpers default the parameter to `SEPARATE`; the engine, data proxy, Set, Form and ExtractFromFile compare against `COMBINED` only; the editor uses `?? DEFAULT_SETTINGS.binaryMode` (`SEPARATE`); the editor's settings dialog writes `"separate"` when the value is undefined (which is likely how Main and Reminders got it); the public DTO strips the key on create and update. The `binaryMode` in `ai-utilities` and `nodes-langchain` is an unrelated node parameter. **T0** (throwaway, 404 after): `settings: {}` reads back `{}`, so no default is added; the non-default values keep `callerPolicy` and `timeSavedMode` and drop `binaryMode`. **The guard:** `scripts/settings_parity.py`, used by `check-content-parity.py` (committed vs live; a paired copy vs its original through the copy spec's allowlist), by the diff tool and by the deploy helper's verify. The Main and Reminders exports now carry their live settings; before the refresh, the new guard was red on both (Main 4 keys, Reminders 1). The Reminders spec allowlists `binaryMode`'s absence. The six mutants are red (`tests/unit/settings-parity.test.py`, 13 cases, in `check-all`; *extended 2026-10-23 by D4-1 to 15 cases and eight mutants, an allowlisted key PRESENT on a copy now being red, §3s*), and two live mutants on the real guard exit 1. *The pre-push audit found two mutants of the rules that the first test version did not kill:* the "covers absent only" check disabled (mutant 6 had been red for a different reason), and the "committed but not live" branch disabled (no case). Both are killed now, shown by running each mutated module against the test. Settings that are not an object now fail loud instead of comparing as empty. `docs/n8n-rollback.md` is corrected in place. |
| **Main draft reading (2026-10-22)** | **Ruling (Yigitcan):** the reading of Main's draft diff is ACCEPTED: position-only changes plus a `null` name on the published version record are behaviour-neutral. The brief's stop wording "touches nodes" was Cowork's and too broad; the intent was "changes behaviour". **D3e approved** in its daytime form, together with writing the fresh raw export of the original Purge outside the repo, next to the D0 backups. |

**S10, the Q18 premise check** (the S2 pattern, a temporary workflow on the approved list):
- **Setup:** 3 items; item 2 fails on a row-dependent cast (the S5 lesson: a constant is folded at plan
  time); `continueErrorOutput`; modes `independently` and `single`.
- **Per mode it measures:** items on output 0, items on output 1, rows left, the error item's keys, and
  the exact detail string `Build Owner Alert (Purge|Reminders)` would build from it.
- **Q18 expects, under `independently`:** items 1 and 3 succeed on output 0, item 2 goes to output 1,
  and 1 row is left.
- **STOP condition:** any difference that changes what the four nodes' consumers receive stops the
  round, and Q18 is re-ruled before D3c.

**S10 result ✅ (2026-10-20): Q18's expectation holds, so no re-ruling.** Method:
- a temporary workflow, the S2 pattern;
- edge refusal shown with both S6 signals on both of its paths;
- the deletes run under `continueErrorOutput`, one branch per mode;
- the rows left read as `salon_ro`.

| Mode | Output 0 | Output 1 | Rows left (of 3) | Error item | Detail the builders build |
|---|---|---|---|---|---|
| `independently` | 2 items: rows 1 and 3 | 1 item | 1 (row 2) | the input's own keys plus `error` (an object); **no `message`**; no SQL text anywhere in the item | the value `[object Object]`, rendered `-object Object-` by the markdown escape; "failed items: 1" |
| `single` | 0 | 1 item | 3: the whole batch undone | `{error, message}`, `message` a string | the SQL error text (measured: `invalid input syntax for type integer`, followed by the seeded value), "failed items: 1" |

- **The detail strings were computed by running the builders' OWN statement**, extracted from the
  committed `Build Owner Alert (Purge)` and `Build Owner Alert (Reminders)` exports and run on the
  captured items. They were not computed from a hand copy.
- **Airtable's error items carried the input's keys too, under `continueErrorOutput`, by inference.**
  This is inferred from the live history of `Reminder Error (lookup)`, a downstream node that only spreads
  `...i.json`, and not measured on an Airtable node directly. It does not contradict §3p's "no other
  keys": the three nodes read there all run `continueRegularOutput`. The same split shows on Postgres
  (S5 against S10, next bullet). Those items carry the trigger's own keys alongside `error` (an object) and
  `message` (a string).
  - So the only TOP-LEVEL-KEY difference under `independently` is the missing `message`, which is what
    Q18 accepted.
  - The `error` object's inner structure was not compared.
- **The error item differs between the two `onError` modes.** Under `continueRegularOutput` (S5) the
  `independently` error item was `{error}` alone, with none of the input's keys. Under
  `continueErrorOutput` (S10) it carries the input's keys. A consumer's reading of one mode does not
  transfer to the other.
- **The mandatory Phase 7 alert-detail fix now rests on a measurement of these nodes' own configuration.**

**Common to every copy:**
- The copy is generated OFFLINE from the committed original by `scripts/build-workflow-copy.py`. Then
  `diff-workflow-copy.py --phase test`, `check-sql-params.py` and the contract check must be green BEFORE
  any live write.
- **Postgres node:** `executeQuery`, typeVersion 2.6, array `queryReplacement`. `onError` and
  `alwaysOutputData` are exactly the original's, and the diff tool enforces it.
- **Batching:** `independently` for the four Q18 nodes, the default `single` for every other node.
  With one item, `single` is per-item and keeps Airtable's error keys.
- **The shape spec moves out of `tests/db/contract-run.cjs`** into one module that the runner and the
  generator share (contract-integrity: one source). After the move, the five mutants are re-run: all
  five must go red, each naming its own rule.
- The copy's export is committed as `n8n/workflow.<x>.copy.sanitized.json` with a `PAIRS` line in
  `check-exports-parity.sh`, so a live copy cannot drift unguarded. `check-sql-params` will then count
  more than 0 nodes for the first time.

`⟨T⟩` below is table T's Airtable-shaped projection (`id`, `createdTime`, `fields`), the pattern §3q
proved on every column type.

**Flags are abbreviated below.** Every run passes `--allow` with the step's full data-node list (D3a 2 ·
D3b 5 · D3c 2 · D3d 8, the §6 names), plus `--phase` and the trigger flag WITH its name. The temporary
trigger is a NEW node named **`Temporary Test Trigger`**. *(Corrected 2026-10-22: it is in the D3c Reminders copy's
export, kept there for D4's M7 window; the D3d Purge copy's was removed for D3e.)* The diff tool's selftest uses its
own fixture name. **A copy's test path is a fixed `owner-mig-<workflow>` name with no random part.** It sits in
the committed copy spec and export, behind Access and the HMAC signature, exactly like the production paths the public
exports already carry. *(Corrected 2026-10-22: that holds for a moved REAL trigger. A temporary trigger feeds `Load
Config` directly, with no signature node in front, so Access is its only layer (Q13, S6).)* *(Corrected at D3a: this sentence first promised that no full test path would enter a commit, a promise
a committed copy export cannot keep.)*

**D3a · Drill State Read**
- **Flags:** `--allow "Read Conversation" "Count Markers"`; the webhook sits on an `owner-mig-…` test
  path (`--trigger "Receive Drill Read"`).
- **`Read Conversation`:**
  - SQL: `⟨conversations⟩ WHERE id = $1`, with `[$json.record_id]`.
  - Consumer: `Shape Drill State`.
  - 0 rows → `{}` (S2) → NOT-FOUND. An error → `{error, message}` (S4, `single`) → STORE-ERROR, through
    `!id && error`.
- **`Count Markers`:**
  - SQL: `⟨processed_messages⟩ WHERE message_id = $1`, with
    `[$('Verify Drill Signature').first().json.messageId]`.
  - The `WHERE` is the positive identity check Q11 asked of D3. A Postgres error item carries no `id`
    (S5).

**D3a result ✅ (2026-10-20): the Drill State Read copy is built, drilled and parked inactive.**

*Offline:*
- **The shape spec moved to `db/shape-spec.json`:** columns plus the kind → SQL templates. The contract
  runner and the copy generator both read it. **After the move, the five mutants were re-run on a fresh
  seed, and all five went red, each naming its own rule:** null 5 tables · `""` 4 · `false` 1 · field
  timestamp 5 · `createdTime` 5. The real run is green, and it is still red on empty tables.
- **`scripts/build-workflow-copy.py` generated the copy** from the committed original and
  `db/copies/drill-state.json`. Its one selftest is in `check-all`: every spec's copy must pass the diff
  tool's test phase and `check-sql-params`, and a spec that names a non-data node is refused.
- **The diff tool on the copy:** test phase green; the swap phase red, because the copy is still on its
  test path.
- **§4.1's positive controls were all red:** an unrelated node changed, a connection changed, a data
  node renamed, and a data node's `onError` changed. The clean copy is green.
- **`check-sql-params`:** 2 Postgres nodes, the first non-zero count.

*Against the database (`tests/db/copy-contract.cjs`, new, as `salon_ro`; ids never printed):*
- The copy's own two queries passed 7 of 7 cases: full row, sparse row, the `handoff` row and an absent
  id; a marker, a sparse marker and no marker. Each case returned the expected row count with 0 contract
  violations.
- **Control:** the same copy with `jsonb_strip_nulls` and `NULLIF` removed was red on the sparse rows.

*Live:*
- The copy was created INACTIVE and activated only for its drills.
- **Edge refusal on its test path, with both S6 signals:** 403 with an Access header, executions 0 → 0.
- **Signed oracle drills, all as expected:**

  | Case | Response |
  |---|---|
  | full row | `confirming\|book\|1` |
  | sparse row | `new\|\|0`: the empty `last_intent` is dropped and reads as empty |
  | the `handoff` row | `handoff\|clarify\|1` |
  | an absent id | `NOT-FOUND\|0` |
  | a wrong signature | 403 `REFUSED` |

- **Hostile `messageId` inside the allowed class:** `mig-pm-full--`, `--mig-pm-full` and `mig.pm_full` each
  counted 0 markers, where `mig-pm-full` counts 1, so the value was taken literally. A quote, which is
  outside the class, was refused 403 before any query ran.
- The drills changed no row.
- All of the copy's executions are `webhook` mode, and it was deactivated after the drills.

*Export and parity:*
- `n8n/workflow.drill-state.copy.sanitized.json` was taken from live. It equals the generated copy (the
  live-only `webhookId` is dropped, as in the other small-workflow exports), and it carries the Postgres credential placeholder.
- A `PAIRS` line puts it under `check-exports-parity`.

*Declared guard change, then narrowed (ruling, 2026-10-20):*
- **The problem:** `check-content-parity.py` refused the inactive copy ("PUBLISHED GRAPH UNAVAILABLE",
  exit 2). n8n removes `activeVersion` on deactivation, and nothing runs an inactive workflow.
- **The first fix (`4bca654`) passed ANY inactive workflow. Cowork found that this made a production
  workflow that went inactive green everywhere:** no other guard asserts that the originals are active.
- **Yigitcan's ruling:** the inactive pass is for migration copies ONLY, and an inactive original must go
  red.
- **Now:** a workflow counts as a copy only if the `PAIRS` array in `check-exports-parity.sh` pairs its id
  with a `.copy.sanitized.json` export. That array is the single place ids are already paired with
  exports, so no second list exists to drift. An inactive copy compares its draft. Any other inactive
  workflow exits 1 ("INACTIVE ORIGINAL").
- **Shown:**
  - live: the inactive copy is green and an active original is green;
  - `tests/unit/content-parity-inactive.test.py` (in `check-all`) passes 6 of 6 cases:

    | Case | Result |
    |---|---|
    | an inactive copy | pass |
    | an inactive original | 1 |
    | an inactive original that still shows a published graph | 1 |
    | an active workflow without a visible published graph | 2 |
    | a copy-named export with an unpaired id | 1 |
    | a copy's id on a non-copy export | 1 |

  - the old "any inactive passes" rule, restored as a mutant, fails four of them.
- **⚠ At D6b the roles invert:** the originals go inactive and the copies go active. This rule is
  revisited in D6b's own plan, not assumed to carry over.
- **Test path in a committed copy export: accepted as a recorded deviation** (ruling, 2026-10-20). An
  inactive copy has no listener, and the path is Access-covered and HMAC-signed.

*Clean-up:*
- 11 seed rows were deleted; counts went 0 → 11 → 0.
- The seed workflow returns 404.
- **The live instance now holds 6 workflows:** the 5 originals, active, plus this copy, inactive until
  D6b.
- Both parity guards are 0.

*Pending:*
- **STORE-ERROR** (the copy's error path) waited for the K-3 window. *Drilled there on 2026-10-22: see the K-3
  result.*

**D3b · Owner Actions** (`--trigger "Receive Owner Action"`)
- **`Find Target Conversation`:**
  - SQL: `⟨conversations⟩ WHERE id = $1`.
  - Consumer: `Validate Release Target`, which keeps rows with `id && !error`.
- **`Check Owner Replay`:**
  - SQL: `⟨processed_messages⟩ WHERE message_id = $1`.
  - Consumer: `Owner Replay Seen?`. An error fails closed: `is_replay = true`.
- **`Release Handoff Lock`:**
  - SQL: `UPDATE salon.conversations SET stage = 'new', last_intent = '' WHERE id = $1 RETURNING ⟨…⟩`.
  - Consumer: `Release Wrote?`, which tests `!error && !!id`.
  - 0 rows → `{success: true}` and no `id` → the release-failure branch, the same branch an Airtable error
    took. **Equivalent.**
- **`Re-read Released Conversation`:**
  - SQL: `⟨conversations⟩ WHERE id = $1`.
  - Consumer: `Write Verified?`. `NULLIF` drops the `''`.
- **`Record Owner Action Processed`:**
  - SQL (Q17 (a)): `INSERT … VALUES ($1, 'owner:dashboard', 'owner', $2::timestamptz) ON CONFLICT
    (message_id) DO UPDATE SET message_id = EXCLUDED.message_id RETURNING ⟨…⟩`.
  - Consumer: `Marker Written?`.
- **Measured: the alert builders never read a data node's output.** They read `Owner Replay Seen?` only.

**D3b result ⚠ (2026-10-20): the Owner Actions copy is built, `run-d11` passes 13 of 13 against the copies, and
the copy is parked inactive. The Q17 race could not be reproduced on the corrected copy.**

*Offline:*
- **Generated** from the committed original and `db/copies/owner-actions.json`. The marker takes the Q17
  (a) form.
- **The diff tool:** test phase green; swap phase red, because the copy is on its test path.
- **The positive controls were all red:** `Marker Written?`'s condition changed, its branches swapped,
  the marker's `onError` removed, `alwaysOutputData` added to it. The clean copy is green.
- **`check-sql-params`:** 5 nodes; 7 across all exports now.

*Against the database (`copy-contract`, as `salon_ro`):*
- The three read nodes passed 7 of 7 cases.
- A write node is refused by the tool.

*Live, edge:* refusal with both S6 signals on the copy's test path.

*Declared deploy fault, found while reading the drill's responses, and fixed:*
- **The fault:** the copy is generated from the SANITIZED export, and the first deploy swapped in only the
  Postgres credential. The live copy's three Telegram nodes therefore carried the placeholder chat id and
  credential id, and every success answered `degraded: alert_undelivered`. Nothing was sent: 5 alerts were
  undelivered.
- **Who caught it:** not the drill's pass/fail. `run-d11.sh` checks codes, state and the marker count,
  never the response body, so a `degraded` answer passes: the pre-fix run was 13 of 13 too. It was caught
  by reading the bodies.
- **The guard had it:** `check-content-parity` reports "LIVE IS SANITISED" on that copy. The fault was the
  ORDER: the drill ran before the guard.
- **The fix:** a copy is now deployed as the LIVE original plus only the generated copy's data-layer delta
  (the data nodes, the trigger's test path, a temporary trigger). Before any drill, two checks must pass:
  - no placeholder in the live copy;
  - `diff-workflow-copy` live original vs live copy: only the data nodes differ. The D3a copy was checked
    the same way and passed.
- **⚠ That is a PROCEDURE, not a committed control.** The deploy helper and the race script live in the
  session scratchpad and are not in this repo, and the two checks are run by hand before each drill.
  Committing the deploy helper is an open item before D3c.
- The D3b copy was corrected with one PUT (an approved edit), re-seeded, and every drill re-run.

*Drills on the corrected copy:*
- **`run-d11.sh`: 13 passed, 0 failed.** `OWNER_ACTION_URL` was the copy's test path, `STATE_URL` the D3a
  copy, and `TARGET_RECORD` a seeded `handoff` row with a fresh `last_updated`. The pre-fix run was also
  13 of 13.
  - Every refusal left the row unchanged.
  - The release wrote `stage='new'` and an empty `last_intent`.
  - The replay kept the marker count at 1 → 1.
  - The control (no token, 403) and the treatment (200) differ.
- **The Q17 race: ⚠ NOT reproduced on the corrected copy.** 15 attempts were made:
  - 3 plain pairs;
  - 9 pairs released together by a start barrier;
  - 3 rounds of 6 identical requests at once.
  
  Every time, exactly one execution reached the marker (1 marker row, the "written" path) and the others
  were refused 409 `not_locked`, the same as the original. **None took the marker-failure path.**
- **The one true overlap happened on the PRE-FIX deploy.** Both executions ran
  `Record Owner Action Processed`, both took `Marker Written?`'s "written" branch, and there was 1 marker
  row. That copy's race path (`Find Target` → `Validate` → `Check Owner Replay` → `Release` → `Re-read` →
  marker → `Marker Written?`) was identical to the corrected one; it differed only in the Telegram nodes
  AFTER `Marker Written?`. **Measured:** comparing node by node what the first deploy posted with the
  corrected live copy (ids, positions and `webhookId` ignored), the only non-data nodes that differ are
  the three Telegram nodes. The node sets and the connections are equal.
- **Together with S2b's statement-level measurement, this is the evidence for Q17 (a) on the copy. It is
  NOT the brief's "both on the written path" reproduced on the corrected copy, and it is recorded as that
  gap.**
- **Probe faults, declared:**
  - importing the race script re-ran its top level: 6 requests to already-released rows, all 409, nothing
    written. It is guarded now.
  - Seed rows were re-created between rounds.

*Outbound (K-5):*
- 16 Telegram alerts were delivered to the owner's chat by the corrected copy (release successes).
- No other recipient.
- Every execution of both copies is in `webhook` mode.

*Clean-up:*
- `run-d11` writes its marker as `d11-<run>`, not `mig-`. This round's prefix-guarded delete therefore
  also removed rows matching `message_id LIKE 'd11-%' AND sender_key = 'owner:dashboard' AND channel =
  'owner'`. Declared.
- Counts went back to 0, and 0 `d11-` rows are left.
- The seed workflow returns 404.
- **The live instance holds 7 workflows:** the 5 originals, active, and 2 copies, inactive.
- Both parity guards are 0, with 7 exports paired.

*Pending at the time:* the copy's error paths (replay-check unavailable, release failed) waited for the K-3
window. *Drilled there on 2026-10-22: see the K-3 result.*

**D3c · Reminders** (`--temp-trigger "Temporary Test Trigger"` → `Load Config (Reminders)`)
- **`Find Due Appointments`:**
  - SQL: `⟨appointments⟩ WHERE status = 'booked' AND NOT reminded AND start_utc > $1::timestamptz AND
    start_utc <= $2::timestamptz ORDER BY created_at, id`.
  - Consumer: `Build Reminder Payload`, which reads `fields.service`, `fields.start_utc`,
    `fields.sender_key`, `fields.channel` and the top-level `id`.
  - 0 rows, with no `alwaysOutputData` → no item, as on Airtable (S2).
  - An error → output 1 → `Reminder Error (lookup)`.
- **`Stamp Reminded`:**
  - SQL: `UPDATE salon.appointments SET reminder_sent = $2::timestamptz, reminded = true WHERE id = $1
    RETURNING ⟨…⟩`, mode **`independently`**.
  - Output 0 leads nowhere. Output 1 → `Reminder Error (stamp)`. K-6 covers its 0-row case.

**D3c status ⛔ STOPPED (2026-10-20) at the deploy helper's verify, as the brief's stop rule requires. No drill ran.**

*Done before the stop:*
- **Step 0:** the live original's PUBLISHED `Load Config (Reminders)` assigns `whatsappSendDisabled` exactly
  once outside comments, to the literal `true`, and the published `Send Disabled?` tests `=== true`. The
  draft is the same.
- **The pre-D3c rulings are committed:**
  - **the deploy helper**, `scripts/deploy-workflow-copy.py`: automatic, fail-closed checks, with its
    selftest in `check-all`.
    - *Corrected after the pre-push audit:* the first version said its three checks were each necessary.
      Switching them off pairwise disproved that, and the audit also found that the original itself passed
      as a "copy".
    - **The helper now has four checks, measured by switching each off in a scratch copy:**
      - **swapped** (every spec data node is Postgres on a real credential; the test path and the temporary
        trigger are present) is indispensable: without it the original itself passes.
      - **diff** is indispensable: without it a changed non-data node passes.
      - **placeholders** and **not-sanitised** overlap. Either one alone still catches every placeholder
        case, and together they are the only checks that see a placeholder inside a data node's parameters.
        That selftest case goes red only when both are off.
    - **"Reads back inactive"** is a separate check in `run()`, live only; the selftest does not cover it.
    - **Before a PUT, `--update` also requires the target's data nodes to be Postgres already.** An
      original's are Airtable, so a name collision cannot make an original look like a copy.
    - `--update` and `--verify` refuse the original's id, and any target that is active, not named as the
      spec, or whose data nodes are not Postgres. Shown live, read-only: an active production workflow was
      refused as a target.
    - Secrets travel in a 0600 header file, not in curl's argv.
  - **`run-d11` fails a degraded 200.**
- **The copy spec `db/copies/reminders.json` passes offline:** builder selftest; diff test phase green,
  swap phase red; `check-sql-params`; the deploy helper's selftest.
  - **Positive controls red:** `Send Disabled?` forced false, the send brake flipped in `Load Config`,
    `Stamp Reminded`'s `onError` changed.
  - **One control first came back GREEN: a temporary trigger wired past the kill-switch.**
    `diff-workflow-copy` allowed a temp trigger with ANY edges. Fixed: its edges must equal a real
    trigger's edges, with a new selftest case that goes green only when the rule is switched off. Declared.

*The stop:*
- The helper created the copy INACTIVE, then its diff check failed with **"workflow settings differ"**.
- **Measured (read-only):** the live original Reminders' settings are `{binaryMode: "separate",
  executionOrder: "v1"}`. The copy's are `{executionOrder: "v1"}`.
- The helper posted the live original's settings and got 200, yet `binaryMode` is absent from the copy
  it read back. That points to the public API dropping this setting on create; the drop itself is
  inferred, not probed.
- **The same class is wider.** The committed exports carry only `executionOrder` for every workflow, yet
  live Main also carries `availableInMCP`, `binaryMode`, `callerPolicy` and `timeSavedMode`.
  `check-content-parity` does not compare settings, so this live-versus-committed difference was
  invisible until now.
- Purge, Owner Actions and Drill State carry only `executionOrder`, which is why D3a and D3b verified
  clean.
- **State left:** the D3c copy is inactive with 0 executions, not paired, and not exported. The seed
  workflow is deleted (404), every table is 0, and both parity guards are 0.

*Decision:* ruled 2026-10-20, (a) then (b) (see the rulings table). D3d (Purge) is not affected by this
class; D4 (Main) is.

**D3c resume, 2026-10-20: (a) tried, the setting is dropped again, now MEASURED. ⛔ Stopped for the
operator's step (b).**
- **The write:** one `--update` PUT to the inactive D3c copy, through the deploy helper.
- **What was sent:** the body's settings were `{binaryMode: "separate", executionOrder: "v1"}`. This is
  shown by rebuilding the helper's body in memory from the same live original; the helper sends exactly
  `name`, `nodes`, `connections` and `settings`.
- **What came back:** the API answered 200, the copy read back `active: false`, and its settings read
  back as `{executionOrder: "v1"}`.
- **Conclusion:** the public API drops `binaryMode` on update. This is measured: the body was rebuilt in
  memory from the same live original, the answer was 200, and the read-back lacks the setting.
  - **The create half rests on the same evidence:** create and update send the same body, built by the
    same `assemble()` from the live original's settings, and the first deploy read back without it too.
  - **Not known:** whether the editor's Workflow Settings shows this field. `--verify` will tell.
- The helper's verify failed closed again ("workflow settings differ"). No drill ran.
- **Next:**
  - Yigitcan sets the setting on the copy in the editor (step (b));
  - then `--verify` must be green before any drill;
  - the copy goes into `PAIRS` only after that.

**D3c, 2026-10-22: (b) dead, ruling (A) "decide by measurement", and step 1 STOPPED on a binary-capable
node.**
- **Operator statement (Yigitcan, 2026-10-22), not verified by Claude:** the copy's Workflow Settings
  screen in the editor has NO binary-mode field. The fields shown are:
  - Execution Logic, Error Workflow, Timezone;
  - the four save options, two redact options;
  - Timeout, Available in MCP, Estimated time saved.

  Nothing was changed or saved.
- **So neither route tried so far can set `binaryMode`:** the API drops it (measured), and the editor's
  Settings screen has no field (operator). *This is an inference about those two routes only.* An editor
  JSON import or paste, and the CLI's `import:workflow`, were not tried. Cowork found no n8n documentation page
  for a per-workflow `binaryMode`, so its effect is unknown.
- **Also an operator statement, recorded only:** the copy's Timezone shows "Default – Europe/Vienna". D3d
  still measures the Purge schedule's timezone, as §3r requires.
- **Ruling (A), Yigitcan, 2026-10-22:** decide by measurement whether binary data can occur in Reminders,
  instead of setting the field.
- **Step 1, measured read-only:**
  - **(c) positive control:** the scanner (it counts node output items with a non-empty `binary`) finds 1
    in a fixture execution that carries binary, and 0 in one that does not.
  - **(b) history:** 335 retained executions of the original, 2026-10-08 → 2026-10-22, all `trigger`
    mode. **0 output items carry binary. But all 335 took the OPS-5 lookup-error path.**
    `Build Reminder Payload`, the dry-run, the Zernio node and `Stamp Reminded` never ran in that window.
    This zero therefore says nothing about the send path; it describes what the history covers.
  - **(a) static:** no Code node references `binary`, and the Telegram node is `sendMessage` with no file
    field. **But `Send Reminder (Zernio Template)` is an HTTP Request node whose options hold only
    `timeout`.** Its response format is therefore the default, `autodetect` (quoted from n8n-mcp's node
    database; that this matches the instance's version was not measured). With `autodetect`, a response
    that is neither JSON nor text comes out as a FILE, i.e. binary. *That behaviour is n8n's documented
    autodetect semantics, also not measured on this instance.* **That is a binary-capable node, a
    stop condition of the brief.**
  - **What keeps it from running today:** the measured send brake. `whatsappSendDisabled` is literal
    `true` in the published graph, so the node sits on the branch that never runs.
  - The history shows the node ran 0 times in that window, **but because of OPS-5, not because of the
    brake.** Every execution left at the lookup error before reaching `Send Disabled?`, so the brake
    itself was never exercised there.
- **⛔ Stopped before step 2.** No allowance was added, nothing live changed, and the D3c copy stays
  inactive and unpaired.
- **Decision for Yigitcan:** see the turn's report.
- **For D4 (step 4 of the brief, recorded now):** Main's four extra settings (`availableInMCP`,
  `binaryMode`, `callerPolicy`, `timeSavedMode`) each get their OWN measurement in the settings-parity
  step. There is no blanket allowance.

**D3d · Processed Purge** (`--temp-trigger "Temporary Test Trigger"` → `Load Config (Purge)`)
- **The `Find` nodes:**
  - `Find Old Processed`: `WHERE created_at < $1::timestamptz`. The `!= ""` guard disappears, because the
    column is `NOT NULL`.
  - `Find Stale Conversations`: `WHERE recent_messages <> '' AND last_updated < $1`.
- **The write nodes:**
  - `Delete Old Processed` and `Delete Old Leads`: `DELETE … WHERE id = $1 RETURNING id, true AS
    deleted`, **`independently`**.
  - `Scrub Recent Messages`: `UPDATE … SET recent_messages = '' WHERE id = $1 RETURNING ⟨…⟩`,
    **`independently`**.
- **`Count Leads Total`, `Find Old Leads` and `Count Leads After`:** the projection holds `created_at`
  only, as Airtable's `fields: ["created_at"]` did, with `WHERE created_at < $1` on the last two.
- **Consumers:**
  - `Aggregate Leads Total` and `Leads Purge Sane?` recognise a record by its `id`.
  - `Verify Leads Purge` reads `Delete Old Leads`' non-error items and `Count Leads After`'s `id` items.
  - `Count Leads After` runs once per delete item, as it does today.

**Q12 approval list:**

| Step | Workflows created, edited or activated, and temporary triggers | When they go, and how their absence is proven |
|---|---|---|
| S10 | one probe workflow (the S2 pattern) | deleted at the end of S10, GET returns 404 |
| D3a | "MIG COPY — Drill State Read" (inactive; test path; active during drills only) · a seed/clean-up workflow (the S2 pattern) | the seed workflow is deleted at the end of the step (404); the copy stays inactive until D6b |
| D3b | the Owner Actions copy, the same way · the D3a copy re-activated for `STATE_URL` · a seed workflow | the same |
| D3c | the Reminders copy plus its temporary trigger · a seed workflow | the same |
| D3d | the Purge copy plus its temporary trigger · a seed workflow | the same |
| D3e | removing the Purge copy's temporary trigger (an edit) · deactivating and re-activating the original · activating and deactivating the copy | `diff --phase swap` green (no temporary trigger; the path equals the original's) **and** the old test path returns 404 with the owner token |

Every temporary path's edge refusal is measured with both S6 signals: the Access header, and no
execution created.

**Outbound safety:**
- **D3a:** no outbound node.
- **D3b:** 3 Telegram nodes, all to the owner's chat (K-5).
- **D3c:** the Zernio node is behind `Send Disabled?`.
  - **Before D3c is built, the live `whatsappSendDisabled` is re-measured; if it is not `true`, STOP.**
  - The second layer: seed `sender_key`s are `widget:w-mig-…`, so the recipient is not a phone number.
- **D3d:** Telegram to the owner.
  - Today's behaviour, kept: no aged lead produces a `no_candidates` "purge-error" alert.
  - The seed carries 1 aged lead among at least 5, so the cap is at least 1 and a clean run alerts no one.
  - The throttle lives in each workflow's own static data.

**Drills** (§6 matrix and §4.3, named here, not restated):
- **D3a:** the state oracle: found, NOT-FOUND, the marker count and REFUSED. STORE-ERROR is in the K-3
  window.
- **D3b:**
  - `run-d11.sh`: 8 cases / 13 assertions. `OWNER_ACTION_URL` and `STATE_URL` point at the copies' test
    paths, and `TARGET_RECORD` at a seeded row. The id is read into a variable as `salon_ro` and never
    printed (Q16). Cowork read that with `STATE_URL` set, the script does not fall back to the Airtable
    PAT route.
  - Plus the **Q17 race:** two concurrent requests with the same `messageId` → 1 marker row, and both on
    the "written" path.
- **D3c:**
  - dedupe (one dry-run item, `reminded = true`, no second item);
  - re-arm by the seed workflow;
  - boundary appointments;
  - the 120 s concurrency guard.
- **D3d:**
  - aged rows go and fresh ones stay;
  - the PII scrub;
  - the leads TTL: a delete within the cap, `leads_purge_capped` and `no_candidates`.
- **All copies:**
  - a hostile `messageId` inside the allowed format;
  - the diff tool's positive controls;
  - alerts measured from the builder's output, not from Telegram alone (the throttle can make it `[]`).
- **The K-3 window drills every copy's error path.** The REVOKE and GRANT blocks are prepared for the
  operator:
  - `salon_migrator` → `SET ROLE salon_owner`;
  - secrets by env inheritance only;
  - guarded, each block self-verifying;
  - the GRANT block proves that `salon_app`'s SELECT works again.

**D3c result ✅ (2026-10-22): the Reminders copy is verified, paired, drilled and parked inactive.** Its error
paths ride in D4's M7 window (speed plan).
- **Verify** (deploy helper, with the spec's allowlist): green. Only the 2 data nodes, the test path and the
  temporary trigger differ from the live original; there is no new placeholder; the copy is not sanitised.
  `binaryMode`'s absence passes through the allowlist.
- **Paired:** `n8n/workflow.reminders.copy.sanitized.json` is in `PAIRS`; parity 9/9, the settings check
  included. The export is the generated copy with the LIVE copy's settings, because the API dropped
  `binaryMode`.
- **Contract:** the copy's own `Find Due Appointments` SQL run as `salon_ro`: 2 rows when 2 are due, 0 when none,
  0 shape violations; a write node is refused.
- **Outbound checklist:** `whatsappSendDisabled` is assigned once outside comments, to the literal `true`, both on
  the copy's draft and on the original's published version, and `Send Disabled?` tests "is true". Every seed
  recipient is a `widget:w-mig-d3c-…` label. Across all drills the Zernio node and the owner Telegram node ran
  **0** times, and every dry-run recipient was a seed label.
- **Drills (K-4: the copy was active only 20:05–20:10 and 20:10–20:15 UTC), each read from node outputs and
  `salon_ro`:**
  - first run: exactly the 2 due rows went through the dry-run and were stamped (`reminded`, `reminder_sent`). The
    boundary rows were not touched: one just beyond the 24-hour window, one in the past, one already reminded,
    one cancelled;
  - a second hit within 120 s: the concurrency guard returned nothing, and no node after it ran;
  - after 120 s: the two stamped rows were not selected again (dedupe). *Declared:* the "beyond the window" row
    had been seeded only 10 minutes past the cutoff. After 11 minutes it slid inside and was picked up, so the
    boundary was measured from both sides, but this run was not the planned empty run;
  - after a re-arm by the seed workflow: exactly the re-armed row went through;
  - **the empty case:** `Find Due Appointments` returned 0 items and `Build Reminder Payload` did not run, as on
    Airtable (S2). *Declared:* this came from an UNPLANNED second drill pass inside the same K-4 window, started
    when I imported the drill script as a module (its body ran on import). It was left to finish, because
    stopping it midway could have left the copy active; the script ends by deactivating the copy. The script is
    guarded against import now.
  - **All 8 executions:** `webhook` mode, `success`, 0 binary items; no `trigger`-mode execution.
- **Clean-up:** 6 seed rows removed by the prefix guard, so the tables are at 0; the seed workflow deleted (404);
  the copy inactive. **It keeps its temporary trigger** (`owner-mig-reminders`, behind Access) for D4's M7 window;
  the trigger is removed before any swap (Q13).

**D3e result ✅ (2026-10-22, the daytime form; approved by Yigitcan, ruling 2026-10-22).** It ran at 20:16–20:17 UTC (22:16 Vienna),
about six hours away from the 04:00 tick. *Declared reading:* "daytime" was read as "no night tick, at least an
hour from 04:00 Vienna", which is the brief's operational condition, not as a clock range.
- **Step 0:**
  - the original's draft equals its published version, nodes AND connections, by full-object comparison;
  - its `versionId` equals its `activeVersionId` (recorded);
  - a fresh raw export was written outside the repo, in a new directory next to the D0 restore point (mode 600,
    sha256 recorded beside it, content not printed);
  - the copy's temporary trigger was removed (the approved edit; 28 → 27 nodes, read back);
  - `diff --phase swap`, live original vs live copy, is green.
- **Step 1:** original deactivated (read back inactive) → copy activated (read back active, a published version
  present). Exactly one active.
- **Step 2:** copy deactivated → original re-activated. Read back: the original is active, the copy inactive, and
  `versionId` and `activeVersionId` are unchanged. Published equals draft, and the parity guards are green (9/9,
  settings included; structural 0).
- **Never both active:** the active flags were read back after every call.
- **Step 3:** no execution of either workflow in the window (original 14 → 14, copy 6 → 6).
- The copy's committed export now carries no temporary trigger (swap phase, Q13). The recovery path was armed
  and never needed.
- **Recorded gap (ruling):** the copy never fires in trigger mode before the cutover. Its trigger node is
  identical to the original's (diff tool, swap phase green).

**D3d result ✅ (2026-10-22): the Processed Purge copy is built, drilled and parked inactive.** Its error paths
waited for the K-3 window. *Drilled there the same day: see the K-3 result.*

*Offline:*
- **Generated** from the committed original and `db/copies/purge.json`. Eight data nodes; `Delete Old
  Processed`, `Scrub Recent Messages` and `Delete Old Leads` batch `independently` (Q18). The temporary
  trigger feeds `Load Config (Purge)`, which is what the real schedule feeds.
- **The diff tool:** test phase green; swap phase red, because the temporary trigger is present.
- **Positive controls, all red:** the lead cap raised, the purge cutoff shortened, `Delete Old Leads`'
  `onError` changed, the temporary trigger wired past `Load Config`.
- **`check-sql-params`:** 8 nodes; 15 across 8 exports now.

*Live:*
- **Deployed through `deploy-workflow-copy.py`; verify green.** Purge carries no extra settings, as
  measured, so the hidden-settings class does not touch it.
- **`copy-contract`:** 7 of 7 read cases.
- **Edge refusal:** both S6 signals.
- **Seed:**
  - 2 aged and 2 fresh `processed_messages`;
  - 2 stale conversations with text, 1 fresh, and 2 stale with an empty or NULL `recent_messages`;
  - 5 fresh leads and 1 aged, so the total is 6 and the cap is `floor(6 × 0.2) = 1`.
- **Three runs, through the temporary trigger:**

  | Run | Result |
  |---|---|
  | R1, clean | The 2 aged `processed` rows deleted, the fresh kept. The 2 stale conversations scrubbed; the fresh one and the empty/NULL ones untouched. The aged lead deleted, within the cap. `Count Leads After` gave `{}`, and `Verify Leads Purge` returned nothing: the arithmetic held, and no alert was sent. |
  | R2, nothing left | `no_candidates`. ONE owner alert was delivered ("branch: leads"), the original's current behaviour. |
  | R3, 3 aged leads added | `leads_purge_capped` (candidates 3, cap 1, total 8). No lead deleted. The alert was throttled: the builder returned `[]` within 30 minutes. |

- **Every run:** 0 binary items, `webhook` mode only. The copy was deactivated afterwards.

*Export, parity, clean-up:*
- `n8n/workflow.purge.copy.sanitized.json` is in `PAIRS`. Both parity guards are green, with 8 exports.
- The prefix-guarded delete removed 2 + 5 + 8 rows, and the tables are 0.
- The seed workflow returns 404.
- The Reminders copy is unchanged: inactive, unpaired, 0 executions.

**D3e fire times: MEASURED, read-only (2026-10-22).**
- **The setup:** the original Purge has no workflow-level timezone; its settings are `executionOrder` only.
  The published trigger is `scheduleTrigger` v1.3 with `{interval: [{field: days, triggerAtHour: 4}]}`.
- **What the trigger itself reports, in its own output, in all 14 retained executions (2026-10-09 →
  2026-10-22):** `Timezone: "Europe/Vienna (UTC+02:00)"` and `Hour: "04"`. Every one of them started at
  02:00 UTC.
- **So the copy fires at 04:00 Europe/Vienna:**
  - **02:00 UTC** until the clock change;
  - **03:00 UTC from 2026-10-25** (an inference from the zone name; not yet observed after the change).
- D3e's swaps stay at least an hour away from that time.
- The operator's editor observation ("Default – Europe/Vienna") agrees.

**K-3 error-path window: RUN 2026-10-22 and CLOSED (ruling, see §3r "K-3 closed"), results below.** It covers D3a, D3b and D3d; Reminders is excluded
(ruling (iii)).

*First operator run, 2026-10-22: stopped at the baseline check, nothing revoked.*
- The operator's prep passed (docker not in debug mode; both sha256 values matched). `k3-window.sh` then
  printed `permission denied for schema salon` and `cannot reach Postgres as salon_migrator — not starting`.
- **Cause (Cowork, from the script at `7836d42`):** the catalog checks ran as `salon_migrator` WITHOUT
  `SET ROLE salon_owner`. The migrator holds `salon_owner` with `INHERIT FALSE`, and schema USAGE is granted
  only to `salon_app` and `salon_ro` (`002_roles.sql`), so even resolving `'salon.<table>'` is denied.
- The script exited before its EXIT trap was armed, and before any REVOKE.
- The same defect sat in each stage's check, in the restore trap's check (it would have printed a FALSE
  `RESTORE FAILED` after a successful grant) and in `k3-restore.sh`'s 20/20 count.
- **Why the offline test did not see it:** its fake replaced `q()` whole, so the role context never reached
  the store. The handover listed the real psql path as unverified, and that was the gap that failed.
- **Fix, in the scripts only (no role or grant change):**
  - every statement now runs after `SET ROLE salon_owner`, placed inside `q()` (in `k3-restore.sh`, `owner()`),
    so no call can skip it;
  - a read-only `--check` mode proves the connection, the `SET ROLE` and the catalog read before the window.
    It runs no GRANT or REVOKE, so the first stage is the first time those run as `salon_owner`; a failure
    there rolls back and the trap reports it;
  - `k3-restore.sh` prints its own line when a step fails (before, `set -e` ended it on psql's raw error).

*Why four stages and not one:*
- A single REVOKE breaks each copy at its FIRST data node. Several error paths sit deeper: the replay
  check, a failed release, the unwritten marker, the delete and scrub writes.
- One operator window therefore runs four declared privilege stages, in an order that keeps rows to work
  on:
  - **W1:** UPDATE on conversations and DELETE on processed_messages and leads are revoked.
  - **R1:** SELECT on processed_messages and leads.
  - **R2:** SELECT on conversations.
  - **W2:** INSERT and UPDATE on processed_messages.

*The operator's scripts:* `db/ops/k3-window.sh` (REVOKE) and `db/ops/k3-restore.sh` (GRANT and proof).
- **How root gets them:** root FETCHES them from the pushed, reviewed commit through GitHub's raw URL for
  that SHA. It compares their sha256 with the values in the hand-over and runs them from `/root`.
- **Why:** root never runs a file from, or runs `git` inside, the unprivileged account's working tree.
  That account is the one Claude runs as, and letting it decide what root executes would cross the "Claude
  has no sudo" boundary (pre-push audit, M2).
- **Every stage** restores `salon_app`'s full grant and revokes its own set in ONE transaction. It then
  checks the catalog: if `salon_app` lacks anything other than exactly that set, it aborts.
- **A stage advances only on Claude's flag file.** The flag directory is in Claude's home, so no other
  local user can advance it.
- **On any exit (end, error, timeout, Ctrl-C) the EXIT trap tries to restore the full grant, then CHECKS
  it.**
  - It prints `RESTORED` only when `salon_app` lacks nothing.
  - Otherwise it prints `RESTORE FAILED — run k3-restore.sh` and exits non-zero (1, or the signal's status
    when a signal ended the run).
  - Further Ctrl-Cs are ignored during the restore. *That was measured by the pre-push auditor: without the
    ignore, a second SIGINT cut the GRANT off. The committed test does not cover it.*
  - *(Corrected after the pre-push audit, M1: the first version printed RESTORED without checking, and
    said nothing when the restore itself failed.)*
- **The window refuses to start if any of these holds:** `salon_app` is not at its full grant; the baseline
  catalog check fails (Postgres unreachable, or a privilege error); the flag directory is missing or not
  empty; another run holds the lock.
- **`k3-window.sh --check`** runs only the baseline check and exits; it issues no GRANT or REVOKE and needs no
  flag directory. The operator runs it first.
- **Secrets:** the passwords reach psql by environment inheritance only (`PGPASSWORD` + `exec -e NAME`).
- **The restore script** re-grants, checks 20 of 20 privileges in the catalog, and proves it by behaviour:
  it connects AS `salon_app` and SELECTs from all five tables.
- **Offline test, committed: `tests/ops/k3-window.test.sh`, 21 of 21, covering both scripts.**
  - **How it fakes the store:** only the `docker` word of each script copy is pointed at a fake (count
    asserted on the `docker` TOKENS outside comments; a source with two is refused at setup). A tripwire
    `docker` first on PATH records any escape, and its silence is the last case. `q()`, `as()` and `owner()`
    therefore run for real.
  - The fake checks the exact `compose … exec … psql` argument shape, and that the password arrives by
    environment.
  - **It models the role boundary of `002_roles.sql`:**
    - the session starts as the `-U` role;
    - a statement that touches `salon.` before `SET ROLE salon_owner` fails with `permission denied for
      schema salon`;
    - only `salon_owner` may GRANT or REVOKE.
  - **Red on the old scripts, green on the fixed ones:**
    - the `7836d42` scripts fail 15 of 21. In 11 of them the output is the operator's exact message; the
      other 4 fail because `--check` did not exist yet or a message text changed;
    - the fixed scripts with only the `SET ROLE` removed fail 11 of 21;
    - the cases that still pass never reach a statement that touches the schema (root, env file, flag
      directory, an unknown argument, an unreachable store).
  - `--check`: OK on a full grant without issuing a GRANT or REVOKE; names a missing privilege and changes
    nothing; fails when Postgres is unreachable.
  - a full run applies W1 → R1 → R2 → W2 and restores, with every statement run as `salon_owner`;
  - a wrong set aborts and restores;
  - a timeout restores;
  - a Ctrl-C while W1 is applied restores;
  - **the store going away during W1 gives RESTORE FAILED and exit 1, never a false RESTORED.** A mutant
    that claims RESTORED without checking is caught.
  - a non-full baseline refuses and changes nothing;
  - a stale flag refuses;
  - Postgres unreachable refuses;
  - a missing flag directory refuses;
  - a non-root user is refused;
  - `k3-restore.sh` restores to 20 of 20 and salon_app reads all five tables; a grant that does not take
    reports 18 of 20; a denied read, an unreachable store or a missing password each fail with the script's
    own line.

  It is not in `check-all`, because its waits add time.
- **Limit:** the fake still does not exercise real psql or Postgres. *(Corrected: this line used to say the
  call "is the same form as the D2b-2 operator blocks". The form was the same, but the role context was
  not, and that is what failed.)* The connection, the `SET ROLE` and the catalog read are proven by the
  operator's `--check` run before the window.
- **Operator check before running:** docker must not be in debug mode (`docker info --format '{{.Debug}}'`
  prints `false`). A debug daemon may log exec requests, and `-e NAME` carries the value inside that
  request. *(Audit LOW; that a debug daemon logs it is an assumption, not measured.)*
- **Timing (K-4):** the window opens at least an hour away from the Purge copy's schedule, 04:00
  Europe/Vienna (02:00 UTC until 2026-10-25, 03:00 UTC after). Activating the copy arms its schedule, and an
  unplanned run would consume the seed rows and alert the owner.

*Claude's side:*
- **Before `go`, with the full grant:**
  - seed: three fresh `handoff` targets t1, t2 and t3; a marker; the D3d seed rows;
  - activate the three copies;
  - the control: the D3a oracle on t1 reads normally.
- **Each stage is confirmed from the catalog through `salon_ro`** (it can read `has_table_privilege` for
  `salon_app`; measured) before its drills, and again after them. A drill run in the wrong state does not
  count.

| Stage | D3a (Drill State) | D3b (Owner Actions) | D3d (Purge) |
|---|---|---|---|
| W1 | oracle on t1 reads normally (the control: reads still work) | release t1 → **502** `release_failed`, release-failure alert built, t1 unchanged | **Delete Old Processed**, **Scrub Recent Messages** and **Delete Old Leads** go to output 1 → `Purge Error (processed / PII / leads)`. The detail VALUE is `[object Object]` (Q18, now on the real copy). Rows unchanged |
| R1 | `STORE-ERROR\|count-markers` | release t2 → **503** `replay_check_unavailable`, t2 unchanged | `Find Old Processed` and `Count Leads Total` errors → `Purge Error (processed / leads)`, detail = the SQL error text (`single`). The PII branch works normally |
| R2 | `STORE-ERROR\|read-conversation` | release any id → **404** `not_found` (a store error reads as "missing", the original's design) | `Find Stale Conversations` error → `Purge Error (PII)`. The processed and leads branches work normally |
| W2 | oracle reads normally | release t3 → **200** `{ok: true, degraded: "marker_unwritten"}`, t3 released, 0 marker rows, marker-failure alert built | — |

**K-3 result (2026-10-22, scripts at `484999a`).**

*How it ran:*
- The operator's `--check` returned OK *(operator statement)*.
- Before `go`, with the full grant:
  - the seed was in place (t1, t2 and t3 in `handoff`, one marker, the D3d rows);
  - D3a and D3b were active, and every test path was refused at the edge (both S6 signals);
  - the control: the D3a oracle on t1 read `handoff|clarify|1`.
- The D3d copy was active only for its own drill in each stage, then deactivated (K-4).
- Each stage was confirmed from the catalog through `salon_ro`, before its drills and again after them.
  All eight confirmations matched.
- After `W2.done` the catalog showed `salon_app` lacking nothing: the script's own restore, read through
  `salon_ro`.
- *A seed defect of mine was caught before `go`.* The D3d texts had gone into `last_intent`, because the
  column list was wrong. The snapshot showed no stale texts; the rows were cleaned by the prefix guard and
  re-seeded with the right columns.

*Measured, per stage:*

| Stage | D3a | D3b | D3d |
|---|---|---|---|
| W1 | `handoff\|clarify\|1` (control) | 502, t1 unchanged. Execution: `Release Wrote?` output 1 → release-failure alert built and sent → `Respond Release Failed`. **The body at the edge was `error code: 502`** (finding 1) | `Delete Old Processed` 0/2, `Scrub Recent Messages` 0/2, `Delete Old Leads` 0/1, each → its `Purge Error` node. Rows unchanged. **Detail `[object Object]`, owner text `-object Object-`: Q18 confirmed on the real copy.** One alert per branch, three built, three sent |
| R1 | `STORE-ERROR\|count-markers` | 503 `replay_check_unavailable`, t2 unchanged | `Find Old Processed` → `Purge Error (processed)` with the SQL error text. The PII branch scrubbed s1 and s2 and kept f1. Leads: both read errors reached `Purge Error (leads)`, **plus a `no_candidates` refusal** (finding 2). Builder 0 (per-branch throttle) |
| R2 | `STORE-ERROR\|read-conversation` | 404 `not_found` | `Find Stale Conversations` → `Purge Error (PII)` with the SQL error text. Processed deleted old1 and old2; leads deleted the one aged row (6 → 5), and `Verify Leads Purge` stayed silent. Builder 0 (throttle) |
| W2 | `handoff\|clarify\|1` | 200 `{ok: true, degraded: "marker_unwritten"}`. t3 released (`new`, empty `last_intent`), 0 marker rows, marker-failure alert built and sent | — |

*Across the window:*
- 12 copy executions (D3a 5, D3b 4, D3d 3): all in `webhook` mode, all `success`.
- Binary items:
  - D3a and D3d: 0;
  - D3b: 1 per execution, from `Receive Owner Action`'s `rawBody: true`. That is the HMAC raw body, by
    design, and the original's.

*Findings, carried (not fixed here):*
1. **The body of an origin 502 is replaced on the way to the client.**
   - What the client gets is `error code: 502`, not `{ok: false, error: "release_failed"}`. *Observed at the
     edge.* The replacement is attributed to Cloudflare's edge, but that was not measured at the origin, and
     the tunnel in between is also a candidate.
   - 503 and 404 bodies pass through unchanged.
   - The original's `Respond Release Failed` is the same node (502 in both exports). So the original is
     affected by construction, not by measurement: this is a shared behaviour, not a copy divergence.
   - A dashboard consumer has to key on the status code.
2. **A read failure in the leads branch reports twice.**
   - `Count Leads Total` and `Find Old Leads` carry `alwaysOutputData` with `continueErrorOutput`.
   - So besides the error item on output 1, each emits an empty item on output 0. The branch carries on
     and adds a `no_candidates` refusal next to the two real errors.
   - Nothing is deleted (the cap refuses), but the owner would read "no candidates" during a store outage.
   - The original carries the same settings.

*Deviation (declared):* the plan's oracle read after the restore was replaced by `k3-restore.sh`'s behaviour
proof (`salon_app` SELECT on all five tables). The copies had already been deactivated, per K-4.

*Clean-up, done:*
- the copies deactivated;
- the rows removed by the prefix guard (2 processed, 6 conversations, 5 leads), so the tables are at 0;
- the seed workflow deleted (GET 404);
- the flag files removed;
- both parity guards at 0.

*After the window, as planned:*
- the operator runs `k3-restore.sh`;
- Claude confirms 20 of 20 privileges through `salon_ro`, and an oracle read works;
- then the clean-up, the copies deactivated, and the parity guards.

*As run on 2026-10-22 (corrected here, see the deviation above):* the clean-up, the deactivation and the parity
guards came first, right after the window. The oracle read is replaced by `k3-restore.sh`'s `salon_app`
SELECT proof. *That proof came in afterwards (operator statement): `k3-restore.sh` OK, catalog 20/20, `salon_app`
SELECT on all five tables, run from a new session because the window terminal had frozen (§3r "K-3 closed").*
*Claude's 20-of-20 confirmation after it (measured 2026-10-22, 16:47 UTC, through `salon_ro`):* `has_table_privilege`
gives 20/20 for `salon_app`, and the missing set is empty. *The planned oracle read stays replaced (deviation above).*

*Owner alerts (K-5):* Purge alerts are throttled per branch for 30 minutes, so after W1 they are measured
from the error item and the builder's output, not from Telegram.

**D3e · the Purge rehearsal: ✅ DONE 2026-10-22 in its daytime form ("D3e result" in §3r). DAYTIME ONLY since 2026-10-22 (K-7 (b)): the
night-tick steps 2 and 4 below are superseded by the order in the box that follows.**

> **Order as re-ruled (2026-10-22):** (0) a fresh raw export of the original Purge, kept outside the repo · draft
> equals published measured · the original's `versionId` recorded · `diff --phase swap` green. (1) In daytime,
> away from 04:00 Vienna: deactivate the original → activate the copy → measure (exactly one active, read back).
> (2) Deactivate the copy → re-activate the original → measure `active` and that the `versionId` equals step 0's.
> No night runs. **Gap, recorded:** the copy never fires in trigger mode before the cutover; its trigger node is
> identical to the original's (diff tool).

*Fire times:*
- The fire times are recorded from a MEASUREMENT taken in D3d: the instance's timezone setting plus the
  schedule's cron configuration.
- They are not taken from the assumption that 04:00 is Vienna time.
- The executions measured so far fired at 02:00 UTC. The European clock change on 2026-10-25 is exactly
  the kind of assumption that measurement settles.

*Order:*
0. **A FRESH raw export of the original Purge is taken and kept OUTSIDE the repo, next to the D0
   backups.** Also in this step:
   - draft equals published is measured;
   - the original's `versionId` is recorded;
   - `diff --phase swap` must be green;
   - the aged and fresh `mig-` rows are seeded. *(Superseded 2026-10-22: the daytime rehearsal runs no tick, so no
     seed is needed.)*
1. At a daytime slot away from the tick: **deactivate the original FIRST**, then activate the copy. Each
   call's timestamp and the read-back `active` flags are recorded: exactly one is active.
2. At the copy's tick, its `trigger` execution is measured:
   - aged `mig-` rows gone and fresh ones kept (`salon_ro` counts);
   - the leads arithmetic correct;
   - no alert.
3. Daytime: deactivate the copy, activate the original. Its `versionId` must equal the one recorded in
   step 0, and exactly one is active.
4. At the next tick, the original's `trigger` execution exists. Under OPS-5 it may be an Airtable error
   plus an alert; it still proves the original ran.
5. The copy is left inactive, and the clean-up runs.

*If any verify fails:* deactivate the copy and re-activate the original at once (step 3). If the
`versionId` moved, restore from the fresh raw export.

*Longest window with neither active:* two sequential API calls, seconds. If the copy's activation is not
200 within 60 s, the original is re-activated at once; the bound is about 3 minutes. The swap happens away
from the tick, so **no tick is missed.**

*Side effect (night order, superseded 2026-10-22: the daytime rehearsal skips no night):* the original's Airtable clean-up is skipped for one night. Its filter is "older than the
cutoff", so the next run catches up.

**Acceptance per copy:**
- diff (test phase) green;
- `check-sql-params` green with more than 0 nodes counted;
- the contract check green;
- the drills green;
- the outbound checklist holds;
- clean-up back to 0;
- the export committed and covered by parity;
- Turnstile measured at the start and the end.

**D3 ends WITHOUT D3e:** four copies green, and every error path drilled in the K-3 window.

**Automation-fit:** neither. Every step is a gated live write or a wait.

## 3s · D4 plan: APPROVED 2026-10-23 (Yigitcan, plan-gate), with rulings D4-1 to D4-9

The plan was presented in chat in the full `/plan-flow` format, built from reads of the committed export and the
live instance at `8843aff` (read-only, no commit). This section records the approval, the rulings and each step's
result. **D4 runs in three steps, each committed and stopped for review:** D4a (offline build) → D4b (the copy's
live drills) → D4c (the M7 operator window).

**Read by Cowork from the committed Main export @`8843aff`, recorded with the approval:** Main has exactly ONE trigger,
the webhook `barber-inbound`, so moving it to the copy's test path moves BOTH lanes (widget and whatsapp) · the
calendar calls are HTTP nodes · the calendar id in `Load Config` is a group calendar.

**Measured while planning (2026-10-23, read-only):**
- Main: active · `versionId` and `activeVersionId` unchanged since the settings-parity round (the values are kept out
  of the repo) · draft equals published apart from node positions. 5 originals active, 4 copies inactive, every table 0.
- Database `salon` is owned by `postgres` (`pg_database.datdba`, read through `salon_ro`), so `salon_owner` cannot
  REVOKE CONNECT on it (§3r K-3's recorded risk, now with its mechanism).
- No `salon_app` session was open in `pg_stat_activity`. *Not evidence yet:* that read was not shown able to see
  another role's sessions; M7 measures it with a positive control.
- The stage CHECK: every stage literal Main writes (9) is in the list (§3d); the rest is the stored value passed back.
- `Validate Payload` bounds `senderId` to `^[A-Za-z0-9:+._-]{3,80}$`, so no quote or comma reaches a formula.
- The deploy helper sent the live original's settings as they were, `availableInMCP: true` included, and the
  settings guard passed an EQUAL value on a copy. So a Main copy would have been created exactly as exposed as Main
  with every guard green. *Whether the API keeps `availableInMCP` on create is not measured;* the instance's API spec
  lists it as an ordinary setting ("Defaults to false"), not as derived like `binaryMode`.

**Rulings (Yigitcan, 2026-10-23):**

| | Ruling |
|---|---|
| **D4-1** | **Yes.** A key a copy spec allowlists must be ABSENT on the copy: present is red, whatever its value. The deploy helper never sends an allowlisted key. Main's copy allowlists `binaryMode` and `availableInMCP`. |
| **D4-2** | **Accepted, as an extension of K-6.** A 0-row UPDATE on `Update Appointment Cancelled`, `Update Appointment (Reschedule)` or `Record Alert Class` returns `{success: true}` on output 0 on Postgres, where Airtable raised an error and an alert. It needs the row to vanish inside one run, and no workflow deletes appointments or conversations. |
| **D4-3** | **Measure first, rule after.** Whether a `single`-batching Postgres error item under `continueErrorOutput` carries the input's keys is measured in M7-T3 (`Save State` fails). Its consumers (`Send Error Response`, `Lead Unavailable Reply`, `Booking State-Unsaved Reply`) spread `$json` into the owner alert; the customer reply does not depend on it. |
| **D4-4** | **SET every mapped column, `created_at` included (1:1).** On Postgres one `created_at` column serves both Airtable's `createdTime` and its `created_at` field; nothing reads an appointment's `createdTime` (searched: one code comment). |
| **D4-5** | **NOT cleared** at approval: whether the calendar in `Load Config` holds no real bookings was unconfirmed, and it gated every calendar-writing drill (G1–G3, G12). D4a was unaffected. *Cleared 2026-10-23 by Yigitcan with a canary ("Salon Bookings" is a separate calendar; D4b result below).* |
| **D4-6** | **Yes.** The drill spend row (`bot_metrics`, the current UTC month: no `mig-` prefix is possible, the key IS the month) is deleted at the end by that one key, a declared exception to the prefix guard, and its total is reported. The drills stop if the month's row passes **1.00 USD**. |
| **D4-7** | **Yes.** `testing.md` rule plus `scripts/check-import-safe.py`, in `check-all`, and run over a window's own scripts before the window. |
| **D4-8** | **Yes, constrained.** The termination targets ONLY `usename = 'salon_app' AND datname = 'salon'`; the superuser performs exactly two kinds of statement (GRANT/REVOKE CONNECT, that termination); the offline test proves that no other statement can run as superuser; `--check` runs first; writing `~/m7-flags` is approved for the window. **Cowork reads the script before the operator runs it.** |
| **D4-9** | **Yes.** `tests/run-regression.sh` gains optional env vars; unset, they leave every request as it was. |

**D4a · offline build ✅ (2026-10-23).** Nothing live was written, activated or called; the only live reads were
`salon_ro` contract reads, and Turnstile at the start and the end (403 both times).
- **`db/copies/main.json`:** 17 queries, the trigger on `owner-mig-main`, `settings_allow` `binaryMode` +
  `availableInMCP`. Every node keeps `single` batching (one item each). Upserts SET exactly the mapped columns
  (D4-4); `Record Processed` stays `DO NOTHING` (Q17); the three multi-row reads order by `created_at, id`.
  *Declared:* `last_intent`'s parameter carries `?? null`, so an undefined value binds as NULL instead of relying on
  how the driver formats `undefined`.
- **Generated copy:** diff test phase **green**; swap phase **red** (the trigger is on its test path); §4.1's positive
  controls each **red** (an unrelated node · a connection · a renamed data node · a data node's `onError` · its
  `alwaysOutputData` · the Turnstile literal in `Load Config`); `check-sql-params` counts **17** Postgres nodes;
  `build-workflow-copy --selftest` green with the new spec.
- **The 8 read queries, as `salon_ro` (`tests/db/copy-contract.cjs`, 32 cases, all green):**
  - *Declared method change:* the tables are empty and D4a may not write, and `salon_ro` can neither INSERT nor
    create a temp table. So each query ran twice: **(i) its exact text against the real table**, 0 rows, which
    proves the text, the privileges and the parameter types and measures no shape; **(ii) against fake fixture
    rows** (`tests/db/fixtures/main-reads.json`, all `mig-d4`): the runner's new fixture mode swaps only the
    `FROM salon.<table>` source for `jsonb_populate_recordset(NULL::salon.<table>, …)`, the table's own row type,
    and keeps the copy's projection, WHERE, ORDER BY and parameters.
  - Fixture results: full and sparse rows found 1 each, other senders and a cancelled row excluded (the booking
    reads return 2 of 4), misses 0, **0 violations**.
  - **Control:** the same copy with `jsonb_strip_nulls`, `NULLIF` and the boolean `CASE` removed is **red on all 8
    nodes** (empty strings, null, `false`, a non-ISO timestamp).
  - **The seeded real-table run of the same queries is D4b's**, through the seed workflow it already plans.
- **Settings guard (D4-1):** `copy_vs_original` reds an allowlisted key PRESENT on a copy. `tests/unit/settings-parity.test.py`
  now has 15 cases and each red case must name the rule it trips. *Found while doing it:* after the rule change,
  mutant 3 and the `executionOrder` case went red for the WRONG reason (the copy still carried `availableInMCP`); both
  were fixed to isolate their own rule. Against the OLD rule the new mutants 7 and 8 (an equal value on the copy) are
  green, so the test measures the change.
- **Deploy helper:** `assemble()` drops every allowlisted key from the request. `--turnstile off|on COPY_ID` writes
  the ONE Turnstile literal in an INACTIVE copy's `Load Config` (refused unless exactly one literal exists, it is in
  the opposite state, and the target is the inactive, named, Postgres copy). After `off`, the copy with that literal
  put back in memory must pass the full verify; after `on`, the full verify. Selftest: green on every spec, with new
  cases (an allowlisted key kept with the original's value → red · a second literal or another node changed with
  the lowered gate → red · `on`-check while still off → red · off twice, on while on, two literals → refused).
  - **Mutants:** `assemble()` keeping the keys → selftest red (Main's and Reminders' clean copies); the `off` check
    returning green → red. *Declared:* a second, textual `Load Config` comparison in the `off` check was written
    first; its mutant SURVIVED, because the verify already reds every other difference, so it was removed.
- **`db/ops/m7-window.sh`** (operator script) and **`tests/ops/m7-window.test.sh`** (offline, 29 checks, green):
  stages C1 (REVOKE CONNECT + terminate `salon_app`'s sessions in `salon`) · T1 (`appointments` UPDATE) · T2
  (`bot_metrics` SELECT) · T3 (`conversations` INSERT, UPDATE); `--check`; `--restore`; C1's positive control (what
  `salon_migrator` saw before must not be fewer than what the superuser terminated, or its "0 open" is blind and C1
  aborts; with no session open it says the control was not exercised); the k3 pattern otherwise
  (lock, flags, a trap that restores and checks, stage-by-stage catalog checks).
  - **The D4-8 boundary, proven offline three ways:** across every scenario the superuser received only the three
    allowed statements · the code names the `postgres` role in one call, inside `superuser()`, which takes a keyword
    mapped by a `case` and passes no stdin · the function run in isolation sends GRANT CONNECT only when SQL is piped
    at it, and refuses unknown keywords. `--check` proves the superuser path with the GRANT itself, a no-op while the
    grant stands, and sends nothing when the state is not baseline.
  - **Mutants, each red against the test:** stdin passed through `superuser()` · an extra superuser statement · no
    termination · a check run as the superuser · `--check` granting before it checks · a termination without
    `datname` · the termination before the REVOKE · C1's visibility control removed (8 of 8).
  - *Not measured:* how the superuser authenticates (the container's local socket, no password). The operator's
    `--check` decides it.
  - *Declared:* like `k3-window.test.sh`, the test is not in `check-all` (it waits on real flag timeouts).
- **`tests/run-regression.sh`:** `CURL_HEADER_FILE`, `SESSION_PREFIX`, `MESSAGE_PREFIX` and **`LEAD_MARKER`**.
  *Declared:* `LEAD_MARKER` is a fourth variable beyond the three the plan named; the plan's own mock-data rule needs
  it, because a `leads` row carries no sender or message id for the prefix guard. With a fake `curl` and a fixed
  clock, the 46 requests are byte-identical to the old harness with no variable set; with all four set, 46 of 46
  carry the header file and the prefixes.
- **Pre-push audit follow-ups (declared, `security-auditor`, push PASS):**
  - **HIGH, fixed:** with `--turnstile` beside `--update` or `--verify`, the guards checked one id and the PUT went
    to the OTHER, unchecked one; the auditor's stub run sent the copy's content to the original's id. The three write
    modes are now exclusive (refused in `main()` and again in `run()`, before any API call), and the Turnstile PUT
    asserts it targets the checked id. Selftest: the three pairs refused with 0 API calls; each of the two guards,
    removed alone, turns the selftest red.
  - **LOW, fixed:** C1's "0 open" had no positive control (above) · the Ctrl-C case now also asserts it did not exit
    through the flag timeout · the harness says where the header file must live (outside the repo, 0600, deleted
    after) · Main's version ids are no longer written here.
- **`scripts/check-import-safe.py` + the `testing.md` rule (D4-7):** in `check-all` (selftest + `scripts/` and
  `tests/`: 13 files, 4 live-capable, 0 faults). Two top-level lines in the deploy helper carry the `# import-safe:`
  reason (offline siblings). On the scratch scripts: the D3c drill script with its guard is green; without it, red.

**D4b · the Main copy's live drills ✅ (2026-10-23).** Everything ran on the copy's test path through the owner
service token, widget channel only, the copy activated per drill block and deactivated after each one.
- **Start:** `check-import-safe` green over the window's own scripts · Main's `versionId`/`activeVersionId` recorded
  privately (compared again at the end; not written into the repo) · Main Turnstile 403 · every table 0.
  *Declared:* the brief asked for the check "over the scratchpad"; it was red on 84 faults, all in the earlier rounds'
  scripts, so those were moved into an archive folder there (reversible), and the check ran green over what remained.
- **Copy:** created inactive by the deploy helper, verify green. Live settings: `callerPolicy`, `executionOrder`,
  `timeSavedMode`, equal to Main's; `availableInMCP` and `binaryMode` absent (D4-1).
- **Seeded contract (completes D4a's method):** the seed workflow (S2 pattern; its four paths each refused at the edge
  without a token) wrote fake `mig-` rows; the 8 reads, taken from the LIVE copy, ran against the real tables as
  `salon_ro`: 24/24 green; cleaned back to 0.
- **Turnstile window on the copy (§4.5):** before it, the copy's literal `true` · E, a request with no token → 403 at
  the edge with the Access header, execution count unchanged · owner token + dummy Turnstile token → 403
  `turnstile_failed`, no data or LLM node run. `--turnstile off` at 20:23:03 UTC, `on` at 20:51:53 UTC (about 29
  minutes; the copy was inactive between drill blocks). After `on`: literal `true`, full verify green, E refused again,
  the dummy token 403 with no data node. Main: 403 at the start and the end.
- **D4-5 cleared by a canary.** Yigitcan: "Salon Bookings" is a separate calendar with no entries this week (operator
  screenshot). **G1** booked Mon 26 Oct 15:00 Vienna, after the 25 Oct DST change: `start_utc` 14:00 UTC (+01:00),
  `Book Appointment` → `Verify Slot` → `Write Appointment` → `Save State (Post-Write)`. The round stopped there;
  Yigitcan confirmed the event in "Salon Bookings" *(operator statement, not API-verified)*.
- **G2, the canary's removal:** cancelled through the flow ("Cancel your…" → "…is cancelled"). (i) `Delete Booking
  Event` 204 · (ii) the same slot asked again: the copy's own `Get Calendar Busy` returned 0 busy intervals for the
  whole day · (iii) the row is `cancelled`. `Build Cancel-Aborted State` did not run.
- **G12, the same slot rebooked after the cancel (observed path):** Google answered **409 `duplicate`**, because the
  deterministic event id stays reserved by the cancelled event → `Get For Reconcile` 200 with status `cancelled` →
  `Verify Reconcile` false → `Build Reconcile-Handoff State`: handoff and an owner alert, no new event, the row stays
  `cancelled`. `Write Appointment`'s `ON CONFLICT` branch was therefore NOT reached. The path is calendar-side and the
  topology is the original's. *Product observation, not a migration difference:* a customer who cancels and then
  rebooks the exact same slot and service is handed to a human.
- **G3:** booked A (27 Oct) → moved to B (28 Oct): "Moved", the row points at B with `reminded` false, `Delete Old
  Event (Reschedule)` 204, no orphan state → B cancelled (204, row `cancelled`).
- **G4–G11:** `tests/run-regression.sh` against the copy's path with the D4-9 variables: **28/28**. Its bookings use the
  suite's own date (24 Oct, before the DST change; the DST case is G1's). From the execution data: `Capture Lead` once,
  `Lead Unavailable Reply` never · alerts went through `Find Conversation Row` → `Record Alert Class` · the duplicate
  `messageId` stopped at `Check Processed` with no `Extract Intent` · the invalid payload's 400 ran no data node · the
  handoff lock ran no LLM.
- **H1:** 4 in-class hostile `messageId`s (`--`, `.`, `_`, `:=+/`) → 200, each stored literally in its own
  `processed_messages` row; 5 out-of-class (quote, comma, space, `;`, newline) → 400, no data node. **H2:** 4 in-class
  `sessionId`s → 4 separate conversations; 7 out-of-class (the same five, `%`, 81 characters) → 400, no data node.
- **M5a:** the month's `bot_metrics` row set to 10.00 → `Spend Gate` output 1, `Extract Intent` not run, a
  deterministic handoff reply, a `spend_cap` alert. The measured total was written back afterwards.
- **Output shapes from the execution data (the plan's write-shape criterion):** every output item of the 17 Postgres
  nodes across the copy's 85 executions, checked with `tests/contract/shape.cjs` (field types from
  `db/shape-spec.json`): **0 violations**. Each of the 17 produced records at least once, and the five 0-row paths gave
  `{}` (`Load State`, `Check Processed`, `Find Booking`, `Find Booking (Reschedule)`, `Read Spend`). Control: four
  mutated outputs are red, each on its own rule (top-level keys, a null field, `createdTime`, a numeric string).
  *Declared:* a scratch script, not committed; the rules it calls are the committed ones.
- **External effects:** calendar events created 8 = deleted 8 (counted from the execution data, ids never printed).
  Final sweep: every drill day read through the copy's `Get Calendar Busy`: 0 busy intervals, 0 drill slots busy.
  Positive control for that read: during the suite, two `Get Reschedule Busy` reads saw 1 busy interval while a drill
  booking stood. `Send WhatsApp (Zernio)` ran 0 times. LLM spend **0.169342 USD** (round stop 1.00). Owner alerts went
  to Yigitcan's chat (K-5).
- **Observation, the same in the original:** on a session's FIRST turn an alert's `Find Conversation Row` runs before
  `Save State` creates the row, returns 0 items, and `Record Alert Class` does not run, so that alert's throttle is not
  recorded (seen on a pre-hours date alert and on M5a). The original's node has the same flags (no
  `alwaysOutputData`, `continueErrorOutput`) and the same order.
- **Export and pairing:** `n8n/workflow.main.copy.sanitized.json` is the generated copy with the live copy's settings;
  `PAIRS` 10/10; `check-sql-params` counts 34 Postgres nodes in 10 exports. Controls on the new pair: the export with
  its Turnstile literal flipped → red (`Load Config` drift); with `availableInMCP` added → red (settings).
- **Clean-up:** the prefix-guarded delete (32 conversations, 6 appointments, 67 processed messages, 1 lead) and the
  declared single-key delete of the month's row (D4-6; it held 0.169342) → every table 0; seed workflow 404. **End
  state:** 5 originals active, 5 copies inactive and paired; Main's version ids unchanged; Main Turnstile 403.
- **Not in D4b:** M5b, M7, T3 and the Reminders error paths (D4c). D4-3 stays open until M7-T3.
- **✅ D4b CLOSED by Yigitcan (2026-10-23).** The two observations (the rebooked just-cancelled slot; the first-turn
  alert class) are not migration regressions and are NAMED Phase 7 items ([PHASE-7-PLAN.md](PHASE-7-PLAN.md), open
  items). **For D4c:** Cowork read `db/ops/m7-window.sh` at `426446a` line by line and approved it as written
  (sha256 `61b0b80f5f02a9fd9e923b2b119d9bbaa094948a304f0e2a02185a285f1cd4ba`); writing `~/m7-flags` during the window and
  activating the Main and Reminders copies for the M7 drills are approved (Reminders per K-4, minutes :05–:50).

**D4c · the M7 window ✅ run 2026-10-23; ⏸ STOPPED for the D4-3 ruling.** The operator: `--check` OK, baseline OK
*(operator statement)*. Two more approvals for this window (Yigitcan, in writing): the seed workflow "MIG SEED — D4c"
with T1's fake due row and the clean-up, and two `--turnstile` PUTs on the inactive Main copy. Claude wrote the flags;
before every stage the script's state was confirmed from the catalog through `salon_ro` (CONNECT and the 20 table
privileges). Timeline (UTC): `go` 21:30:19 · C1.done 21:30:56 · T1.done 21:33:20 · T2.done 21:33:51 · T3.done 21:34:42
· the catalog back at full access right after.
- **Before `go`:** the seed workflow's three paths refused at the edge; T1's due row written (`booked`, not reminded,
  starting 3 hours ahead). **Session-count positive control:** right after the seed request, `salon_ro` counted 1
  `salon_app` session, so its count is not blind. The Main copy's Turnstile literal off at 21:30:12.
- **C1 (CONNECT revoked, sessions terminated; catalog `f -`, 0 sessions):**
  - Main copy: 503 `state_unavailable`; `Extract Intent` not run; a `state_unavailable` owner alert. **S4's
    auth-failure shape, measured:** the error item is `{error, message}`, `message` = `permission denied for database
    "salon"`, `error.description` = "User does not have CONNECT privilege.".
  - Reminders copy (inside K-4's minutes): `Find Due Appointments` → output 1 → `Reminder Error (lookup)` → owner
    alert, whose detail shows the real reason.
- **T1 (UPDATE on `appointments` revoked):** Reminders: `Find Due` found the due row → `Send Disabled?` → dry-run →
  `Stamp Reminded` output 1 → `Reminder Error (stamp)` → owner alert. The row stayed unstamped (`reminded` false, no
  `reminder_sent`). The alert's detail reads `-object Object-`: the Phase 7 mandatory item (S10, Q18) reproduced on a
  real failure.
- **T2 = M5b (SELECT on `bot_metrics` revoked):** `Read Spend` emitted `{}` on output 0 (its `alwaysOutputData`) and
  the error on output 1; `Spend Gate` read `{}` as no spend and failed OPEN: the LLM ran and the customer got the
  normal answer; one `spend_meter_unavailable` owner alert. **Also measured:** `Record LLM Spend` failed too, because
  `INSERT … RETURNING` and `ON CONFLICT DO UPDATE` need SELECT, so that turn's cost was not counted. The meter
  under-counts during a read outage, visibly (the alert).
- **T3 (INSERT and UPDATE on `conversations` revoked), D4-3's measurement:** `Save State` → output 1 → `Send Error
  Response`: 503 `state_unavailable`. **The error item under `single` + `continueErrorOutput` carries ONLY `{error,
  message}`, not the input's keys** (the SQL reason is in `message`). That is the shape recorded for Airtable's error
  item on 2026-08-16 (exec 84, decision log), so the store swap does not change it. **What it does downstream (the
  same in the original):** `Build Owner Alert` takes the class from the reply node (`state_unavailable`) but finds no
  `state` or `sender_key`, so the alert reads `sender: unknown`, `channel: unknown`, `stage: unknown` (C1's alert,
  read), and its throttle key is `state_unavailable:unknown`, shared by EVERY customer. T3's alert was suppressed by
  C1's, 4 minutes earlier (the key read from the copy's throttle state). **Ruling D4-3 is Yigitcan's.**
- **After:** the Main copy's Turnstile literal on at 21:36:09 (about 6 minutes off; the copy inactive between drill
  blocks), full verify green; activated once: no token → 403 at the edge, executions unchanged; dummy token → 403
  `turnstile_failed`, no data or LLM node. Main: 403, version ids unchanged. Clean-up: the prefix-guarded delete (1
  conversation, 1 appointment, 1 processed message) and the D4-6 single-key delete of the month's row (it held
  0.00249 USD, T3's turn; T2's was never counted) → every table 0; seed workflow 404. 5 originals active, 5 copies
  inactive and paired. The operator's own `--restore` output and the script's C1 line (sessions seen/terminated)
  are the operator's to report.
- **Declared:** the drill script's error-text helper read the message from the wrong place in C1 (it printed `None`);
  it was fixed and the C1 text re-read from the same executions. The flag files stay in `~/m7-flags` (the script
  refuses a non-empty directory, so they cannot advance a later window).
- **D3c's error paths:** lookup (C1) and stamp (T1) drilled; `Reminder Error (send)` stays unreachable while sends are
  disabled, as in the original (recorded gap).
- **Operator statements (2026-10-23, screenshots to Cowork; not Claude's measurements):** the prep block's
  `sha256sum -c` OK · `--check` OK · the window printed "stage C1 applied · CONNECT revoked · salon_app sessions seen:
  1, terminated: 1, open now: 0 (the count's visibility shown)", then T1, T2 and T3 applied with exactly their sets,
  "all four stages done" and "RESTORED — CONNECT granted, salon_app lacks no table privilege."; `--restore` afterwards
  OK; `~/m7-flags` removed by the operator after the window (Claude measured it absent at the next round's start).
- **Rulings (Yigitcan, 2026-10-23):** **D4-3 = (a), accepted 1:1** (the error item matches Airtable's recorded shape,
  exec 84); building the alert's sender, channel and stage from node references is a NAMED Phase 7 item. **T2's
  uncounted spend** under a SELECT-only revoke is a Phase 7 observation, not a migration difference: a real outage
  fails the read and the write together, as on Airtable. **✅ D4 CLOSED. ✅ D3 fully closed** (the Reminders error
  paths were drilled in M7).

## 3t · D5 + D6a + D6b plan: APPROVED 2026-10-23 (Yigitcan, plan-gate), decisions 1–14 with three amendments

The plan was presented in chat in the full plan-gate format, from reads of `4b5ee73` and the live instance only
(read-only). **Its main finding:** if the dashboard read Postgres live during D5, its release button would hand a
Postgres id to the ORIGINAL Owner Actions, which still runs on Airtable: the split brain §3 measured. So D5's code is
built and proven before the cutover, and the dashboard's live switch happens inside D6b's window.

**Measured while planning (read-only):** 5 originals active, 5 copies inactive and paired, every table 0 · no export
has an `errorWorkflow` setting or an `executeWorkflow` node, so nothing but this repo's own guards refers to a workflow
id · only Main carries tags (two) · the copies' `staticData` holds drill throttle keys and Reminders' run guard;
Main's original holds 253 throttle keys · the dashboard is not running (no listener) and its env file exists · the
existing nightly backup job runs as a non-root user with a retention window, so it reaches Postgres through
`docker exec` rather than the compose project · the parity
guard reds every inactive original (`INACTIVE ORIGINAL`), so it reds all five after the cutover unless told otherwise
· `check-live-parity` defaults to Main original's id · the deploy helper has no swap mode.

**Decisions (Yigitcan, 2026-10-23):**

| # | Decision |
|---|---|
| 1 | D5's code lands on `main` with ONE path (`airtable.ts` removed, no store switch); the dashboard stays stopped until D6b. |
| 2 | The dashboard's env takes the standard `PG*` names with `salon_ro`; its Airtable lines stay until D6c (the rollback path). |
| 3 | D6a restores into a `--network none` throwaway container from the running image, not into a scratch database in the live cluster (§3j corrected in place). |
| 4 | D6a's restore test runs on seeded `mig-` rows (empty tables prove only the schema); the seed workflow needs its own approval. |
| 5 | Both the dump and the restore check run nightly. |
| 6 | D6b's order: Purge → Reminders (minutes :05–:50) → Drill State → Owner Actions → dashboard → Main; at least 30 minutes after the last copy drill; at least an hour from the Purge tick. |
| 7 | **Amended:** NO second full suite on the production path (the same copy passed 28/28 in D4b, and the swap diff proves only the path differs). Acceptance on the production path is a routing smoke only: one booking and its cancel through the flow, in a Turnstile window of at most 10 minutes, measured both ways. |
| 8 | With Airtable quota-blocked, roll back immediately only on a SAFETY trigger (a double booking, a PII or secret leak, Turnstile not restorable, a red parity guard, an outbound send); on a functional red, stop and report, and Yigitcan decides. |
| 9 | After the cutover the guards take a DECLARED role inversion: exactly one active per pair; both active red; both inactive red; an inactive original green only under the declaration; `check-live-parity` targets the active holder of `barber-inbound`. |
| 10 | O3: no. The approved §3a method stays (separate ids); R1–R3 are not run. |
| 11 | **Amended:** `staticData` is not moved, PROVIDED Main original's 253 keys are listed by CLASS (name pattern → what it is → its expiry) and every class is shown to expire. A class that does not expire is a STOP. |
| 12 | **Amended:** Main's tags move to D7, after acceptance, not in the cutover window. |
| 13 | Purge's first trigger-mode tick is a soak item, not an acceptance gate. |
| 14 | §6's acceptance item 5 is corrected in place: the permanent off-server copy is D6d, in the final security pass. |

**Schedule (Yigitcan, 2026-10-23):** the TARGET is the migration done and Phase 7 resumed by **Monday 2026-10-26,
night**. The stop rule's 2026-11-08 stays as the emergency exit, not the target. **Three rounds:** (1) every offline
build (D5's store module and tools, D6a's backup script and its test, D6b's swap mode, guard inversion and the
`staticData` class list); (2) D5's live check, D6a's operator block and the L3 (Codex) review of `store.ts`, in
parallel; (3) D6b's window and acceptance, then Phase 7.

**Round 1 · the offline builds ✅ (2026-10-24), one open item: #11's Schedule Trigger keys (ruling below).** Nothing live
was written or activated; the only live reads were `salon_ro` reads and n8n GETs. Turnstile 403 at the start and the end.
- **D5 (`web/dashboard/lib/store.ts`, replacing `airtable.ts`; one path).** Four constant, parameterless reads; `sender_key`,
  `gcal_event_id`, `computed_reply` and `cancel_target_id` are never selected; each panel's column list is the displayed
  set plus five non-PII context columns that no panel draws (*corrected in Round 3b, Codex F7: this line said "exactly
  the displayed set", which the module's own header contradicted*); `LIMIT 101` gives the truncation flag; the Airtable
  shape the panels were written against; a pool of four with a 10 s statement timeout; before its first read the module
  asks whether the connected role holds a TABLE write privilege on the five salon tables and refuses if it does
  (*narrowed in Round 3b, Codex F1: this line said "can write any salon table"; the check does not see column grants,
  assumable roles, functions or the large-object path*).
  - `lib/store.test.ts` (9 tests, in `check-all` through the dashboard's own `check`). **Ten mutants, all red.** *Found by
    a mutant:* the first "not a proxy" test checked `Function.length`, which does not count a parameter with a default
    value, so a read that let its caller pick the table passed; the test now reads the source, and the mutant is red.
    ⚠ *Corrected in Round 3b (Codex CRT #10 F4):* those source checks catch the spellings they look for and nothing
    more; Codex kept all nine tests green with twelve proxy mutants. They are NOT a proof that the module is not a proxy,
    and the "proven from the source" wording of commit `cb6fd92`'s message and of this record overclaimed. History is not
    rewritten; the behaviour-based test is a Phase 7 named item.
  - **As `salon_ro` (live read):** (i) the four statements on the real (empty) tables run; (ii) on fake `mig-` rows of
    each table's own row type: the filters keep the right rows, the truncation works at 101, **0 shape violations**, and
    `salon_ro` holds 0 table write privileges. Control: the same statements without `jsonb_strip_nulls`/`NULLIF`/`CASE` are red
    on appointments, leads and handoff. *Corrected by that control:* the first comment said a missing `::float8` would
    make the spend panel show nothing; inside `jsonb_build_object` a `numeric` is already a JSON number, so the cast is a
    guard against a future raw select, and the comment and test now say so.
  - **The browser boundary (CRT #10, claim 1):** `next build` (offline) puts none of `PGPASSWORD`, `PGHOST`, `salon_ro`,
    the driver, the SQL or the PII column names in the client chunks; the server chunks carry them (the search's positive
    control). `check-client-imports` bans `store.ts` and the `pg` driver for client code; a client file importing either is
    red, the driver by its own rule.
  - **`tests/run-d11.sh`:** the direct route reads Postgres as `salon_ro` and now COUNTS the replay markers; its parser
    still turns every failure into `READ-FAILED`. Live: a missing record → `NOT-FOUND|0`; a deliberately wrong password →
    `28P01` → `READ-FAILED`; a parser mutant that reads an error as not-found is red.
  - `.env.example` gains the dashboard's `PG*` names; the Airtable names stay until D6c. *Declared:* the deny rule blocks
    reading `.env.example` by path and `git diff -- .env.example`; neither was routed around: the content came from
    `git show HEAD:.env.example` (pushed, public, placeholder-only) and the file was only written.
  - The sanitizer test now also plants a real-looking id on one Postgres node of the Main copy export: caught, by name.
  - *Declared:* the `next build` output (`.next/`, gitignored) is left in place; deleting it is an `rm -rf`.
- **D6a (`db/ops/pg-backup.sh` + `tests/ops/pg-backup.test.sh`).** One snapshot for the dump AND its per-table counts and
  ordered md5s (`pg_export_snapshot` + `pg_dump --snapshot`), so a write between the dump and the count cannot raise a false
  alarm; sha256 and stats beside the dump, mode 600; `pg_restore --list` must show five tables; a full restore into a
  throwaway container from the running image with no network, removed on exit; restored stats must equal the dump-time
  ones; 14-day retention on its own files only; `--verify FILE` re-checks any dump. No password anywhere.
  - The offline test (24 checks, in `check-all`) runs the script against a fake docker that records every argv. **Twelve
    mutants, all red.** *Found by the test:* a failure inside `ct="$(container)"` printed its reason into the variable, so
    the log would have shown no reason; `die` writes to stderr now.
  - **As `salon_ro`:** the stats statement runs on the real tables; on fake rows its md5 is the same for the rows in any
    order and differs when one field changes.
  - **Not measured yet (round 2, the operator's block):** real `pg_dump`/`pg_restore`, the throwaway's start, and a
    flipped byte meeting the real `pg_restore`. The nightly job is NOT edited in this round.
- **D6b, the swap mode (`deploy-workflow-copy.py --swap COPY_ID`).** Refused unless the original and the copy both read
  back inactive; the copy's trigger takes the original's LIVE path (read, never typed); its temporary trigger is removed;
  the swap-phase checks run on that content before the write and on the live copy after it; nothing is activated.
  Selftest: per spec, the clean swap is green and an unswapped copy, the original passed as the copy, a changed non-data
  node, a credential placeholder, a placeholder inside a data node's query, a temporary trigger left in, a trigger left on
  its test path and a lowered Turnstile are red; on a simulated instance the order guard, the pre-write check, the
  post-write check (the API "dropping" the path change) and the exclusivity hold. **Of twelve mutants, eleven are red;**
  the twelfth removed verify()'s not-sanitised check from the swap checks and SURVIVED, because in the swap phase every
  non-data node must equal the live original, so the check was removed rather than kept.
- **D6b, the declared role inversion.** `ROLES` in `check-exports-parity.sh` (all five `original` today) and
  `scripts/pair_roles.py` hold the rules: exactly one active per pair, the declared one; content parity lets a workflow be
  inactive only when ROLES declares its pair's other side live, and only against its own PAIRS export;
  `check-live-parity` compares the ONE active holder of `barber-inbound` against that workflow's own export.
  `pair-roles.test.py` (26 checks; thirteen mutants red, re-run with Python's bytecode cache off after the first run
  reused a stale compiled mutant), the inactive-rule test with the declaration flipped (10 cases), and a
  `live-parity-target` test against a loopback stand-in for the API (before, after, two holders); five wiring mutants red.
  **Live (read-only):** exports parity 10/10, 5 pairs hold their declared roles, live parity on the resolved holder (Main
  original) OK.
- **#11, `staticData` by class (live originals, read-only; no key's sender part and no value printed).**
  - **Main, 253 `ownerAlerts` keys in 16 classes** (17 class/sender-kind groups: `handoff` 165, `handoff_lock` 38, five
    `date_*` classes 37, and nine smaller ones, including `state_unavailable` with an `unknown` sender and with a widget
    sender, and `zernio_send_failed` with WhatsApp senders): every
    value is a timestamp, every key is far outside the 30-minute window (the youngest about four days old). The reader
    (`Build Owner Alert`) throttles only while the value is a number AND younger than the window, so **every class
    expires**.
  - **Purge and Reminders:** their `ownerAlerts` keys (class:branch) expire the same way; Reminders' `reminderRunAt` is
    read only within 120 s (it was 32 minutes old).
  - **⏸ Two keys of another kind: `node:Purge Schedule` and `node:Reminder Schedule`**, the Schedule Trigger node's own
    state (read by n8n's core, not by this repo's code): `{"recurrenceRules": [null], "recurrenceRuleSignatures": [null]}`,
    **identical on the originals and on their copies** (the copies wrote their own when they were activated in D3/D4). It
    is not a time window, so "shown to expire" does not apply in the form decision #11 asked; what holds is that nothing
    differs and nothing would be lost. **Per #11 this is a STOP for that item: ruling needed.** The recommendation is to
    accept it (no action at the cutover).
  - *Observation:* Main original's throttle keys include WhatsApp sender keys, i.e. phone numbers, in n8n's own
    database; they stay with the inactive original and are not moved. Not a migration difference.

**Rulings after round 1 (Yigitcan, 2026-10-23):** the history rewrite is approved (as R-1) · **#11 CLOSED:** the two
Schedule Trigger state keys are n8n's own trigger state, identical on original and copy, so nothing is lost by not moving
them; `staticData` is not moved · `page.tsx` logging the full error server-side goes to the final security pass list.

**Round 1's commits, rewritten before the push (approved).** Round 1's first audit found three LOW operational-inventory
findings, covering six items (the nightly job's time, the compose directory's ownership, an env file's mode, a
docker-group membership, the dump directory, a realistic container name); the fix commit corrected the tree, and the re-audit noted that the lines
were still in two earlier UNPUSHED commits. The six local commits were rebuilt with plumbing (as R-1) so that the lines
appear in no commit, the test's run-time stamp was neutralised, and the D6b message now states the measured mutant count.
Old → new: `1d04216` → `c3635c6` · `ed07fd8` → `cb6fd92` · `24bc29a` → `c3f7d6e` · `e83024b` → `f63d2c2` · `6457463` →
`a622aa8` · `e897192` folded in (its content is in the commits above). The new head's tree equals the old head's except
the declared stamp and the removal of a parenthetical the corrected message made false. Checked before the branch moved:
in the new range no commit adds any of the inventory strings (`git log -S`), while the same search finds them in the old
commits (its positive control); each new commit differs from its old one only in the three affected files. Pushed as a
fast-forward from `4b5ee73`. *Corrected here after the push audit (A1):* the sentence on the nightly job said
"unprivileged"; a user who can run docker is effectively root-equivalent, so it now says "non-root".

**Round 2 · D5's live check ✅ (2026-10-24).** The seed workflow ("MIG SEED — D5", two Access-covered paths, each refused
at the edge without a token) wrote 102 conversations (101 at `handoff`, one not), 3 appointments and 2 leads, all `mig-d5`
with distinct markers in the fields E2 keeps out. The dashboard ran from `main`'s code (`a622aa8`, fresh `next build`) on
a loopback test port with Claude's `salon_ro` env only (no API key or Access token in its process), and was read raw and
through headless Chromium:
- **D5-1:** the four panels render the seeded rows: the queue shows exactly 100 rows with "showing the first 100 — there are
  more", newest first within the unconfirmed-first ordering; masked senders (`widget:w-mig-…`); "notification NOT
  confirmed" on the rows with no alert class; appointments with the masked customer, Vienna times and "reminded"; leads with
  the masked name and phone, the sparse row as dashes; the header "4 of 4 database reads". **The spend panel shows its
  honest empty state** ("this period not recorded yet"). *Declared:* no current-month `bot_metrics` row was seeded,
  because its key is the month itself and its clean-up would need the single-key delete approved for D4 only; the spend
  read's shape was proven on fixture rows in round 1.
- **D5-2 (E2):** none of the seven markers (the full sender suffix, the event-id, reply and cancel-target markers, the full
  customer and lead names, the full phone) appears in the raw HTML, the RSC payload or the DOM.
- **CRT #10, claim 1:** the client chunks of the build that served carry none of the credential-path strings; the server
  chunks carry them (positive control). **Claim 2:** through the dashboard's own env and driver, as `salon_ro`, INSERT,
  UPDATE, DELETE, TRUNCATE and CREATE each return `42501` (inside rolled-back transactions); the page itself rendered, so the
  module's write check passed. **Claim 3:** round 1's offline source checks; the L3 (Codex) review followed and found them
  weaker than claimed (Round 3b, F4). **Claim 4:**
  `check-deploy-separation` in `check-all`.
- **D5-5:** with a deliberately wrong password the page says "could not load … did not answer" and names the privilege
  check; with no `PG*` env it says "not configured"; neither shows a seeded value.
- *Probe faults, declared:* three of the probe's text needles matched nothing (the masked-sender form, the spend panel's
  wording, the header counter's markup); the saved DOM showed each rendered correctly, and the probe's needles were wrong.
- *Declared:* the release button was NOT clicked: Next loads the dashboard's own env file, whose release URL still points at
  the ORIGINAL Owner Actions (Airtable), so a click would be §3's split brain. Release end to end is D6b's.
- The three servers were stopped by their own process groups (started for this purpose); no listener remains.
- **State left for D6a:** the seed rows stay in place (the restore test needs data, decision 4); the seed workflow is
  inactive. Clean-up follows the operator's D6a result.

**Round 3a · D6a closed, the seed cleaned, the nightly call added (2026-10-24).**
- **D6a's operator run** *(operator statements, screenshots to Cowork; not Claude's measurements)*: the server's repo at
  `59009e7` with a clean tree and `sha256sum -c` OK for `db/ops/pg-backup.sh` · `dump written (20K) from one snapshot` ·
  `verify OK — checksum, 5 tables in the TOC, full restore into a throwaway, stats equal (107 rows)` (107 = the D5 seed's
  102 + 3 + 2 rows, so the restore was compared on real data, decision 4) · **negative a** (a byte flipped AFTER the
  checksum was written): `FAILED at verify: checksum`, exit 1 · **negative b** (a byte flipped BEFORE, checksum rewritten
  to match): `FAILED at verify: the dump's table of contents lists 4 of 5 tables' data`, exit 1, i.e. the real
  `pg_restore` refused the corrupt archive · the test files removed. Cowork read the script line by line first (the live
  database is only read: one REPEATABLE READ snapshot, pg_dump, the stats; the restore happens only in the network-less
  throwaway; no secret). **✅ D6a CLOSED (Yigitcan, 2026-10-24): M8 met.**
- **Seed clean-up:** every seeded row was under the clean-up prefix (rows outside it: 0 in every table); the
  prefix-guarded delete removed 102 conversations, 3 appointments and 2 leads; every table 0; the seed workflow 404.
- **The nightly call (approved, outside the repo):** checked first that the existing nightly job is the backup user's own
  scheduled job (no system-wide entry), that this user may use the container runtime (its group and the socket's
  permissions), and that the job's own log shows last night's run completing every container step. The script was backed
  up with its mode, ONE line was added after the existing database step (the call to `db/ops/pg-backup.sh` with the
  job's backup directory, its output to the job's log, its failure through the job's own `die`), the diff showed exactly
  that line, and `bash -n` parses the script; mode and owner unchanged. It was NOT run by hand: its first real run is the
  next nightly one, and reading that run's log is a soak item. *Residual, stated:* the job calls the script from the
  repo's working tree, so an uncommitted edit present at that hour is what runs (auditor I-2; ruled in Round 3b: final
  security pass).
- **A2 (ruling):** the throttle keys left in the inactive Main original's `staticData` (WhatsApp senders, i.e. phone
  numbers) join the final security pass list.
- *Declared (auditor INFO I-1):* the round-1 rewrite paragraph said "three LOW lines" while listing six items; it now says
  three findings covering six items.

**Round 3a · TODO-1 fixed: a swap-phase Turnstile window, and every window checks before it writes (2026-10-24).**
D6b's acceptance needs the Turnstile window ON THE SWAPPED Main copy (decision 7), and the deploy helper's `--turnstile`
could not do it: its check required the TEST phase (trigger on the test path, temporary trigger present), so on a swapped
copy it was red in both directions (measured offline), and it PUT first and checked after, so a red copy was already
written with its gate lowered when the check said so.
- **New mode `--turnstile-swapped off|on COPY_ID`** (a separate flag, not phase detection: on the production holder the
  operator NAMES the phase and the check MEASURES it; a copy in the other phase is refused before any write, in both
  directions). It checks the patched content in memory against the swap phase BEFORE the PUT ('off': the copy with the
  one literal put back must pass `swap_check`, so nothing can ride along with the lowered gate; 'on': the copy as is),
  refuses an ACTIVE target, and after the PUT re-reads and re-checks the live copy and its inactive state.
- **The test-phase `--turnstile` now checks before it writes too** (the same defect class), accepting exactly what it did.
- Exclusive with every other write mode in both `main()` and `run()`, refused before any API call.
- Selftest 125 ✓ / 0 ✗ (24 new lines; the 100 earlier ones unchanged in result). **Fifteen mutants, all red**, among them:
  the PUT moved ahead of the pre-check (each phase), the swap mode checking with the test phase, phase selection inverted,
  an active target accepted, the 'off' check not restoring the literal, exclusivity removed (main, run), the pre- or
  post-check removed. One mutant (the post-check skipped in the test phase only) first SURVIVED because no case covered
  it; the case was added and it is red. An independent mutant run by the LEAD (the PUT ahead of the pre-check, both
  phases) is red.
- The scratchpad D6b driver uses the new mode; its #11 flag is removed (#11 closed).
- *Was open, ruled and built in Round 3b:* the new mode did not require the ORIGINAL to be inactive. It now does, and it
  also requires ROLES to declare the copy live (Round 3b below).

**Round 3b · the pre-cutover fixes and the window's preparation (2026-10-24).** Codex audited `store.ts` at `59009e7`
(CRT #10, findings F1–F13). Codex's overall verdict: no browser credential leak today and no request-controlled SQL; the
guards and tests admit future counterexamples. **Rulings (Yigitcan, 2026-10-24):** F3 and F1 fixed now (F1 in two parts:
narrow the module's claim; revoke the large-object writers at the database); F2 → the final security pass, with Q16; F4
and F7 → the overclaims corrected in the docs now, the behaviour test and the column trim → Phase 7; F5, F6, F8–F13 →
Phase 7 named items (F12 and F13 are 1:1 with the Airtable dashboard: Cowork read `airtable.ts` at `4b5ee73`, page size
100, the queue by `last_updated` descending, appointments by `start_utc` ascending); the `--turnstile-swapped` order guard
now; auditor I-2 → the final security pass. **CRT #10 is recorded as: current behaviour holds per Codex; the static
proofs are weaker than claimed (Phase 7).** Turnstile 403 at the start and the end.
- **F1, measured live first (read-only, as `salon_ro`, from the catalog):** EXECUTE is true for `salon_ro` AND
  `salon_app` on `lo_create`, `lo_creat`, `lo_from_bytea`, `lo_put`, `lowrite`, `lo_truncate`, `lo_truncate64` and
  `lo_unlink` (PUBLIC's default, no ACL set); `lo_import`/`lo_export` are already superuser-only; zero large objects
  exist. An earlier probe the same day: `TEMPORARY` and `CREATE` (database, schema `salon`, schema `public`) refused.
- **F1 (b): `db/schema/003_revoke_large_object_writes.sql`.** It revokes EXECUTE from PUBLIC on those eight functions in
  database `salon` only (function privileges are per database), inside one transaction that also checks that none of
  PUBLIC, `salon_app` or `salon_ro` can still execute any of them and rolls back if one can; it refuses any other
  database; it is idempotent. *Declared:* `lo_unlink` is included although the ruling said "create or write": deleting a
  large object is a write. **No workflow uses any of them:** a search of all ten exports, the five copy specs and the
  schema files for the large-object function names found nothing, and the same search matched a planted `lo_create(0)`
  (positive control). ⚠ `pg-backup.sh`'s verify restore (into the throwaway) uses `--no-privileges`, and the script has
  no real-restore path; a real restore done the same way would carry neither 002's grants nor this revoke, so the file
  says to re-apply both after one (*worded so after the review: the first draft read as if the script restored
  production*). **Not yet applied:** the
  operator runs a dry run (the same checksum-verified file with its final `COMMIT` turned into `ROLLBACK`) and then the
  real run, through the container's superuser socket, with `has_function_privilege` for both roles on all eight shown
  before (true: the positive control) and after (false). *(Applied and measured later the same day: Round 3c below.)* *Not tested offline:* this machine has no Postgres engine of its
  own, so the operator's dry run is the file's first execution.
- **F1 (a): the module's claim narrowed** (`store.ts`): the header and `WRITE_CHECK`'s comment now say it is a TABLE-
  privilege check (`has_table_privilege` for INSERT, UPDATE, DELETE and TRUNCATE on the five tables, for the connection's
  role) and name what it does not see: column grants, roles reachable by `SET ROLE` without inheritance, functions (the
  large-object writers, SECURITY DEFINER), sequences, other tables and schemas, schema CREATE and database TEMPORARY,
  ownership, BYPASSRLS; and that it runs once per process (F2, deferred). Its test is renamed to the narrow form. The
  SQL is unchanged (ruled).
- **F3: the pool's error listener** (`store.ts`): attached once, at construction; it logs only a class (a SQLSTATE or a
  Node errno code, otherwise `unknown`), never the message or the error object. A new test ports Codex's idle-error
  probe: the REAL pg pool, built by `store.ts`, with a fake connection; four idle errors (two codes, a code-looking
  string, none) are emitted; none escapes, each logs exactly one line with the right class and without the message
  marker, and the next read opens a fresh connection. `store.test.ts` 9 → 10, the dashboard's `check` 51 → 52. **Mutants,
  all red:** the listener removed (the error escapes); the listener attached on every read (two lines); the message
  appended or the error object logged (leak); the code passed through unfiltered; `once` instead of `on` (the second
  idle error escapes; the LEAD's own). *Not measured:* a real database restart; the connection is fake, the pool is real.
- **F4, the overclaim corrected:** round 1's record above, ROADMAP, the `store.ts` header and the test header now say
  the source checks catch the spellings they look for and are not a proof. *Declared:* commit `cb6fd92`'s message says
  "proven from the source" and overclaims the same way; history is not rewritten.
- **F7, corrected:** round 1's record above, the `store.ts` header (the rule's middle clause, "a field that is not
  displayed is not fetched", is NOT met today) and the test header. Re-measured here: the five context columns
  (appointments' `end_utc`, `reminder_sent`, `created_at`; leads' `created_at`; the queue's `stage`) are in the
  projections and no panel or page reads them (search over the dashboard; control: `start_utc` is found in the
  appointments panel).
- **The `--turnstile-swapped` order guard** (`deploy-workflow-copy.py`): refused before the content check and before any
  write unless ROLES (read through `pair_roles`, the one parser) declares exactly this pair with LIVE = `copy`, AND the
  original reads back inactive; both directions, 'off' and 'on'; the test-phase `--turnstile` reads neither. Selftest
  125 → 134 ✓, 0 ✗, on ROLES fixtures with fake ids. **Mutants, all red:** the ROLES check removed (3 ✗), the inactive
  check removed (2 ✗), the guard applied to the test phase too (2 ✗); the LEAD's own, at the call site: the read-back
  flag ignored (2 ✗), original and copy swapped (7 ✗). Against today's repo (all five ROLES lines `original`) it refuses,
  as intended.
  **Consequences for the window, declared (D6b driver, scratchpad):** (1) the ROLES flip is no longer after `post`: it is
  a LEAD step **6b**, one commit, between `swap-main` and `smoke-main`, because the guard needs it; `smoke-main` now
  predicts the guard with the helper's own check and stops before touching anything if it would refuse. (2) The gate is
  restored ('on') BEFORE any rollback, never after: once the original is active again, the guard refuses 'on' and the
  parked copy would keep a lowered literal. `smoke-main`'s `finally` already restores first.
- **The pre-window reads (read-only, `d6b_run.py pre`): GREEN.** Main's holder is the original; Turnstile literal true
  and a dummy token 403; Main's version values unchanged; every table 0; all five pairs original-active, copy-inactive,
  `pair_roles.judge` 0 errors, ROLES all `original`; the copies' youngest activity about 13 hours old (≥ 30 min); the
  Purge tick about 9 hours away.
- **Records:** PHASE-7-PLAN named items (6)–(15) and final security pass items 8 (F2) and 9 (I-2); the CRT #10 row in
  MASTER-BRIEF §9; ROADMAP. **Waiting:** the operator block (003, the dashboard's env lines), then the D6b window.
- **The L2 review before the push** (security-auditor: push OK; two code reviews) found that the decision log and the
  CRT #10 row read as if 003 were already applied, and that 003's restore note read as if the backup script restored
  production; all three are corrected. *Declared:* the round's docs commit message says "F1 and F3 fixed before the
  cutover" and the 003 commit message's "Applied by the operator" describes the procedure; 003 is NOT applied yet, so
  F1's database half is open until the operator's run is measured. The messages were not rewritten.

**Round 3c · D6b: the cutover and its acceptance (2026-10-24). ✅ D6b CLOSED.** Yigitcan's brief was the written
go-ahead and named the live work: the `--swap` PUTs, each original deactivated and each copy activated, the ROLES flip
commit between `swap-main` and `smoke-main`, the two `--turnstile-swapped` PUTs on the Main copy, a seed workflow,
Google Calendar create and cancel through the flow, LLM spend up to 1.00 USD, the dashboard started from `main`'s code
with its own env file, `run-d11` on the production paths, the race drill and the dashboard release. Not in it: tags (D7),
`staticData` (not moved), Airtable, Zernio. Rollback was not triggered. Turnstile 403 at the start and the end.
- **003 applied** *(operator statements, screenshots to Cowork)*: checksum OK; dry run `…ROLLBACK`, then still 8/8
  executable; real run `…COMMIT`, then 8/8 not executable for `salon_ro` and `salon_app`. **Measured by Claude as
  `salon_ro`:** the catalog shows EXECUTE false on all eight for both roles while the reading functions stay true (the
  control); `lo_create` and `lo_from_bytea` return `42501` inside rolled-back transactions and a read is allowed. **F1's
  database half is closed.**
- **Step 0 (14:15 UTC) GREEN:** `d6b_run.py pre` (five originals active, five copies inactive and paired, tables 0,
  Main's dummy token 403, version values unchanged and recorded privately, every copy's `staticData` window expired);
  the scratchpad tools import-safe; a fresh `next build` of the dashboard whose client chunks carry none of the
  credential-path strings (server chunks: the positive control).
- **The swaps, 14:15:57–14:18:14 UTC, in decision 6's order**, each `GREEN` and read back (original inactive, copy active,
  swap-phase check green before and after the PUT, exactly one active per pair): Purge (more than an hour from its tick) → Reminders
  (minute :16, temporary trigger removed) → Drill State and Owner Actions (no token refused at the edge; owner token with
  a bad signature reached the COPY and was refused; no execution on the original) → **the dashboard**, started detached
  on `127.0.0.1:3210` from the fresh build with a clean environment: its own env file, read by Next itself, plus the
  committed mock client config passed as `CLIENT_CONFIG_JSON` (the engine's inline config is the same demo client); it
  rendered "4 of 4 database reads" → Main (the copy on `barber-inbound`, the dummy token 403 by the copy, none on the
  original).
- **Step 6b, the ROLES flip:** all five lines `copy`, and the five copy exports brought to the swapped shape by the
  helper's own `swap_patch` applied to the COMMITTED copy and original exports (byte-identical JSON round trip checked
  first), so nothing live entered them. Inverted mode, live: exports parity 10/10 with five pairs as declared; live
  parity on the active holder of `barber-inbound`, the Main copy. *Declared:* the flip was first committed while two role
  tests were red (they still assumed "every pair original"): a `| tail` after each test swallowed its exit code, so the
  chain went on to the commit. The tests now follow the declaration; the two local commits were squashed into one with
  clean tests before the push (ruling, as R-1).
- **A1 (routing smoke) and A3 (race) in ONE Turnstile window on the Main copy: 97 s**, opened and closed with the
  helper's swap-phase mode (checked before and after each write; the order guard satisfied), measured both ways
  (published literal true, dummy token 403 by the copy). Eleven turns, every reply the expected one: a booking and its
  cancel (Delete 204, the row `cancelled`, the copy's freeBusy empty on the slot), one ask, then two sessions asking for
  the same slot, the first confirming ("You're booked"), the second confirming after the first one's reply ("that time
  was just taken"), and the winner cancelling through the flow. LLM spend 0.028 USD; Send WhatsApp 0.
  **A3's five points (PHASE-7-PLAN M2):** one booked row on the race slot inside the window · the loser in `handoff`
  with its event id cleared · the loser's event deleted (`Cancel Our Event` on its success output, then
  `Build Race-Lost State`, which only a clean withdrawal reaches) · `race_other_count` 0, 0 and 1 (the smoke booking, the
  winner, the loser; never −1) · `Build Orphan State` never ran. *Declared:* the second confirm was sent after the first
  reply, so the second writer is caught by write-then-verify; a truly simultaneous pair can make both yield (the
  documented symmetric limit) and was not attempted. *Declared, instrument faults fixed without a new live action:* the
  driver first printed two reds; Google answers the delete with an empty 204, so the node's output has no `statusCode`
  (the driver looked for one), and a cleared event id is stored as `''` by the same `|| ''` expression the original's
  Airtable mapping uses (the driver asked `IS NULL`); with both read correctly, events created 3 = deleted 3.
  **The calendar itself, read afterwards:** a short-lived read-only workflow on an Access-covered path, built from the
  Main copy's OWN live `Load Config` and `Get Calendar Busy` nodes (same credential; no calendar id handled), deleted
  (404) after each read: 2026-10-26 in Vienna → one calendar answered, the exact window, **0 busy intervals**, 0
  errors, covering the race slot and every acceptance slot. *Not shown:* that this probe can go non-empty; the calendar
  has no busy interval at all through 2026-12-19, so no positive control exists without creating an event. The
  calendar's identity rests on the same credential's `events.list` seeing the winner's live event during the race
  (`race_other_count` 1).
- **A2: `run-d11` on the production paths, 13/13** (`owner-release` and `owner-drill-state`), on a seeded handoff row;
  control (no token, 403) and treatment (200) differ.
- **A4: the dashboard release.** First run RED for configuration: the board said "not configured to write. Nothing was
  sent." Its env file had none of `OWNER_ACTION_URL` and `CF_OWNER_ACCESS_CLIENT_ID/SECRET` *(operator statement: 9
  names before, 12 after; backup taken)*. The dashboard was restarted by stopping its own process group by PID; the
  release was then clicked in the real board (headless Chromium through CDP) on the second seeded handoff: the board
  said "Released"; the row went to `new` with an empty `last_intent`; one release marker; the Owner Actions COPY ran
  once (`success`, `Build Owner Alert (Release)` and `Send Owner Alert (Telegram)` with `ok: true`); the original ran
  none.
- **A5:** Reminders' first hourly tick in trigger mode, 15:00:38 UTC on the copy, `success`, no error; none on the
  original. **A6 (soak, decision 13):** Purge's first trigger-mode tick, tonight (its first after the DST change).
- **A7:** Turnstile literal true on the copy, dummy token 403. **A8:** the inverted guards green; live mutants red: one
  ROLES line declared `original` → `check-pair-roles` FAIL (an undeclared swap); the Main copy's content against the
  ORIGINAL's export → `check-content-parity` DRIFT. *Declared:* `check-live-parity` compares topology only (node names
  and connections), so it passes the copy against the original's export (the same graph); content is
  `check-content-parity`'s job. **A9** *(operator statement)*: from the operator's machine, 5432 timed out and 22
  succeeded (the control).
- **Cleanup:** the seed workflow's prefix-guarded path removed 6 conversations, 2 appointments and 13 markers; no prefixed
  row and no other row remain; the month's `bot_metrics` row is KEPT (ruling: it is now the real spend meter, 0.028 USD;
  "tables 0" now means "no prefixed test row left"); the seed workflow and the calendar probe are 404. During the window
  no row outside the drill prefixes appeared; the parked originals ran nothing; their version values are unchanged.
- **Soak and open:** A6; tonight's nightly job, the first with the Postgres dump and its restore check; the dashboard
  runs as a detached process Claude started (not a supervised service: it does not survive a reboot); the two env-file
  backups (`.env.local.bak-r3b`, `-r3c`) hold secrets and go after the soak.
- **Rulings recorded with this round** (Yigitcan, 2026-10-24, in the Round 3c brief): `storeError`'s unfiltered code on
  the page and the Purge time in public files join the final security pass (PHASE-7-PLAN items 10 and 11).

**K-6 after the cutover · the dashboard's route, measured (2026-10-24).** Read-only, from the server, after the
dashboard started listening again. **Ruling (Yigitcan): the route STAYS** — the Phase 6 design, the owner's only path
that does not need SSH. *Correcting a premise:* the brief that opened this check assumed that with no known dashboard
hostname the dashboard was not reachable from the internet; that was an unmeasured inference and it was wrong, and the
check stopped on it as instructed before anything else was done.
- **The listener:** `127.0.0.1:3210` only; no wildcard bind.
- **The connector:** the tunnel runs as a root host service with no private network namespace, so it CAN reach the
  host's loopback; what decides reachability is its ingress.
- **The ingress it has loaded**, read from the connector's own local metrics server (identity shown: its metric family
  is present and it reports four edge connections; the journal was tried first and returns nothing to this user, so it
  is not a source): six rules, **one targets the dashboard's port under a dashboard hostname**; the positive control,
  n8n's webhook origin rule, is found; the last rule is a catch-all status. No hostname or rule text was printed or kept
  (the saved copy was deleted after parsing).
- **Session-less requests to that hostname:** `/`, `/api/release` and a static asset each answer **302 to the Access
  login**, with no dashboard content in the body.
- **The Access policy** (Cloudflare API, GET only, with the token already on the server; the token sits in a 0600 header
  file, never on a command line): the application covering the dashboard hostname is self-hosted with ONE policy,
  decision **allow**, include type **email** with **one** address named, no require or exclude, no `everyone`, no
  bypass, no login-method-only rule; application session **730 h**. No application with a wildcard host pattern exists
  (8 applications, all exact hosts), so none can widen it. **Positive control:** the application on n8n's `owner-*`
  paths reads as decision `non_identity` with include type `service_token`, which is the Service Auth S6 measured.
- *Observation, not ruled:* a 730-hour session is long for a page that shows customer data.
- **Cleanup (approved):** the two env-file backups of Round 3b/3c (they held secrets) and the operator's scratch
  directory holding the 003 file are deleted and shown absent; the dashboard's env file itself is in place.

## 4 · "No new bug": QA design

1. **Mechanical diff — `scripts/diff-workflow-copy.py <original> <copy> --allow <node names>`.**
   - Fails if: any node outside the allow-list differs in type, parameters, credentials or
     `onError`/`alwaysOutputData`; any connection differs; a node is added or removed.
   - The allow-list is exactly the Airtable node names for that workflow. Allowed changes:
     `type`/`typeVersion`/`parameters`/`credentials` of those nodes only.
   - A declared temporary test trigger (spike S7) is allowed only while the copy is on a test path,
     and must be gone at cutover. **Ruling Q13 makes it the ONLY way to test schedule-triggered copies;
     n8n's manual/test execution is not used in this phase.** Its security conditions:
     - **only on a path behind Access.** Purge deletes, so an unprotected trigger would let anyone fire a
       deletion, which makes spike S6 (Access covers the copy paths) its precondition;
     - **removed before the swap**, its absence proven by this diff tool against the original.
   - **Positive control first:** change one unrelated node → red · change one connection → red · rename a
     data node → red · clean copy → green.
2. **Contract-shape test.** For each of the 34 nodes: its SQL runs against the seeded DB (as `salon_ro`
   for reads; writes through the n8n test path), and the output is asserted:
   - top-level keys = `{id, createdTime, fields}`; `id` matches `^rec[A-Za-z0-9]{14}$`
   - no `null`, no `false`, no `""` inside `fields`; timestamps match `…T…\.\d{3}Z`; numbers are numbers
   - the 0-row result matches what that node's consumer expects (`{}` where `alwaysOutputData` is set)

   **Recorded Airtable shapes exist for comparison** (§3b, from the D0 backup): the record shape
   `{createdTime, fields, id}`, the 0-row `{}` and the error-item shape. They are extracted in D2 as
   KEY/TYPE fixtures, never values; the leads rows behind them are PII. What no fixture covers is a
   record with an absent field. **Ruled (Q4): D4 does NOT wait for it.** S9 rides on D6c's export read.
   D4 proceeds on the recorded shapes, the static scan and the end-to-end drills.
3. **Per-workflow drills on a test path against a mock-prefixed seed** (§6 mock data). Each workflow's
   own existing drills re-run: `run-d11.sh` for Owner Actions + Drill State, the purge drills, the
   reminders dedupe, Main's golden subset.
4. **Security:**
   - hostile `message_id` and `senderId` values (quote, comma, `$1`, `;`, newline, an SQL-comment
     sequence) through the widget test path → normal or duplicate behaviour, row counts unchanged
   - the role negative tests (§3g)
   - the network checks (§3h)
5. **Acceptance window (D6b):** the full suite against the cutover. The **Turnstile window protocol**
   (ruling 2026-10-18) applies to the cutover AND to the D4 copy's drills: the copy carries the same
   Turnstile gate, so lower it on that workflow only, run, restore, and measure (published
   `enabled:true` + dummy token → 403).

## 5 · Critical-Review Targets

**New, migration-specific** (criteria: 1 irreversible · 2 money/quota · 3 data leak · 4 shared state ·
5 silent failure):

| # | Target | Crit. | Runnable verification |
|---|---|---|---|
| M1 | Data-layer swap equivalence | 4+5 | `diff-workflow-copy.py` green per copy, red on its 3 mutants |
| M2 | SQL injection | 3+1 | `check-sql-params.py` green, red on its 4 mutants; hostile-input drill rows unchanged |
| M3 | DB least privilege | 3+1 | §3g's negative tests: every one returns "permission denied" |
| M4 | Network exposure | 3 | `ss -ltn` has no wildcard 5432; external probe times out |
| M5 | **Spend-meter continuity: the LLM brake on the new store** | **2** | seed `bot_metrics` at ≥ cap → the LLM node MUST-NOT-RUN · break the read (revoke SELECT for one drill) → fail-open **plus** a `spend_meter_unavailable` alert, never silent |
| M6 | Idempotency on Postgres | 4 | same `message_id` twice → one booking, one processed row; residual race documented (§3e) |
| M7 | Store-outage visibility | 5 | revoke `salon_app` CONNECT for one drill → Main returns infra-unavailable (5xx + flag) and alerts the owner; the brain MUST-NOT-RUN. **The same operator window also runs Reminders' K-3 error-path drills** (speed plan, 2026-10-22: one window, not two) |
| M8 | Backup restorability of the new store | 1 | §3j restore test green; flipped-byte dump red |
| M9 | DB secrets never in repo or transcript | 3 | host-leak + secret-scan green; the new deny rule measured from a subagent |
| M10 | Airtable shutdown ordering | 1+2 | export exists, is checksummed and restore-readable BEFORE the first revoke (§7) |

**Existing CRTs the migration invalidates or touches:**

| CRT | Why | Re-proven at |
|---|---|---|
| **#11** D11 owner path (closed) | Owner Actions' 5 nodes + replay marker change store | D3: `run-d11.sh` 8 cases / 13 assertions against Postgres |
| **#8** booking mutation (closed, with residual) | `cancel_target_id` + `Find Booking` change store | D4 drills; D6b acceptance |
| **#10** dashboard API-layer authz (closed) | the read path moves from a read-only PAT to `salon_ro` | D5 |
| #1a idempotency (open) | dedupe store moves; race residual | D4 (M6) + Q5 |
| #1b no double-book (open) | the mirror moves; M2's lost-race graph is re-measured | D6b race drill |
| #6 error visibility (open) | every data-layer error branch now fronts Postgres | D3/D4 (M7) |
| #4 secrets/PII (open) | new credential type in exports; sanitizer must mask it | D2 (sanitizer) + every export |
| #2, #5, #9, #12, #13 | logic not touched; drills pass through data nodes | covered by D4/D6b drills, not re-audited |

## 6 · Skeleton (node level) · integrations · mock data · acceptance · drill matrix

**Files (new):**
- `docs/MIGRATION-PLAN.md` (this file)
- `db/schema/001_init.sql` (tables, constraints, `gen_rec_id()`, `sender_masked`)
- `db/schema/002_roles.sql` (passwords come from psql variables set from env, never literal)
- `scripts/check-sql-params.py`
- `scripts/diff-workflow-copy.py`
- `tests/contract/` (shape tests)
- `tests/db/role-negative.sh`
- the seed and cleanup scripts (prefix-guarded)

**Files (changed):** `web/dashboard/lib/airtable.ts` (→ a pg client, renamed in D5) ·
`tests/run-d11.sh` (PAT route) · `scripts/check-content-parity.py` (Postgres credential masks) ·
`scripts/package.json` (`check-all` gains the two gates) · `.env.example` (names only) · `n8n/*.sanitized.json` (exports of the copies)
**Outside the repo (Yigitcan):** compose + env · the nightly backup job · n8n credential.

**Nodes swapped, by name (each is Airtable → Postgres `executeQuery`; same name, same connections):**
- **Main (17):** Load State · Save State · Capture Lead · Write Appointment · Check Processed · Record
  Processed · Save State (Post-Write) · Find Booking · Update Appointment Cancelled · Re-read Cancel
  State · Find Booking (Reschedule) · Find Old Booking (Reschedule) · Update Appointment (Reschedule) ·
  Read Spend · Record LLM Spend · Find Conversation Row · Record Alert Class
- **Owner Actions (5):** Find Target Conversation · Check Owner Replay · Release Handoff Lock · Re-read
  Released Conversation · Record Owner Action Processed
- **Processed Purge (8):** Find Old Processed · Delete Old Processed · Find Stale Conversations · Scrub
  Recent Messages · Count Leads Total · Find Old Leads · Delete Old Leads · Count Leads After
- **Reminders (2):** Find Due Appointments · Stamp Reminded
- **Drill State Read (2):** Read Conversation · Count Markers

Each keeps its `onError` and `alwaysOutputData`. Main's 6 `<Node> Errored?` IFs read `!!$json.error`;
**whether a Postgres error item carries `error` the same way: *spike S4*.**

**Integrations:**
- **Postgres:** new.
- **Airtable:** NO requests until D6c's export. After that, only revocations.
- **n8n:** copies created, activated and deactivated, each gated.
- **Google Calendar:** touched only by drills on a test calendar slot, as today.
- **LLM:** the D4 drills and the D6 acceptance spend under the cap, which is now metered on Postgres (M5).
- **Zernio:** none (the webhook stays closed). **Telegram:** owner alerts from drills, as today.

**Mock data:**
- Every seed row uses the prefix **`mig-`** (sender keys `widget:w-mig-…`, message ids `mig-…`) and
  obviously fake names and numbers. It is marked mock in the seed file.
- Cleanup is a prefix-guarded delete that refuses any row without the prefix and is gated as an
  irreversible action. It runs at D7.
- Nothing real is migrated (Q1).

**Acceptance (the phase is done when):**
1. All five workflows and the dashboard run on Postgres, with Airtable on no runtime path.
2. M1–M10 green, each with its red direction shown.
3. CRTs #8, #10 and #11 re-proven.
4. A nightly `pg_dump` exists and has been restore-tested.
5. ~~A permanent off-server copy exists.~~ *Corrected 2026-10-23 (decision 14, §3t): this is D6d, moved to the final
   security pass by the 2026-10-22 speed plan; it is not a D6 acceptance item.*
6. The Airtable export has been taken before the revocations.
7. The D0 restore levels have been rehearsed: credential decryption (D2) and re-activate-the-original
   (D3 Purge).
8. Governance surfaces updated (D7).

**⚙ Drill matrix:**

| Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|
| Duplicate message (idempotency) | same `mig-` message id twice to the Main copy | one reply path, 1 processed row | Check Processed → duplicate branch | Book Appointment (2nd) |
| Hostile `message_id` | quote / comma / `$1` / SQL-comment ids | normal or duplicate behaviour; row counts unchanged | Check Processed (parameterized) | any write outside the expected rows |
| Double-booking race | two senders, one slot, parallel, both "yes" | **PHASE-7-PLAN M2's five measured items:** (1) exactly ONE `booked` row for that slot · (2) the loser's `stage='handoff'` with `gcal_event_id` cleared · (3) the loser's calendar event cancelled, not orphaned · (4) **`race_other_count >= 1`**, which separates a real race from a `verify_incomplete` handoff · (5) `Build Orphan State` did NOT run. *("one booking + handoff" was the weak, never-measured expectation M2 replaced; corrected.)* M2 is a structural measurement and is re-measured after the migration (§8) | write-then-verify; Cancel Our Event; Build Race-Lost State | a 2nd surviving booking; Build Orphan State |
| New customer (0 rows) | unknown sender | `found=false` path, welcome reply | Merge State with `{}` | Mark Handoff |
| Uncertain turn | low-confidence text | 1st clarify / 2nd handoff, as today | clarify ladder | booking |
| Owner release (CRT #11) | `run-d11.sh` against Postgres | 13/13 | Release Handoff Lock + replay marker | a 2nd release on replay |
| Spend cap (M5) | `bot_metrics` ≥ cap | LLM skipped, deterministic reply | Spend Gate | LLM node |
| Spend read broken (M5) | revoke SELECT for one drill | fail-open + alert | owner alert | silence |
| Store outage (M7) | revoke CONNECT for one drill | 5xx + `error` flag + alert | infra-unavailable branch | the brain |
| Purge on Postgres | aged `mig-` rows + fresh ones | old gone, new kept; leads TTL branch | Delete Old * | deletion of fresh rows |
| Reminders dedupe | due `mig-` appointment | one reminder, `reminded=true`; a reschedule re-arms it | Stamp Reminded | a 2nd send |
| Role negatives (M3) | §3g | permission denied on each | — | any DDL/DML succeeding |
| Rollback rehearsal | Purge swap then revert | the original runs next schedule | re-activate the original | both active at once |
| DST / timezone | booking across a DST edge, `mig-` | correct wall-clock time; `timestamptz` round-trip | Resolve Date path | — |

## 7 · Airtable shutdown (D6c) · gates and order

1. **Gate 0:** the cutover has passed acceptance, and the soak has passed: **7 days with no rollback
   trigger (ruling Q9).**
   - **The soak runs in the BACKGROUND (ruling, 2026-10-20).** Phase 7 starts right after D6b's
     acceptance. Only D6c (these revocations) waits for the soak (speed plan 2026-10-22; D7's close used
     to wait too).
   - **Recorded risk:** a rollback during the soak means re-running whatever Phase 7 results exist by
     then.
   - **Note:** while OPS-5 lasts, Airtable is an unlikely rollback target before its quota resets
     (unmeasured, because measuring spends quota). The D0 restore point is the real fallback.
2. **Gate 1, the export:** every table **including Customers** is exported through the API, in Airtable's
   own record shape, to an out-of-repo directory, checksummed, and its record counts compared with the
   base. The export is copied off-server. *This is the only Airtable read the phase plans. It needs quota,
   so it waits for OPS-5's reset or plan change.*
3. **Gate 2, nothing still reads Airtable:** a repo-wide search plus the live workflows (all five active
   copies hold zero Airtable nodes) plus the dashboard env. Each search gets a positive control.
4. **Revoke (Yigitcan, in Airtable):** first the n8n PAT, then the dashboard's read-only PAT. Measured by
   behaviour: a call with each returns 401.
5. **Base: NOT deleted by this phase.** It stays as an exported, unreferenced archive. Deleting it is
   irreversible and a separate decision (it also holds Customers).

## 8 · Phase 7 premises that change (list only; re-derived at D6b's acceptance, ruling 2026-10-20)

- **K-5** (regression from the widget lane): the lane is unchanged, but its expectations about the
  store change.
- **K-1** / the Turnstile window plan: the 7-1 window's **Airtable request budget** stops being a premise.
- **CRTs #1a, #1b, #6, #8, #10, #11:** their evidence becomes migration evidence (§5).
- **M2's measured lost-race graph:** node names are kept, but the data nodes behind it change, so it is
  re-measured. The migration's race drill row (§6) already asserts M2's five items, so this
  re-measurement is what the D6b race drill produces.
- **The drill matrix:** rows that assert Airtable formulas, `!= ""` guards, `sender_masked`'s formula, or
  quota behaviour.
- **The ship-gate items that name an Airtable PAT** or the base.
- Rules and docs that name Airtable as the store: `booking-integrity.md` · `spend-safety.md` (timeouts) ·
  `honesty-demos.md` ("one swap to real" = the client's base) · `DATA-MODEL.md` · `MASTER-BRIEF.md`
  stack · README/case study.
- **Model 1 (per client):** each client gains a Postgres service, its secrets and its backup step,
  instead of an Airtable base.

## 9 · NOT-build (already §2) · automation-fit · D2's first spikes

**Automation-fit:**
- **Neither** for D2, D3's swaps, D6 and D7: every step there is a gated live write or needs
  Yigitcan's hands.
- **Optional `/goal`** for one inner loop only: D4's OFFLINE build ("build the Main copy's JSON until
  `diff-workflow-copy` + `check-sql-params` + the contract test are green"). It has no live writes
  inside the loop. Not used unless Yigitcan asks.

**D2 spikes** (each needs a live write, and each is gated; none runs before "approved"):

| # | Question | Smallest safe probe |
|---|---|---|
| S1 | Can two active workflows hold one production webhook path? | two throwaway workflows on a throwaway path, activate both, read the error · **✅ ANSWERED 2026-10-20 (§3q): NO.** With A active on an Access-covered throwaway path, activating B on the same method + path returned 409 "There is a conflict with one of the webhooks" and B stayed inactive; the owner-token request reached A only (A's executions 0→1, B's 0→0). Control: with A deactivated, B activated (200) and answered. The cutover order (§3a) is confirmed: a wrong order fails loudly |
| S2 | On this instance's Postgres node: return shape for rows / 0 rows (with and without `alwaysOutputData`) / `RETURNING` / `ON CONFLICT DO NOTHING RETURNING` with 0 rows / `jsonb` parsing / `timestamptz` serialization; and which typeVersion is available | a throwaway workflow against a scratch table · **✅ ANSWERED 2026-10-19 (design branch chosen by Q17, 2026-10-20); one answer changed the design (§3o):**<br>· INSERT … RETURNING returns its rows (`rec`+14 ids).<br>· **A WRITE that returns 0 rows** (ON CONFLICT DO NOTHING RETURNING) gives `{success: true}` and no `id`, **with or without** `alwaysOutputData` *(corrected 2026-10-20: "NOTHING without it" was inferred from the SELECT case and never run; measured in §3p)*.<br>· **Q17 (a), measured 2026-10-20:** `ON CONFLICT … DO UPDATE SET message_id = EXCLUDED.message_id RETURNING id` returns the EXISTING id on a conflict, 1 row, `created_at` unchanged; a fresh id is the control (§3p).<br>· A **READ** with 0 rows gives `{}` with `alwaysOutputData` (the same as Airtable) and nothing without it.<br>· The Airtable-shaped SELECT conforms: `fields` is a parsed object, `createdTime` is ISO-ms-Z, empty values are dropped.<br>· A raw `timestamptz` serializes as ISO-ms-Z; a raw `numeric` comes back as a STRING but as a number inside jsonb; booleans and null pass through.<br>· typeVersion 2.6 works.<br>· A node runs once per input item, the same as the Airtable nodes. |
| S3 | `queryReplacement`: does an array expression keep comma / quote / `$2` / newline values as one parameter; what does the comma-string form do | the same, with hostile values · **✅ ANSWERED 2026-10-20 (§3p):** the array form returned 14 hostile values identical (comma, quotes, `$2`, newline, injection text, backslash, unicode, `{{ }}`, `${…}`/`$1:raw`, empty string, object → `jsonb`, `null`, number); an expression or filter inside a value is not evaluated. Control: the string form splits on commas, and with a single `$1` the value `a,b` came back as `a`, **silently truncated**. Evidence for the gate's array-only rule; no design change |
| S4 | Error item shape under `continueRegularOutput` (auth failure, SQL error) | the same, with a wrong password and a bad SQL statement · **PARTLY ANSWERED by S8 and S5:** under the `single` batching mode (S8's, one item) an SQL error is `{error, message}`, Airtable's keys (Airtable's live error item: `error` an object, `message` a string). *Corrected 2026-10-20:* under `independently` and `transaction` it is `{error}` alone, with no `message` (S5, §3p). Every shape satisfies the `Errored?` IFs (`!!$json.error`). The auth-failure shape is not run (it needs an extra credential, which is not on the approved list). **Branch chosen (ruled 2026-10-20):** drill M7 in D4, REVOKE CONNECT on `salon_app` with the existing credential (operator step); residual in §3p |
| S5 | Per-item parameters under each batching mode (purge deletes N rows) | 3 input items, 3 parameter sets · **✅ ANSWERED 2026-10-20, branch chosen by Q18 (§3p):** on success every mode deletes 3 of 3 with 3 items out. When item 2 fails: `single` undoes the whole batch and emits 1 `{error, message}`; `independently` deletes items 1 and 3 and emits `{error}` with no `message`; `transaction` rolls back but reports item 1 as deleted. No mode gives the multi-item write nodes' consumers what they were written against · **Q18 ✅ ruled 2026-10-20: `independently` for the four** |
| S6 | Does the Access application cover a copy's owner path? | a credential-less request to the copy's path → refused at the edge · **✅ ANSWERED 2026-10-19:** an `owner-…` path is covered. No token → 403 from Access at the edge (a Cloudflare Access header, and no n8n execution created); the owner service token → 200 from n8n; the n8n API's service token → 403. Executions went 0 → 1: only the owner-token request reached n8n |
| S7 | On-demand execution for schedule-triggered copies (Reminders, Purge) | **Ruled by Q13: no manual/test execution.** A declared temporary webhook trigger, only behind Access (S6 first), removed before the swap and proven absent by the diff tool |
| S8 | n8n → Postgres by service name; the credential works; DDL is refused | a SELECT, then a `CREATE`, through n8n · **✅ ANSWERED 2026-10-19:** the connection by service name works and runs as `salon_app` on `salon`. Each attempt was wrapped so that a success rolls itself back, and Postgres's own messages show all five refused: CREATE TABLE "permission denied for schema salon" · DROP "must be owner of table leads" · TRUNCATE "permission denied for table leads" · ALTER "must be owner" · TEMP "permission denied to create temporary tables". CONNECT on the `postgres` database: false |
| S9 | one Airtable record with an ABSENT field, the case no recorded fixture covers (§3b). **Ruled (Q4): rides on D6c's export read, not on D2** | none extra: read from the export |
| S10 | Under `continueErrorOutput`, the configuration of all ten Purge/Reminders data nodes: per-item routing and the error item under `independently` and `single` (the Q18 premise check, §3r) | 3 items, item 2 failing on a row-dependent cast · **✅ ANSWERED 2026-10-20 (§3r):** `independently`: rows 1 and 3 on output 0, row 2 on output 1, 1 row left; the error item keeps the input's keys plus an `error` object, with no `message`, so the builders' detail value is `[object Object]` (rendered `-object Object-`). `single`: the whole batch undone, one `{error, message}` on output 1, detail = the SQL error text. Q18 holds as ruled |

## 10 · Budget and emergency exit

| Step | Rounds (Claude) | Yigitcan's hands |
|---|---|---|
| D1 | 1–2 | ruling |
| D2 | 4 | compose + secrets · n8n credential · credential-decryption test · HMAC line |
| D3 | 3 | approvals per copy/activation |
| D4 | 4 | approvals · Turnstile window |
| D5 | 2 | dashboard env |
| D6 | 3 | backup-job approval · off-server choice · external probe · Airtable revocations |
| D7 | 1 | — |
| **Total** | **18–19** | |

*These are estimates. The cost report's 12–14 excluded re-verification; this budget includes it.*

**⚠ SUPERSEDED 2026-10-22: the round-count budget (the original estimate table above and the re-baselined counts below) no longer governs (Yigitcan: the round count is not
reliably countable).** It is kept as history. **The stop rule that replaces it:** the migration stops on
**(a)** a third fix-of-a-fix (unchanged), **(b)** a step stopping twice on the same unresolved question, or
**(c)** D6b's acceptance not reached by **2026-11-08**. On a stop, **Airtable Team** is put on the table.
*Note:* the Airtable quota may reset around 2026-11-01 (unmeasured); if it does, the comparison is redone.
**Speed plan (same day, §3r):** nothing waits on the soak except D6c's revocations · D3e is daytime-only ·
Reminders' K-3 drills ride in D4's M7 window · Q16 and D6d move to the final security pass.

**Re-baselined (Yigitcan, 2026-10-20; superseded 2026-10-22, above):**
- **The work remaining from now:** D3 4 · D4 6 · D5 2 · D6 4 · D7 1 = **17 rounds**.
- **The emergency exit sits at 1.5× that: 25 rounds from now** (25.5, rounded down, as the original
  rounded 27–28.5 to 28). "Third fix-of-a-fix" stays.
- **The per-step 2× rule reads against these re-baselined step budgets, counted from 2026-10-20** (D3: 2× 4
  rounds). This is how the ruling is read here; Yigitcan corrects it if he meant otherwise.
- **Reason on record:** the rounds were cut smaller on purpose, for step-by-step control, so the original
  budget's unit no longer matches. No stop so far was non-convergence.
- The table above is kept as the original estimate.

**Emergency exit (declared at D1, before any measurement; re-baselined 2026-10-20; its round-count triggers are SUPERSEDED by the 2026-10-22 stop rule above, and the on-exit steps below still hold):** stop the phase if **the total passes 1.5× the
budget (28 rounds; from 2026-10-20: 25 rounds from then)**, or **any single step passes 2× its own budget without meeting its exit gate.**
- On exit: the copies are kept inactive; the originals remain the active code path; Postgres and its
  volume are kept.
- The proposal on the table becomes **Airtable Team**. Its price is not measured; Yigitcan reads it.
- "Third fix-of-a-fix" (the brief's stop rule) also stops a step regardless of budget (now stop rule (a) above).

## 11 · Rulings (Yigitcan, 2026-10-19: "onaylıyorum", with Cowork's recommendations)

- **Q1 ✅** No data migration: an empty schema plus the `mig-` seed.
- **Q2 ✅** Test per workflow, swap in one coordinated cutover; the Purge rehearsal is the one exception.
- **Q3 ✅** The `rec`+14 id format is kept.
- **Q4 ❌** D4 does NOT wait for the absent-field fixture. S9 rides on D6c's export read; D4 proceeds on
  the recorded shapes, the static scan and end-to-end drills.
- **Q5 → Phase 7.** The migration's rule is "behaviour does not change", so the equivalence proof stays
  clean.
- **Q6 ✅, with the wording corrected** (§3g): no DIRECT write; an INDIRECT write through n8n is held by
  a procedural boundary (the approval gate), not a technical one.
- **Q7 ✅** Postgres on `127.0.0.1` only.
- **Q8 → decided in D6**, not now.
- **Q9 ✅** A 7-day soak.
- **Q10 ✅ APPLIED 2026-10-19, before Main's copy was taken** (§3f, with its evidence).

**Raised at D2a's close (2026-10-19), both ruled the same day**
- **Q11 ✅ APPLIED 2026-10-19 on the original, before D3 copies it.** `Shape Drill State` now answers
  `STORE-ERROR|<read>` when a store read failed. Live, with the store down: control `NOT-FOUND|0` →
  treatment `STORE-ERROR|read-conversation+count-markers`; only that node's code changed. `run-d11.sh`
  treats it as a hard failure on BOTH of its routes (an allow-list of reading shapes; its direct read now
  returns `READ-FAILED` on an error JSON), and both guards are in `check-all` (see ARCH-DEC 2026-10-19).
  **For D3:** an error item that also carried an `id` would read as found, and so would a node-level
  throw that passes its input through unchanged (auditor's recollection of n8n core, not verified). That is theoretical with
  Airtable's measured error shape, and the Postgres version adds a positive identity check on the markers
  (`message_id` equals the requested one). Originally: Drill State Read presents an infrastructure error as "not found".
  - **Measured:** both of its Airtable reads returned error items (quota/rate message), and the
    response was still `NOT-FOUND|0` with 200.
  - **Why it matters:** `run-d11.sh` uses this endpoint as its state oracle. During a store outage, an
    "unchanged" assertion can pass because both readings are the same `NOT-FOUND|0`, which is a silent
    failure in a test instrument (CRT #6's class).
  - **Why the migration cannot fix it inside the copy:** the defect sits in `Shape Drill State`, outside
    the data layer, so the mechanical diff rule (§4) forbids changing it in D3's copy.
  - **Options:** fix the ORIGINAL before D3 copies it (Q10's pattern), or leave it to Phase 7 and mark
    every CRT #11 run during an outage as not evidence.
  - **Recommendation:** fix it before D3. D3 re-proves CRT #11 through this exact oracle.
- **Q12 ✅ ruled and applied 2026-10-19.** For any workflow that uses a database credential, the
  approval gate names: creating it · activating it · editing it, active or inactive · executing it by
  hand, active or inactive (§3g). *The first version named only the first two; the audit found the rest
  open.*
- **Q13 ✅ ruled 2026-10-19, with Yigitcan's condition "nothing runs by hand, no manual at all if
  possible":** n8n's manual/test execution is NOT USED in this phase. Schedule-triggered copies go through
  a declared temporary webhook trigger, only behind Access and removed before the swap. If a manual run
  looks unavoidable, stop and ask. Drill requests to an approved active workflow's normal trigger are
  outside the rule (`irreversible-actions.md`). Originally asked: Read literally, it could
  include the signed drill and regression POSTs Claude sends to Main's production webhook once Main
  uses a database credential (D4 onward); then every regression run would need approval. **Intended
  scope unconfirmed.** Is it n8n's manual/test execution only, or webhook drills too? Must be ruled before
  D4.

**Raised in D2b-3 (2026-10-19 / 2026-10-20)**
- **Q17 ✅ ruled 2026-10-20 (Yigitcan): (a).** The owner replay marker becomes `INSERT … ON CONFLICT
  (message_id) DO UPDATE SET message_id = EXCLUDED.message_id RETURNING id`; `Record Processed` (Main) stays
  `DO NOTHING`. The premise was measured before it was recorded (§3p).
- **Q18 ✅ ruled 2026-10-20 (Yigitcan): (a) `independently`** for the four multi-item write nodes (§3p). The
  alert builders' detail fix is a mandatory Phase 7 item.
- **S4's auth-failure shape ✅ ruled 2026-10-20:** D2 may close with it open; its branch is drill M7 in D4
  (REVOKE CONNECT on `salon_app`, existing credential, operator step), residual as stated in §3p.

**D3 plan (2026-10-20)**
- **✅ APPROVED by Yigitcan (plan-gate), with rulings K-1 to K-7** (§3r). The round runs S10 → D3a → D3b → D3c →
  D3d, each step committed and stopped for review. D3e needs its own written go-ahead.

**D4 plan (2026-10-23)**
- **✅ APPROVED by Yigitcan (plan-gate), with rulings D4-1 to D4-9** (§3s). D4 runs D4a → D4b → D4c, each step
  committed and stopped for review. D4-5 (the calendar) gated D4b and was cleared on 2026-10-23 with a canary.

**D5 + D6a + D6b plan (2026-10-23)**
- **✅ APPROVED by Yigitcan (plan-gate), decisions 1–14 with amendments to #7, #11 and #12** (§3t). Target: done and
  Phase 7 resumed by 2026-10-26 night; 2026-11-08 stays the emergency exit. Three rounds: offline builds → live checks
  + D6a operator block + Codex → D6b window and acceptance.
