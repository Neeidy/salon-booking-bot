# code-style

**Purpose:** keep code (JS/TS in `web/`, n8n Code nodes, JSON schemas) small, clear, and honest.

- Small and clear over clever. A junior should read it once and get it.
- **Validate inputs early, fail loud.** Never swallow an error to "keep going" — surface it (see [handoff.md](handoff.md), error branch).
- Honest names: a function/node named `bookAppointment` books an appointment and nothing else.
- No dead code, no commented-out blocks, no unused nodes on the n8n canvas.
- Comments explain **why**, not what. The what is the code.
- In n8n Code nodes: keep them tiny; prefer a native node when one exists (deterministic-before-AI).

**Why:** this is a resellable template — every client inherits this code unchanged, so clarity compounds.
