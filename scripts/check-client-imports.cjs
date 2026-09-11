#!/usr/bin/env node
/**
 * check-client-imports — the BUILD-TIME server/client boundary.
 *
 * WHY THIS EXISTS
 * `@salon/shared/config` reads the filesystem. A `window` tripwire already lives inside it, but that
 * is a RUNTIME guard: a mistaken client import still BUILDS and only explodes in a real visitor's
 * browser. Worse, ESM evaluates an imported module's top-level code BEFORE the importer's body, so a
 * server-only module imported ahead of the tripwire is never protected by it. This script is the
 * build-time half.
 *
 * ⚠ WHAT THIS GATE IS *NOT*, corrected before it was ever committed (security-auditor F1, 2026-09-11).
 * The first draft of this header called that module "the door every secret-adjacent value walks
 * through". That was false when it was written. Config reaches the browser by a SECOND route this
 * gate cannot see: `web/site/app/page.tsx` passes the whole config object as a PROP to a client
 * component, and Next serialises client-component props into the RSC payload — measured in the built
 * `index.html`, which carries `googleCalendarId`, `channels.whatsapp.accountId`, `bot.killSwitch` and
 * `bot.llmCostCapUsd` in plain sight. Harmless TODAY only because the committed config is the
 * `demoMode` mock and every value is a `REPLACE_WITH_…` placeholder — but this is a resold template,
 * and a real client filling that file in would publish their own calendar and channel ids.
 * An import graph shows REACHABILITY, never DATA FLOW. Closing that route is a different control
 * (pass a field list, not the config object) and it is a NAMED open item in docs/ROADMAP.md under
 * CRT #10b, not something this file quietly implies it already did.
 *
 * WHY NOT ESLint (measured 2026-09-11, Phase 6c plan K-3)
 *   - `web/` contains ZERO eslint configs; one rule is not worth a new toolchain.
 *   - `no-restricted-imports` is per-file and does NOT follow the import graph. The hazard named in
 *     docs/ROADMAP.md is precisely the TRANSITIVE one: client -> helper -> banned. A graph walk is
 *     strictly stronger than the lint rule it replaces, not a cheaper substitute for it.
 *
 * WHAT IT DOES
 *   1. Roots  = every file under the scanned apps whose FIRST statement is 'use client'.
 *               (In the App Router that directive marks a boundary: everything reachable from it is
 *               client code, whether or not those files carry the directive themselves.)
 *   2. Walk   = follow every non-erased import / export-from / dynamic-import / require /
 *               `import x = require()` / relative `new URL()` that has a
 *               LITERAL specifier, transitively. Anything it cannot follow — a computed specifier, an
 *               unresolvable relative path, a tsconfig path alias, an unscanned app — FAILS the gate
 *               rather than being skipped, because a silent stop is indistinguishable from a pass.
 *   3. Verdict= a BANNED module reachable from any root is an error, reported WITH THE CHAIN.
 *
 * THREE RULE CLASSES
 *   A. Named modules (BANNED_FILES) — banned by resolved FILE PATH, not by import spelling, so
 *      `@salon/shared/config` and a hand-written `../../shared/src/config/loadConfig.ts` are the
 *      same offence. A specifier-based rule would miss the second.
 *      A SYMLINK and a HARDLINK both defeated this until 2026-09-12: `resolveFileish` follows a link
 *      to prove the target exists but returns the LINK's path, while BANNED_FILES was keyed by the
 *      real one — one file, two strings. Identity is now the canonical path AND `(device, inode)`;
 *      `realpath` alone is NOT enough, because a hardlink has its own genuine path and no link to
 *      resolve. See `fileIds()`. ⚠ *This paragraph described the hole as open for one round after the
 *      code had closed it, and it is the first block a reviewer reads — a security file contradicting
 *      itself is worse than one that says nothing.*
 *      **Still true, and deliberately so:** a genuine COPY of a banned file is NOT caught. That is
 *      content duplication, a different rule from path aliasing, and banning by content would be a
 *      far noisier gate.
 *   B. Any Node builtin reachable from a client root, in EITHER spelling (`node:fs` and plain `fs`;
 *      the first cut tested only the prefix, so the commoner form passed as third-party). Bans the
 *      CLASS, so the next server-only module is caught before anyone adds it to a list.
 *   C. Named third-party specifiers (BANNED_SPECIFIERS) that are server-only by contract and resolve
 *      into node_modules, where neither A nor B can see them — `next/headers`, `server-only`.
 *
 * WHAT THIS GATE DOES NOT SEE, stated rather than left to be inferred:
 *   - The walk STOPS at genuinely third-party packages (a workspace package symlinked into
 *     node_modules IS followed). A banned module reached THROUGH a dependency is invisible; the count
 *     of such specifiers is printed on every run so the boundary is visible, not assumed.
 *   - DATA FLOW, per the F1 note above. Reachability is not the same question.
 *
 *   - A file the PARSER cannot read. It is reported as a blind spot, never skipped.
 *
 * Type-only vs inline-type erasure: see `extractImports` below. Deliberately NOT restated here — a
 * second copy of a rule always drifts (.claude/rules/governance-sync.md §1).
 *
 * FAIL-ABILITY IS PROVEN BY `--selftest`, which `check-all` runs immediately BEFORE the gate — not by
 * the bare invocation below, which runs the gate alone. (The first draft of this line said "on every
 * run", which is false for the very command printed first under USAGE.) It builds synthetic fixtures in
 * a temp directory and asserts the analysis goes RED for every leak shape it claims to cover and GREEN
 * for every legitimate one. The list is not repeated here — run it and read the table, which is printed
 * from the cases that actually executed. (A prose copy of a test list is the second truth this repo
 * keeps finding: the closing line of that very table once said "7" while 8 cases had run.)
 *
 * USAGE
 *   node scripts/check-client-imports.cjs            # gate the repo   (exit 1 on violation)
 *   node scripts/check-client-imports.cjs --selftest # prove it can go red, both directions
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { isBuiltin } = require('node:module');

const REPO = path.resolve(__dirname, '..');

/** Apps whose client boundary is enforced. A missing directory is skipped, not an error — */
/** `web/dashboard` is a .gitkeep today and gains files in CP 6c-1. */
const SCAN_ROOTS = ['web/site', 'web/dashboard', 'web/snippet'];

/**
 * F7 (security-auditor, 2026-09-11): SCAN_ROOTS was a hand-written list, so a NEW app — `web/admin`,
 * say — got silent zero coverage: an explicit 'use client' file importing a banned module exited 0.
 * The vacuity rule could not help, because it only looks at roots that are already on the list. Every
 * directory under `web/` that has its own package.json must therefore be on the list or declared
 * below, with its reason. This is the same doctrine as NO_CLIENT_ROOTS_OK, one level up.
 */
const NOT_AN_APP = {
  'web/shared': 'a library, not an app — it has no client boundary of its own; it is the TARGET of ' +
                'the rules, and it is walked whenever an app imports it',
};

/** Where a `@salon/<name>` specifier resolves from. Read from each package's own `exports` map — */
/** never a hardcoded copy of it (.claude/rules/contract-integrity.md). */
const WORKSPACE_DIRS = ['web/shared', 'web/site', 'web/snippet', 'web/dashboard'];

/**
 * Rule class A. Key = repo-relative path of the module. Value = why it may not reach a browser.
 * ADDING ONE IS A SINGLE LINE — and it must carry its reason, because a ban nobody can justify is a
 * ban the next person deletes.
 */
/**
 * ⚠ ASYMMETRY WITH `EXTRA_CLIENT_ROOTS`, stated because the two rules look alike and are not
 * (code-reviewer #17, 2026-09-12). A declared client ENTRY must exist or the gate fails — a rename
 * must break it, never quietly empty it. A banned FILE is deliberately NOT existence-checked: one of
 * them (`config.generated.json`) is a gitignored build artefact that legitimately does not exist in a
 * fresh clone, and failing on that would make the gate unrunnable exactly where it is needed most.
 * A banned file that disappears costs nothing — nothing can import it — while a client entry that
 * disappears costs the whole subtree's coverage. Opposite policies, opposite failure costs.
 */
