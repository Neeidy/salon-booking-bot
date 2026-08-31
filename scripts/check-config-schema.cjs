#!/usr/bin/env node
/**
 * Config ↔ schema contract guard (FIX-2, closes SCREEN-INVENTORY BULGU-3).
 *
 * WHY: `schemas/client.config.schema.json` is the CONTRACT we hand a new client — "fill this in and
 * it runs". That promise is worthless if the config the bot ACTUALLY runs on does not satisfy it.
 * It didn't: the live `Load Config` carried `channels.widget.turnstile` (rejected by the channel
 * definition's `additionalProperties:false`) and `ownerAlert` (undeclared, passing only because the
 * root is open). A schema that rejects production is a schema that is lying.
 *
 * WHAT: ajv-validates BOTH configs against the COMMITTED schema (contract-integrity.md: validate
 * against the committed file, never a hand-written copy):
 *   1. config/client.config.example.json  — the template a client fills in
 *   2. the `const config = {...}` literal inside the `Load Config` node of the committed
 *      sanitized main workflow — what the bot really runs on
 *
 * NOT CHECKED — deliberately: `Load Config (Reminders)` and `Load Config (Purge)` are workflow-local
 * PARTIAL configs (no services/workingHours), not client configs, so the client schema does not apply
 * to them. Their shared keys are covered instead by scripts/check-cancel-validation-parity.py
 * (business.timezone + bot.killSwitch across two, ownerAlert across all three).
 *
 * SCOPE LIMIT (honest): this proves SCHEMA CONFORMANCE, not example↔live KEY PARITY. The live main
 * Load Config legitimately omits reminder-only keys (bot.whatsappSendDisabled, bot.reminderHoursBefore,
 * channels.whatsapp.accountId/reminderTemplate) because those belong to `Load Config (Reminders)`; the
 * schema marks them optional, so this guard passes. "Fill in the config and it runs" is therefore only
 * PARTLY machine-checked — a client config missing an optional-but-needed key would still validate.
 *
 * Close-gate + security-auditor check. Non-zero exit = the config contract drifted.
 */
const fs = require('fs');
const path = require('path');
const Ajv = require('ajv');

const ROOT = path.resolve(__dirname, '..');
const SCHEMA = process.env.CONFIG_SCHEMA || path.join(ROOT, 'schemas/client.config.schema.json');
const EXAMPLE = process.env.CONFIG_EXAMPLE || path.join(ROOT, 'config/client.config.example.json');
const WORKFLOW = process.env.SANITIZED_PATH || path.join(ROOT, 'n8n/workflow.sanitized.json');

function fail(msg) { console.log('CONFIG CONTRACT DRIFT — ' + msg); process.exit(1); }

/** Pull the config literal out of the Load Config node. Pure data — evaluated, never executed. */
function liveConfig(wfPath) {
  const wf = JSON.parse(fs.readFileSync(wfPath, 'utf8'));
  const node = wf.nodes.find(n => n.name === 'Load Config');
  if (!node) fail(`no 'Load Config' node in ${wfPath}`);
  const js = node.parameters.jsCode || '';
  const start = js.indexOf('const config = {');
  const end = js.lastIndexOf('};');
  if (start < 0 || end < 0) fail("could not locate the `const config = {...}` literal in Load Config");
  // The slice is EVALUATED, so it must be the literal and nothing else. Brace-counting is not safe here
  // (messageTemplates contain literal braces: "You're booked: {service}, {date} {time}."), so instead we
  // assert the TAIL — everything after the literal must be just the node's return statement. If someone
  // ever adds real code after the literal, this fails loudly instead of silently executing it.
  const tail = js.slice(end + 2);
  if (!/^\s*return\s*\[\{[\s\S]*\}\];?\s*$/.test(tail)) {
    fail('the Load Config node has code AFTER the config literal — the extractor would execute it. '
       + 'Revisit scripts/check-config-schema.cjs before trusting this run. Tail was: '
       + JSON.stringify(tail.slice(0, 120)));
  }
  try {
    return new Function(js.slice(start, end + 2) + '\nreturn config;')();
  } catch (e) {
    fail('Load Config literal is not evaluable as plain data: ' + e.message);
  }
}

const ajv = new Ajv({ allErrors: true, strict: false });
const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf8'));
const validate = ajv.compile(schema);

const targets = [
  ['config/client.config.example.json (the client template)', JSON.parse(fs.readFileSync(EXAMPLE, 'utf8'))],
  ["Load Config node literal (what the bot actually runs)", liveConfig(WORKFLOW)],
];

let bad = false;
for (const [label, cfg] of targets) {
  if (!validate(cfg)) {
    bad = true;
    console.log(`  ✗ ${label} does NOT satisfy the committed schema:`);
    for (const e of validate.errors) {
      console.log(`      ${e.instancePath || '(root)'} ${e.keyword} ${JSON.stringify(e.params)}`);
    }
  }
}
if (bad) fail('a config the system depends on fails its own committed contract (see above)');

console.log('config contract OK — example + live Load Config both validate against the committed '
  + 'schemas/client.config.schema.json (reminders/purge Load Configs are partial by design and are '
  + 'covered by check-cancel-validation-parity.py instead)');
