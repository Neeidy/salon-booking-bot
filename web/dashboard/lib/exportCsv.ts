/**
 * Owner CSV export (Phase 7 item (a)): appointments and leads, the panels' rows and the panels' columns, MASKED
 * with the same server-side functions the panels use (`lib/mask.ts`). Served by two GET route handlers,
 * `app/api/export/appointments/route.ts` and `app/api/export/leads/route.ts`, which take no input at all.
 *
 * WHAT IT READS: only `store.ts`'s existing constant reads, `readAppointments` and `readLeads`, passed in by the
 * route. No new statement, no new query path, nothing a request can steer. A full name, a full phone number and
 * the columns E2 keeps out (`sender_key`, `gcal_event_id`, `computed_reply`, `cancel_target_id`) cannot be in the
 * file, because the reads do not fetch the last four and every PII cell goes through a mask before it is written.
 *
 * THE FLAG IS A RELEASE GATE, NOT A SECURITY BOUNDARY. `DASHBOARD_EXPORT_ENABLED` must be exactly `1` for the
 * routes to answer and for the page to draw the links; anything else, including unset, gives a 404 and no link.
 * It exists so this code can be merged and deployed before the Phase 7-2 Codex audit has read it, and switched
 * on only after. It does not decide WHO may download: the boundary for that is Cloudflare Access in front of the
 * whole dashboard host (measured in K-6). These routes do NOT verify Access themselves (no JWT check, no header
 * check); a request that reached them without Access would be served exactly like one that came through it.
 *
 * CSV SAFETY: every cell is quoted (RFC 4180: a `"` doubled), lines end in CRLF, and the file starts with a UTF-8
 * byte-order mark so a spreadsheet reads `…` and accented names correctly. A cell beginning with `=`, `+`, `-`,
 * `@`, a tab or a carriage return is prefixed with `'`, the OWASP neutraliser for formula injection: a customer
 * who types `=HYPERLINK(...)` as their name must not have it evaluated on the owner's machine. The cost, stated:
 * a masked phone (`+43…67`) is written as `'+43…67`.
 *
 * Pure apart from `process.env` as a default argument: the reads, the timezone and the clock are injected, which
 * is what lets `lib/exportCsv.test.ts` run it without a database.
 */
import type { Page } from './store.ts';
import type { Appointment, Lead } from './types.ts';
import { maskName, maskPhone, assertMasked } from './mask.ts';
import { appointmentSections, when } from './appointmentView.ts';

export const EXPORT_FLAG = 'DASHBOARD_EXPORT_ENABLED';
type Env = Record<string, string | undefined>;

/** True only for the exact string `1`. `true`, `yes`, `0` and unset are all OFF: a gate that guesses is not one. */
export function exportEnabled(env: Env = process.env): boolean {
  return env[EXPORT_FLAG] === '1';
}

/** The links the page draws: none at all while the flag is off. */
export function exportLinks(env: Env = process.env): Array<{ href: string; label: string }> {
  return exportEnabled(env)
    ? [
        { href: '/api/export/appointments', label: 'Appointments (CSV)' },
        { href: '/api/export/leads', label: 'Leads (CSV)' },
      ]
    : [];
}

const FORMULA_START = /^[=+\-@\t\r]/;

/** One cell: neutralised if it could start a formula, then quoted. */
export function csvCell(value: string): string {
  const v = FORMULA_START.test(value) ? `'${value}` : value;
  return `"${v.replace(/"/g, '""')}"`;
}

/** BOM, a header row, the rows, CRLF after every line. */
export function toCsv(header: string[], rows: string[][]): string {
  return `﻿${[header, ...rows].map((r) => r.map(csvCell).join(',')).join('\r\n')}\r\n`;
}

const WITHHELD = '— (withheld: it did not pass the masking check)';
/** The panels' rule: a value that fails `assertMasked` is not written. Failing blanks one cell, not the file. */
export function maskedCell(fn: (raw: string | undefined) => string, raw: string | undefined, what: string): string {
  try { return assertMasked(fn(raw), what); } catch { return WITHHELD; }
}