const BANNED_FILES = {
  // F6 (security-auditor, 2026-09-11): banning only `loadConfig.ts` banned the DOOR and left the
  // PAYLOAD open. `web/site/lib/config.ts` imports this JSON directly and nine components import
  // that — so adding 'use client' to any one of them would put the whole client config (calendar id,
  // channel account id, kill-switch, cost cap) into the browser bundle with the gate still GREEN.
  // It is data, not code, which is exactly why the walk would not have looked inside it.
  'web/site/config.generated.json':
    'the whole baked client config; it belongs to the SERVER render. The widget gets a deliberately ' +
    'narrowed subset baked into its own bundle (web/snippet/build.mjs), and that narrowing is the ' +
    'control — importing this file from browser code goes around it',
  'web/shared/src/config/loadConfig.ts':
    'reads the filesystem (node:fs) and is the server/build-time config door; a client bundle that ' +
    'reaches it evaluates Node-only code in a visitor browser, ahead of its own window tripwire',
};

/**
 * Files that are BROWSER CODE BY CONSTRUCTION even though they carry no 'use client' directive,
 * because they are not Next files at all.
 *
 * FOUND BY RUNNING THE GATE, not by reading it (2026-09-11): with roots defined as "files whose first
 * statement is 'use client'", `web/snippet` contributed ZERO roots — so the embeddable widget, which
 * is 100% browser code and ships to every client's own website, had NO coverage while the gate
 * printed OK. Silent zero-coverage is the worst state a gate can be in: it is indistinguishable from
 * a pass. Each entry must EXIST, or the gate fails — a rename must break the gate, never quietly
 * empty it.
 */
const EXTRA_CLIENT_ROOTS = {
  'web/snippet/src/index.ts':
    'the embeddable snippet entry (esbuild IIFE, browser-only); it is not a Next file, so no ' +
    "'use client' directive marks it",
};

/**
 * Scan roots allowed to contribute zero client roots, each with the reason. Without this, a directory
 * full of code and no client entry passes VACUOUSLY — the same shape as the snippet gap above.
 * Empty today; an all-server-component app would be added here WITH its reason, never silently.
 */
const NO_CLIENT_ROOTS_OK = {};

/**
 * Rule class C. Bare specifiers that are server-only by contract but resolve to node_modules, so
 * neither the file list nor the builtin check can see them (code-reviewer S2, 2026-09-11).
 */
const BANNED_SPECIFIERS = {
  'next/headers':
    'reads the request cookies/headers on the server; importing it from a client component is a ' +
    'server/client boundary violation that Next only reports at build or request time',
  'server-only':
    'its entire purpose is to throw when it reaches a client bundle; if it is reachable from a ' +
    'client root, something server-only came with it',
};

const CODE_EXT = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']);
const RESOLVE_EXT = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json'];

// ---------------------------------------------------------------------------------------------
// Source scanning
// ---------------------------------------------------------------------------------------------

/**
 * Import extraction — done by the TYPESCRIPT PARSER, not by pattern matching.
 *
 * WHY THIS IS A PARSER AND NOT A LEXER, recorded because the answer cost three audit rounds.
 * The first three versions of this file hand-rolled a scanner: blank the comments and string bodies,
 * then run regexes over what is left. It was reviewed three times and each round found a fresh batch
 * of holes OF THE SAME CLASS — a module specifier blanked along with the string that held it; a
 * `'use client'` directive blanked by the same rule; a regex literal containing a backtick eating the
 * file to EOF; a DIVISION misread as a regex deleting the rest of its line, import included; a
 * default import bound to the name `type` classified as erasure (esbuild emits it); a default binding
 * beside an inline type stopping the walk; a missing semicolon merging two statements so the real
 * import was discarded by the very bound that detected the merge; a BOM costing a module its first
 * import; `import()` inside a template literal invisible; and JSX PROSE naming a module firing the
 * gate on correct code.
 *
 * Every one of those is a LEXING problem, and lexing JS/TS correctly is a solved problem that nobody
 * should re-solve by hand in a governance script. The fix is not a fourth patch — it is deleting the
 * lexer. `ts.createSourceFile()` answers all ten cases with no heuristics at all (measured before the
 * rewrite, 2026-09-12): the JSX prose case simply does not appear in the AST, and a computed
 * specifier arrives DISTINGUISHED rather than missed.
 *
 * WHY typescript 5.9.3 AND NOT THE ONE IN web/ — a declared deviation (governance-sync.md §5).
 * `web/` pins `typescript@7.0.2`, which is the Go port: its npm package is a wrapper (`lib/` holds
 * only `tsc.js`, `getExePath.js`, `version.cjs`), the classic compiler API is absent, and the AST it
 * does expose sits behind an `unstable/` export. A governance gate must not depend on an API its own
 * vendor labels unstable, so `scripts/` pins 5.9.3 — used ONLY as a parser here, never to typecheck
 * anything. Two versions, two jobs, and this comment is why.
 */
const ts = require('typescript');

const SCRIPT_KIND = {
  '.tsx': ts.ScriptKind.TSX, '.ts': ts.ScriptKind.TS,
  '.jsx': ts.ScriptKind.JSX, '.js': ts.ScriptKind.JS,
  '.mjs': ts.ScriptKind.JS, '.cjs': ts.ScriptKind.JS,
};

function parse(rawSrc, fileName) {
  return ts.createSourceFile(
    fileName, rawSrc, ts.ScriptTarget.Latest, true,
    SCRIPT_KIND[path.extname(fileName)] ?? ts.ScriptKind.TSX,
  );
}

/** True when the file's first statement is the 'use client' directive. */
function isClientEntry(rawSrc, fileName = 'f.tsx') {
  const first = parse(rawSrc, fileName).statements[0];
  return !!first && ts.isExpressionStatement(first)
    && ts.isStringLiteral(first.expression) && first.expression.text === 'use client';
}

/**
 * Every module specifier in a file, with how it is imported.
 * kind: 'value' (emitted, followed) | 'type' (erased, ignored) | 'inline-type' (rejected)
 *     | 'nonliteral' (a blind spot: the specifier is computed, or the file does not parse)
 *
 * TYPE-ONLY IMPORTS ARE ERASED — AND THE LINE IS DRAWN DELIBERATELY.
 * `import type X from 's'` / `export type { X } from 's'` emit NOTHING under every compiler setting,
 * so they are neither flagged nor followed. Not a courtesy: the live tree does exactly this today
 * (LiveChatPanel type-imports ClientConfig), so a gate without this rule would fire on correct code.
 * The INLINE form `import { type X } from 's'` is REJECTED instead — its erasure depends on
 * `verbatimModuleSyntax`, a flag in a different file that anyone may flip, and a guard whose
 * correctness depends on an unrelated setting is the second-truth problem again.
 */
function extractImports(rawSrc, fileName = 'f.tsx') {
  const sf = parse(rawSrc, fileName);
  const found = [];
  const lineOf = (n) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;

  // A file the parser cannot read is a blind spot, not a pass.
  // ⚠ `sf.parseDiagnostics` is INTERNAL to TypeScript — it is absent from the public `typescript.d.ts`
  // and is read here because no public API reports parse errors for a single createSourceFile() call.
  // The first cut defaulted it to `[]`, which means a TypeScript upgrade that drops the field would
  // make every unparseable file read as CLEAN — a silent blinding of the check, which is exactly the
  // failure mode this repo forbids. It throws instead: loud, and impossible to miss.
  const diags = sf.parseDiagnostics;
  if (!Array.isArray(diags)) {
    throw new Error(
      'ts.SourceFile.parseDiagnostics is missing. This gate reads that INTERNAL field to detect a file '
      + 'the parser cannot read; without it, an unparseable file would silently look clean. The pinned '
      + `parser is typescript@${ts.version}. Pin it back, or port this check to a public API.`);
  }
  if (diags.length) {
    found.push({ spec: null, kind: 'nonliteral', line: 1,
                 reason: `the file does not parse (${ts.flattenDiagnosticMessageText(diags[0].messageText, ' ')})` });
  }

  const clauseKind = (clause) => {
    if (!clause) return 'value';                       // side-effect import: pure top-level evaluation
    if (clause.isTypeOnly) return 'type';              // erased under every setting
    if (clause.name) return 'value';                   // a default binding is a VALUE, whatever sits beside it
    const nb = clause.namedBindings;
    if (nb && ts.isNamedImports(nb) && nb.elements.length > 0 && nb.elements.every((e) => e.isTypeOnly)) {
      return 'inline-type';
    }
    return 'value';
  };

  const walk = (node) => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteralLike(node.moduleSpecifier)) {
      found.push({ spec: node.moduleSpecifier.text, kind: clauseKind(node.importClause), line: lineOf(node) });
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier
               && ts.isStringLiteralLike(node.moduleSpecifier)) {
      found.push({ spec: node.moduleSpecifier.text, kind: node.isTypeOnly ? 'type' : 'value', line: lineOf(node) });
    } else if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)
               && ts.isStringLiteralLike(node.moduleReference.expression)) {
      found.push({ spec: node.moduleReference.expression.text, kind: 'value', line: lineOf(node) });
    } else if (ts.isCallExpression(node)) {
      const isDynamicImport = node.expression.kind === ts.SyntaxKind.ImportKeyword;
      const isRequire = ts.isIdentifier(node.expression) && node.expression.text === 'require';
      if (isDynamicImport || isRequire) {
        const arg = node.arguments[0];
        if (arg && ts.isStringLiteralLike(arg)) {
          found.push({ spec: arg.text, kind: 'value', line: lineOf(node) });
        } else {
          found.push({ spec: null, kind: 'nonliteral', line: lineOf(node),
                       reason: 'a computed specifier' });
        }
      }
    } else if (ts.isNewExpression(node) && ts.isIdentifier(node.expression)
               && node.expression.text === 'URL') {
      // `new URL('./x', import.meta.url)` is how a bundler is told to pull in a worker or an asset.
      // Only a RELATIVE literal is a module reference; an absolute or schemed URL is a runtime URL.
      const arg = node.arguments?.[0];
      if (arg && ts.isStringLiteralLike(arg) && arg.text.startsWith('.')) {
        found.push({ spec: arg.text, kind: 'value', line: lineOf(node) });
      }
    }
    ts.forEachChild(node, walk);
  };
  walk(sf);
  return found;
}

