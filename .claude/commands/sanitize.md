---
description: Strip secrets + PII from an n8n export and produce n8n/workflow.sanitized.json.
---

# /sanitize

Run before committing any n8n work. The ONLY workflow file that may be committed is the sanitized one.

1. Take the raw n8n export (gitignored) as input.
2. Remove/replace:
   - all credentials, API keys, tokens, webhook secrets → placeholders.
   - real webhook URLs / tunnel hostnames → generic placeholders.
   - **pinned/test data containing PII** (real phone numbers, names, message text) → fake sample data.
3. Write the result to `n8n/workflow.sanitized.json`.
4. Re-open it and confirm: no secret patterns, no real PII, no real hostnames.
5. Hand off to the `security-auditor` agent for an independent pass before push.

Fails loud if any secret/PII pattern remains. See [../rules/security-secrets.md](../rules/security-secrets.md).