/** A last row, so a file cut at the read's 100-row cap says so inside the file and not only in a header. */
const TRUNCATED_ROW = ['(truncated: the dashboard reads at most 100 rows and more exist; this file is not complete)'];

/** `AppointmentsPanel`'s rows (booked, today and later) and its columns, the time split for a spreadsheet. */
export function appointmentsCsv(page: Page<Appointment>, tz: string, nowMs: number): string {
  const { todays, upcoming } = appointmentSections(page.rows, tz, nowMs);
  const date = (iso: string | undefined) => {
    const t = Date.parse(iso ?? '');
    return Number.isFinite(t) ? new Date(t).toLocaleDateString('en-CA', { timeZone: tz }) : '';
  };
  const rows = [...todays, ...upcoming].map((r) => [
    date(r.start_utc),
    when(r.start_utc, tz)?.time ?? '',
    maskedCell(maskName, r.customer_name, 'customer name'),
    r.service ?? '',
    r.channel ?? '',
    r.reminded ? 'yes' : '',
  ]);
  if (page.truncated) rows.push(TRUNCATED_ROW);
  return toCsv([`date (${tz})`, `time (${tz})`, 'customer', 'service', 'channel', 'reminded'], rows);
}

/** `LeadsPanel`'s rows and columns. */
export function leadsCsv(page: Page<Lead>): string {
  const rows = page.rows.map((r) => [
    maskedCell(maskName, r.name, 'lead name'),
    maskedCell(maskPhone, r.phone, 'lead phone'),
    r.status ?? 'new',
    r.source ?? '',
  ]);
  if (page.truncated) rows.push(TRUNCATED_ROW);
  return toCsv(['name', 'phone', 'status', 'source'], rows);
}

export type ExportKind = 'appointments' | 'leads';
export interface ExportDeps {
  env: Env;
  readAppointments: () => Promise<Page<Appointment>>;
  readLeads: () => Promise<Page<Lead>>;
  /**
   * `store.ts`'s per-process read tripwire is reset only by the page render; without this, the fifth export
   * request after a render would be refused as a fan-out. One export is one read.
   */
  resetBudget: () => void;
  /** Only the appointments file needs it; called inside the try, so a missing config is a 500, not a crash. */
  timezone: () => string;
  now: () => number;
}

const notFound = () => new Response('Not Found', { status: 404, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' } });

/** The whole route: flag first, before anything is read or configured. */
export async function exportResponse(kind: ExportKind, deps: ExportDeps): Promise<Response> {
  if (!exportEnabled(deps.env)) return notFound();
  let body: string;
  try {
    deps.resetBudget();
    body = kind === 'appointments'
      ? appointmentsCsv(await deps.readAppointments(), deps.timezone(), deps.now())
      : leadsCsv(await deps.readLeads());
  } catch (e) {
    // Only the error's NAME and a code-shaped `code` reach the log, never its message (a driver message can
    // carry the host); the response carries neither. Same discipline as store.ts's idle-error log.
    const name = e instanceof Error ? e.name : 'unknown';
    const code = e && typeof e === 'object' && 'code' in e && typeof e.code === 'string' && /^[0-9A-Z]{5}$|^E[A-Z0-9_]+$/.test(e.code) ? e.code : '';
    console.error(`[export] ${kind} failed: ${name}${code ? ` ${code}` : ''}`);
    const misconfigured = name === 'ConfigError';
    return new Response(misconfigured ? 'Export unavailable: the dashboard is misconfigured.' : 'Export unavailable: the data could not be read.', {
      status: misconfigured ? 500 : 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
    });
  }
  const day = new Date(deps.now()).toISOString().slice(0, 10);
  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${kind}-${day}.csv"`,
      // A PII file: no shared cache may keep a copy, and no browser may guess it is something else.
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}
