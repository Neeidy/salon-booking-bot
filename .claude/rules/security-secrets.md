# security-secrets

**Purpose:** the repo is **PUBLIC** — keep every secret AND every piece of customer PII out of git.

**Where secrets live (never in git):**
- Production secrets → **n8n Credentials** and **Vercel env**. The repo holds only `.env.example` (names + fake placeholders).
- Local dev → `.env` (gitignored). Copy from `.env.example`, fill locally, never commit.
- Rotate immediately on any suspected leak.

**PII is treated like a secret (this is a PUBLIC repo):**
- Customer names, phone numbers, and message content are **never committed** — not in exports, not in
  screenshots, not in test fixtures. Use fake/test data only.
- n8n exports: commit **only** `n8n/workflow.sanitized.json` — pinned/test data and credentials stripped
  (see [../commands/sanitize.md](../commands/sanitize.md)).
- Real per-client `config/client.config.json` is gitignored; only `client.config.example.json` (mock) is committed.

**Two identifier classes that look harmless and are NOT (measured, 2026-09-11):**
- **A full widget `sender_key` is a BEARER CREDENTIAL, not PII.** `Find Booking` looks appointments up by
  `sender_key`, and on the widget it derives from the client-supplied `sessionId` — "session-token strength,
  not a verified identity". Anyone holding the full value can POST it as their own `sessionId` and reach that
  conversation's cancel/reschedule. **Never commit a full one.** A prefix is fine: `w-` is a fixed literal in
  `chatClient.ts`, so `widget:w-…` leaks zero entropy.
- **A full `gcal_event_id` is the same secret wearing a different coat.** It is `hex(sender_key|date|time|
  serviceId)` — a **UTF-8 hex encoding, not a hash** — so it reverses to the `sender_key` with one command.
  Treat a full event id exactly like a full `sender_key`. Decoding one INSIDE a report re-exposes it.
- Airtable record ids are redacted to a bare `rec…` (ruling `4a29c2c`): a partial id is unusable without the
  base id and a PAT, so keeping three characters buys the reader nothing and costs pure exposure.

**Before every commit:** run `/sanitize` and the `security-auditor` agent (pre-push secret + PII scan).

**Why:** one leaked token or one real customer number in a public repo is a real-world breach, not a demo bug.
