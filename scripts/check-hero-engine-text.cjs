#!/usr/bin/env node
/*
 * Guard: the hero's demo bot lines must stay ENGINE-VERBATIM.
 *
 * WHY: the public marketing page shows the bot talking. Those bubbles are not decoration — a visitor
 * reads them as what the product actually says. Inventing or drifting that copy is a logged defect class
 * in this repo. Two of the four scenarios use strings that live as LITERALS inside n8n Code nodes, so
 * web/site/lib/heroScenarios.ts necessarily holds a DERIVED copy of engine wording
 * (.claude/rules/contract-integrity.md allows a derived copy only with a drift guard — this is it).
 *
 * What this checks, against the COMMITTED sanitized workflow and the committed example config:
 *   1. every engine LITERAL shape the hero reproduces still exists in its named node
 *   2. every messageTemplates key the hero fills still exists in the config
 * Exit 1 = the engine's wording moved and the marketing page is now quoting something the bot no
 * longer says.
 */
"use strict";
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const WF = process.env.SANITIZED_PATH || path.join(ROOT, "n8n/workflow.sanitized.json");
const CFG = process.env.CONFIG_EXAMPLE || path.join(ROOT, "config/client.config.example.json");

// [node name, exact substring that must appear in that node's jsCode, which hero bubble depends on it]
const LITERALS = [
  ["Compute Availability", "— shall I book it? (yes / no)", "W12 booking confirm-ask"],
  ["Build Cancel-Confirm State", 'Reply "yes" to cancel, or anything else to keep it.', "W19 cancel confirm-ask"],
  ["Answer FAQ", "is ${money(one)}.", "W3 single-service price"],
  ["Answer FAQ", "'Opening hours — '", "W5 opening hours"],
  ["Answer FAQ", "' · '", "W5 hours separator"],
  ["Answer FAQ", "'closed'", "W5 closed-day word"],
];
const TEMPLATE_KEYS = [
  ["bookingConfirmed", "W13"], ["cancelDone", "W20"], ["handoff", "W44"], ["handoffLocked", "W47"],
];

const wf = JSON.parse(fs.readFileSync(WF, "utf8"));
const cfg = JSON.parse(fs.readFileSync(CFG, "utf8"));
const nodeCode = (name) => {
  const n = (wf.nodes || []).find((x) => x.name === name);
  return n ? (n.parameters && n.parameters.jsCode) || "" : null;
};

let bad = 0;
for (const [node, needle, why] of LITERALS) {
  const code = nodeCode(node);
  if (code === null) { console.error(`  ✗ node "${node}" not found (${why})`); bad++; continue; }
  if (!code.includes(needle)) { console.error(`  ✗ ${node}: literal moved — ${why}\n      expected to find: ${needle}`); bad++; }
}
for (const [key, w] of TEMPLATE_KEYS) {
  if (!cfg.messageTemplates || typeof cfg.messageTemplates[key] !== "string") {
    console.error(`  ✗ messageTemplates.${key} missing (${w})`); bad++;
  }
}
if (bad) {
  console.error(`HERO TEXT DRIFT: ${bad} engine source(s) no longer match what the public hero quotes.`);
  console.error("  → update web/site/lib/heroScenarios.ts to the engine's new wording (never the reverse).");
  process.exit(1);
}
console.log("hero engine-text OK — all 6 engine literals and 4 messageTemplates keys the hero quotes still exist");
