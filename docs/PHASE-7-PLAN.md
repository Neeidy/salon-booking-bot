# Phase 7 — Test + Codex + DoD · PLAN v3

> **Status:** APPROVED by Yigitcan, 2026-09-17. Derived against `232321c` (181 files).
> **This file exists because v2 did not.** The Phase 7 plan was produced once before, lived only in
> chat, and evaporated — so v3 had to be derived from scratch. A plan that is not in the repo is not a
> plan, it is a memory (`governance-sync.md` §2: every standing decision lands in the repo).
> **v3 was re-derived, not inherited:** v2's premises had all moved — 6d did not exist, the `leads` TTL
> did not exist, the ship gate was not consolidated, and the Codex findings had not arrived.

## ⚠ STEP 0 — before the first BUILD step

**Ship-gate #17: `CF_API_TOKEN` revoked or reduced to Read, AND the four leaked credentials rotated.**
Yigitcan's hands. CP 7-0 does not start until it is done. Planning was not blocked by it; building is.

---

## §1 · DISTANCE TO SHIP — measured from the repo, 2026-09-17

| DoD item (`testing.md`) | State | Evidence |
|---|---|---|
| built | ✅ | 5 live workflows (191·19·27·44·9), 3 web apps, 181 files |
| **tested** (happy + key edge) | **◐ two distinct gaps** | `run-regression.sh` carries 25 assertions, but `fire()` hard-codes `channel:"widget"` → one lane only; and the file's own header says it gets `403 turnstile_failed` against the production gate and passes ONLY with `channels.widget.turnstile.enabled` flipped false. 3 unit files. `run-d11` 13/13 |
| cleaned | ☐ | never run repo-wide for this phase |
| sanitized | ✅ | 5 exports equal live; `secret-scan` / `host-leak` 0 |
| **README / case-study** | **◐** | README §"Case study — the embeddable widget (Phase 6b)" exists; `docs/CASE-STUDY.md` does NOT |
| pushed | ✅ | `232321c` |
| resume-point memory | ✅ | written AND read back, SHA matched |
| Loom | ☐ | ship gate 20 |

**Critical-Review Targets — counted, not recalled:** 14 rows · **5 closed** (3·7·8·10·13) · **9 open**
(1a·1b·2·4·5·6·9·11·12).

🔴 **Cross-surface drift found while measuring:** `MASTER-BRIEF.md` §9 still shows **#11 as `[ ]`** while
`docs/ROADMAP.md` records `CP 6d · CRT #11 REMEDIATION` as done. Two surfaces disagree, two days apart.
CP 7-2 reconciles it — by ticking it after an audit, or by writing why it cannot be ticked. Not by the
build ticking its own row.

**v1 scope (`MASTER-BRIEF.md` §7) vs what exists:** *golden set · edge · jailbreak · critical-targets
audit · sanitize · README/case-study · Loom.* `golden-set.md` (18 lines) and `jailbreak-cases.md`
(44 lines) EXIST but **neither has been run in this phase**; `sanitize` ✅; case-study and Loom missing;
the audit has 9 open rows.

### Open items — four buckets

| Bucket | Items | One-line reason |
|---|---|---|
| **PHASE 7** | the regression's Turnstile blocker · CRT 1a/1b/2/4/5/6/9/11/12 · `CASE-STUDY.md` · `RUNBOOK.md` · K-2 dead keys · the §9 #11 drift · the `handoffShown` twin (the parity suite stays green if one caller is deleted) · `golden-set`/`jailbreak` never run | all of them are inside the definition of "test + audit + DoD" |
| **SHIP GATE** | 11–20 (one numbered list in `ROADMAP.md`) | needs deployment or Yigitcan's hands; not build work |
| **v2 / LATER** | `Idempotent Replay` stored reply · `messageTemplates` schema requirement · transcript loss on navigation · font subsetting · `Customers` table · BULGU-4 · R2 · the W57/W58/W60 text mismatch | improves the product but does not change whether it can be sold |
| **DELETE** | *(empty)* | every open item belongs to a bucket or is already closed; an invented "delete" bucket would be padding |

