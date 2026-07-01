---
description: Read the error WITH Yigitcan, explain the cause, then teach the fix.
---

# /debug

Debugging is teaching — never a silent fix.

1. **Read the error together** — quote the actual message / failed node, don't paraphrase away the detail.
2. **Explain the cause** — what actually happened and why (the mechanism, not just the symptom).
3. **Propose the fix** — the smallest change that addresses the cause, and what it will and won't fix.
4. **Verify** — reproduce, apply, confirm the error is gone and nothing else broke.
5. **Capture** — if it's a recurring class (e.g. timezone, idempotency), note it so it doesn't return.

For n8n: check the error branch first — a failure should already be VISIBLE (see [../rules/n8n-conventions.md](../rules/n8n-conventions.md)).
