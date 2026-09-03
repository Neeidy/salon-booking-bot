#!/usr/bin/env node
/*
 * generate-config-types.cjs — build-time tooling for Phase 6 (contract-integrity rule).
 *
 * WHY: web/site and web/dashboard need TypeScript types for the client config. Hand-writing an
 * interface would create a SECOND TRUTH next to schemas/client.config.schema.json — exactly the
 * hand-mirrored copy .claude/rules/contract-integrity.md forbids: the schema gains a key, the
 * interface does not, and the drift is silent because both still compile. So the types are
 * GENERATED from the committed schema and guarded against drift.
 *
 * This is the same pattern already proven in this repo by compile-intent-validator.cjs
 * (generate from the committed schema + a --check drift guard), applied to a second contract.
 *
 * MODES:
 *   node scripts/generate-config-types.cjs           → (re)write web/shared/src/config/client.config.types.ts
 *   node scripts/generate-config-types.cjs --check   → DRIFT-GUARD: regenerate in memory and compare
 *                                                      against the committed file. Exit 1 on drift.
 *
 * DRIFT-GUARD TRIGGERS — stated honestly: there is NO CI and NO git hook in this repo, so nothing
 * runs this automatically. It fires because:
 *   (a) .claude/agents/security-auditor.md lists it in the pre-push gate the agent runs, and
 *   (b) `npm run check -w @salon/shared` runs it, and
 *   (c) whenever schemas/client.config.schema.json changes — regenerate, commit, re-run --check.
 *
 * RUN IT AFTER `npm ci`, NOT `npm install`: the output is formatted by json-schema-to-typescript's
 * transitive prettier (^3.9.6), so an unpinned install can float that version and report a FAKE drift.
 * scripts/package-lock.json is what pins it.
 */
"use strict";
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SCHEMA_PATH = path.join(ROOT, "schemas", "client.config.schema.json");
const OUT_PATH = path.join(ROOT, "web", "shared", "src", "config", "client.config.types.ts");

const HEADER = [
  "// >>> GENERATED from schemas/client.config.schema.json — DO NOT EDIT BY HAND.",
  "// Regenerate: node scripts/generate-config-types.cjs   ·   Drift-guard: same script with --check",
  "// Hand-editing this file re-creates the second-truth problem the generator exists to remove",
  "// (.claude/rules/contract-integrity.md).",
  "",
].join("\n");

async function generate() {
  // json-schema-to-typescript v16 is ESM-only → dynamic import from this CJS script.
  const { compile } = await import("json-schema-to-typescript");
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
  const body = await compile(schema, "ClientConfig", {
    bannerComment: "",
    additionalProperties: false,
    style: { singleQuote: true },
  });
  return HEADER + body.trimEnd() + "\n";
}

async function main() {
  const fresh = await generate();
  if (process.argv.includes("--check")) {
    if (!fs.existsSync(OUT_PATH)) {
      console.error("CONFIG-TYPES DRIFT: " + path.relative(ROOT, OUT_PATH) + " is missing — run: node scripts/generate-config-types.cjs");
      process.exit(1);
    }
    const committed = fs.readFileSync(OUT_PATH, "utf8");
    if (committed === fresh) {
      console.log("config types OK — committed client.config.types.ts matches a fresh generation from schemas/client.config.schema.json");
      process.exit(0);
    }
    console.error("CONFIG-TYPES DRIFT: the committed types differ from a fresh generation of the schema.");
    console.error("  → regenerate + commit: node scripts/generate-config-types.cjs");
    process.exit(1);
  }
  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, fresh);
  console.log("wrote " + path.relative(ROOT, OUT_PATH));
}

main().catch((e) => { console.error("generate-config-types failed: " + e.message); process.exit(1); });
