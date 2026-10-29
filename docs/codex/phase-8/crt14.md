<!-- Codex final message, verbatim. Target CRT #14 · prompt: docs/codex/phase-8/prompt.md, pin 35df5cc · Phase 8 R2: container run (image c72-codex-audit:r2), mount check OK, attempt 2 (attempt 1 stopped at the mount check; Codex never started — containment.md) · 2026-10-28 -->

At `35df5ccf53b8593e239bb9a9b5d26591c049fa2d`, I found **four MEDIUM and two LOW findings**. The existing renderer suite passes all 63 cases; the committed mutant suite kills 17/17 mutants.

Tracked files are unchanged. Reproduction scripts and results are under [.audit-render](/home/auditor/work/.audit-render/probe-results.txt); all secret values used were synthetic.

1. **MEDIUM — A service-catalogue assumption remains outside the slots.**

   [workflow.main.sanitized.json:390](/home/auditor/work/n8n/workflow.main.sanitized.json:390), `Build LLM Request`, includes an example classifying hair coloring as `capture_lead`, with notes saying **“asked about hair coloring (not in services)”**.

   Configure the first service as:

   ```json
   {"id":"hair_coloring","name":"Hair Coloring","durationMin":60,"priceEUR":80}
   ```

   Rendering succeeds. The rendered prompt contains both the newly rendered booking example for `hair_coloring` and the unchanged example asserting that coloring is unavailable. The model therefore receives contradictory instructions about that client’s catalogue.

   **Command:** `python3 .audit-render/probe.py`

   **Observed:** `hair coloring service supported and fixed unavailable example remains: True True`

   This is a catalogue-membership assumption, beyond the accepted English-language bound. It is the same kind of service-specific prompt content that motivated the tenth slot.

2. **MEDIUM — Two config keys read by a workflow are silently discarded.**

   [render-client.py:140](/home/auditor/work/scripts/render-client.py:140) projects only keys present in the committed literal. However, [workflow.main.sanitized.json:2091](/home/auditor/work/n8n/workflow.main.sanitized.json:2091), `Build Cancel-Aborted State`, reads:

   - `messageTemplates.cancelRetry`
   - `messageTemplates.dryRunNoChange`

   Neither is in Main’s literal. Supplying client-specific strings for both still removes them from the rendered config. Executing the rendered node uses its fixed fallback messages instead. Omitting both also succeeds, contradicting [RUNBOOK.md:67](/home/auditor/work/docs/RUNBOOK.md:67)’s claim that a missing key the workflows read is refused.

   **Command:** `python3 .audit-render/probe.py`

   **Observed:** `hasRetry:false`, `hasDry:false`; both replies used fixed fallback text, and the config missing these keys rendered with exit `0`.

3. **MEDIUM — Invoking the script through a symlink bypasses repository containment.**

   [render-client.py:42](/home/auditor/work/scripts/render-client.py:42) derives `ROOT` from `abspath(__file__)`, preserving the script’s symlink location. Both containment checks then trust that incorrect root at [render-client.py:221](/home/auditor/work/scripts/render-client.py:221).

   The probe creates:

   ```text
   .audit-render/alias/scripts/render-client.py → actual scripts/render-client.py
   ```

   It invokes that link with `--exports` pointing to the committed exports and `--out .audit-render/output-via-script-link`. That output is inside the actual repository but outside the incorrectly inferred root.

   **Command:** `python3 .audit-render/probe.py`

   **Observed:** `symlinked script output in repository: 0 True synthetic secret present= True`

   These workflow filenames are not ignored at that location; `git check-ignore .audit-render/output-via-script-link/workflow.main.json` returned `1`. The renderer does not automatically commit anything, but this bypass makes secret-bearing output available to ordinary git staging.

   The reproduction removes the generated workflows afterward. The tests mask this condition by explicitly resetting `mod.ROOT` at [render-client.test.py:91](/home/auditor/work/tests/unit/render-client.test.py:91).

4. **MEDIUM — Numeric overflow bypasses the nonfinite-number refusal.**

   [render-client.py:205](/home/auditor/work/scripts/render-client.py:205) rejects literal `NaN` and `Infinity` tokens through `parse_constant`, but does not check whether parsed numbers are finite. [_scalar at line 167](/home/auditor/work/scripts/render-client.py:167) subsequently serializes the resulting infinity.

   Set:

   ```json
   "llmCostCapUsd": 1e999
   ```

   Python parses this as positive infinity. Rendering succeeds and produces JavaScript containing `llmCostCapUsd: Infinity`, defeating a finite monthly spend ceiling.

   **Command:** `python3 .audit-render/probe.py`

   **Observed:** `1e999: 0 llmCostCapUsd=Infinity, finite=false`

   Literal `NaN`, `Infinity`, and `-Infinity` were refused. The broader recorded claim that nonfinite values are refused—[PHASE-8-PLAN.md:170](/home/auditor/work/docs/PHASE-8-PLAN.md:170)—does not hold for overflow.

