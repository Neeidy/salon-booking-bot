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

## Evidence before abandoning a planned approach
If the plan specifies an approach (library, node type, API feature) and the build wants to drop it,
the report MUST include the **evidence** that justified dropping it — the command run and its actual
output, not a conclusion. "X doesn't work here" without a shown check is not acceptable: it turns an
untested assumption into a permanent design decision.