---

## §2 · STANDING RULINGS — premise re-checked, not assumed

| Ruling | Premise still alive? | Verdict |
|---|---|---|
| **K-2** dead `instagram` + `business.locale` keys | ✅ `instagram` in 8+ surfaces, `locale` in both examples + the schema | VALID · the `MASTER-BRIEF` §4 scope change goes in the decision log |
| **K-4** separate `docs/CASE-STUDY.md`, README's 6b section **MOVED** | ✅ file absent, README section present | VALID |
| **K-5** regression from the widget lane | ✅ **measured**: `fire()` hard-codes `channel:"widget"` — it can target that lane, and ONLY that lane | VALID, with the two lines below |
| **E2** `docs/RUNBOOK.md` | ✅ file absent | VALID |
| **K-3** Loom stays at ship gate 20 | ✅ at 20 | VALID · no checkpoint budget may absorb it |

**K-5's two lines, which go into the "tested" DoD as TWO SEPARATE ENTRIES:**
1. **What it proves:** the engine's end-to-end behaviour on the widget lane.
2. **What it does NOT prove:** the WhatsApp adapter boundary is never crossed. `Normalize Inbound`
   selects the lane from the signature header, and a widget run never executes that branch. "Regression
   green" is not "the WhatsApp path works".

---

## §3 · GOAL

> **At the end of Phase 7, this template's central sales claim — "no code change, a new config file and
> new credentials" — can be demonstrated from a single artefact; and the claim that the engine behaves
> correctly rests on evidence gathered WITHOUT lowering any security control.**

Not "close the list". The sentence is derived from §1's two largest gaps: there is no RUNBOOK, and
"tested" currently passes only with the gate down.

---

## §4 · CHECKPOINTS — grouped by class, riskiest seam first

| CP | What | Why here | Round budget | First thing dropped on overrun |
|---|---|---|---|---|
| **7-0** | **THE RISKY SEAM: make the regression runnable WITHOUT lowering Turnstile.** Measure first: a real-token path, a separately signed test lane, or not possible | Everything rests on it. Today "tested" means *"passed with the gate down"* — and lowering the gate is a declared stop condition | **2** | If impossible: **do not redesign** — STOP and report. "I lowered the gate and ran it" is not an option (ruling K-1: it closes as *"run only with the gate down"* and the real-token run becomes **ship gate 21**) |
| **7-1** | **ONE MECHANISM, SIX CRTs**: a live regression plus targeted drills → CRT **1a·1b·2·5·6·12** | Six rows fed by one evidence source; the highest leverage on the list | **4** | 1b (concurrency) — the most expensive drill, and CRT #8 already records a residual |
| **7-2** | **What drills cannot prove → audit**: CRT **4** (secret/PII) · **9** (dashboard auth) · **11** (reconcile the §9 drift) · **12**'s five R3 items. Yigitcan triggers Codex; this build prepares | These are claims about SHAPE, not behaviour; they need reading, not drilling | **3** | 9 → moves to ship gate 18, where its twin already lives |
| **7-3** | **Artefacts**: `docs/CASE-STUDY.md` (K-4, **moved** from README) · `docs/RUNBOOK.md` (E2, dry-run) · K-2 dead-key removal · the `handoffShown` twin | All file work, zero live risk; last because they must carry 7-1/7-2's findings | **3** | K-2 → drops to the v2 bucket; a dead key produces no wrong behaviour |
| **7-4** | **DoD closure**: `cleaned` · run `golden-set` + `jailbreak` · memory · one commit + push | The definition itself | **1** | Nothing — if this CP drops, the phase does not close |

**Total 13 rounds.** Deliberately not uniform: 7-1 gets four because it feeds six CRTs; 7-4 gets one
because it is only the close.

---

## §5 · SKELETON

