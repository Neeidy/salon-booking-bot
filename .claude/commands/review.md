---
description: Clean pass — names, comments, dead code/nodes, no secrets, no PII.
---

# /review

A quality pass (not a bug hunt — for correctness use the `code-reviewer` agent).

- **Names:** functions and n8n nodes honestly describe what they do (verb + object).
- **Comments/sticky notes:** present where the "why" isn't obvious; none stale.
- **Dead code/nodes:** removed — no commented-out blocks, no orphan nodes on the canvas.
- **Secrets/PII:** none in code, config, exports, or screenshots.
- **Consistency:** matches `.claude/rules/code-style.md` and `n8n-conventions.md`.

Output: a short list of concrete cleanups, then apply them.
