# CLAUDE.md — salon-booking-bot (project operating manual)

> **Role of this file:** the operating manual Claude Code follows in THIS repo.
> Architecture is the current versioned master in [MASTER-BRIEF.md](MASTER-BRIEF.md); decisions & rationale
> evolve in [docs/ARCHITECTURE-DECISIONS.md](docs/ARCHITECTURE-DECISIONS.md); live phase status is in
> [docs/ROADMAP.md](docs/ROADMAP.md).

## What this is
A config-driven, reusable salon **booking + lead-capture chatbot template** (Model 1 = one isolated
deployment per client). Tier **T1**. The engine is **n8n**; the frontend is a single **Next.js app on Vercel**.

## Working language
Talk to and teach **Yigitcan in Turkish**; keep tool/library/file/path names and code in **English**.

## Operating protocol (non-negotiable)
- **Plan-mode gate — per phase.** Before building any phase/CP: present the plan **in chat** in the COMPLETE
  `/plan-flow` format → get Yigitcan's **written "approved"** → only then build. The harness / ExitPlanMode
  returning "approved" is **not** Yigitcan's approval and never substitutes for it. Binding definition +
  the mandatory section list + the violation protocol: [.claude/rules/plan-gate.md](.claude/rules/plan-gate.md).
- **CC BUILDS. YIGITCAN AUDITS AND RULES.** CC builds everything it can reach — the n8n flow (MCP /
  raw-API), the frontends, the guards, the docs. **Yigitcan does not build. He is L5: the auditor and the
  final judge**, and his approval is what starts and ends a phase (ruling 2026-09-13, replacing the earlier
  "does the UI-only actions" split).
  - ⚠ **What still physically requires him is a LIMIT, not a role — and it is named rather than implied,
    because an unnamed exception silently becomes a job.** Measured 2026-09-13: the container's host config lives
    in a root-owned directory and CC has no sudo, so container env / compose changes are his; a Cloudflare or n8n
    **credential that does not yet exist** must be created by its owner; and **CC deliberately does not
    generate or hold a secret's literal value** (`.claude/rules/remote-operator.md` — the value you never
    hold is the value you cannot misplace). Everything outside that list, CC does.
  - The PURPOSE the old wording protected has NOT lapsed: Yigitcan must be able to **explain and sell**
    this system. That is now carried by a **WHAT / WHY / HOW walkthrough at every step**, a current
    [FLOW-DIAGRAM](docs/FLOW-DIAGRAM.md), the per-node build packages under `docs/`, and the Loom on the
    ship gate — never by hand-clicking. No black boxes.
  - **Reviewed at the Phase 7 close.** An exception with no review date becomes permanent by silence — and
    what gets reviewed is whether the walkthrough artefacts are actually carrying the understanding, not
    whether to hand building back. *(Trigger: the CP 6d build package had drifted into "Yigitcan will
    build these", against a rule that had already said otherwise a month earlier. The reason the split
    changed is operator load — multi-round manual editor sessions stopped being sustainable.)*
- **One small verifiable step at a time.** Build a piece → test it → confirm understanding → next. No big jumps.
- **Deterministic before AI.** Menu / price / hours / slot lookups = IF/Switch, not an LLM call. Spend an
  LLM only on genuine free-text intent.

## Defense-in-depth (5 layers)
L1 **Claude Code** (self-check) · L2 **repo agents** (`code-reviewer` · `qa-tester` · `security-auditor` ·
`flow-reviewer`) · L3 **Codex** (audits the Critical-Review Targets — gate before "done") · L4 **Cowork**
(architecture review from git) · L5 **Yigitcan** (final approval).

## Security — repo is PUBLIC (critical)
- Secrets NEVER touch git / screenshots / exports → real values live in **n8n Credentials / Vercel env**;
  the repo holds only `.env.example` (names + fake placeholders).
- **PII** (customer names, phone numbers, message content) is treated like a secret: never committed;
  sanitize before any export.
- n8n: only `workflow.sanitized.json` is ever committed. Failures must be **VISIBLE** (error branch), never silent.

## Definition of Done (per phase)
built · tested (happy + key edge) · cleaned · **sanitized (secrets AND PII)** · README / case-study · pushed ·
**resume-point memory written AND read back** (a phase does not close without it — [.claude/rules/testing.md](.claude/rules/testing.md)).

## Rules & commands
**This repo assumes permission prompts may be OFF for the operator** (set per-machine in gitignored local
settings — deliberately NOT committed: a bypass in the committed settings would apply to every clone of what
is a resellable template). The control that does NOT depend on that setting is
[.claude/rules/irreversible-actions.md](.claude/rules/irreversible-actions.md): before a named list of
irreversible operations, ask in chat **in Turkish, about the EFFECT**, and wait for written approval.
Operational accidents are logged in [docs/OPERATIONAL-INCIDENTS.md](docs/OPERATIONAL-INCIDENTS.md) —
product defects stay in ARCHITECTURE-DECISIONS.

Modular rules in [.claude/rules/](.claude/rules/); slash commands in [.claude/commands/](.claude/commands/).
Start any phase with `/plan-flow`; before any commit run `/sanitize` and the `security-auditor` agent.
**Commit/PR authorship — Yigitcan ONLY:** no Claude / Anthropic signature in any commit or PR — no
`Co-Authored-By: Claude…` trailer, no "Generated with Claude Code", no Claude as a contributor
(see [.claude/rules/git-github.md](.claude/rules/git-github.md)).
**Every step/phase report ends with the mandatory VERDICT block** ([.claude/rules/reporting.md](.claude/rules/reporting.md)):
"ready for review" = pushed; no unproven number in the main text (evidence-gated).