**New:** `docs/CASE-STUDY.md` · `docs/RUNBOOK.md`
**Changed:** `tests/run-regression.sh` (per 7-0's finding) · `README.md` (6b section REMOVED, pointing at
CASE-STUDY) · `MASTER-BRIEF.md` §4 (K-2) and §9 (#11) · `config/client.config.example{,-b}.json` +
`schemas/client.config.schema.json` (`locale`, `instagram`) · `web/snippet/src/index.ts` (the twin) ·
`docs/ROADMAP.md` · `docs/ARCHITECTURE-DECISIONS.md`
**n8n:** depends on 7-0's decision. **No new capability family** — NOT-build.

## §6 · INTEGRATIONS
Airtable (reads + drill writes) · Google Calendar (**real event creation in 7-1, approved as part of this
plan under K-3's conditions**) · LLM (regression rounds — quota) · Telegram (alert verification) ·
**Zernio stays CLOSED** (NOT-build).

## §7 · MOCK DATA
Every drill row carries a `d11-` / `reg-` prefix, is labelled mock, and is **deleted at the end of its CP
with a before/after count and the arithmetic shown**. RUNBOOK's dry-run uses
`client.config.example-b.json` — no real customer data. **K-3's conditions:** mock-prefixed titles · the
demo calendar only · deletion with arithmetic proof at CP close. A client calendar would be a separate
decision.

## §8 · CRITICAL-REVIEW TARGETS — re-derived, **criterion 2 included**, each with a runnable check

| CRT | Criterion | Verification command |
|---|---|---|
| 1a idempotency | 4 | `bash tests/run-regression.sh` (dedupe assertion) · `bash tests/run-d11.sh` (marker counter) |
| 1b concurrency | 4 | two parallel `curl`s into one slot → `appointments` count = 1 |
| 2 Calendar write | **1 + 2 (quota)** | the `Book Appointment` execution + a calendar read; **the Google API quota is counted and declared before measuring** |
| 4 secret / PII | 3 | `bash scripts/secret-scan.sh </dev/null && bash scripts/check-no-host-leak.sh` |
| 5 handoff threshold | 1/5 | the regression's uncertain-turn scenarios + the `conversations.stage` column |
| 6 error visibility | 5 | inject a failure → the error branch in the execution + Telegram `ok:true` |
| 9 dashboard auth | 3 | **NOT MEASURABLE TODAY — ship gate 18.** This sentence stands in place of a command (Yigitcan's ruling K-2: the row stays `[ ]` with the note "measurable at gate 18") |
| 11 D11 write path | 1/3 | `bash tests/run-d11.sh` → 13/13 |
| 12 date resolution | 1/4/5 | `node tests/unit/resolve-date.test.cjs` + an audit of the five R3 items |
| **NEW: LLM spend / quota** | **2** | read `bot_metrics` + drill the `LLM_COST_CAP_USD` brake — *criterion 2 has never produced a row in §9 until now* |

## §9 · ACCEPTANCE CRITERIA
1. The regression passes **with Turnstile ON** — or, if it cannot, the reason is measured and written.
2. The "tested" DoD carries **two separate lines**: what was proven, and that the WhatsApp adapter
   boundary was not.
3. Every CRT row that closes has a verification **shown able to go red**.
4. `RUNBOOK.md` exists, its dry-run is verified, and it is labelled **"NOT run end to end"**.
5. `CASE-STUDY.md` exists and that section is **gone** from README — moved, not copied.
6. The §9 #11 drift is reconciled.
7. Gates 0; `run-d11` 13/13; five exports equal live.

## §10 · DRILL MATRIX

| Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|
| duplicate message | same `messageId` twice | one booking | `Check Processed` | a second `Book Appointment` |
| **same slot, two customers** | two parallel requests | **see the measured expectation below** | `Verify Slot` · `Check Race` · `Race Gate` | two `Write Appointment` |
| jailbreak | from `jailbreak-cases.md` | handoff, no write | `Mark Handoff` | `Route Intent`'s write branch |
| uncertain turn ×2 | two low-confidence turns | 1st clarify · 2nd handoff | `Repeat Uncertain?` | `Mark Handoff` on the first |
| missing `dateExpr` | remove the key | `extraction-transient`, no lock | `Extraction Transient?` | any `stage` write |
| DST boundary | booking near the boundary | correct wall-clock time | `Resolve Date` | — |

## §11 · AUTOMATION-FIT
**NEITHER**, re-derived rather than inherited. `/loop` waits on a condition; here each CP's output
changes the next one's DESIGN (7-0's finding decides how 7-1 runs). `/goal` wants autonomous
convergence; half of this phase is **Codex, triggered by Yigitcan** and **a rotation in his hands**.

## §12 · NOT-BUILD
✗ deployment · ✗ opening Zernio · ✗ Supabase · ✗ v2 RAG · ✗ deleting `Customers` · ✗ closing a
ship-gate item "while we're here" · ✗ a new n8n capability family · ✗ **lowering Turnstile for a drill**
· ✗ the eight items in the v2 bucket

---

## M1 · IS TURNSTILE ACTUALLY ON RIGHT NOW? — measured 2026-09-17

**YES. There is no live gap.** Asked two independent ways, because a config value and a behaviour are
two different claims:

- **Config:** the live `Load Config` carries `turnstile: { enabled: true }` in **both** the draft and
  the **published** graph — the one the webhook actually runs.
- **Behaviour:** a real widget-shaped request with a dummy token returns
  `403 {"ok":false,"error":"turnstile_failed"}`.

**Why this was asked at all, and it was the right question:** `run-regression.sh` passes only with the
gate down, so if anyone had flipped it for a drill and not flipped it back, that would not be a planning
item — it would be a live exposure of the same shape as the dev server this repo left listening for 37
hours. It was flipped back. **Nothing to fix; the check is recorded so the next reader does not have to
wonder.**

## M2 · WHAT THE ENGINE DOES TODAY ON A LOST RACE — measured 2026-09-17

The drill matrix's expected value was *"one booking + handoff"*, taken from `booking-integrity.md`'s
design intent and **never measured**. Measured from the live graph, the real behaviour is **richer, and
one branch the matrix never named**:

```
Verify Slot ──► Check Race ──► Race Gate ──┬─ true  ─► Cancel Our Event ─┬─► Build Race-Lost State ─► Save State (Post-Write)
                                           │                             └─► Build Orphan State
                                           └─ false ─► Write Appointment
```

- The **winner** writes the appointment.
- The **loser**'s calendar event is **cancelled**, and `Build Race-Lost State` sets
  `stage: 'handoff'`, clears `gcal_event_id` and writes a `computed_reply`.
- ⚠ **`Check Race` FAILS CLOSED, and this is the part the old expected value would have mis-read:** if
  the calendar list came back paginated (`nextPageToken`) or in a different timezone, it sets
  `race_lost: true` with **`race_other_count: -1`** and `verify_incomplete: true`. So a handoff can be
  produced by an *incomplete verification* rather than by a real race. A drill asserting only "handoff
  appeared" would pass for the wrong reason.
- ⚠ **A third outcome exists:** if `Cancel Our Event` FAILS, the loser goes to `Build Orphan State` —
  neither booked nor cleanly cancelled. The matrix named two outcomes; the engine has three.

**MEASURED EXPECTED VALUE for the drill (this replaces the assumed one):**
1. exactly ONE `appointments` row with `status='booked'` for that slot;
2. the loser's `conversations.stage = 'handoff'` with `gcal_event_id` cleared;
3. the loser's calendar event **cancelled**, not orphaned;
4. **`race_other_count >= 1`** — this is what separates a REAL race from a `verify_incomplete` handoff,
   and without it the case is not evidence;
5. `Build Orphan State` did NOT run.

⚠ **This is a STRUCTURAL measurement, not a behavioural one.** It says what the graph does; it does not
say what happened, because firing two concurrent widget bookings needs the Turnstile gate — which is
exactly CP 7-0. The behavioural confirmation belongs to CP 7-1 and is not claimed here.