// ---------------------------------------------------------------------------------------------
// Resolution
// ---------------------------------------------------------------------------------------------

/**
 * Identity of a file, for the banned-module comparison. Two things defeat a plain string compare, and
 * both were MEASURED before this was written (security-auditor BULGU-3, reproduced by hand 2026-09-12:
 * importing `config.generated.json` directly exits 1, importing it through a symlink exits 0 with
 * "OK — no server-only module is reachable"):
 *   - a SYMLINK (file or directory) — `resolveFileish` follows the link to prove the target exists but
 *     returns the LINK's path, while BANNED_FILES is keyed by the real one: one file, two strings;
 *   - a HARDLINK — which `realpath` does NOT resolve, because a hardlink has its own genuine path.
 * So identity is the canonical path AND the (device, inode) pair. A file that cannot be stat'ed (a
 * gitignored artefact missing from a fresh clone) falls back to its resolved path, which is exactly the
 * behaviour the non-symlink case always had.
 *
 * ⚠ HALF OF THIS HAS NO FAIL-PROOF, measured rather than assumed (security-auditor, 2026-09-12):
 * deleting the `realpath` key leaves the suite at 50/50, and so does dropping `dev` from the inode key.
 * They are not redundant — `realpath` carries the case where the file is absent and only a path exists,
 * and `dev` is what stops two files on different mounts sharing an inode NUMBER — but no case currently
 * distinguishes them. Recorded here rather than implied by a green run.
 */
function fileIds(p) {
  const ids = [];
  try { ids.push('path:' + fs.realpathSync(p)); } catch { ids.push('path:' + p); }
  try { const st = fs.statSync(p); ids.push(`ino:${st.dev}:${st.ino}`); } catch { /* absent: path only */ }
  return ids;
}

function tryFile(p) {
  try { return fs.statSync(p).isFile() ? p : null; } catch { return null; }
}

function resolveFileish(base) {
  const direct = tryFile(base);
  if (direct) return direct;
  for (const e of RESOLVE_EXT) {
    const hit = tryFile(base + e);
    if (hit) return hit;
  }
  // TS bundler resolution: './x.js' is written for './x.ts'
  const swapped = base.replace(/\.(js|jsx|mjs|cjs)$/, '');
  if (swapped !== base) {
    for (const e of RESOLVE_EXT) {
      const hit = tryFile(swapped + e);
      if (hit) return hit;
    }
  }
  for (const e of RESOLVE_EXT) {
    const hit = tryFile(path.join(base, 'index' + e));
    if (hit) return hit;
  }
  return null;
}

/** Build `@salon/<pkg>/<subpath>` -> absolute file, from each workspace package's own exports map. */
function buildWorkspaceMap(repoRoot) {
  const map = new Map();
  for (const dir of WORKSPACE_DIRS) {
    const pkgPath = path.join(repoRoot, dir, 'package.json');
    if (!tryFile(pkgPath)) continue;
    let pkg;
    try { pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8')); } catch { continue; }
    if (!pkg.name || !pkg.name.startsWith('@salon/')) continue;
    const exp = pkg.exports;
    if (exp && typeof exp === 'object') {
      for (const [sub, target] of Object.entries(exp)) {
        const file = typeof target === 'string' ? target : target?.default ?? target?.import;
        if (typeof file !== 'string') continue;
        const spec = sub === '.' ? pkg.name : `${pkg.name}/${sub.replace(/^\.\//, '')}`;
        map.set(spec, path.resolve(repoRoot, dir, file));
      }
    }
    map.set(`__dir__:${pkg.name}`, path.resolve(repoRoot, dir));
  }
  return map;
}

/** -> { file } | { external: true } | { unresolved: true } */
function resolveSpec(spec, fromFile, wsMap, repoRoot) {
  // K1 (code-reviewer, 2026-09-11): this used to test `spec.startsWith('node:')`, so the COMMONER
  // bare spelling — `import { readFileSync } from 'fs'` — fell through to `external` and was skipped
  // in silence, while the header claimed the rule "bans the CLASS". isBuiltin() covers both spellings.
  if (isBuiltin(spec)) return { node: spec };
  if (spec.startsWith('.')) {
    const hit = resolveFileish(path.resolve(path.dirname(fromFile), spec));
    return hit ? { file: hit } : { unresolved: true };
  }
  if (spec.startsWith('@salon/')) {
    if (wsMap.has(spec)) return { file: wsMap.get(spec) };
    // A subpath the exports map does not declare cannot be imported at all; surface it rather than
    // silently treating it as third-party.
    const owner = [...wsMap.keys()].find((k) => k.startsWith('__dir__:') && spec.startsWith(k.slice(8) + '/'));
    if (owner) {
      const hit = resolveFileish(path.join(wsMap.get(owner), spec.slice(owner.slice(8).length + 1)));
      return hit ? { file: hit } : { unresolved: true };
    }
    return { unresolved: true };
  }
  // F4 (security-auditor): a bare specifier may be a WORKSPACE package that npm has symlinked into
  // node_modules. Treating it as third-party made it a silent stop. Follow the symlink: if the real
  // path lands back inside the repo (and not inside another node_modules), it is our own code.
  const ws = resolveBareWorkspace(spec, fromFile, repoRoot);
  if (ws && ws.file) return { workspace: true, file: ws.file };
  // #7 (code-reviewer, 2026-09-12): when the package WAS found but its file could not be resolved
  // (a missing exports target, a broken symlink) the first cut fell through to `external` and the
  // chain vanished into the third-party count. That is the same "one unknown, two opposite verdicts"
  // shape F5 had just fixed one layer up. A package that is OURS but unreadable is a blind spot.
  if (ws && ws.found) return { unresolved: true };
  return { external: true };
}

/** Walk up from `fromFile` looking for node_modules/<pkg>; follow it and keep it if it is ours. */
function resolveBareWorkspace(spec, fromFile, repoRoot) {
  const parts = spec.split('/');
  const pkgName = spec.startsWith('@') ? parts.slice(0, 2).join('/') : parts[0];
  const subpath = spec.slice(pkgName.length).replace(/^\//, '');
  let dir = path.dirname(fromFile);
  while (dir.startsWith(repoRoot)) {
    const candidate = path.join(dir, 'node_modules', pkgName);
    if (fs.existsSync(candidate)) {
      let real;
      try { real = fs.realpathSync(candidate); } catch { return null; }
      if (!real.startsWith(repoRoot + path.sep)) return null;         // genuinely third-party
      if (real.split(path.sep).includes('node_modules')) return null; // a real installed dependency
      let pkg;
      try { pkg = JSON.parse(fs.readFileSync(path.join(real, 'package.json'), 'utf8')); } catch { return { found: true }; }
      if (subpath) {
        const t = pkg.exports?.[`./${subpath}`];
        const f = typeof t === 'string' ? t : t?.default ?? t?.import;
        const target = f ? resolveFileish(path.resolve(real, f)) : resolveFileish(path.join(real, subpath));
        return { found: true, file: target };   // null when the exports target does not exist on disk
      }
      const main = (typeof pkg.exports === 'string' ? pkg.exports : pkg.exports?.['.']) ?? pkg.main ?? 'index.js';
      return { found: true, file: resolveFileish(path.resolve(real, typeof main === 'string' ? main : main?.default ?? 'index.js')) };
    }
    const up = path.dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  return null;
}

// ---------------------------------------------------------------------------------------------
// The walk
// ---------------------------------------------------------------------------------------------

function listFiles(dir, acc = []) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return acc; }
  for (const e of entries) {
    if (e.name === 'node_modules' || e.name === '.next' || e.name === 'dist') continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) listFiles(full, acc);
    else if (CODE_EXT.has(path.extname(e.name))) acc.push(full);
  }
  return acc;
}

