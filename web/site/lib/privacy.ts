/**
 * What the demo does with what a visitor types — the facts the /privacy page and the widget notice state
 * (public demo, honesty additions, 2026-10-29). Each one is read from config or checked against the committed
 * workflows by tests/unit/privacy-facts.test.cjs, so the page cannot quietly claim something the engine does not do.
 */
import { config } from './config';

export { MESSAGE_TEXT_DAYS } from './retention';   // the engine's fixed message-text retention (see retention.ts)

/** Purge deletes a lead after the config's `leadsRetentionDays` — the key it reads itself. Absent → no expiry. */
export const LEAD_DAYS: number | null =
  typeof config.leadsRetentionDays === 'number' ? config.leadsRetentionDays : null;

/** db/ops/pg-backup.sh removes dumps older than KEEP_DAYS — its default, 14. (An operator setting can change it; the
 *  value in force on the server is measured before go-live — PUBLIC-DEMO-PLAN, R2.) */
export const BACKUP_DAYS = 14;

/** Cloudflare's privacy addendum for Turnstile — the bot check in the chat panel. */
export const TURNSTILE_PRIVACY_URL = 'https://www.cloudflare.com/turnstile-privacy-policy/';

/** Every outside service a message or a booking reaches, by what it is used for. */
export const PROCESSORS: { name: string; use: string }[] = [
  { name: 'Vercel', use: 'hosts this website' },
  { name: 'Cloudflare', use: 'the Turnstile bot check in the chat, and the network in front of the booking endpoint' },
  { name: 'Anthropic (Claude API)', use: 'reads your message to work out what you want' },
  { name: 'Google Calendar', use: "the demo's own calendar, where bookings are written" },
  { name: 'Telegram', use: "alerts to the demo's owner" },
  { name: "The demo author's own server", use: 'runs the booking engine (n8n) and its database (Postgres)' },
];
