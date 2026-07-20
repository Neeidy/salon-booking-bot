# Rule: Contract Integrity (single source of truth)

> **Expands:** `CLAUDE.md` — "Operating protocol (non-negotiable)" · the contract this protects:
> `schemas/intent.schema.json`.

## The rule
Any validation of a contract (JSON schema, config shape, enum) MUST run against the **committed
schema file** — never against a hand-written copy of it.
- Preferred: load + validate with **ajv** against the committed schema.
- If the runtime cannot `require` ajv: use an **ajv-standalone compiled validator**, generated FROM
  the committed schema, plus a regeneration script/note in the repo.
- Hand-written ("hand-mirrored") checks are a LAST RESORT, and only with a **drift-guard test**
  committed in the same change.

## Why
Every hand-written copy creates a second truth. Copies drift silently: you fix one, forget the other,
and the system misbehaves with no error at all. A schema validated against itself cannot drift.

## Derived copies
A derived copy is allowed ONLY when an external API forces it (e.g. the LLM structured-output
safe-subset: `minimum`/`maximum` stripped, unions → `anyOf`). It must be derived from the committed
schema, labelled as derived in a comment, and covered by a parity / drift-guard check.