function rel(p, repoRoot) { return path.relative(repoRoot, p).split(path.sep).join('/'); }

/**
 * @returns {{violations: Array, roots: string[], visited: number, unresolved: Array}}
 */
function analyse(repoRoot, scanRoots, bannedFiles, extraRoots = {}, noClientOk = {}, bannedSpecs = {},
                 notAnApp = NOT_AN_APP) {
  const wsMap = buildWorkspaceMap(repoRoot);
  // Keyed by EVERY identity a banned file has, so any route to it is the same offence.
  const bannedAbs = new Map();
  for (const [r, why] of Object.entries(bannedFiles)) {
    for (const id of fileIds(path.resolve(repoRoot, r))) bannedAbs.set(id, why);
  }
  const bannedHit = (file) => {
    for (const id of fileIds(file)) if (bannedAbs.has(id)) return bannedAbs.get(id);
    return undefined;
  };

  const unreadable = [];         // R1: files that RESOLVED but could not be opened (declared up here
                                 // because the ROOT SCAN below is the first thing that can fill it)

  // F7: every web/* directory carrying its own package.json must be scanned or declared.
  const undeclaredApps = [];
  const webDir = path.join(repoRoot, 'web');
  if (fs.existsSync(webDir)) {
    for (const e of fs.readdirSync(webDir, { withFileTypes: true })) {
      if (!e.isDirectory() || e.name === 'node_modules') continue;
      const relDir = `web/${e.name}`;
      if (!tryFile(path.join(webDir, e.name, 'package.json'))) continue;
      if (scanRoots.includes(relDir) || relDir in notAnApp) continue;
      undeclaredApps.push(relDir);
    }
  }

  const roots = [];
  const perScanRoot = [];
  const missingExtra = [];
  const vacuous = [];

  for (const [r, why] of Object.entries(extraRoots)) {
    const abs = path.resolve(repoRoot, r);
    if (tryFile(abs)) roots.push(abs);
    else missingExtra.push({ file: r, why });
  }

  for (const sr of scanRoots) {
    const dir = path.join(repoRoot, sr);
    const files = listFiles(dir);
    const found = [];
    for (const f of files) {
      let src;
      try { src = fs.readFileSync(f, 'utf8'); }
      catch (e) {
        // R1: silently skipping it means never learning whether it was a client ROOT — i.e. a whole
        // subtree that is simply never scanned, with the gate printing OK.
        unreadable.push({ file: rel(f, repoRoot), why: e.code ?? e.message, as: 'a possible client root' });
        continue;
      }
      if (isClientEntry(src, f)) { roots.push(f); found.push(f); }
    }
    const declared = Object.keys(extraRoots).filter((r) => r.startsWith(sr + '/')).length;
    perScanRoot.push({ scanRoot: sr, codeFiles: files.length, roots: found.length + declared });
    if (files.length > 0 && found.length + declared === 0 && !(sr in noClientOk)) {
      vacuous.push(sr);
    }
  }

  const violations = [];
  const unresolved = [];
  const visited = new Set();
  const externals = new Set();   // S2: counted and PRINTED, never skipped in silence
  const nonliteral = [];         // F8: computed specifiers the walk cannot follow

  for (const root of roots.sort()) {
    // Chain-carrying DFS: the report must show HOW the banned module is reached, or it is unactionable.
    const stack = [[root, [root]]];
    const seenInThisRoot = new Set();
    while (stack.length) {
      const [file, chain] = stack.pop();
      if (seenInThisRoot.has(file)) continue;
      seenInThisRoot.add(file);
      visited.add(file);

      if (!CODE_EXT.has(path.extname(file))) continue;
      let src;
      try { src = fs.readFileSync(file, 'utf8'); }
      catch (e) {
        // R1, and it is the one hole that made this gate say OK over a REAL leak (reproduced with
        // chmod 000 on a mid-chain module, 2026-09-12: readable -> exit 1 with the chain printed,
        // unreadable -> "OK — no server-only module is reachable"). The module RESOLVED, so the edge
        // is real; only the READ failed, and everything behind it went unmeasured. This file's own
        // header promises a blind spot is reported and never skipped — that promise covered
        // "unparseable" and this is "unreadable". `code-style.md`: never swallow an error to keep going.
        unreadable.push({ file: rel(file, repoRoot), why: e.code ?? e.message,
                          as: `reached from ${rel(chain[0], repoRoot)}` });
        continue;
      }

      for (const imp of extractImports(src, file)) {
        if (imp.kind === 'nonliteral') {
          nonliteral.push({ at: `${rel(file, repoRoot)}:${imp.line}`, reason: imp.reason,
                            chain: chain.map((c) => rel(c, repoRoot)) });
          continue;
        }
        if (imp.kind === 'type') continue;                       // erased: not followed, not flagged

        if (imp.spec in bannedSpecs) {
          violations.push({
            rule: 'banned-specifier',
            chain: [...chain.map((c) => rel(c, repoRoot)), imp.spec],
            spec: imp.spec,
            at: `${rel(file, repoRoot)}:${imp.line}`,
            why: bannedSpecs[imp.spec],
          });
          continue;
        }

        const r = resolveSpec(imp.spec, file, wsMap, repoRoot);

        if (r.node) {
          violations.push({
            rule: 'node-builtin',
            chain: chain.map((c) => rel(c, repoRoot)),
            spec: imp.spec,
            at: `${rel(file, repoRoot)}:${imp.line}`,
            why: 'a Node built-in cannot exist in a browser; reaching one from a client component ' +
                 'means server-only code crossed the boundary',
          });
          continue;
        }
        if (r.unresolved) {
          // An import the walk cannot follow is a BLIND SPOT, and a gate with an unannounced blind
          // spot measures less than it claims to.
          unresolved.push({ spec: imp.spec, at: `${rel(file, repoRoot)}:${imp.line}` });
          continue;
        }
        if (r.workspace) {
          // F4: a bare specifier can be a WORKSPACE package (npm symlinks it into node_modules), and
          // calling that "third-party" hid the whole chain behind it. Resolved and walked.
          // ⚠ B3 (security-auditor, 2026-09-12): this branch used to `continue` BEFORE the banned
          // check thirty lines below, so a workspace package whose entry resolves to a banned file was
          // walked straight past — measured exit 0 while the same file by relative path exited 1. The
          // identity map was complete; a branch simply never read it. "Any route is the same offence"
          // is a STRUCTURAL claim, and it was written without running the search that disproves it.
          const wsWhy = bannedHit(r.file);
          if (wsWhy !== undefined) {
            violations.push({
              rule: 'banned-module',
              chain: [...chain, r.file].map((c) => rel(c, repoRoot)),
              spec: imp.spec,
              at: `${rel(file, repoRoot)}:${imp.line}`,
              why: wsWhy,
            });
            continue;
          }
          stack.push([r.file, [...chain, r.file]]);
          continue;
        }
        if (r.external) { externals.add(imp.spec); continue; }

        const bannedWhy = bannedHit(r.file);
        if (imp.kind === 'inline-type' && bannedWhy !== undefined) {
          violations.push({
            rule: 'inline-type',
            chain: [...chain, r.file].map((c) => rel(c, repoRoot)),
            spec: imp.spec,
            at: `${rel(file, repoRoot)}:${imp.line}`,
            why: 'every binding is an INLINE type, whose erasure depends on `verbatimModuleSyntax` ' +
                 '(a flag in another file). Write `import type { ... } from ...`, which is erased ' +
                 'under every setting.',
          });
          continue;
        }
        // F5 (security-auditor, 2026-09-11): an inline-type import of a NON-banned module used to
        // stop the walk here. That was this file arguing both sides of one uncertainty: the import is
        // REJECTED when it points at a banned module precisely because it may survive erasure, and
        // was then assumed fully erased when it pointed anywhere else — so a module reached that way
        // was never traversed. Same unknown, opposite conclusions. It is walked now.

        if (bannedWhy !== undefined) {
          violations.push({
            rule: 'banned-module',
            chain: [...chain, r.file].map((c) => rel(c, repoRoot)),
            spec: imp.spec,
            at: `${rel(file, repoRoot)}:${imp.line}`,
            why: bannedWhy,
          });
          continue;
        }
        stack.push([r.file, [...chain, r.file]]);
      }
    }
  }
  return {
    violations, roots: roots.map((r) => rel(r, repoRoot)), visited: visited.size, unresolved,
    perScanRoot, missingExtra, vacuous, externals: [...externals].sort(), nonliteral,
    undeclaredApps, unreadable,
  };
}

