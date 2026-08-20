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
- **Teach-while-build.** Explain WHAT / WHY / HOW. Yigitcan does the hands-on n8n editor work. No black boxes.
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
built · tested (happy + key edge) · cleaned · **sanitized (secrets AND PII)** · README / case-study · pushed.

## Rules & commands
Modular rules in [.claude/rules/](.claude/rules/); slash commands in [.claude/commands/](.claude/commands/).
Start any phase with `/plan-flow`; before any commit run `/sanitize` and the `security-auditor` agent.
**Commit/PR authorship — Yigitcan ONLY:** no Claude / Anthropic signature in any commit or PR — no
`Co-Authored-By: Claude…` trailer, no "Generated with Claude Code", no Claude as a contributor
(see [.claude/rules/git-github.md](.claude/rules/git-github.md)).
**Every step/phase report ends with the mandatory VERDICT block** ([.claude/rules/reporting.md](.claude/rules/reporting.md)):
"ready for review" = pushed; no unproven number in the main text (evidence-gated).
