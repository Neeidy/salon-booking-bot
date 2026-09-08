#!/usr/bin/env node
/*
 * compile-intent-validator.cjs — build-time tooling for CP3 3c (contract-integrity rule).
 *
 * WHY: the n8n Code node cannot `require()` (verified: this instance blocks ajv AND crypto).
 * So we compile the COMMITTED schema (schemas/intent.schema.json) to a self-contained
 * ajv-standalone validator (no require, no import) and embed it in the `Validate Intent` node.
 * The validator is GENERATED from the schema — never hand-mirrored — so it cannot drift from it.
 *
 * MODES:
 *   node compile-intent-validator.cjs          → print the full `Validate Intent` node code
 *                                                 (orchestration + generated validator) to stdout.
 *   node compile-intent-validator.cjs --check   → DRIFT-GUARD: recompile from the schema and compare
 *                                                 the generated block against the block committed inside
 *                                                 n8n/workflow.sanitized.json. Exit 1 on drift.
 *
 * DRIFT-GUARD TRIGGERS (not dormant):
 *   (a) CP3 Definition-of-Done gate — must pass before CP3 is called done.
 *   (b) Whenever schemas/intent.schema.json changes — regenerate, re-paste into the node, re-run --check.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const Ajv = require("ajv");
const standaloneCode = require("ajv/dist/standalone").default;

const ROOT = path.resolve(__dirname, "..");
const SCHEMA_PATH = path.join(ROOT, "schemas", "intent.schema.json");
const WORKFLOW_PATH = path.join(ROOT, "n8n", "workflow.sanitized.json");
const NODE_NAME = "Validate Intent";

const BEGIN = "// >>> GENERATED validator — from schemas/intent.schema.json — DO NOT EDIT — regenerate: node scripts/compile-intent-validator.cjs";
const END = "// <<< END GENERATED validator";

// The hand-written orchestration. `run()` is declared first (readable), the generated validator
// sits between the markers, and `return run()` fires last — so the generated `const schema` is
// initialised before validateIntent() is ever called (avoids a const temporal-dead-zone crash).
const ORCHESTRATION = [
  "// Validate Intent — CP3 3c.1 (upgraded from Parse Intent).",
  "// [top] hand-written orchestration  ·  [middle] GENERATED validator  ·  [bottom] return run()",
  "// Regenerate the validator: node scripts/compile-intent-validator.cjs  (never hand-edit the block)",
  "",
  "function run() {",
  "  const ctx = $('Build LLM Request').first().json;   // channel, sender_key, text, state",
  "  const raw = $json;                                  // Anthropic Messages API response",
  "",
  "  const handoff = (reason) => [{ json: {",
  "    channel: ctx.channel, sender_key: ctx.sender_key, text: ctx.text,",
  "    intent: 'handoff', confidence: 0, slots: null,",
  "    valid: false, invalid_reason: reason,",
  "    state: { ...ctx.state, last_intent: 'invalid' }",
  "  } }];",
  "",
  "  // 1) trust gate — structured output is only guaranteed on stop_reason 'end_turn'",
  "  if (!raw || raw.stop_reason !== 'end_turn') return handoff('stop_reason:' + ((raw && raw.stop_reason) || 'missing'));",
  "",
  "  // 2) parse the structured JSON string (defensive — a bad shape must never crash the node)",
  "  let parsed;",
  "  try { parsed = JSON.parse(raw.content[0].text); }",
  "  catch (e) { return handoff('parse_error'); }",
  "  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return handoff('not_object');",
  "",
  "  // 3) normalize enum case — guard EVERY access, tolerate any unexpected shape",
  "  if (typeof parsed.intent === 'string') parsed.intent = parsed.intent.toLowerCase();",
  "  if (parsed.slots && typeof parsed.slots === 'object' && typeof parsed.slots.faqTopic === 'string') {",
  "    parsed.slots.faqTopic = parsed.slots.faqTopic.toLowerCase();",
  "  }",
  "",
  "  // 4) validate against the committed schema (generated validator below)",
  "  let valid = false;",
  "  try { valid = validateIntent(parsed) === true; } catch (e) { valid = false; }",
  "  const reason = valid ? null",
  "    : (validateIntent.errors && validateIntent.errors[0]",
  "        ? 'schema:' + (validateIntent.errors[0].instancePath || '/') + ' ' + validateIntent.errors[0].message",
  "        : 'schema_invalid');",
  "",
  "  return [{ json: {",
  "    channel: ctx.channel, sender_key: ctx.sender_key, text: ctx.text,",
  "    intent: valid ? parsed.intent : (typeof parsed.intent === 'string' ? parsed.intent : null),",
  "    confidence: valid ? parsed.confidence : (typeof parsed.confidence === 'number' ? parsed.confidence : 0),",
  "    slots: valid ? parsed.slots : null,",
  "    valid,",
  "    invalid_reason: reason,",
  "    // TRANSIENT vs LOCKING (2026-09-09f, Codex MED-6). A payload that PARSED but failed the committed schema",
  "    // is an extraction defect on OUR side of the contract, not a customer intent. It used to reach",
  "    // `Invalid or Handoff Gate` and write stage='handoff' — a PERMANENT lock: Codex sent",
  "    // {\"intent\":\"answer_faq\",\"confidence\":0.92,\"slots\":{\"faqTopic\":\"price\"}} (the `dateExpr` key simply",
  "    // absent) and a customer asking a price question was muted for good. That is the same class as the `hi`",
  "    // bug this phase opened with, so it is not being shipped twice. The three failures ABOVE (bad",
  "    // stop_reason, unparseable JSON, non-object) keep the lock: those are not a contract slip, they are the",
  "    // model not answering at all. This flag is what `Extraction Transient?` routes on.",
  "    extraction_transient: !valid,",
  "    state: { ...ctx.state, last_intent: valid ? parsed.intent : 'invalid' }",
  "  } }];",
  "}",
  "",
  "__GENERATED_BLOCK__",
  "",
  "return run();",
  "",
].join("\n");

function generateBlock() {
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
  const ajv = new Ajv({ code: { source: true }, allErrors: true });
  const validate = ajv.compile(schema);
  let code = standaloneCode(ajv, validate);

  const m = code.match(/module\.exports\s*=\s*(\w+)\s*;/);
  if (!m) throw new Error("compile: could not locate the standalone entry export");
  const entry = m[1];

  // strip module wrapper, rename the numbered entry to a stable name for the orchestration
  code = code
    .replace(/^"use strict";/, "")
    .replace(new RegExp("module\\.exports\\s*=\\s*" + entry + "\\s*;", "g"), "")
    .replace(new RegExp("module\\.exports\\.default\\s*=\\s*" + entry + "\\s*;", "g"), "")
    .replace(new RegExp("\\b" + entry + "\\b", "g"), "validateIntent")
    .trim();

  return BEGIN + "\n" + code + "\n" + END;
}

function fullNodeCode() {
  return ORCHESTRATION.replace("__GENERATED_BLOCK__", generateBlock());
}

function extractCommittedBlock() {
  if (!fs.existsSync(WORKFLOW_PATH)) return { status: "no-workflow" };
  const wf = JSON.parse(fs.readFileSync(WORKFLOW_PATH, "utf8"));
  const node = (wf.nodes || []).find((n) => n.name === NODE_NAME);
  if (!node) return { status: "no-node" };
  const js = (node.parameters && node.parameters.jsCode) || "";
  const b = js.indexOf(BEGIN);
  const e = js.indexOf(END);
  if (b === -1 || e === -1) return { status: "no-markers" };
  return { status: "ok", block: js.slice(b, e + END.length).trim() };
}

if (process.argv.includes("--check")) {
  const fresh = generateBlock().trim();
  const committed = extractCommittedBlock();
  if (committed.status === "no-workflow") {
    console.error("DRIFT-CHECK: workflow.sanitized.json not found."); process.exit(1);
  }
  if (committed.status === "no-node") {
    console.log("DRIFT-CHECK: '" + NODE_NAME + "' node not committed yet (pre-3c.1) — nothing to check."); process.exit(0);
  }
  if (committed.status === "no-markers") {
    console.error("DRIFT-CHECK: '" + NODE_NAME + "' node has no GENERATED markers — cannot verify."); process.exit(1);
  }
  if (committed.block === fresh) {
    // WHOLE-NODE check, added 2026-09-09f. Comparing ONLY the generated block left the hand-written
    // orchestration as a SECOND TRUTH: this file's ORCHESTRATION constant and the committed node body could
    // diverge and every guard stayed green. It actually happened in this round — the `extraction_transient`
    // flag was edited into the node and this file still printed the old orchestration, so `--check` said OK
    // while `compile-intent-validator.cjs` (print mode) would have silently reverted the fix on the next
    // regeneration. That is precisely what .claude/rules/contract-integrity.md forbids, so the guard now
    // covers the whole node, not just the part that is easy to compare.
    const wf = JSON.parse(fs.readFileSync(WORKFLOW_PATH, "utf8"));
    const nodeJs = ((wf.nodes || []).find((n) => n.name === NODE_NAME).parameters || {}).jsCode || "";
    if (nodeJs !== fullNodeCode()) {
      console.error("DRIFT-CHECK: MISMATCH — the generated validator is current, but the committed '"
        + NODE_NAME + "' node body differs from a fresh full compile (orchestration drift).");
      console.error("  → reconcile ORCHESTRATION in this file with the node, or regenerate the node from it.");
      process.exit(1);
    }
    console.log("DRIFT-CHECK: OK — committed '" + NODE_NAME + "' node (orchestration + validator) matches a fresh compile of schemas/intent.schema.json."); process.exit(0);
  }
  console.error("DRIFT-CHECK: MISMATCH — the committed validator differs from a fresh compile of the schema.");
  console.error("  → regenerate: node scripts/compile-intent-validator.cjs, re-paste into '" + NODE_NAME + "', re-sanitize.");
  process.exit(1);
}

process.stdout.write(fullNodeCode());
