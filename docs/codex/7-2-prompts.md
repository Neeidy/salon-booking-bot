# Phase 7-2 — Codex audit prompts (Tur 1)

The exact text each Codex run received. A run's prompt is the `common` block followed by its target block, with
`{PIN}` replaced by the SHA of the commit that added this file. Nothing else is sent, so the audit can be repeated
from this file alone. Approved template: the 7-2 plan (Yigitcan's rulings 2026-10-25, K1–K5).

**How each run is made (Yigitcan's brief, 7-2 Tur 1):** a fresh `git worktree` at the pin, outside the main checkout ·
`codex exec -s read-only -C <worktree> --json -o <final message>` under a stripped environment (`HOME`, `PATH`,
`TERM` only), session persistence ON (the session file is the log that records each command's working directory),
and these features off: browser and computer use, apps, plugins, image generation, multi-agent, hooks, shell
snapshot. After each run `scripts/codex-containment.py` reads that run's two logs; a flag or a log with no positive
control stops the round.
**Why the containment check exists:** the read-only sandbox blocks writes and network, but Codex's own session
header declares READ access to the filesystem root. Reads outside the worktree are therefore stopped by the prompt
and detected afterwards, not prevented.

**Lanes (no shared files):** A = `1a` → `1b` → `2` → `5` → `6` → `12` → `4` · B = `9` → `11`. A and B run in parallel.

<!-- prompt:common -->
You are auditing a public repository: an n8n-based salon booking chatbot (the engine is exported n8n workflow JSON;
the owner dashboard is a Next.js app; the store is Postgres). The repository is checked out read-only at commit
{PIN} in your working directory.

Rules for this run:
- Audit, do not rewrite. Do not propose refactors or style changes; report defects.
- Read only files inside this repository directory. Do not access any path outside it, environment variables or
  /proc. Use only git history reachable from HEAD: no `--all`, reflog, branch or stash listing.
- No network. Do not modify any file.
- The production workflows are the `n8n/workflow.*.copy.sanitized.json` exports (Main, Owner Actions, Purge,
  Reminders, Drill State). The exports without `.copy` are parked originals; read them only if a record points
  there. `n8n/staged/` holds prepared, not-yet-deployed edits.
- Sanitised values (credential ids, hosts, calendar ids) appear as placeholders. That is intended, not a finding.
- Known, recorded limits: the repository records open items and accepted limits with their stated bounds — in
  `docs/PHASE-7-PLAN.md` (the open-items table's PHASE 7 row, and the final security pass list near the top) and in
  the target's rule files. Such an item is not a finding unless its stated bound or scope is wrong; if it is, say
  so with evidence.
- Do not quote any value that looks like a credential, a host name or personal data; refer to it by file and line.

Report, in Markdown:
1. Findings, most severe first. Each: severity (CRITICAL / HIGH / MEDIUM / LOW) · location (file:line, or workflow +
   node name) · a concrete failure scenario (input or state → wrong outcome) · evidence (the exact code, or an
   offline command you ran and what it showed).
2. What you checked and found sound, briefly, so the coverage of this audit is visible.
3. A verdict on the last line: `VERDICT: pass`, `VERDICT: revise` or `VERDICT: block`.
<!-- /prompt -->

<!-- prompt:1a -->
Target — Critical-Review Target 1a: idempotency. The same inbound message delivered twice must produce one booking,
never two. Risk criterion: shared state (two runs, one row).

In scope:
- Main copy (`n8n/workflow.main.copy.sanitized.json`): `Check Processed`, `Check Processed Errored?`, `Is Duplicate`,
  `Idempotent Replay`, `Dedupe Gate`, `Record Processed`, `Build Dedupe-Marker Alert`, and the path from
  `Receive Inbound Message` / `Normalize Inbound` to them; how the message id is derived.
- `db/schema/001_init.sql` (`processed_messages`), the Purge copy's `Find Old Processed` / `Delete Old Processed`.
- `.claude/rules/booking-integrity.md` §1, `tests/unit/message-id-guard.test.cjs`.

The repository's own claims, with their stated bounds:
- `processed_messages.message_id` is UNIQUE and `Record Processed` uses `ON CONFLICT DO NOTHING`, so a second marker is
  a no-op.
- "The UNIQUE does not close the check-then-record race": two deliveries can both pass `Check Processed` before either
  records. The repository leaves this race open (ruling Q5) and states no bound for it.
- `Idempotent Replay` answers `duplicate_ignored` and returns no stored copy of the first reply (a v2 item).

Questions: is a second booking, a second calendar event or a second outbound reply reachable for one message id on
the current Main copy, by sequential or concurrent delivery? For the check-then-record race: trace what the second
run actually does on the booking path, and state what bounds it, if anything. Does the 30-day TTL open a replay
window that matters?
<!-- /prompt -->

<!-- prompt:1b -->
Target — Critical-Review Target 1b: concurrency / no double booking. Two different customers, the same slot, about
the same time. There is no atomic lock across Postgres and Google Calendar; the guard is write-then-verify. Risk
criterion: race / TOCTOU.

In scope:
- Main copy: `Build Event Request`, `Book Appointment`, `Verify Slot`, `Check Race`, `Race Gate`, `Cancel Our Event`,
  `Build Race-Lost State`, `Build Orphan State`, `Build Verify-Unavailable State`, `Write Appointment`,
  `Build Mirror-Failed State`; the reschedule twins (`Book Reschedule Appointment`, `Verify Slot (Reschedule)`,
  `Check Race (Reschedule)`, `Race Gate (Reschedule)`, `Cancel New Event (Reschedule)`,
  `Build Reschedule Race-Lost State`, `Build Reschedule Race-Orphan State`,
  `Build Reschedule Verify-Unavailable State`); the availability read
  before them (`Get Calendar Busy`, `Compute Availability`, `Slot Gate`).
- `.claude/rules/booking-integrity.md` §2; `docs/PHASE-7-PLAN.md` §4e–§4f (the simultaneous-pair drill record).

The repository's own claims, with their stated bounds:
- `Check Race` treats any OTHER non-cancelled, non-transparent event overlapping our slot as a loss; the loser cancels
  only its own event.
- A verify read that is paginated, or whose calendar timezone differs from the shop's, is treated as lost.
- Accepted limit: "a truly simultaneous pair can make BOTH writers see the other and BOTH yield — no double booking,
  but no booking either." The race must be visible and recoverable.

Questions: is a double booking (two live, overlapping events, or two booked rows for one slot) reachable on the
current Main copy, on the booking or the reschedule path? Does the overlap test match the slot and service duration
in every case it is used? Can a loss be silent, or can a yield remove the other customer's event? Does the accepted
limit's stated bound hold as written?
<!-- /prompt -->

<!-- prompt:2 -->
Target — Critical-Review Target 2: Google Calendar writes. External and hard to undo. Risk criterion: irreversible.

In scope:
- Main copy, every Calendar call: `Get Calendar Busy`, `Book Appointment`, `Verify Slot`, `Cancel Our Event`,
  `Get For Reconcile`, `Delete Booking Event`, `Get Reschedule Busy`, `Book Reschedule Appointment`,
  `Verify Slot (Reschedule)`, `Cancel New Event (Reschedule)`, `Delete Old Event (Reschedule)`; their timeouts,
  `onError` settings and error branches; the reconcile path (`Reconcile Gate`, `Verify Reconcile`, `Reconcile 404?`,
  `Reconcile OK?`, `Classify Reconcile Failure`) and the deterministic event id (`Event ID Valid?`,
  `Reschedule Event ID Valid?`); the cancel and reschedule delete gates (`Cancel Delete Gate`,
  `Classify Cancel Delete`, `Reschedule Delete Gate`, `Classify Reschedule Delete`); `Live Booking?` / dry-run.
- `.claude/rules/spend-safety.md` (timeouts), `.claude/rules/booking-integrity.md`.

The repository's own claims, with their stated bounds:
- Every external HTTP call carries an explicit timeout (15 s for Calendar) and an error branch.
- Recorded open item (3): a customer who cancels and rebooks the exact same slot and service is handed to a human,
  because the deterministic event id stays reserved by the cancelled event (Google answers 409).

Questions: can the bot create an event that no row, reply or alert accounts for (an orphan)? Can it delete or move
an event it does not own, or the wrong one? Is any Calendar failure silent? Can a dry-run path reach a real write?
Are retries or the reconcile path able to create a duplicate?
<!-- /prompt -->

<!-- prompt:5 -->
Target — Critical-Review Target 5: the human-handoff threshold. Low confidence must lead to a human, never to a
guessed action. Risk criterion: wrong action / silent.

In scope:
- Main copy: `Extract Intent`, `Validate Intent`, `Extraction Transient?`, `Repeat Extraction Failure?`,
  `Build Extraction-Retry State`, `Invalid or Handoff Gate`, `Uncertain Turn?`, `Repeat Uncertain?`,
  `Confirm Pending & Uncertain?`, `Build Clarify State`, `Mark Handoff`, `Handoff Reply`, `Check Handoff Lock`,
  `Handoff Lock Reply`, `Merge State`, `Route Intent`, `Load Config` (the threshold).
- `.claude/rules/handoff.md`, `.claude/rules/prompt-injection.md`, `schemas/intent.schema.json`,
  `tests/unit/validate-intent.test.cjs`, `tests/jailbreak-cases.md`.

The repository's own claims, with their stated bounds:
- `confidence < 0.7` (config) marks a turn uncertain. With a cancel/reschedule confirmation pending → immediate
  handoff; otherwise the first uncertain turn asks one clarifying question without a stage change, the second hands off.
- A schema failure with no confirmation pending is `extraction-transient` (no stage change, owner alert); the second
  in a row hands off. An explicit handoff intent or an unparseable model answer hands off on the first turn.

Questions: can a turn below the threshold, or with an invalid or missing field, reach a booking, cancel or
reschedule write, or drop a pending confirmation? Can the ladder loop without ever handing off? Is the threshold read
from config everywhere it is applied? Can message content change the route outside the action allow-list?
<!-- /prompt -->

<!-- prompt:6 -->
Target — Critical-Review Target 6: error visibility. A failure must reach the owner; never silent. Risk criterion:
silent failure.

In scope:
- Main copy: every node with an `onError` setting and where its error output goes; `Build Owner Alert`,
  `Send Owner Alert (Telegram)`, `Owner Alert Failed`, `Alert Context`, `Record Alert Class`, `Alert Record Failed`,
  `Send Error Response`, the `… Errored?` IFs, `Outbound Send Failed`, `Calendar Unavailable Reply`,
  `LLM Unavailable Reply`, `Lead Unavailable Reply`, `Build Spend-Meter Alert`.
- Purge copy (`n8n/workflow.purge.copy.sanitized.json`) and Reminders copy (`n8n/workflow.reminders.copy.sanitized.json`):
  every error branch, `Build Owner Alert (Purge)`, `Build Owner Alert (Reminders)`, the `Owner Alert Failed …` leaves.
- `.claude/rules/handoff.md` ("Infrastructure failure ≠ conversational handoff"), `.claude/rules/n8n-conventions.md`,
  `tests/unit/owner-alert-detail.test.cjs`, `tests/unit/leads-purge-read-error.test.cjs`,
  `tests/unit/reschedule-orphan-alert.test.cjs`.

The repository's own claims, with their stated bounds:
- Every external call has an error path that notifies the owner; an infrastructure failure returns a distinct
  response and is never presented as a conversational handoff.
- Postgres nodes set no statement timeout and the Telegram nodes set no timeout (recorded gaps in spend-safety.md):
  a query that FAILS is routed, a query that HANGS is bounded only by driver/server defaults.

Questions: is there a node whose failure goes nowhere, or ends the execution without an alert or a distinct
response? Is any error item read in a way that loses the reason or the customer context? Can an alert's own failure
hide the original failure? Can the throttle suppress an alert class that should always be seen?
<!-- /prompt -->

<!-- prompt:12 -->
Target — Critical-Review Target 12: date resolution. A wrong-day booking is irreversible, and a model was once wrong
at confidence 0.92, so no threshold catches it. Risk criteria: irreversible + shared state + silent.

In scope:
- Main copy: `Resolve Date`, `Date Alert?`, `Merge Slots`, `Build Event Request`, `Build Reschedule Event Request`,
  `Validate Intent`, the `Extract Intent` prompt / `Build LLM Request`, `Load Config` (timezone, hours).
- `schemas/intent.schema.json` (`dateExpr`), `tests/unit/resolve-date.test.cjs`, `tests/unit/validate-intent.test.cjs`.
- The round-5 record: `docs/ROADMAP.md`, the entry "CODEX ROUND 5 — five R3 items" (items (1) to (5)), and the CRT 12
  evidence in `docs/ARCHITECTURE-DECISIONS.md` §7.

The repository's own claims, with their stated bounds:
- Round 5 (2026-09-09, Airtable era) recorded five R3 items as fixed: (1) the test harness was one node short of the
  escalation loop; (2) placeholder recognition was case-blind on the live side; (3) draft edges were reported as the
  published graph; (4) an accepted gap's cost was recorded wrong; (5) two documents contradicted the record. These
  never went through a second-vendor audit.
- Times are stored in UTC and shown in the shop's timezone; DST is handled at the boundary.

Questions: can a customer's date expression resolve to a different day than the one confirmed, or a slot be booked
at the wrong wall-clock time (DST, midnight, week and month edges, the shop's timezone vs UTC)? Does the confirm path
book the slot the customer was shown? For each of the five round-5 items: is it closed on TODAY's artefacts (the
Postgres copies, the current guards and tests), still open, or no longer applicable — with evidence?
<!-- /prompt -->

<!-- prompt:4 -->
Target — Critical-Review Target 4: secret and PII handling in a PUBLIC repository. Risk criterion: data leak.

In scope:
- `scripts/secret-scan.sh`, `scripts/check-no-host-leak.sh`, `scripts/check-hook-drift.sh`,
  `scripts/check-content-parity.py` (placeholder handling), `.claude/commands/sanitize.md`, `.gitignore`,
  `.env.example`, `tests/unit/staged-sanitised.test.py`, `tests/unit/sanitize-postgres.test.cjs`.
- Every committed export under `n8n/` (including `n8n/staged/`), `db/`, `tests/` fixtures and `docs/` for leaked
  values.
- `.claude/rules/security-secrets.md`, `CLAUDE.md` ("Security — repo is PUBLIC").

The repository's own claims, with their stated bounds:
- Secrets live in n8n Credentials / environment files, never in git; customer PII is never committed; only sanitised
  exports are committed.
- A full widget `sender_key` and a full `gcal_event_id` are bearer credentials (the event id hex-encodes the
  sender key) and must never be committed in full.
- Masking is forward-only: a value masked later still exists at earlier revisions (recorded, not a finding by itself).
- The commit message is a channel the host-leak guard cannot see (stated in that guard's own known limits).

Questions: is there a secret, a host, a real identifier or personal data in a committed file at HEAD? Can a real
value pass the guards (secret scan, host-leak, the sanitise check) into a commit — which shapes do they miss? Can a
committed export carry a full `sender_key` or event id? Do the guards fail closed when their own configuration is
missing?
<!-- /prompt -->

<!-- prompt:9 -->
Target — Critical-Review Target 9: dashboard auth, plus the owner CSV export route and ship gate 18. The dashboard
shows customer PII and holds one destructive action. Risk criterion: data leak / unauthorized destructive action.

In scope:
- `web/dashboard/` — every route (`app/page.tsx`, `app/api/release/route.ts`, `app/api/export/appointments/route.ts`,
  `app/api/export/leads/route.ts`), `lib/` (`store.ts`, `exportCsv.ts`, `mask.ts`, `ownerAction.ts`, `alertState.ts`,
  `appointmentView.ts`, `shopConfig.ts`, `types.ts`), `components/`, `scripts/serve.sh`, and their tests.
- `scripts/check-client-imports.cjs`, `scripts/check-deploy-separation.sh`, `db/schema/002_roles.sql` (the read role).
- Ship gate 18 in `docs/ROADMAP.md` (the numbered ship-gate list) and the K-6 record (`docs/MIGRATION-PLAN.md` §3t,
  `docs/PHASE-7-PLAN.md`).

The repository's own claims, with their stated bounds:
- Authentication is Cloudflare Access in front of the dashboard; Access is configured outside this repository, and
  its measured behaviour (a session-less request redirected, a one-email allow policy) is a recorded measurement, not
  code you can read.
- The export routes answer 404 unless `DASHBOARD_EXPORT_ENABLED` is exactly `1`; the flag is a release gate until
  this audit, not a security boundary.
- The store credential is read-only and never reaches a browser bundle (CRT 10, closed; its F4–F13 are recorded open
  items).

Questions: with Access assumed in place, what can a request reach that it should not — unmasked PII, another
customer's data, an unbounded export, a CSV that executes in a spreadsheet, a destructive call without the intended
checks? What does the code itself enforce if Access were bypassed or misconfigured, and is that stated honestly?
Is the export route safe to switch on as written?
<!-- /prompt -->

<!-- prompt:11 -->
Target — Critical-Review Target 11: the D11 owner write path (release a handoff lock from the dashboard through an
n8n webhook), plus a record drift. Risk criteria: irreversible + unauthorized write on shared state.

In scope:
- Owner Actions copy (`n8n/workflow.owner-actions.copy.sanitized.json`): `Receive Owner Action`,
  `Verify Owner Signature`, `Signature Valid?`, `Owner Request Fresh?`, `Validate Owner Action`, `Action Allowed?`,
  `Check Owner Replay`, `Owner Replay?`, `Find Target Conversation`, `Validate Release Target`, `Target Locked?`,
  `Release Handoff Lock`, `Re-read Released Conversation`, `Write Verified?`, `Record Owner Action Processed`, the
  alert and respond nodes.
- `web/dashboard/lib/ownerAction.ts`, `web/dashboard/app/api/release/route.ts`, `tests/run-d11.sh`; the Main copy's
  `Check Handoff Lock` (what the lock protects).
- The drift: `MASTER-BRIEF.md` §9 shows row 11 open, while `docs/ROADMAP.md` records "CP 6d · CRT #11 REMEDIATION
  (Codex, 2026-09-13)" as done.

The repository's own claims, with their stated bounds:
- The path is HMAC-signed with a freshness window, behind Access Service Auth, with an action allow-list, target
  validation, write-then-verify, an owner alert and idempotent replay.
- `run-d11.sh` passed 13/13 on the production paths (A2) — a recorded run, not committed output.

Questions: can anything other than the dashboard's signed request cause a write? Can a valid request write a
conversation it should not (wrong target, unlocked target, a replay, a stale request, a different action)? Can a
write succeed without verification or fail silently? Does `run-d11.sh` test the claims it is said to test? Do the
two records of row 11 reconcile with the current Owner Actions copy — which findings of the 2026-09-13 remediation
still hold on the Postgres copy, and which are open?
<!-- /prompt -->
