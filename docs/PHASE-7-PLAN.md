# Phase 7 — Test + Codex + DoD · PLAN v3

> **Status:** APPROVED by Yigitcan, 2026-09-17. Derived against `232321c` (181 files).
> **This file exists because v2 did not.** The Phase 7 plan was produced once before, lived only in
> chat, and evaporated — so v3 had to be derived from scratch. A plan that is not in the repo is not a
> plan, it is a memory (`governance-sync.md` §2: every standing decision lands in the repo).
> **v3 was re-derived, not inherited:** v2's premises had all moved — 6d did not exist, the `leads` TTL
> did not exist, the ship gate was not consolidated, and the Codex findings had not arrived.

## Ship-gate #17 — MOVED to the end-of-phase security pass (Yigitcan's ruling, 2026-10-18)

**Ship-gate #17** (`CF_API_TOKEN` revoked or reduced to Read, AND the four leaked credentials rotated)
**is no longer the gate in front of CP 7-0.** It moved to a security pass at the END of Phase 7. It stays
OPEN on the ship gate — the row is not deleted, only its position changed.

*(This section used to read "STEP 0 — before the first BUILD step … CP 7-0 does not start until it is
done." That was the plan as approved on 2026-09-17; the rotation then stopped on a measured capability
wall — the Cloudflare account id is unreachable from this machine — and the plan is corrected in place
rather than annotated beside, per `governance-sync.md` §6.)*

**Why the deferral is safe:**
*Yigitcan's rationale (his ruling, recorded as given), with what was measured against it:*
- **None of the four leaked values sits on a customer path.** The four that leaked on 2026-09-13 are: two
  Cloudflare service tokens (each an id + secret pair), the n8n API key, and the owner's Telegram chat id.
  The two service tokens gate the n8n API and the owner-only `/webhook/owner-*` path; the API key is an
  operator tool; the chat id addresses the OWNER, not a customer. No customer request is authenticated by
  any of them. *(`CF_API_TOKEN` did NOT leak — it is on #17 because its Edit scope must be reduced after the
  rotation, a separate reason. An earlier draft of this paragraph listed it among the four; corrected.)*
- **The leaked values went into a transcript on the machine that already stores them.** Measured
  2026-10-18: all six variables the leak printed are present in `~/.n8n-api.env` (presence only — values
  not read). ⚠ **That makes "no new exposure" true for THIS MACHINE and not beyond it:** the transcript is
  a session that was also transmitted to the model provider, which this framing does not cover.

