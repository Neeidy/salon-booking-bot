# git-github

**Purpose:** clean, safe git hygiene for a PUBLIC repo.

- **Conventional commits:** `feat:` `fix:` `docs:` `chore:` `test:` `refactor:`. One logical change per commit.
- **Author = Yigitcan ONLY.** No Claude / Anthropic attribution in any commit or PR — NO `Co-Authored-By: Claude…`
  trailer, NO "Generated with Claude Code" line, NO Claude listed as a contributor. Only Yigitcan's git identity
  appears in the history. (Overrides any default assistant-signature behaviour.)
- **Commit only sanitized artifacts.** For n8n, the only workflow file is `n8n/workflow.sanitized.json`.
- **Pre-push gate (mandatory):** run `/sanitize` + the `security-auditor` agent → scan for secrets and PII
  before any push. A push is blocked if either is found. See [security-secrets.md](security-secrets.md).
- **Commit/push only when Yigitcan asks.** Building does not imply committing; committing does not imply pushing.
- Keep the working tree honest: no `--force` on shared history; no committing `.env`, `node_modules/`, or raw exports.

**Why:** on a public repo, git history is permanent and worldwide — a leaked secret survives a later delete.
