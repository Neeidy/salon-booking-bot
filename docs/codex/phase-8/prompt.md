# Phase 8 R2 — Codex audit prompt, CRT #14 "client render isolation"

The exact text the Codex run receives: the block below, with `{PIN}` replaced by the SHA of the commit that added this
file. Nothing else is sent, so the audit can be repeated from this file alone. One target, one run.

**How the run is made (the 7-2 R2 harness, `docs/codex/7-2-r2/containment.md`):** one throwaway container (label
`c72=run`, all capabilities dropped, no new privileges) from the image `c72-codex-audit:r2`, whose dependencies come
from the committed lockfiles (unchanged since that image was built); a read-only single-branch export of the pushed
`main` at the pin, copied inside to a writable working directory; a temporary Codex home holding only a copy of the
CLI's login file; a mount check before Codex starts (a failure stops the round). Codex's own sandbox cannot run inside
a container, so the container is the boundary; these features are off: apps, browser use, computer use, hooks, image
generation, the in-app browser, multi-agent, plugins, remote plugins, plugin sharing, shell snapshot.
`scripts/codex-containment.py` reads the run's logs afterwards, as information.

<!-- prompt -->
You are auditing a public repository: an n8n-based salon booking chatbot (the engine is exported n8n workflow JSON;
the owner dashboard is a Next.js app; the store is Postgres). Your working directory is a writable copy of the
repository at commit {PIN}, with the git history of `main` up to it and the dependencies installed from the committed
lockfiles. You may run the repository's own tests and offline commands there; anything you change in the copy is
discarded and is not a fix.

TARGET — client render isolation. The repository is a template: one isolated deployment per client. The five
committed workflow exports (`n8n/workflow.*.sanitized.json`) are the demo client's workflows, and some per-client
values sit inside their nodes. `scripts/render-client.py` is meant to produce one client's five workflows from that
client's config file and a local secret-input file, so that a new client needs no hand edit of any node. Its plan,
the slots it claims to fill and its stated bounds are in `docs/PHASE-8-PLAN.md`; its tests are
`tests/unit/render-client.test.py` and `tests/unit/render-client-mutants.py`; the demo client's config is
`config/client.config.example.json`, a fictional second client's is `config/client.config.example-b.json`, and the
config schema is `schemas/client.config.schema.json`. The operator procedure is `docs/RUNBOOK.md` §0b.

Answer these four questions, each with evidence (the code or text at {PIN}, or an offline command you ran and what it
showed):
1. Can any value of the demo client reach another client's rendered workflows — through a slot filled incompletely or
   wrongly, a node or field the render does not touch, an input it accepts without checking, or a refusal path that
   leaves demo values behind?
2. Can the render's output or its secret input reach the repository, git, a log, the terminal, or a file readable by
   another user?
3. Does any per-client value sit in the exports OUTSIDE the slot set the plan names? Search the exports yourself; do
   not rely on the plan's list.
4. Do the refusals the script and its docs claim actually hold (a config key the workflows read but the config lacks,
   a value of another kind, list elements, empty strings, NaN, moved anchors, an output path inside the repository or
   reaching it through a link or `..`, the secret file's mode, owner, link, type and keys)? Is there an input that
   should be refused and is not, or a test that would stay green if the property it names were broken?

For each finding give a severity (HIGH / MEDIUM / LOW), the file and line, a concrete failing input or scenario, and
the offline command that shows it. Do not report style or refactors.

Rules for this run:
- Read only files inside this working directory. Do not access any path outside it, environment variables or /proc.
  Use only git history reachable from HEAD: no `--all`, reflog, branch or stash listing.
- No network.
- Write temporary files only under a directory you create inside the working directory or under the system temp
  directory, never into the repository's tracked paths.
- Recorded bounds: an item the repository records as an accepted bound with its reason (`docs/PHASE-8-PLAN.md`, the
  script's and tests' own comments) is not a finding unless its stated bound or scope is wrong; if it is, say so with
  evidence.
- Some suites need what this environment does not have (the live n8n instance, the host-leak guard's local file).
  Say which you could not run.
- End with a short summary: per question, a one-line answer, and the list of findings by severity.
