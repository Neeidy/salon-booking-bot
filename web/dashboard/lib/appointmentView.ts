/**
 * Which appointments the owner sees, and how their time is written: shared by `AppointmentsPanel` and the CSV
 * export (`lib/exportCsv.ts`), so the file the owner downloads holds the rows the panel shows, not a second
 * opinion about them. Moved out of the panel unchanged in Phase 7 F2; the panel's comments on WHY each rule
 * exists stay where the rules are drawn.
 *
 * Pure: no store, no config. The timezone and the clock are arguments, which is what makes it testable.
 */
import type { Appointment } from './types.ts';

export interface AppointmentSections {
  /** Rows with a parseable start time. */
  dated: Appointment[];
  /** Rows without one: counted, never placed on a day. */
  undated: number;
  /** Booked, on today's date in the shop's timezone (earlier today included). */
  todays: Appointment[];
  /** Booked, after now, and not today. */
  upcoming: Appointment[];
}

export function appointmentSections(rows: Appointment[], tz: string, nowMs: number): AppointmentSections {
  const dated = rows.filter((r) => Number.isFinite(Date.parse(r.start_utc ?? '')));
  const today = new Date(nowMs).toLocaleDateString('en-CA', { timeZone: tz });
  const isToday = (r: Appointment) =>
    new Date(Date.parse(r.start_utc!)).toLocaleDateString('en-CA', { timeZone: tz }) === today;
  return {
    dated,
    undated: rows.length - dated.length,
    todays: dated.filter((r) => isToday(r) && r.status === 'booked'),
    upcoming: dated.filter((r) => Date.parse(r.start_utc!) > nowMs && !isToday(r) && r.status === 'booked'),
  };
}

/** The panel's wording of a start time, in the shop's timezone. */
export function when(iso: string | undefined, tz: string): { day: string; time: string } | null {
  const t = Date.parse(iso ?? '');
  if (!Number.isFinite(t)) return null;
  const d = new Date(t);
  return {
    day: d.toLocaleDateString('en-GB', { timeZone: tz, weekday: 'short', day: 'numeric', month: 'short' }),
    time: d.toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit' }),
  };
}
