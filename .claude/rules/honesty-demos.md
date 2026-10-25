# honesty-demos

**Purpose:** keep the project honest — it is a demo/learning build until stated otherwise.

- Mark mock as mock: services, prices, hours, and the sample salon are **config-driven mock data**.
- No invented metrics, no fake customer names, no "trusted by X shops" claims.
- Frame the path to production as **"one swap to real"**: the client's real Zernio number + Google Calendar
  + **their own Postgres** — not a rebuild. Under Model 1 (one isolated deployment per client) "their own
  Postgres" means three things per client: **a Postgres service, its secrets, and its backup step**
  (`docs/MIGRATION-PLAN.md` §8). *(It used to say "+ Airtable base". Since the cutover of 2026-10-24 the store
  is Postgres; Airtable is read-only until D6c and is not part of a new client's setup.)*
- **Do not let "one swap" overstate the config story.** Two config keys are dead today (`instagram`,
  `business.locale` — K-2, in the v2 backlog), the engine reads its config from an inline copy in the `Load Config`
  node rather than from the file, and the config-only second client (Phase 8) has not been built. "No code
  change" is the design goal, not yet a demonstrated fact.
- If something isn't built or wasn't tested, say so plainly. A visible gap beats a hidden one.

**Why:** this is a portfolio/vitrin piece — its credibility is the product. Honesty is the differentiator.