**Measured before writing this (2026-10-18), not assumed:** no CP in this plan requires a Cloudflare API
WRITE. Every Cloudflare-shaped line in this file was grepped; the only one that writes to Cloudflare is
#17 itself. (Positive control: `grep -ciE turnstile` returned 9 against `00c626f`, before this round's edits.) ⚠ One conditional: CP 7-0's *real-token* option could turn out to need a Turnstile widget
hostname-allow-list change, which IS a Cloudflare write. That is an outcome 7-0 might discover, not a
requirement the plan states — and if it is the only route, it is blocked by the same missing account id
and 7-0 stops and reports rather than routing around it.

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
ship-gate item "while we're here" · ✗ a new n8n capability family · ✗ lowering Turnstile for ANY purpose other than a regression/drill run under the **window protocol** below *(changed 2026-10-18 by Yigitcan's ruling; this line used to read "✗ lowering Turnstile for a drill")*
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

---

## CP 7-0 · RESULT — measured 2026-10-18 (round 1 of 2) · ⛔ STOPPED for a ruling before 7-1

**Verdict: a real-token path for the automated suite is NOT POSSIBLE from this machine, and every
remaining route either changes the security model or tests only a sliver. Per the plan: no redesign —
stop and report. K-1 applies.**

### The measurement — a 2×2, each cell in a FRESH headless browser

| | Cloudflare's always-pass test key | the REAL site key |
|---|---|---|
| `127.0.0.1` | ✅ token minted | ❌ **error 600010** |
| `localhost` | ✅ token minted | ❌ **error 600010** |

- **The control is what makes the treatment mean something.** The test key mints on both hostnames, so
  the widget script loads and the harness works; the real key fails on both with the same code. ⚠ *Narrower
  than it first read:* an always-pass test key does not run a real bot-detection challenge, so it proves the
  harness and the script — not that this browser could pass a real challenge.
- **What 600010 is, from Cloudflare's own error-code table, not from memory:** `600*` = *"Generic challenge
  failure — Bot behavior detected."* The hostname-allow-list failure is a DIFFERENT code, **110200**
  *"Domain not authorized"*. We got 600010, so **the measured wall is bot detection, and a hostname change would not
  address it.** ⚠ What is NOT measured: whether the hostname list is ALSO wrong — if bot detection is
  evaluated first, a 110200 could be masked behind it. The conditional recorded earlier on 2026-10-18 is
  resolved only in that narrower sense: no Cloudflare write is indicated by what was measured.
- Getting past bot detection would be detection evasion against our own control. It is not an option.

⚠ **An instrument defect was caught on the way, and it would have produced a false PASS.** The first real-key
run reported `TOKEN len=21`. A real Turnstile token is hundreds of characters (Cloudflare's documentation — no real token was minted in this round to measure it); 21 is exactly the length of
`XXXX.DUMMY.TOKEN.XXXX`, the test key's dummy. The control and treatment URLs differed only in their `#`
fragment, which the browser treats as a SAME-DOCUMENT navigation — the page never reloaded, and the driver
read the control's leftover result. Every cell above was then re-run in its own fresh browser with a query
string. **The token's length was the only thing that gave it away.**

### A structural fact that decides the remaining options

`Turnstile Gate` checks only `channel === 'widget'` and `turnstile.enabled === true` — **there is no
session memory**. Every widget message goes to `Verify Turnstile`, and a Turnstile token is single-use
(Cloudflare's documented behaviour; not separately measured here). **So every message needs a fresh token.**

### The routes, and why none is taken without a ruling

| Route | Status | Why |
|---|---|---|
| (a) real token from this machine | ❌ measured impossible | 600010 bot detection, both hostnames |
| (b) a signed test lane in production (HMAC bypasses Turnstile) | ⛔ **security-model change** | replaces a verification layer on the PUBLIC endpoint for signed requests — a declared stop condition; it would also never exercise `Verify Turnstile` itself |
| (c) human-minted tokens (Yigitcan's real browser) | ◐ a sliver only | one token per message × the harness's own header estimate of "~44 requests" (a comment in `tests/run-regression.sh`, not a count), each single-use and short-lived — workable for two or three targeted drills, not for a suite |
| (d) lower the gate for the run | ⛔ forbidden | NOT-build here, and a declared stop condition |
| (e) **PROPOSED, not adopted:** a drill COPY of Main behind `/webhook/owner-*` with Turnstile off in the copy only | ◐ needs a ruling | production's gate never moves and its security model is untouched; the copy is behind Access Service Auth and active only during a drill. ⚠ The cost is a second truth — a copy that drifts tests something that is not production, the exact defect this repo keeps paying for — so it is viable ONLY with a parity check (every node equal to Main except the Turnstile flag) run immediately before each drill, and it does not prove `Verify Turnstile` itself |

### ⛔ THE RULING NEEDED BEFORE 7-1 — a conflict inside the approved plan

K-1 says: if 7-0 cannot be solved, "tested" closes as *"run only with the gate down"* and the real-token run
becomes **ship gate 21**. But this plan's NOT-build also says **✗ lowering Turnstile for a drill**. Read
together, they leave 7-1 with **no live route at all**: the gate up fails on bot detection, the gate down
is forbidden. Which of these governs 7-1 is Yigitcan's to rule — it decides how 7-1 runs, which is exactly
why 7-0 stops here instead of flowing into it.


---

## WINDOW PROTOCOL — Yigitcan's ruling, 2026-10-18

**The NOT-build line above changed.** Turnstile MAY be lowered **only for the duration of a regression/drill
run**, under this protocol, and for no other purpose. This is the security-model stop condition's
pre-approval **for this scope only**: Turnstile only · the widget lane only · the run's duration only. Any
other security change is still a STOP.

**Why, as ruled:** there is no paying customer; a window lasts minutes; the exposure is "findable but not
being looked for", not hidden. **K-1's label is now the accurate description:** *"tested — gate lowered for
the duration of each run, restored and measured after each."* Ship gate **21** (a run with the gate UP =
Yigitcan's real-browser E2E) stays as K-1 set it.

**Every window, inside ONE turn:** lower → run → restore → **measure that it is restored** (published graph
`enabled:true` AND behaviour: a dummy token → `403 turnstile_failed`). A window never crosses a turn
boundary. Open and close times and the duration are recorded. **Every turn begins by measuring the gate;**
found lowered → restore first, measure, and report it as an INCIDENT at the top.

**How a window is executed (designed 2026-10-18, NOT yet run):** a pre-window raw backup of Main; the flip
changes exactly one token (`turnstile: { enabled: true }` → `false` inside `Load Config`), and the diff is
asserted to be that one token before the PUT; the run sits under a hard timeout; restoration PUTs the
BACKUP's own body (not a re-edit) from a shell `trap`, so it happens even if the run fails or is killed; then
both measurements, then `exports-parity` + `live-parity` to prove Main is byte-equal to the commit again.

## CP 7-0 · STATUS 2026-10-18 — protocol designed, window NOT opened

**The window was not opened, and the reason is not the gate.** Declaring the call budget (step 1) found
that **Airtable has refused every API call since 2026-10-06 22:00 UTC** — the monthly quota is exhausted
(`docs/OPERATIONAL-INCIDENTS.md` OPS-5). With the data layer down, every regression turn fails at
`Load State`: all assertions would go red for the quota, not for the behaviour under test. Control and
treatment cannot separate, which is a declared stop condition — and a window with no evidential value is
pure exposure. **The gate stayed UP the whole turn.**

**Step 1 — measured:**
- **LLM cost cap:** `llmCostCapUsd: 10.00` in the PUBLISHED config (`maxTurnsPerConversation: 12`,
  `killSwitch: false`). The brake reads spend from Airtable; on a read error its path goes only to an owner
  alert and never reaches `Build LLM Request` — **it fails closed**, read from the published graph. ⚠ Its
  BEHAVIOUR (a turn refused at the cap) was NOT measured: that needs Airtable, and lowering the cap is outside
  the approved scope.
- **Call budget — declared, and the declaration is what found the outage:** one window ≈ 52 requests
  (the 46-request suite + 4 for the race drill + 2 for a DST booking), each making several Airtable calls,
  plus counting and K-3 cleanup. Against that, the scheduled jobs' OWN cost — measured from real executions on
  a day with nothing to remind or purge, so a floor — already takes **the large majority of the free plan's
  monthly allowance**. *(The per-turn estimate and the window's total are an ESTIMATE from the graph, not a
  measurement. Exact counts are deliberately kept out of this public repo — combined, they let a stranger
  compute how few widget messages would take the data layer down for a month. Figures are in the round
  report.)*

## 7-1 · WINDOW PLAN — PROPOSED, not run

**First criterion, as asked: the fewest windows and the shortest total time.** Answer: **ONE window, ~7
minutes**, plus everything else outside it.

**Inside the window — only what genuinely needs the widget lane with the gate down:**

| Work | Requests | Feeds |
|---|---|---|
| the full regression suite | 46 | CRT 1a (idempotency #3) · 2 (book / cancel / reschedule) · 5 (handoff, clarify ×2, lock) · 12 (past / invalid / pre-hours dates) · part of 6 |
| the race drill — two bookings fired in parallel into one slot, then both "yes" | 4 | CRT 1b, asserted on the M2 expectation (`race_other_count >= 1`, no orphan) |
| one DST-boundary booking | 2 | CRT 12 |

~52 requests at `PACE=4` (the edge rate limit is 20/min/IP; the pace is not a workaround, it keeps us under
our own rule) ≈ 3.5 minutes of pacing + model latency ≈ **6–7 minutes, one window.**

**Outside the window — gate UP, no exposure:** `run-d11` (owner path, not the widget lane) · the unit
suites (`resolve-date`, `validate-intent`, `locked-once-parity`) · error visibility on the scheduled
workflows (OPS-5 is itself a live demonstration of it) · reading executions for MUST-RUN / MUST-NOT-RUN
nodes · the K-3 cleanup counts · both parity gates.

**A saving to rule on:** CP 7-0's remaining deliverable — "prove the protocol end to end once" — is the
SAME act as 7-1's window. Running them as ONE window instead of two halves the exposure and the quota cost.

**Preconditions for that window, all measured at the start of its turn:** (1) Airtable answering again —
quota reset or plan change (Yigitcan) — AND the remaining allowance, read from the workspace usage page,
measured above the window's declared budget with margin, since background jobs keep consuming daily; (2) the gate measured UP; (3) baseline row counts
taken for K-3's arithmetic.
