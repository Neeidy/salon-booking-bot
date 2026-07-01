# n8n — engine notes

> **Role of this folder:** binds the n8n engine to the repo. The engine runs on the RS; the repo keeps the
> **sanitized** export + screenshots as the source of record.

## Files
- `workflow.sanitized.json` — the ONLY workflow file committed. Produced by `/sanitize` from the raw export.
  **Lands here in Phase 2** (Core bot) — it does not exist yet.
- `screenshots/` — canvas screenshots for the case study (NOT gitignored — portfolio assets).

## Rules that apply
- Raw exports are gitignored (`n8n/*.json` except the sanitized one).
- Every flow follows [../.claude/rules/n8n-conventions.md](../.claude/rules/n8n-conventions.md):
  visible error branch · deterministic-before-AI · idempotency · control-plane lockdown.
- Booking correctness: [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

## Runtime (from MASTER-BRIEF §5)
Develops on the RS n8n editor; runs on the RS behind a Cloudflare tunnel that exposes **only the webhook
endpoints** — the editor/admin UI is never public.

<TODO: after Phase 2, add a one-line description of each major node group here>
