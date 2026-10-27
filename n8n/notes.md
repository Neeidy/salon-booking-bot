# n8n — engine notes

> **Role of this folder:** binds the n8n engine to the repo. The engine runs on the RS; the repo keeps the
> **sanitized** export + screenshots as the source of record.

## Files
- `workflow.<key>.sanitized.json` — the ONLY workflow files committed, one per production workflow, each produced by
  `/sanitize`: `main` (the bot), `owner-actions` (the owner dashboard's write path), `purge` (the 30-day retention
  job), `reminders` (appointment reminders) and `drill-state` (the read-only drill state endpoint). Since D6c
  (2026-10-27) each one is the export of ONE live workflow, named in `scripts/check-exports-parity.sh` → `WORKFLOWS`
  by its id; `<key>` also names its spec, `db/copies/<key>.json`. The Airtable originals and their exports were
  retired at D6c — they stay in git history only.
- `staged/` — an engine edit PREPARED for the next deploy and its declared delta file, until the deploy promotes it.
- `screenshots/` — canvas screenshots for the case study (NOT gitignored — portfolio assets).

## Rules that apply
- Raw exports are gitignored (`n8n/**/*.json` except `workflow.*.sanitized.json` and the staged files).
- Every flow follows [../.claude/rules/n8n-conventions.md](../.claude/rules/n8n-conventions.md):
  visible error branch · deterministic-before-AI · idempotency · control-plane lockdown.
- Booking correctness: [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

## Runtime (from MASTER-BRIEF §5)
Develops on the RS n8n editor; runs on the RS behind a Cloudflare tunnel that exposes **only the webhook
endpoints** — the editor/admin UI is never public.

<TODO: after Phase 2, add a one-line description of each major node group here>
