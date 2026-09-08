---
description: Strip secrets + PII from an n8n export and produce n8n/workflow.sanitized.json.
---

# /sanitize

Run before committing any n8n work. The ONLY workflow file that may be committed is the sanitized one.

1. Take the raw n8n export (gitignored) as input.
2. Remove/replace **by name** — this list exists because a value that is not named here gets forgotten:
   - all credentials, API keys, tokens, webhook secrets → placeholders.
   - real webhook URLs / tunnel hostnames → generic placeholders.
   - **`googleCalendarId`** (inside `Load Config`'s `jsCode`) → `REPLACE_WITH_CALENDAR_ID@group.calendar.google.com`
   - **Telegram `chatId`** (owner-alert node) → `REPLACE_WITH_OWNER_TELEGRAM_CHAT_ID`
   - **Turnstile `secret`** (`Verify Turnstile` bodyParameters) → `REPLACE_WITH_TURNSTILE_SECRET`
   - Airtable base/table ids → `appXXXXXXXXXXXXXX` / `tblXXXXXXXXXXXXXX`
   - **pinned/test data containing PII** (real phone numbers, names, message text) → fake sample data.

   ⚠ **The dangerous move is REFRESHING a node from live.** Re-syncing `Load Config` (or any node holding one of
   the values above) from the live workflow silently reintroduces the real value — that is exactly how a real
   Google Calendar id reached the committed export on 2026-09-07. After any refresh, re-apply the placeholders
   and re-run the guard.
3. Write the result to `n8n/workflow.sanitized.json`.
4. Re-open it and confirm: no secret patterns, no real PII, no real hostnames.
   `scripts/check-content-parity.py` now FAILS loudly (`SANITISE FAILURE`) when the committed export carries a
   real value for any of the three named literals above. Before 2026-09-07 it could not: the masks were applied
   only when live ≠ committed, so a leaked value made both sides equal and the guard went GREEN at exactly the
   moment it had to shout — the PASS condition contained the leak condition. The assertion is unconditional now,
   and it was proven able to go RED for all three (see ARCH-DEC 2026-09-07). **Hardened twice on 2026-09-08:** it also covers only what it NAMES — a `flow-reviewer` pass planted a real
   Airtable base id, table id and credential id and the guard went GREEN, because it asserted only the three
   literals above while step 2 names five classes. All five are asserted now, each proven able to go RED.
   **And:** the
   assertion used to live inside the live-fetch path, so on a machine without n8n credentials the script exited
   BEFORE checking anything and a commit got no sanitise coverage at all. It now runs first, on the committed file
   alone — no network, no credentials — and was re-proven able to go RED for all three masks with the environment
   stripped. Without credentials it still refuses the PARITY half (exit 2) and says so explicitly.
5. Hand off to the `security-auditor` agent for an independent pass before push.

Fails loud if any secret/PII pattern remains. See [../rules/security-secrets.md](../rules/security-secrets.md).
