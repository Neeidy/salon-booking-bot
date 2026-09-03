/**
 * loadConfig — the single door every frontend surface walks through to read client config.
 *
 * WHY THIS EXISTS
 * The template promise is "fill in client.config.json and it runs". Phase 5 (FIX-2 / BULGU-3) proved
 * that promise is only real if the config is validated against the COMMITTED schema — the live engine
 * config had silently drifted out of its own contract. This loader gives the frontend the same
 * guarantee the engine now has: it validates with ajv against schemas/client.config.schema.json
 * (the committed file itself, never a hand-written copy — .claude/rules/contract-integrity.md), and
 * throws on the first violation. A config that does not satisfy the contract must break the BUILD,
 * loudly, not paint a half-branded page (.claude/rules/code-style.md — validate early, fail loud).
 *
 * SERVER / BUILD-TIME ONLY. It reads the filesystem. It must never be imported into a browser bundle.
 * The `window` tripwire below is a RUNTIME guard, not a build-time boundary — it makes the mistake
 * loud instead of silent. The real build-time boundary (a lint rule forbidding this import from client
 * components, plus a bundle scan) lands with the apps in 6a-2 / 6c. The `server-only` package was
 * evaluated and REJECTED: without the `react-server` export condition it throws in plain Node, which
 * would break this package's own test suite (measured 2026-09-03 — see ARCH-DEC §5).
 *
 * WHICH FILE IT READS
 *   config/client.config.json          — the real per-client config, gitignored (used when present)
 *   config/client.config.example.json  — the committed MOCK demo client (fallback)
 * The fallback is deliberate and honest: with no client config present, the surfaces render the
 * Demo Barber Co. mock, which carries demoMode:true, which is what keeps the mock ribbon on screen
 * (.claude/rules/honesty-demos.md). Because falling back is SILENT by nature, loadConfigDetailed()
 * reports `usedFallback` so a build can log which file it actually rendered from.
 */
import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv, { type ErrorObject, type ValidateFunction } from 'ajv';
import type { ClientConfig } from './client.config.types.ts';

export type { ClientConfig };

// A REAL browser has window+document and NO Node process. A jsdom/happy-dom test environment has
// window+document but IS a Node process — it must stay importable, or 6a-2 cannot unit-test a server
// component in a DOM environment. Testing `window` alone would have banned that legitimate case.
const looksLikeBrowser =
  typeof globalThis === 'object' && 'window' in globalThis && 'document' in globalThis;
const isNodeProcess = typeof process !== 'undefined' && Boolean(process.versions?.node);
if (looksLikeBrowser && !isNodeProcess) {
  throw new Error(
    '@salon/shared/config is server/build-time only — it reads the filesystem and must never be ' +
      'bundled into a browser. Load the config in a server component / route handler and pass the ' +
      'values down as props.',
  );
}

/** repo root, from web/shared/src/config/ — overridable so tests never depend on this depth. */
const DEFAULT_REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');

export interface LoadConfigOptions {
  /** Repo root. Default: derived from this file's location. */
  repoRoot?: string;
  /** Explicit config file. Default: client.config.json if present, else client.config.example.json. */
  configPath?: string;
  /** Explicit schema file. Default: <repoRoot>/schemas/client.config.schema.json. */
  schemaPath?: string;
}

/** Thrown when the config does not satisfy its committed contract, or cannot be read at all. */
export class ConfigContractError extends Error {
  readonly configPath: string;
  constructor(message: string, configPath: string) {
    super(message);
    this.name = 'ConfigContractError';
    this.configPath = configPath;
  }
}

export interface ResolvedConfigPath {
  path: string;
  /**
   * true = no per-client config was found on disk and we fell back to the committed mock example.
   * Named for what happened (a fallback), NOT for which file it is: passing the example explicitly
   * via `configPath` is a deliberate choice, not a fallback.
   */
  usedFallback: boolean;
}

export interface LoadedConfig {
  config: ClientConfig;
  /** The file actually read — log this at build time so a missing client config is never invisible. */
  configPath: string;
  usedFallback: boolean;
}

export function resolveConfigPath(options: LoadConfigOptions = {}): ResolvedConfigPath {
  const root = options.repoRoot ?? DEFAULT_REPO_ROOT;
  if (options.configPath) return { path: options.configPath, usedFallback: false };
  const real = join(root, 'config/client.config.json');
  if (existsSync(real)) return { path: real, usedFallback: false };
  return { path: join(root, 'config/client.config.example.json'), usedFallback: true };
}

function formatErrors(errors: ErrorObject[] | null | undefined): string {
  if (!errors?.length) return '(ajv reported no detail)';
  return errors
    .map((e) => `  ${e.instancePath || '(root)'} ${e.keyword} ${JSON.stringify(e.params)} — ${e.message}`)
    .join('\n');
}