5. **LOW — List objects retain fields outside the promised projection.**

   [render-client.py:131](/home/auditor/work/scripts/render-client.py:131) validates a list object by calling `project()`, but discards its result. [Line 153](/home/auditor/work/scripts/render-client.py:153) copies the original list, including unmeasured fields.

   For example, adding:

   ```json
   "extra": {
     "demoAddress": "Musterstrasse 12",
     "secretInput": "SHOULD NOT BE A SLOT"
   }
   ```

   to `services[1]` carries that entire object into Main’s config literal.

   **Command:** `python3 .audit-render/probe.py`

   **Observed:** `unprojected list extras retained: True`

   Required list fields are checked, but lists do not obey the advertised projection onto the committed literal’s own key tree.

6. **LOW — The “never printed” test misses stderr; ownership enforcement also lacks regression coverage.**

   [render-client.test.py:95](/home/auditor/work/tests/unit/render-client.test.py:95) captures only stdout. The assertion at [line 303](/home/auditor/work/tests/unit/render-client.test.py:303) nevertheless claims that secrets are “never printed.”

   I created a temporary mutant that adds:

   ```python
   print(load_secrets(a.secrets), file=sys.stderr)
   ```

   before the successful render log.

   **Command:**

   ```sh
   RENDER_CLIENT="$PWD/.audit-render/mutant-stderr.py" python3 tests/unit/render-client.test.py
   ```

   **Observed:** exit `0`; the “never printed” case remained green, while stderr contained both synthetic secrets. Captured evidence is in [stderr-test.stdout](/home/auditor/work/.audit-render/stderr-test.stdout) and [stderr-test.stderr](/home/auditor/work/.audit-render/stderr-test.stderr).

   A separate mutant removing [render-client.py:241](/home/auditor/work/scripts/render-client.py:241)’s owner check also passed the entire suite:

   ```sh
   RENDER_CLIENT="$PWD/.audit-render/mutant-owner.py" python3 tests/unit/render-client.test.py
   ```

   This is a test-coverage finding; the current owner check itself worked in the targeted probe.

For the remaining requested checks:

- **Independent export search:** I traversed all **2,839 string values** across the five exports, including workflow fields and node parameters, and searched demo-config values, endpoints, identifiers, templates, and config reads. The inventory is [export-inventory.txt](/home/auditor/work/.audit-render/export-inventory.txt). Finding 1 is additional service-specific content outside the named slots. I did not count the recorded comments, unreachable template fallbacks, credential placeholders, EUR/English restrictions, or the explicitly limited leak-scan scope as findings.
- **Ordinary confidentiality controls:** The successful secret-bearing render had a `0700` directory and `0600` files. I found no current ordinary-path stdout/stderr secret disclosure or automatic git operation. Finding 3 bypasses the repository-location protection.
- **Refusals that held:** Missing projected keys, wrong kinds, malformed required list fields, empty templates, empty hour strings, literal nonfinite tokens, changed anchor counts, changed Telegram placeholders, existing output directories, direct repository paths, symlinks into the repository, and `..` paths were rejected.
- **Secret-file checks:** Group/other-readable modes, wrong ownership (tested by substituting the caller UID), leaf symlinks, FIFOs, nonobjects, unknown keys, and invalid/empty values were rejected. A directory fails closed through an uncaught `IsADirectoryError` before the regular-file check. Missing secret keys intentionally leave placeholders, as documented. The mode check enforces no group/other permissions rather than exact equality with `0600`.
- **Filesystem limitation:** A regular secret file with an outside pathname and a hardlink inside the repository is accepted. The probe confirmed this; the check establishes pathname containment, not the absence of other inode aliases. The renderer did not create that inside alias.
- **Unavailable checks:** I did not run live-n8n parity/probe suites or the host-leak guard requiring the unavailable local host file.

Short summary:

- **Q1:** Yes—unrendered catalogue assumptions remain, two read template keys are dropped, and list extras pass through.
- **Q2:** Yes—symlinked script invocation can write secret-bearing workflows into a git-stageable repository location; ordinary output permissions held.
- **Q3:** Yes—the fixed hair-coloring availability example is outside the named slots.
- **Q4:** Most sampled refusals held; missing runtime-read keys and numeric overflow escape rejection, and two additional mutants survived.

**HIGH:** none. **MEDIUM:** catalogue assumption; dropped template keys; repository-output bypass; nonfinite overflow. **LOW:** list projection leakage; stderr/ownership test gaps.