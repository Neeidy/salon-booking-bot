# Public demo R1 — Codex CRT #15, the raw answer

The run's final message, verbatim (`final.md` of the run's temporary Codex home), from the single run at pin `4210208`
with the prompt `docs/codex/public-demo/prompt.md`. How the run was contained: `containment.md` beside this file. What
was done about each finding: `docs/PUBLIC-DEMO-PLAN.md`, "CRT #15 — the Codex run".

---

I found **two MEDIUM test-coverage findings**, and no confirmed runtime defect in the staged changes under the repository’s documented engine model. **The n8n engine premise remains independently unverified:** this copy contains the workflow exports and model tests, but no n8n engine source or runnable instance.

1. **Spend brake: no demonstrated fail-open input with a usable cap.**

   [`Eval Spend`]( /home/auditor/work/n8n/staged/workflow.main.sanitized.json:3452) requires exactly one input item, no error-output items, and either an empty object or a finite, non-negative numeric cost. It closes on query errors, thrown branch-access errors, multiple items, malformed costs, and spend equal to or above the cap.

   Evidence:
   
   - `node tests/unit/eval-spend-fail-closed.test.cjs` — **9/9 passed**.
   - `python3 tests/unit/eval-spend-mutants.py` — **10/10 mutants killed**.
   - `node .audit/paths.cjs` — confirmed no-row → open with `prev:0`; row `4.500000` → open; cost `10` → closed; query error, throw and multiple items → closed.

   The engine behavior is asserted in [`PUBLIC-DEMO-PLAN.md:209`](/home/auditor/work/docs/PUBLIC-DEMO-PLAN.md:209), including prior live observations on Purge. The unit test **implements that premise**, rather than testing n8n itself: successful reads receive an explicit empty output 1, while thrown errors omit it ([test:51](/home/auditor/work/tests/unit/eval-spend-fail-closed.test.cjs:51)). Consequently, these commands cannot independently establish that the premise is correct for the deployed Postgres node. The plan already records this limitation and requires a scratch measurement before deployment; I have not counted it as a finding.

   The unusable-cap bypass is explicitly accepted at [plan:231](/home/auditor/work/docs/PUBLIC-DEMO-PLAN.md:231).

2. **Legitimate readings and accounting: current code passed; precision regressions escape its test.**

   Under that engine model, an empty first-month reading and ordinary Postgres numeric strings work. The current code preserves the numeric value in `_spend.prev`. My accounting probe produced **4.506** from previous spend **4.5** plus call cost **0.006** (`node .audit/paths.cjs`). The existing concurrent-turn accounting race is explicitly accepted in `Build Spend Record`; I am not reporting it.

   **Finding F1 — MEDIUM: the spend suite misses precision loss that changes admission and accounting.**

   Location: [eval-spend-fail-closed.test.cjs:111](/home/auditor/work/tests/unit/eval-spend-fail-closed.test.cjs:111); missing corresponding mutant in [eval-spend-mutants.py:23](/home/auditor/work/tests/unit/eval-spend-mutants.py:23).

   Concrete mutation:

   ```js
   prev = Math.round(Number(c) * 100) / 100;
   ```

   replacing `prev = Number(c);` leaves **all 9 tests green**. Yet:

   - Legitimate `cost_usd:'9.999999'`, cap `10`, becomes `prev:10` and incorrectly blocks.
   - Legitimate `cost_usd:'4.500001'` becomes `prev:4.5`, losing accumulated spend before `Build Spend Record` adds this call.

   Reproduction: `node .audit/rounding.cjs` — prints the passing suite and both incorrect mutant results. This is a coverage defect; the committed staged implementation preserves these values correctly.

3. **Thirty-day Purge: no demonstrated wrong-age deletion or false-success defect in the current branch.**

   The cutoff uses Luxon calendar-day subtraction and emits UTC ([workflow:279](/home/auditor/work/n8n/staged/workflow.purge.sanitized.json:279)). Candidate selection compares typed timestamps using strict `<` ([workflow:369](/home/auditor/work/n8n/staged/workflow.purge.sanitized.json:369)). The schema defines `created_at` as `timestamptz NOT NULL DEFAULT now()` ([schema:117](/home/auditor/work/db/schema/001_init.sql:117)); the historical blank-age comment therefore does not describe a nullable column in this schema.

   The candidate cap is `min(200, floor(total × 0.20))`, and the branch refuses larger candidate sets ([workflow:385](/home/auditor/work/n8n/staged/workflow.purge.sanitized.json:385)).

   Evidence:

   - `node tests/unit/leads-purge-read-error.test.cjs n8n/staged/workflow.purge.sanitized.json` — **11/11 passed**, including read failures, empty cases and cap boundaries.
   - `node .audit/paths.cjs` — June 15 → May 16 cutoff, with the same UTC instant for the three tested zones.
   - `node .audit/probe.cjs` — an injected delete acknowledgement that removes nothing triggers `leads_purge_arithmetic_mismatch` in the current verifier.

   **Finding F2 — MEDIUM: the Purge suite remains green with deletion verification disabled.**

   Location: [leads-purge-read-error.test.cjs:182](/home/auditor/work/tests/unit/leads-purge-read-error.test.cjs:182), covering [Verify Leads Purge:481](/home/auditor/work/n8n/staged/workflow.purge.sanitized.json:481).

   Concrete scenario: ten leads, one old candidate; deletion acknowledges success without removing it. The required arithmetic is `1 − 1 !== 1`, so verification must alert. Replacing the verifier with `return [];` suppresses that protection, but the existing suite still passes **11/11**. Its fake deletion always removes a found row ([test:54](/home/auditor/work/tests/unit/leads-purge-read-error.test.cjs:54)), and no test requires an arithmetic-mismatch alert.

   Reproduction: `node .audit/probe.cjs` — shows the surviving verifier mutant and the current verifier detecting the injected fault.

4. **The staged differences match the declaration, but green tests do not establish every property.**

   A recursive parsed-JSON comparison found exactly:

   - Main: `Eval Spend.jsCode`, `Build Spend-Meter Alert.jsCode`, and sticky content.
   - Purge: `Load Config (Purge).jsCode`; retention changes **90 → 30**, with formatting/comment removal from rendering.

   Both declared-delta checker commands passed. The spend test also confirmed that the alert’s executable code is unchanged after removing comment lines.

   Additional checks passed: staged sanitization, diff-checker self-tests, privacy facts **9/9**, shape-contract tests **3/3**, and SQL-parameter checks **56 nodes**. F1 and F2 show specific broken properties that the targeted suites nevertheless accept; neither suite is wholly incapable of failing.

I did **not** run live n8n/database suites, deployment rehearsals, or the host-leak guard requiring its local file. I did not run the full `check-all` chain. Probe files are confined to `.audit/`; tracked files were unchanged.

Final summary:

- **Q1:** No demonstrated fail-open input with a usable cap; actual n8n engine behavior remains unverified offline.
- **Q2:** Current legitimate-read and accounting paths passed; precision-loss mutations escape coverage.
- **Q3:** Current cutoff, candidate cap and arithmetic verifier passed the offline probes; disabling verification escapes coverage.
- **Q4:** Staged differences are exactly declared; targeted tests have two demonstrated blind spots.
- **Findings:** HIGH: none confirmed. MEDIUM: **F1 spend precision coverage**, **F2 purge verification coverage**. LOW: none.