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

**Before every commit:** run `/sanitize` and the `security-auditor` agent (pre-push secret + PII scan).

**Why:** one leaked token or one real customer number in a public repo is a real-world breach, not a demo bug.