// ---------------------------------------------------------------------------------------------
// Self-test — the gate proves it can go RED before it is allowed to say GREEN
// ---------------------------------------------------------------------------------------------

function selftest() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'client-imports-selftest-'));
  const w = (p, s) => {
    fs.mkdirSync(path.dirname(path.join(tmp, p)), { recursive: true });
    fs.writeFileSync(path.join(tmp, p), s);
  };

  w('web/shared/package.json', JSON.stringify({
    name: '@salon/shared',
    exports: { './config': './src/config/loadConfig.ts', './chat': './src/chat/chatClient.ts' },
  }));
  w('web/shared/src/config/loadConfig.ts', "import { readFileSync } from 'node:fs';\nexport const loadConfig = () => readFileSync;\n");
  w('web/shared/src/chat/chatClient.ts', 'export const sendMessage = () => {};\n');
  w('web/site/package.json', JSON.stringify({ name: '@salon/site' }));

  const BANNED = { 'web/shared/src/config/loadConfig.ts': 'selftest' };
  const SPECS = { 'next/headers': 'selftest', 'server-only': 'selftest' };
  // The fixtures live UNDER web/site, and each case scans one subdirectory of it — so web/site and
  // web/shared are containers here, not apps. Declaring them keeps the F7 rule meaningful instead of
  // firing on every case (which would make it noise rather than a signal).
  const CONTAINERS = { 'web/site': 'selftest container', 'web/shared': 'selftest library',
                       'web/ui': 'selftest workspace library',
                       'web/wspkg': 'selftest workspace library' };
  const run = (dir, extra = {}, noClientOk = {}, extraBanned = {}, notAnApp = CONTAINERS) =>
    analyse(tmp, [dir], { ...BANNED, ...extraBanned }, extra, noClientOk, SPECS, notAnApp);

  const cases = [];
  // RED here must mean exactly what RED means in main(): a violation OR an unresolvable import.
  // The first cut counted only `violations`, so the blind-spot rule had no fail-proof at all and a
  // mis-pathed fixture read as GREEN instead of as the miss it was.
  const check = (name, expectRed, dir, ruleWanted, extra = {}, noClientOk = {}, extraBanned = {},
                 notAnApp) => {
    const res = run(dir, extra, noClientOk, extraBanned, notAnApp);
    const rules = [...new Set(res.violations.map((v) => v.rule))];
    if (res.unresolved.length) rules.push('unresolved');
    if (res.missingExtra.length) rules.push('missing-entry');
    if (res.vacuous.length) rules.push('vacuous');
    if (res.nonliteral.length) rules.push('nonliteral');
    if (res.undeclaredApps.length) rules.push('undeclared-app');
    if (res.unreadable.length) rules.push('unreadable');
    const red = rules.length > 0;
    const ruleOk = !expectRed || !ruleWanted || rules.includes(ruleWanted);
    const pass = red === expectRed && ruleOk;
    cases.push({ name, expect: expectRed ? 'RED' : 'GREEN', got: red ? 'RED' : 'GREEN', pass,
      rules: rules.join(',') || '-' });
    return pass;
  };

  // --- MUST GO RED -----------------------------------------------------------------------------
  w('web/site/a/Direct.tsx', "'use client';\nimport { loadConfig } from '@salon/shared/config';\nexport const X = loadConfig;\n");
  check('L1 direct value import of a banned module', true, 'web/site/a', 'banned-module');

  w('web/site/b/Leaf.tsx', "'use client';\nimport { h } from './helper';\nexport const Y = h;\n");
  w('web/site/b/helper.ts', "import { loadConfig } from '@salon/shared/config';\nexport const h = loadConfig;\n");
  check('L3 TRANSITIVE: client -> helper -> banned', true, 'web/site/b', 'banned-module');

  w('web/site/c/Side.tsx', "'use client';\nimport '@salon/shared/config';\nexport const Z = 1;\n");
  check('L5 side-effect import (no binding, pure top-level eval)', true, 'web/site/c', 'banned-module');

  w('web/site/d/Inline.tsx', "'use client';\nimport { type Cfg } from '@salon/shared/config';\nexport const D: Cfg = 1;\n");
  check('L6 inline-type import (erasure depends on a flag elsewhere)', true, 'web/site/d', 'inline-type');

  w('web/site/e/Node.tsx', "'use client';\nimport { readFileSync } from 'node:fs';\nexport const E = readFileSync;\n");
  check('L7 node: builtin reachable from a client root', true, 'web/site/e', 'node-builtin');

  w('web/site/f/Dyn.tsx', "'use client';\nexport const F = () => import('@salon/shared/config');\n");
  check('L8 dynamic import() of a banned module', true, 'web/site/f', 'banned-module');

  w('web/site/g/Rel.tsx', "'use client';\nimport { loadConfig } from '../../shared/src/config/loadConfig.ts';\nexport const G = loadConfig;\n");
  check('L9 banned reached by RELATIVE path, not by package specifier', true, 'web/site/g', 'banned-module');

  // --- MUST STAY GREEN -------------------------------------------------------------------------
  w('web/site/h/Chat.tsx', "'use client';\nimport { sendMessage } from '@salon/shared/chat';\nexport const H = sendMessage;\n");
  check('L2 ./chat is browser-safe BY DESIGN — must NOT fire', false, 'web/site/h');

  w('web/site/i/Typed.tsx', "'use client';\nimport type { Cfg } from '@salon/shared/config';\nexport const I = (c: Cfg) => c;\n");
  check('L4 `import type` of a banned module is erased — must NOT fire', false, 'web/site/i');

  w('web/site/j/Comment.tsx', "'use client';\n/* see import { loadConfig } from '@salon/shared/config'; for why */\n// import '@salon/shared/config';\nexport const J = 1;\n");
  check('L10 banned specifier that exists only in a COMMENT — must NOT fire', false, 'web/site/j');

  w('web/site/k/Server.tsx', "import { loadConfig } from '@salon/shared/config';\nexport const K = loadConfig();\n");
  // The exemption is not a workaround: this fixture is an all-server app, which is exactly the case
  // NO_CLIENT_ROOTS_OK exists to make someone declare out loud instead of passing by accident.
  check('L11 SERVER component importing config is correct — must NOT fire', false, 'web/site/k',
    null, {}, { 'web/site/k': 'selftest: all-server fixture' });

  // The blind-spot rule needs its own fail-proof, or it is a rule nothing ever exercised. It also
  // guards the selftest against itself: L9 first passed as GREEN only because its fixture path was
  // one level off, i.e. the walk silently stopped instead of reaching the banned module.
  w('web/site/l/Blind.tsx', "'use client';\nimport { x } from './nowhere-at-all';\nexport const L = x;\n");
  check('L12 relative import the walk CANNOT follow is a blind spot', true, 'web/site/l', 'unresolved');

  // --- Every case below exists because code-reviewer proved the gate GREEN on a real leak, or
  // --- proved a rule had no fail-proof at all (mutation M15). None of them was imagined.
  w('web/site/n/Bare.tsx', "'use client';\nimport { readFileSync } from 'fs';\nexport const N = readFileSync;\n");
  check('K1 BARE builtin ("fs", not "node:fs") — was classified external and skipped',
    true, 'web/site/n', 'node-builtin');

  w('web/site/o/Req.tsx', "'use client';\nconst { loadConfig } = require('@salon/shared/config');\nexport const O = loadConfig;\n");
  check('S1 require() of a banned module — this rule had NO fail-proof (mutant M15 survived)',
    true, 'web/site/o', 'banned-module');

  // #9 (code-reviewer, 2026-09-12): the first version of this case pointed at an intermediate module,
  // so F5 (walk inline-type) made it RED and it stayed RED with the K2 fix fully reverted — it did not
  // discriminate. Bound straight to the banned module, the RULE is what decides: with the fix it is a
  // banned-module violation; without it, the gate calls it 'inline-type' and says "every binding is an
  // INLINE type", which is false — there is a default VALUE binding right there.
  w('web/site/p/Mixed.tsx', "'use client';\nimport cfg, { type Cfg } from '@salon/shared/config';\nexport const P: Cfg = cfg;\n");
  check('K2 default binding BESIDE an inline type is a VALUE import, not erasure',
    true, 'web/site/p', 'banned-module');

  w('web/site/q/TypeName.tsx', "'use client';\nimport type from '@salon/shared/config';\nexport const Q = type;\n");
  check('K3 default import BOUND TO THE NAME `type` — esbuild emits it, gate called it erased',
    true, 'web/site/q', 'banned-module');

  w('web/site/r/NoSemi.tsx', "'use client'\nexport type Foo = string\nimport { loadConfig } from '@salon/shared/config'\nexport const R = loadConfig\n");
  check('K4 no semicolons: two statements merged into one match and both vanished',
    true, 'web/site/r', 'banned-module');

  w('web/site/s/Rx.tsx', "'use client';\nconst tick = /`/;\nimport { loadConfig } from '@salon/shared/config';\nexport const S = [tick, loadConfig];\n");
  check('K5 a regex literal containing a BACKTICK blanked the rest of the file',
    true, 'web/site/s', 'banned-module');

  w('web/site/t/Hdr.tsx', "'use client';\nimport { cookies } from 'next/headers';\nexport const T = cookies;\n");
  check('S2 server-only third-party specifier (resolves to node_modules, invisible to the walk)',
    true, 'web/site/t', 'banned-specifier');

  // --- and the false-alarm direction, which is how a gate gets switched off -------------------
  w('web/site/u/Jsx.tsx', "'use client';\nexport const U = () => <p>To import from '@salon/shared/config' read the docs</p>;\n");
  check('K6 JSX PROSE naming a banned module — must NOT fire', false, 'web/site/u');

  w('web/site/v/Multi.tsx', "'use client';\nimport {\n  sendMessage,\n  getSessionId,\n} from '@salon/shared/chat';\nexport const V = [sendMessage, getSessionId];\n");
  check('multi-line import of an allowed module — must NOT fire', false, 'web/site/v');

  w('web/site/w/Div.tsx', "'use client';\nimport { sendMessage } from '@salon/shared/chat';\nexport const W = (a, b) => a / b / 2;\n");
  check('division operators are not regex literals — must NOT fire', false, 'web/site/w');

  // --- the four import forms the header advertises that had NO fail-proof (code-reviewer R3/R4/R5,
  // --- 2026-09-12): each behaved correctly and each survived a mutant that deleted its branch.
  w('web/site/ef/Re.tsx', "'use client';\nexport { loadConfig } from '@salon/shared/config';\n");
  check('R3 `export { x } from` a banned module', true, 'web/site/ef', 'banned-module');

  w('web/site/ef2/Star.tsx', "'use client';\nexport * from '@salon/shared/config';\n");
  check('R3b `export * from` a banned module', true, 'web/site/ef2', 'banned-module');

  w('web/site/ieq/Eq.tsx', "'use client';\nimport cfg = require('@salon/shared/config');\nexport const E = cfg;\n");
  check('R4 `import x = require()` (TS export-assignment form)', true, 'web/site/ieq', 'banned-module');

  w('web/site/wk/leak.ts', "import { loadConfig } from '@salon/shared/config';\nexport const l = loadConfig;\n");
  w('web/site/wk/Wk.tsx', "'use client';\nexport const W2 = () => new Worker(new URL('./leak.ts', import.meta.url));\n");
  check('R5 `new Worker(new URL(...))` — a bundler DOES pull that module in',
    true, 'web/site/wk', 'banned-module');

  // B3: a WORKSPACE package whose entry resolves to a banned file. The workspace branch used to walk
  // on without ever asking whether the target was banned — measured exit 0 (security-auditor).
  fs.mkdirSync(path.join(tmp, 'web/wspkg'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'web/wspkg/package.json'),
    JSON.stringify({ name: 'cfg-kit', main: './entry.json' }));
  fs.writeFileSync(path.join(tmp, 'web/wspkg/entry.json'), '{"a":1}');
  fs.mkdirSync(path.join(tmp, 'web/node_modules'), { recursive: true });
  fs.symlinkSync(path.join(tmp, 'web/wspkg'), path.join(tmp, 'web/node_modules/cfg-kit'), 'dir');
  w('web/site/ws3/Use3.tsx', "'use client';\nimport cfg from 'cfg-kit';\nexport const B3 = cfg;\n");
  check('B3 a WORKSPACE package whose entry IS the banned file', true, 'web/site/ws3', 'banned-module',
    {}, {}, { 'web/wspkg/entry.json': 'selftest payload' });

  // BULGU-3: a banned file reached through a SYMLINK or a HARDLINK. Reproduced by hand on the real
  // tree first — the same file imported directly exited 1, imported through a symlink exited 0 saying
  // "no server-only module is reachable" — which falsified this file's own central sentence about
  // banning by resolved path. Identity is now the canonical path AND (device, inode).
  w('web/site/sym/Comp.tsx', "'use client';\nimport cfg from './link.json';\nexport const S3 = cfg;\n");
  fs.writeFileSync(path.join(tmp, 'web/site/payload.json'), '{"a":1}');
  fs.symlinkSync(path.join(tmp, 'web/site/payload.json'), path.join(tmp, 'web/site/sym/link.json'));
  check('BULGU-3 a banned file reached through a SYMLINK', true, 'web/site/sym', 'banned-module',
    {}, {}, { 'web/site/payload.json': 'selftest payload' });

  w('web/site/hard/Comp.tsx', "'use client';\nimport cfg from './hard.json';\nexport const S4 = cfg;\n");
  try { fs.linkSync(path.join(tmp, 'web/site/payload.json'), path.join(tmp, 'web/site/hard/hard.json')); }
  catch { fs.writeFileSync(path.join(tmp, 'web/site/hard/hard.json'), '{"a":1}'); }
  check('BULGU-3b ...and through a HARDLINK, which realpath does NOT resolve',
    true, 'web/site/hard', 'banned-module', {}, {}, { 'web/site/payload.json': 'selftest payload' });

  // The GREEN side: a genuine COPY is a different file and must NOT fire. Without this the fix could
  // be "ban anything with the same content", which is a different and much noisier rule.
  w('web/site/copy/Comp.tsx', "'use client';\nimport cfg from './copy.json';\nexport const S5 = cfg;\n");
  fs.writeFileSync(path.join(tmp, 'web/site/copy/copy.json'), '{"a":1}');
  check('BULGU-3c a genuine COPY is a different file — must NOT fire', false, 'web/site/copy',
    null, {}, {}, { 'web/site/payload.json': 'selftest payload' });

  // R1: the one hole that made this gate print OK over a real leak. Reproduced on the real tree with
  // chmod 000 before it was fixed; pinned here so it cannot come back.
  //
  // ⚠ The unreadable module deliberately sits OUTSIDE the scanned directory. The first version of this
  // fixture put it inside, where the ROOT SCAN also opens every file — so the case went RED through the
  // root-scan guard and survived a mutant that disabled the WALK guard entirely (44/44). It was proving
  // the wrong half. Caught by this file's own mutation run, which is what that run is for.
  w('web/site/r1lib/mid.ts', "import { loadConfig } from '@salon/shared/config';\nexport const m = loadConfig;\n");
  w('web/site/r1/Comp.tsx', "'use client';\nimport { m } from '../r1lib/mid';\nexport const R1 = m;\n");
  fs.chmodSync(path.join(tmp, 'web/site/r1lib/mid.ts'), 0o000);
  check('R1 WALK half: an unreadable MID-CHAIN module must not drop its subtree in silence',
    true, 'web/site/r1', 'unreadable');
  fs.chmodSync(path.join(tmp, 'web/site/r1lib/mid.ts'), 0o644);
  check('R1b ...and the same chain, readable, is the leak it was hiding',
    true, 'web/site/r1', 'banned-module');

  // The other half: a file inside a scanned app that cannot be opened might BE a client root, and the
  // walk never reaches it to find out. A second client root keeps the vacuity rule out of the way.
  w('web/site/r1root/Ok.tsx', "'use client';\nimport { sendMessage } from '@salon/shared/chat';\nexport const O = sendMessage;\n");
  w('web/site/r1root/mystery.tsx', "'use client';\nexport const M = 1;\n");
  fs.chmodSync(path.join(tmp, 'web/site/r1root/mystery.tsx'), 0o000);
  check('R1c ROOT-SCAN half: an unopenable file might be a client root nobody scans',
    true, 'web/site/r1root', 'unreadable');
  fs.chmodSync(path.join(tmp, 'web/site/r1root/mystery.tsx'), 0o644);
  check('R1d ...and readable, that same app is clean', false, 'web/site/r1root');

  // The `export … from` type distinction had no GREEN side, so a mutant that ignored isTypeOnly lived.
  w('web/site/eft/Ty.tsx', "'use client';\nexport type { ClientConfig } from '@salon/shared/config';\n");
  check('R3c `export TYPE { x } from` a banned module is erased — must NOT fire', false, 'web/site/eft');

  // --- the re-review's findings, each turned into the case it was missing -----------------------
  w('web/site/k4/NoSemiKw.tsx', "'use client'\nexport type { Foo }\nimport { loadConfig } from '@salon/shared/config'\nexport const K4b = loadConfig\n");
  check('#1/#10 merged statement WITHOUT `=` (a lexer-era hole; kept as an anti-revert sentinel)',
    true, 'web/site/k4', 'banned-module');

  w('web/site/bom/helper.ts', "\uFEFFimport { loadConfig } from '@salon/shared/config';\nexport const h = loadConfig;\n");
  w('web/site/bom/Comp.tsx', "'use client';\nimport { h } from './helper';\nexport const B = h;\n");
  check('#2 a BOM-prefixed module lost its FIRST import', true, 'web/site/bom', 'banned-module');

  w('web/site/rx2/Div2.tsx', "'use client';\nlet c = 1, t = 2;\nconst r = c++ / t; import { loadConfig } from '@salon/shared/config';\nexport const R2 = [r, loadConfig];\n");
  check('#4 a DIVISION misread as a regex must not delete the rest of the line',
    true, 'web/site/rx2', 'banned-module');

  w('web/site/tpl/Un.tsx', "'use client';\nimport { sendMessage } from '@salon/shared/chat';\nexport const T1 = `never closed\nexport const T2 = sendMessage;\n");
  check('#3 an UNTERMINATED template literal (lexer blanked to EOF; parser reports it unparseable)',
    true, 'web/site/tpl', 'nonliteral');

  w('web/site/tpl2/In.tsx', "'use client';\nexport const A2 = async () => `${(await import('@salon/shared/config')).loadConfig}`;\n");
  // Under the hand-rolled lexer this was invisible, and the best that could be done was to ANNOUNCE it
  // as a blind spot. The parser resolves it properly, so the expected rule tightened from 'nonliteral'
  // to 'banned-module' — a found import beats an announced hole. Recorded rather than quietly edited:
  // this is the one case out of 38 whose expectation the rewrite changed, and it changed for the better.
  check('#5 import() inside a template literal is RESOLVED, not merely announced',
    true, 'web/site/tpl2', 'banned-module');

  // F4 had NO case at all: `resolveBareWorkspace` was 28 unexercised lines (code-reviewer #8).
  fs.mkdirSync(path.join(tmp, 'web/ui/src'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'web/ui/package.json'),
    JSON.stringify({ name: 'ui-kit', exports: { './x': './src/x.ts' } }));
  w('web/ui/src/x.ts', "import { loadConfig } from '@salon/shared/config';\nexport const x = loadConfig;\n");
  fs.mkdirSync(path.join(tmp, 'web/node_modules'), { recursive: true });
  try { fs.symlinkSync(path.join(tmp, 'web/ui'), path.join(tmp, 'web/node_modules/ui-kit'), 'dir'); } catch {}
  w('web/site/ws/Use.tsx', "'use client';\nimport { x } from 'ui-kit/x';\nexport const WS = x;\n");
  check('F4 a WORKSPACE package reached by a BARE specifier (symlinked into node_modules)',
    true, 'web/site/ws', 'banned-module');

  // #7: the package is ours and WAS found, but its file cannot be resolved -> blind spot, not "third-party".
  fs.writeFileSync(path.join(tmp, 'web/ui/package.json'),
    JSON.stringify({ name: 'ui-kit', exports: { './gone': './src/does-not-exist.ts' } }));
  w('web/site/ws2/Use2.tsx', "'use client';\nimport { y } from 'ui-kit/gone';\nexport const WS2 = y;\n");
  check('#7 a workspace package found but UNRESOLVABLE is a blind spot, not third-party',
    true, 'web/site/ws2', 'unresolved');

  // --- security-auditor's bypasses P3/P5/P6/P7/P9/P11, each turned into a case that must go RED ---
  w('web/site/x/Payload.tsx', "'use client';\nimport cfg from '../../site-config.generated.json';\nexport const X = cfg;\n");
  w('web/site-config.generated.json', '{"business":{"name":"x"}}');
  check('F6 the PAYLOAD (config JSON) imported directly, bypassing the banned door',
    true, 'web/site/x', 'banned-module', {}, {},
    { 'web/site-config.generated.json': 'selftest payload' });

  w('web/site/y/Dyn.tsx', "'use client';\nconst which = 'x';\nexport const Y = () => import(which);\n");
  check('F8 dynamic import with a COMPUTED specifier is an unfollowable blind spot',
    true, 'web/site/y', 'nonliteral');

  w('web/site/z/mid.ts', "import { loadConfig } from '@salon/shared/config';\nexport type A = number;\nexport const m = loadConfig;\n");
  w('web/site/z/Walk.tsx', "'use client';\nimport { type A } from './mid';\nexport const Z: A = 1;\n");
  check('F5 inline-type to a NON-banned module must still be WALKED, not assumed erased',
    true, 'web/site/z', 'banned-module');


  // --- The two coverage rules. Both exist because the gate was MEASURED covering nothing, not
  // --- because they were imagined: web/snippet contributed zero roots while the gate printed OK.
  w('web/site/m/plain.ts', "import { loadConfig } from '@salon/shared/config';\nexport const M = loadConfig;\n");
  check('L13 app with code but NO client root = vacuous coverage', true, 'web/site/m', 'vacuous');

  check('L14 ...unless it is declared browser-by-construction, and then it is WALKED',
    true, 'web/site/m', 'banned-module', { 'web/site/m/plain.ts': 'selftest entry' });

  check('L15 ...or explicitly exempted with a reason', false, 'web/site/m', null, {},
    { 'web/site/m': 'selftest: all-server app' });

  check('L16 a declared entry that does NOT exist must break the gate, not empty it',
    true, 'web/site/h', 'missing-entry', { 'web/site/h/renamed-away.tsx': 'selftest' });

  // LAST, because creating a new app changes what every other case would see. Order is part of the
  // fixture here, so it is stated rather than left as an accident someone later "tidies up".
  fs.mkdirSync(path.join(tmp, 'web/admin'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'web/admin/package.json'), JSON.stringify({ name: '@salon/admin' }));
  w('web/admin/Leak.tsx', "'use client';\nimport { loadConfig } from '@salon/shared/config';\nexport const A = loadConfig;\n");
  check('F7 a NEW web/* app that nobody added to the scan list', true, 'web/site/h', 'undeclared-app');

  check('F7b ...and GREEN once that app is declared with a reason', false, 'web/site/h', null, {}, {},
    {}, { ...CONTAINERS, 'web/admin': 'selftest: declared' });

  fs.rmSync(tmp, { recursive: true, force: true });

  const width = Math.max(...cases.map((c) => c.name.length));
  console.log('SELFTEST — fail-ability of this gate, proven both directions\n');
  for (const c of cases) {
    console.log(`  ${c.pass ? 'ok  ' : 'FAIL'} ${c.name.padEnd(width)}  expect ${c.expect.padEnd(5)} got ${c.got.padEnd(5)} [${c.rules}]`);
  }
  // ⚠ WHAT THIS TABLE DOES NOT COVER, measured rather than implied: every case calls `analyse()` and
  // reads the lists it returns, so it proves the ANALYSIS and not the REPORTING. A mutant that disables
  // main()'s `if (unreadable.length)` block leaves this table fully green (verified 2026-09-12). The
  // exit-1 paths are covered by real-tree drills instead — which is a weaker place for them to live, and
  // saying so is cheaper than discovering it.
  console.log('\n  scope: these cases exercise analyse(); main()\'s reporting/exit paths are covered by');
  console.log('         real-tree drills, not by this table.');
  const failed = cases.filter((c) => !c.pass);
  console.log(`\n  ${cases.length - failed.length}/${cases.length} selftest cases passed`);
  if (failed.length) {
    console.error('\nFAIL: the gate does not behave as documented — it cannot be trusted to gate anything.');
    process.exit(1);
  }
  // DERIVED, never typed by hand: this sentence was written as "7 ... 4" while 8 and 4 had run, in
  // the very file whose subject is that a claim must equal its measurement.
  // S3 (code-reviewer): the NUMBER was derived but the NOUN was hand-typed and wrong — three of the
  // RED cases are coverage failures (blind spot, vacuous coverage, missing declared entry), not leak
  // shapes. Both halves are derived now.
  // #11 (code-reviewer, 2026-09-12): `undeclared-app` and `nonliteral` were added in the very round
  // that introduced this set and were not put in it, so the derived noun was wrong AGAIN — the second
  // time this one line has misdescribed its own numbers. Both are coverage failures by the code's own
  // words ("silent zero coverage", "unfollowable blind spot").
  const COVERAGE_RULES = new Set(['unresolved', 'vacuous', 'missing-entry', 'undeclared-app', 'nonliteral']);
  const redCases = cases.filter((c) => c.expect === 'RED');
  const coverage = redCases.filter((c) => c.rules.split(',').every((r) => COVERAGE_RULES.has(r))).length;
  console.log(`  RED in ${redCases.length} cases = ${redCases.length - coverage} leak shapes `
    + `+ ${coverage} coverage failures; GREEN in ${cases.length - redCases.length} legitimate ones.`);
}

