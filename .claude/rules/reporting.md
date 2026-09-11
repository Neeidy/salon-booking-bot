# reporting

**Purpose:** every step/phase output ends with the SAME fixed verdict block — so a reviewer
(Cowork, Codex, Yigitcan) reads status the same way every time, and no unproven number leaks into prose.

**Mandatory template — paste at the END of every step/phase report, verbatim structure:**

```
## VERDICT
STATUS: ✅ done / ⚠ partial / ❌ blocked
COMMIT: <hash> · <file list>
TESTED: <what was tested, how — if nothing, write "not tested">
UNVERIFIED CLAIMS: <every claim whose evidence is NOT committed — Lighthouse scores,
  perf numbers, timings, etc. A number without committed evidence NEVER appears in the main body.>
OPEN ITEMS: <loose ends>
NEXT: <the single next step>
```

## ONE VERDICT per message, and it is the LAST thing in it
**A message contains exactly ONE `## VERDICT` block, and nothing is written below it — not one line.**
If the message covers several sub-units (an audit, then a fix round, then another audit, then a commit),
the single VERDICT at the end covers all of them. Interim summaries are allowed and belong ABOVE it.

**Why:** the block's entire value is that it is SCANNABLE — a reviewer jumps to the bottom and reads
status in a fixed shape without re-deriving it from prose. The moment prose appears underneath, the
reader has to hunt for the block, and a block you have to hunt for is not a fixed shape any more; it is
just another paragraph. Two VERDICTs in one message are worse still: the reader cannot tell which one is
the message's actual status.

Trigger (2026-09-11, Phase 6b): the rule said "every step/phase report ends with the VERDICT block" and
did NOT say "it is the last thing in the message". Rounds grew to cover several sub-units, a VERDICT got
printed at the end of each one, and the narrative continued below them. Nothing in the old wording
forbade it — which is why the wording, not the habit, is what changed here.

**Hard rules:**
- **"ready for review" = pushed.** Never call work "ready / awaiting approval" until it is committed AND
  pushed to its branch — Cowork verifies from git only and cannot see your working tree.
- **No unproven numbers in the main text.** Any metric (Lighthouse, load time, contrast ratio…) whose proof
  is not in the commit goes under UNVERIFIED CLAIMS, never stated as fact in the body.
- **STATUS is honest:** `⚠ partial` if any acceptance item is unmet; `❌ blocked` if it cannot proceed.
  Green means built + tested + pushed, nothing less.
- **COMMIT lists real hashes and files.** If not yet pushed, STATUS cannot be ✅ and COMMIT says "not pushed".

**Why:** this project's credibility is its honesty (see [honesty-demos.md](honesty-demos.md)). A uniform,
evidence-gated verdict is how a reviewer trusts the report without re-deriving it.

## Live-state sync is part of closing a phase (no drift)
When a checkpoint/phase closes, update BOTH live-state surfaces **in the same closing step** as the
commit — never as a later task:
1. **`docs/ROADMAP.md`** — flip the checkbox + record the commit hash (it is the single live phase source).
2. **The resume-point note** (the project's progress memory) — new state + the single next step.

If either surface still describes the *previous* state after the VERDICT block, the phase is **not done**.
A live-state surface that lags the commit is silent drift — the same failure `governance-sync.md` forbids
across surfaces, here across time. (Trigger: memory lagged a full checkpoint behind at CP4, 2026-07-26.)

## A claim ABOUT a guard is written AFTER the mutation test, never beside the code
Do not write the comment, sticky or doc sentence that says what a guard covers at the same moment you
write the guard. Break it first, watch the test go red, and then write only what the test actually showed.

Trigger (2026-09-09, three times in one round, all by the same hand):
- `"Verified by tests/unit/resolve-date.test.cjs, which asserts every DAYS key resolves"` — 8 of 18 keys had
  no case at all. Committed AND deployed.
- `"every month reference here requires a preposition"` — two alternatives in that very regex had none,
  which is why "may 2 of us come friday" fired.
- `"Only markers that can only point FORWARD are kept"` — `from`, `until`, `after`, `starting` are
  direction-blind in English ("I have been coming from june"), so seven ordinary sentences abstained.

Each was written in the same keystroke as the code, each sounded right, and none was ever executed. The
regex was not the defect; the untested justification was. An unproven coverage claim is worse than none —
it is the reason nobody re-checks, and it makes the next reviewer's job start from a false premise.

Practical form: the mutation run comes first and the sentence quotes it. If you cannot point at the mutant
that dies, you do not get to write the claim.

## A STRUCTURAL claim needs evidence too, not just a behavioural one
"Every X goes through Y", "this is the single entry point", "both paths pass through here" — these are
claims about the SHAPE of the system, and they are asserted far more casually than claims about behaviour.
They need the same proof: the grep / the connection dump / the reference list, shown.

Trigger (2026-09-07): the date guard was defended as "one node, and both booking and reschedule pass through
it". `flow-reviewer` then found `Reschedule Lookup` reading `$('Validate Intent')` — UPSTREAM of the guard, so
the whole reschedule branch bypassed it. The behaviour had been drilled; the topology had only been assumed.
The same round produced a second instance: renaming a node was called safe without listing its references.

Practical form: before writing "all/every/only/single" about structure, run the search that would DISPROVE it
and put its output in the report. A structural claim with no shown search is an assumption wearing a fact's
clothes — and it is the more dangerous kind, because a passing drill on one path reads as proof for all of them.

## Evidence before abandoning a planned approach
If the plan specifies an approach (library, node type, API feature) and the build wants to drop it,
the report MUST include the **evidence** that justified dropping it — the command run and its actual
output, not a conclusion. "X doesn't work here" without a shown check is not acceptable: it turns an
untested assumption into a permanent design decision.


## A claim about your OWN CAPABILITY is a claim like any other
"I have no browser", "I can't reach that", "that isn't runnable here" — these are asserted more casually
than any guard comment, because the subject feels like self-knowledge rather than a measurement. It is not.
Run the check, then write the sentence.

Trigger (2026-09-11): the build said it had no browser. A subagent then found chromium under
`~/.cache/ms-playwright` and drove it. Full measurement and the runnable commands live in
[remote-operator.md](remote-operator.md) → "The capability FACT" — not repeated here, because a second copy
always drifts (`governance-sync.md` §1).

This kind is worse than a false guard comment, not better: a wrong guard comment misleads the next reviewer
and is eventually read; a wrong capability claim silently moves work onto Yigitcan's turns, and nobody ever
sees the cost. Practical form: before "I can't", run the one command that would disprove it.