/**
 * One compiled validator per schema file. Compiling is the expensive part, and a server component may
 * call this per request. Keyed by path because tests deliberately point at other schema files.
 */
const validatorCache = new Map<string, ValidateFunction>();

/**
 * Cache key = resolved path + mtime. Path alone was wrong: in a long-lived `next dev` process, editing
 * schemas/client.config.schema.json would keep validating against the STALE compiled schema until
 * restart — i.e. "we validate against the committed schema" would be quietly false in that window.
 * Resolving also stops a relative and an absolute reference to one file compiling twice.
 */
function getValidator(schemaPath: string, configPath: string): ValidateFunction {
  const resolved = resolve(schemaPath);
  let key = resolved;
  try {
    key = `${resolved}:${statSync(resolved).mtimeMs}`;
  } catch {
    // Unreadable — fall through; the compile below turns it into a ConfigContractError.
  }
  const cached = validatorCache.get(key);
  if (cached) return cached;
  try {
    // strict:false + no ajv-formats: the schema's "format" keywords are documentation, and ajv treats
    // an unregistered format as an annotation. scripts/check-config-schema.cjs is configured the same
    // way today — but nothing ENFORCES that they stay aligned, so if one side ever adds ajv-formats,
    // align the other in the same change (they are two call sites of one contract, not two contracts).
    const ajv = new Ajv({ allErrors: true, strict: false });
    const validate = ajv.compile(JSON.parse(readFileSync(schemaPath, 'utf8')));
    validatorCache.set(key, validate);
    return validate;
  } catch (e) {
    // A schema we cannot compile means we cannot validate — and an unvalidated config is not trusted.
    // This must surface as ConfigContractError like every other failure here, or a caller's
    // `catch (e instanceof ConfigContractError)` misses it and loses which config was being loaded.
    throw new ConfigContractError(
      `the committed schema at ${schemaPath} is not a usable JSON Schema: ${(e as Error).message}`,
      configPath,
    );
  }
}

/**
 * Validate an ALREADY-PARSED config object against the committed schema. Same validator, same errors as
 * the file path — the env-var source (CLIENT_CONFIG_JSON, used by the site's prebuild) must not get its
 * own second-class check. `source` only labels the error message.
 */
export function validateConfigObject(
  raw: unknown,
  options: { schemaPath?: string; repoRoot?: string; source?: string } = {},
): ClientConfig {
  const root = options.repoRoot ?? DEFAULT_REPO_ROOT;
  const schemaPath = options.schemaPath ?? join(root, 'schemas/client.config.schema.json');
  const source = options.source ?? '(in-memory config)';
  if (!existsSync(schemaPath)) {
    throw new ConfigContractError(
      `committed schema not found at ${schemaPath} — the config cannot be validated, so it will not be trusted`,
      source,
    );
  }
  const validate = getValidator(schemaPath, source);
  if (!validate(raw)) {
    throw new ConfigContractError(
      `${source} does NOT satisfy schemas/client.config.schema.json:\n${formatErrors(validate.errors)}`,
      source,
    );
  }
  return raw as ClientConfig;
}

/**
 * Read + validate the client config, and report WHICH file was used. Throws ConfigContractError on a
 * missing/unreadable file, unparseable JSON, an unusable schema, or any schema violation.
 * Never returns a partially-valid config.
 */
export function loadConfigDetailed(options: LoadConfigOptions = {}): LoadedConfig {
  const root = options.repoRoot ?? DEFAULT_REPO_ROOT;
  const { path: configPath, usedFallback } = resolveConfigPath(options);
  const schemaPath = options.schemaPath ?? join(root, 'schemas/client.config.schema.json');

  if (!existsSync(configPath)) {
    throw new ConfigContractError(`client config not found at ${configPath}`, configPath);
  }
  if (!existsSync(schemaPath)) {
    throw new ConfigContractError(
      `committed schema not found at ${schemaPath} — the config cannot be validated, so it will not be trusted`,
      configPath,
    );
  }

  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(configPath, 'utf8'));
  } catch (e) {
    throw new ConfigContractError(`${configPath} is not valid JSON: ${(e as Error).message}`, configPath);
  }

  const config = validateConfigObject(raw, { schemaPath, repoRoot: root, source: configPath });
  return { config, configPath, usedFallback };
}

/** The common case: just give me the config. Use loadConfigDetailed() when the source file matters. */
export function loadConfig(options: LoadConfigOptions = {}): ClientConfig {
  return loadConfigDetailed(options).config;
}

/**
 * The ONE place the demoMode default lives. The key is optional in the schema, so "absent" must mean
 * the same thing everywhere: a real client install shows no mock ribbon. Scattering `?? false` across
 * surfaces is how one surface eventually disagrees with another.
 */
export function isDemoMode(config: ClientConfig): boolean {
  return config.demoMode === true;
}