// ---------------------------------------------------------------------------------------------

function main() {
  if (process.argv.includes('--selftest')) return selftest();

  const { violations, roots, visited, unresolved, perScanRoot, missingExtra, vacuous, externals,
          nonliteral, undeclaredApps, unreadable } =
    analyse(REPO, SCAN_ROOTS, BANNED_FILES, EXTRA_CLIENT_ROOTS, NO_CLIENT_ROOTS_OK, BANNED_SPECIFIERS);

  // F4 (security-auditor): tsconfig `paths` aliases are not resolved by this walk. None exist today —
  // measured — but if one is added, every import through it becomes invisible. Announce, never guess.
  const aliasing = [];
  const unreadableTsconfig = [];
  for (const sr of SCAN_ROOTS) {
    const tc = path.join(REPO, sr, 'tsconfig.json');
    if (!tryFile(tc)) continue;
    try {
      // tsconfig.json is JSONC: comments AND trailing commas are legal. The first cut stripped only
      // comments and swallowed the parse error, so a single trailing comma switched this detector OFF
      // in silence (code-reviewer, 2026-09-12). A blind-spot detector that disables itself quietly is
      // worse than not having one, so a tsconfig we cannot read is now a FAILURE, not a shrug.
      const raw = fs.readFileSync(tc, 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
        .replace(/,(\s*[}\]])/g, '$1');
      const parsed = JSON.parse(raw);
      if (Object.keys(parsed.compilerOptions?.paths ?? {}).length) aliasing.push(`${sr}/tsconfig.json`);
      if (parsed.extends) unreadableTsconfig.push(`${sr}/tsconfig.json (extends another config, which this gate does not follow)`);
    } catch (e) {
      unreadableTsconfig.push(`${sr}/tsconfig.json (${e.message})`);
    }
  }

  console.log('check-client-imports — build-time server/client boundary');
  for (const p of perScanRoot) {
    console.log(`  ${p.scanRoot.padEnd(16)} ${String(p.codeFiles).padStart(3)} code files -> ${p.roots} client root(s)`);
  }
  console.log(`  client roots in total: ${roots.length}`);
  for (const r of roots) console.log(`    - ${r}`);
  console.log(`  modules reachable from them: ${visited}`);
  console.log(`  banned modules: ${Object.keys(BANNED_FILES).length} file(s) + every Node builtin `
    + `+ ${Object.keys(BANNED_SPECIFIERS).length} specifier(s)`);
  // S2: the walk STOPS at third-party packages. That is a real boundary of what this gate measures,
  // so it is printed rather than left for a reader to infer from silence.
  console.log(`  apps discovered under web/: scanned ${perScanRoot.length}, `
    + `declared not-an-app ${Object.keys(NOT_AN_APP).length}, undeclared ${undeclaredApps.length}`);
  console.log(`  third-party specifiers the walk stops at (NOT inspected): ${externals.length}`);
  if (externals.length) console.log(`    ${externals.join(', ')}`);

  if (undeclaredApps.length) {
    console.error('\nFAIL: a directory under web/ has its own package.json but is neither scanned nor');
    console.error('declared. A new app must not start life with silent zero coverage:');
    for (const a of undeclaredApps) console.error(`    ${a}`);
    console.error('  Add it to SCAN_ROOTS, or to NOT_AN_APP with the reason it has no client boundary.');
    process.exit(1);
  }

  if (unreadableTsconfig.length) {
    console.error('\nFAIL: a tsconfig could not be read, so the path-alias blind-spot check did not run.');
    console.error('A detector that disables itself in silence is worse than an absent one:');
    for (const a of unreadableTsconfig) console.error(`    ${a}`);
    process.exit(1);
  }

  if (aliasing.length) {
    console.error('\nFAIL: a tsconfig declares `compilerOptions.paths`. This walk resolves relative,');
    console.error('workspace and node: specifiers — NOT path aliases, so every import written through');
    console.error('one would be invisible to this gate while looking perfectly normal:');
    for (const a of aliasing) console.error(`    ${a}`);
    console.error('  Teach resolveSpec the alias map, or do not use aliases in a gated app.');
    process.exit(1);
  }

  if (unreadable.length) {
    console.error('\nFAIL: a module RESOLVED but could not be read, so everything behind it is');
    console.error('unmeasured. This is the shape that made this gate print OK over a real leak:');
    for (const u of unreadable) console.error(`    ${u.file}   (${u.why})   ${u.as}`);
    process.exit(1);
  }

  if (nonliteral.length) {
    console.error('\nFAIL: something in a client-reachable module that this walk cannot follow, so');
    console.error('everything behind it is unmeasured — the same blind spot this gate refuses to');
    console.error('accept for relative imports:');
    for (const n of nonliteral) console.error(`    ${n.at}   ${n.reason}   (reached from ${n.chain[0]})`);
    process.exit(1);
  }

  if (missingExtra.length) {
    console.error('\nFAIL: a declared browser-by-construction entry does not exist. A rename must break');
    console.error('this gate, never quietly empty it:');
    for (const m of missingExtra) console.error(`    ${m.file}  (${m.why})`);
    process.exit(1);
  }

  if (vacuous.length) {
    console.error('\nFAIL: a scanned app has code files but contributes NO client root, so this gate');
    console.error('covers none of it while printing OK — vacuous coverage is indistinguishable from a');
    console.error('pass. Add a browser-by-construction entry, or declare it in NO_CLIENT_ROOTS_OK with');
    console.error('a reason:');
    for (const v of vacuous) console.error(`    ${v}`);
    process.exit(1);
  }

  if (unresolved.length) {
    console.error('\nFAIL: imports the walk could not resolve. An unfollowable import is a BLIND SPOT,');
    console.error('and a gate with an unannounced blind spot measures less than it claims to:');
    for (const u of unresolved) console.error(`    ${u.at}  ->  ${u.spec}`);
    process.exit(1);
  }

  if (violations.length) {
    console.error(`\nFAIL: ${violations.length} server-only module(s) reachable from a client component.\n`);
    for (const v of violations) {
      console.error(`  [${v.rule}] ${v.at}   imports '${v.spec}'`);
      console.error(`    chain: ${v.chain.join('\n           -> ')}`);
      console.error(`    why:   ${v.why}\n`);
    }
    process.exit(1);
  }

  console.log('\nOK — no server-only module is reachable from any client component.');
}

main();
