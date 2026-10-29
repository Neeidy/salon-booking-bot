# honesty-demos

**Purpose:** keep the project honest — it is a demo/learning build until stated otherwise.

- Mark mock as mock: services, prices, hours, and the sample salon are **config-driven mock data**.
- No invented metrics, no fake customer names, no "trusted by X shops" claims.
- Frame the path to production as **"one swap to real"**: the client's real Zernio number + Google Calendar
  + **their own Postgres** — not a rebuild. Under Model 1 (one isolated deployment per client) "their own
  Postgres" means three things per client: **a Postgres service, its secrets, and its backup step**
  (`docs/MIGRATION-PLAN.md` §8). Airtable was retired at D6c (2026-10-27) and is not part of a new client's setup.
- **Do not let "one swap" overstate the config story.** What is shown (Phase 8, R1, 2026-10-28; offline): **a new
  client = a config file + secret inputs → `scripts/render-client.py` → import into its own n8n; no node edited by
  hand** (with both secret inputs given) — and its bounds go in the same sentence wherever it is claimed: EUR only (`priceEUR`, and `€` written in two nodes), customer text in English, two config keys that drive nothing (`instagram`, `business.locale`), the prompt carries a fixed example that hair colouring is not offered; a client offering it gets a contradicting prompt until a Main edit (quality only: `Merge Slots` and `Slot Gate` refuse a service id the config does not hold), the new instance's credentials linked by hand, and not yet shown on a real second deployment
  (`docs/PHASE-8-PLAN.md`). The engine still carries its config as literals inside its nodes, which the render fills;
  it does not read the config file at run time. *(Corrected 2026-10-28: this line said the config-only second client
  had not been built and that "no code change" was only a goal; the render and its offline proof now exist.)*
- If something isn't built or wasn't tested, say so plainly. A visible gap beats a hidden one.

**Why:** this is a portfolio/vitrin piece — its credibility is the product. Honesty is the differentiator.
