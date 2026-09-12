/**
 * The shop's own settings, read from the SAME transport the site uses: `CLIENT_CONFIG_JSON` in the
 * environment. Server-only, like everything in this directory.
 *
 * WHY THIS FILE EXISTS AT ALL — it closes two hardcoded copies that `code-reviewer` found (K5, K6):
 *   - `AppointmentsPanel` had `TZ = 'Europe/Vienna'` inline. The repo already ships a SECOND example
 *     client on `Europe/Berlin`, so the dashboard was wrong for a config that exists today. It did not
 *     LOOK wrong, because Berlin and Vienna share an offset — which is worse, not better: the first
 *     client outside CET would have had every appointment drawn at the wrong wall-clock time with no
 *     error anywhere. `booking-integrity.md` says times are stored in UTC and displayed in the shop's
 *     CONFIGURED timezone; a literal is not a configuration.
 *   - `SystemHealth` had `CAP_USD = 10`, in the same file whose comment explains why the safety
 *     switches are NOT shown from a copy. It made the copy it had just argued against.
 *
 * WHY ENV AND NOT `@salon/shared/config`: that loader reads the filesystem, and ARCH-DEC (2026-09-03)
 * recorded what that costs in a Next app — a dynamic `readFileSync` made the tracer pull the whole
 * project in, and `config/` was not traced anyway. Env is the transport this repo already chose.
 *
 * FAIL-CLOSED, deliberately. A dashboard that silently falls back to a default timezone shows plausible
 * wrong times, and plausible-wrong is the failure mode this project keeps refusing.
 */

interface ShopConfig {
  timezone: string;
  llmCostCapUsd: number | null;
  businessName: string;
}

let cached: ShopConfig | null = null;

export function shopConfig(): ShopConfig {
  if (cached) return cached;

  const raw = process.env.CLIENT_CONFIG_JSON;
  if (!raw) {
    throw new Error(
      'CLIENT_CONFIG_JSON is not set. The dashboard renders times in the shop\'s timezone and the '
      + 'spend meter against the shop\'s cap; both come from the client config. Refusing to render '
      + 'rather than guess — a dashboard showing plausible wrong times is worse than one that stops.',
    );
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(raw) as Record<string, unknown>;
  } catch (e) {
    throw new Error(`CLIENT_CONFIG_JSON is not valid JSON: ${(e as Error).message}`);
  }

  const business = parsed.business as { timezone?: unknown; name?: unknown } | undefined;
  const bot = parsed.bot as { llmCostCapUsd?: unknown } | undefined;
  const timezone = typeof business?.timezone === 'string' ? business.timezone : '';
  if (!timezone) {
    throw new Error('CLIENT_CONFIG_JSON has no business.timezone; every time on this board depends on it.');
  }

  cached = {
    timezone,
    // The cap may legitimately be absent — the meter then shows spend WITHOUT a denominator rather
    // than inventing one.
    llmCostCapUsd: typeof bot?.llmCostCapUsd === 'number' ? bot.llmCostCapUsd : null,
    businessName: typeof business?.name === 'string' ? business.name : 'Dashboard',
  };
  return cached;
}
