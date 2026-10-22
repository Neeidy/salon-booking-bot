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
| **D3** | **The four small workflows as copies:** Drill State Read → Owner Actions → Reminders → Processed Purge. Each is an inactive copy, with mechanical diff, contract test and drills on a test path. **Purge rehearsal:** swap → verify → re-activate the original → verify → leave the copy inactive. **Plan APPROVED 2026-10-20 with rulings K-1 to K-7 (§3r); D3e needs its own go-ahead.** **S10 ✅ · D3a ✅ · D3b ⚠ (Q17 race gap, evidence accepted) · D3c ⛔ waiting for the operator's binaryMode step · D3d not started (§3r).** | 4 copies green · rehearsal measured in both directions |
| **D4** | **Main as a copy:** 17 nodes, 8 filter formulas (18 across all five), 43 `fields` references kept byte-identical by the contract shape | diff + contract + drills green; Turnstile window protocol on the COPY |
| **D5** | **Dashboard + tools:** `airtable.ts` → a read-only Postgres client · `run-d11.sh` PAT route · parity masks · `.env.example` | CRT #10's boundary re-proven against Postgres |
| **D6** | **a) Pre-cutover gate:** `pg_dump` in the nightly job plus a restore test (§3j). **b) Coordinated cutover + acceptance window.** **Phase 7's premise re-check happens at D6b's acceptance, and Phase 7 starts right after it** (ruling 2026-10-20). **c) Soak, then the Airtable shutdown** behind the export gate (§7). The 7-day soak runs in the BACKGROUND; only D6c and D7's close wait for it. **d) Permanent off-server target.** | acceptance suite green · rollback trigger list armed · export taken before any revoke |
| **D7** | Close: governance surfaces (rules, DATA-MODEL, MASTER-BRIEF stack, README), test-data cleanup, resume point. *(The Phase 7 premise list moved to D6b's acceptance, ruling 2026-10-20.)* Waits for the soak. | DoD |

*Why D6 carries the shutdown and not D7: the D0 rulings already attach the Airtable export gate and the
off-server target to D6 (ARCHITECTURE-DECISIONS 2026-10-19). Moving them would contradict a recorded
ruling, so they stay. The soak sits inside D6 so that the rollback target outlives the cutover.*

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
  write is listed, so the CHECK does not reject a value the flow legitimately produces. *Not yet measured.*
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
| `Record LLM Spend` (upsert) | `INSERT … ON CONFLICT (period_key) DO UPDATE SET cost_usd = EXCLUDED.cost_usd` (1:1, absolute) | duplicate period rows |

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
- **Negative control:** a dump with a flipped byte must fail `pg_restore`, and the checksum must go red
  (D0's lessons: `integrity_check` and `bundle verify` both checked less than assumed).
- **The nightly job lives outside the repo**, so editing it needs Yigitcan's approval
  (`irreversible-actions.md`, writing outside the repo root).
- **Permanent off-server target: decided in D6, not now (ruling Q8).** Recommendation on the table: a
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
  - Q16 (split `salon_ro`'s column access before D5);
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
| **K-7** | **(a), full verification:** the copy's scheduled run (`triggerAtHour: 4`), then the original's next scheduled run (two nights). |
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
trigger is a NEW node named **`Temporary Test Trigger`**. It is not in any export yet; the diff tool's
selftest uses its own fixture name. **A copy's test path is a fixed `owner-mig-<workflow>` name with no random part.** It sits in
the committed copy spec and export, behind Access and the HMAC signature, exactly like the production paths the public
exports already carry. *(Corrected at D3a: this sentence first promised that no full test path would enter a commit, a promise
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

*Owner alerts (K-5):* Purge alerts are throttled per branch for 30 minutes, so after W1 they are measured
from the error item and the builder's output, not from Telegram.

**D3e · the Purge rehearsal (NOT in this round; its own go-ahead).**

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
   - the aged and fresh `mig-` rows are seeded.
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

*Side effect:* the original's Airtable clean-up is skipped for one night. Its filter is "older than the
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
| M7 | Store-outage visibility | 5 | revoke `salon_app` CONNECT for one drill → Main returns infra-unavailable (5xx + flag) and alerts the owner; the brain MUST-NOT-RUN |
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
5. A permanent off-server copy exists.
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
     acceptance. Only D6c (these revocations) and D7's close wait for the soak.
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

**Re-baselined (Yigitcan, 2026-10-20):**
- **The work remaining from now:** D3 4 · D4 6 · D5 2 · D6 4 · D7 1 = **17 rounds**.
- **The emergency exit sits at 1.5× that: 25 rounds from now** (25.5, rounded down, as the original
  rounded 27–28.5 to 28). "Third fix-of-a-fix" stays.
- **The per-step 2× rule reads against these re-baselined step budgets, counted from 2026-10-20** (D3: 2× 4
  rounds). This is how the ruling is read here; Yigitcan corrects it if he meant otherwise.
- **Reason on record:** the rounds were cut smaller on purpose, for step-by-step control, so the original
  budget's unit no longer matches. No stop so far was non-convergence.
- The table above is kept as the original estimate.

**Emergency exit (declared at D1, before any measurement; its round counts were re-baselined on 2026-10-20, above):** stop the phase if **the total passes 1.5× the
budget (28 rounds; from 2026-10-20: 25 rounds from then)**, or **any single step passes 2× its own budget without meeting its exit gate.**
- On exit: the copies are kept inactive; the originals remain the active code path; Postgres and its
  volume are kept.
- The proposal on the table becomes **Airtable Team**. Its price is not measured; Yigitcan reads it.
- "Third fix-of-a-fix" (the brief's stop rule) also stops a step regardless of budget.

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
