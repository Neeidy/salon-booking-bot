/**
 * The shapes the dashboard reads. These mirror `docs/DATA-MODEL.md`, and they are DELIBERATELY
 * narrower than the tables: a field absent here is a field `airtable.ts` does not request, which is
 * the point (E2 — data not fetched cannot leak).
 *
 * ⚠ These are hand-written, and that makes them a second truth against `docs/DATA-MODEL.md`. The
 * repo's own `contract-integrity.md` says a hand-mirrored contract needs a drift guard committed in
 * the same change. There is none yet: Airtable's schema is not a committed JSON schema, so the
 * generator pattern used for `client.config.types.ts` does not apply as-is. The honest form of the
 * guard is a check that every name here exists in the base's schema — reachable through the
 * `schema.bases:read` scope the PAT already has. NAMED, not built (docs/ROADMAP.md).
 */

/** Every value Airtable returns carries its record id; it is PII-adjacent and never rendered. */
interface Row { id: string }

export interface Appointment extends Row {
  start_utc?: string;
  end_utc?: string;
  service?: string;
  channel?: string;
  status?: 'booked' | 'cancelled';
  reminded?: boolean;
  reminder_sent?: string;
  created_at?: string;
  /** PII. Masked before it crosses any boundary. */
  customer_name?: string;
}

export interface Lead extends Row {
  /** PII. */
  name?: string;
  /** PII. Masked; a phone number is the one field a leaked dashboard screenshot would expose. */
  phone?: string;
  source?: string;
  status?: 'new' | 'contacted' | 'converted';
  created_at?: string;
}

export interface HandoffRow extends Row {
  /**
   * The Airtable FORMULA field, not the raw key. `sender_key` itself is a bearer credential on the
   * widget lane (`security-secrets.md`) and is deliberately never fetched. The formula's earlier
   * defect — and its fix — are recorded in `airtable.ts`.
   */
  sender_masked?: string;
  stage?: string;
  /**
   * ⚠ EMPTY DOES NOT MEAN "no alert" — it means the alert was never delivered, or never produced.
   * `Record Alert Class` writes this only AFTER the Telegram send succeeds (Codex #5). A dashboard
   * that renders empty as good news lies to the owner. See `alertState.ts`.
   */
  last_alert_class?: string;
  last_alert_at?: string;
  last_intent?: string;
  turn_count?: number;
  last_updated?: string;
  /**
   * PII — the customer's own last messages, newline-joined, each already truncated to 80 characters
   * by the engine. FETCHED, because D9 displays it and the rule is "a field that is displayed is
   * fetched" (Yigitcan's synthesis, 2026-09-12). It renders only from a SERVER component, so it
   * reaches the page behind Cloudflare Access and never an RSC payload.
   *
   * The engine's daily purge clears this column after 30 days (`Scrub Recent Messages`), so an old
   * conversation legitimately shows nothing here — that is retention working, not data missing.
   */
  recent_messages?: string;
}

export interface SpendRow extends Row {
  period_key?: string;
  cost_usd?: number;
  updated_at?: string;
}
