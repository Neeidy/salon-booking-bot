/**
 * D1 · D2 · D3 · D5 · D6 — appointments. SERVER component (see app/page.tsx).
 *
 * Times are stored in UTC and shown in the shop's timezone; that split is the product's own rule, so
 * the formatting lives here rather than being left to whatever the viewer's browser happens to be.
 *
 * ⚠ D5 and D6 are DIFFERENT empty states and are not collapsed into one. "No bookings today" is an
 * ordinary Tuesday; "no bookings ever" means the shop has not started. Showing the same sentence for
 * both tells a new owner their system is broken.
 */
import type { Page } from '../lib/airtable.ts';
import type { Appointment } from '../lib/types.ts';
import { maskName, assertMasked } from '../lib/mask.ts';
import { shopConfig } from '../lib/shopConfig.ts';

// K5 (code-reviewer, 2026-09-12): this was `const TZ = 'Europe/Vienna'` — a literal, in a
// config-driven product that already ships a second example client on Europe/Berlin. It did not look
// wrong because the two share an offset, which is exactly what made it dangerous: the first client
// outside CET gets every time drawn wrong, silently. Read from the shop's own config now.
function when(iso: string | undefined, TZ: string): { day: string; time: string } | null {
  const t = Date.parse(iso ?? '');
  if (!Number.isFinite(t)) return null;
  const d = new Date(t);
  return {
    day: d.toLocaleDateString('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }),
    time: d.toLocaleTimeString('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit' }),
  };
}

export function AppointmentsPanel({ page }: { page: Page<Appointment> }) {
  const { timezone: TZ } = shopConfig();
  const now = Date.now();
  const dated = page.rows.filter((r) => Number.isFinite(Date.parse(r.start_utc ?? '')));
  // A row with no start time cannot be placed on any screen. It is EXCLUDED from the lists and
  // COUNTED below rather than dropped in silence — measured 2026-09-12, these are Airtable UI
  // artefacts (completely empty rows), not broken writes, but a count the owner can see is how
  // anyone would notice if that ever stopped being true.
  const undated = page.rows.length - dated.length;

  const today = new Date().toLocaleDateString('en-CA', { timeZone: TZ });
  const isToday = (r: Appointment) =>
    new Date(Date.parse(r.start_utc!)).toLocaleDateString('en-CA', { timeZone: TZ }) === today;

  const todays = dated.filter((r) => isToday(r) && r.status === 'booked');
  const upcoming = dated.filter((r) => Date.parse(r.start_utc!) > now && !isToday(r) && r.status === 'booked');
  // K4: this was called `anyBookedEver` and was computed from a 30-day, 100-row window — so a shop
  // whose table held 121 appointments of which 118 were cancelled (measured 2026-09-12, before that
  // day's drill cleanup; the counts have moved since and the defect does not depend on them) was told
  // "no bookings yet", the one sentence reserved for a shop that has never started. Wrong, and wrong
  // in the reassuring direction.
  const anyBookedInWindow = dated.some((r) => r.status === 'booked');
  const hasRowsButNoneActive = dated.length > 0 && !anyBookedInWindow;

  const Row = ({ r }: { r: Appointment }) => {
    const w = when(r.start_utc, TZ);
    return (
      <li className="row">
        <strong>{w ? `${w.day} ${w.time}` : '—'}</strong>
        <span>{assertMasked(maskName(r.customer_name), 'customer name')}</span>
        <span className="sw">{r.service ?? '—'}</span>
        <span className="tech">{r.channel ?? '—'}{r.reminded ? ' · reminded' : ''}</span>
      </li>
    );
  };

  return (
    <section className="panel" aria-labelledby="appt-h">
      <div className="q-head">
        <h2 id="appt-h">Appointments</h2>
        {page.truncated && <span className="tech">showing the first {page.rows.length} — there are more</span>}
      </div>

      <h3>Today</h3>
      {todays.length === 0 ? (
        anyBookedInWindow
          ? <p className="release">No bookings today.</p>                         /* D5 */
          : hasRowsButNoneActive
            /* Neither D5 nor D6: there ARE appointments here, none of them still stand. Saying
               "no bookings yet" would be false; saying "no bookings today" would hide the history.
               ⚠ This used to end "— every one was cancelled", which the code does not know: it tests
               `!some(status === 'booked')`, and `status` is an optional single-select, so a row with
               a start time and a BLANK status makes that sentence a lie. The panel's own comment
               already says empty rows appear in this table. The claim is reduced to what is measured
               (`code-reviewer` #4, 2026-09-12). */
            ? <p className="release">
                {dated.length} appointment{dated.length === 1 ? '' : 's'} in this window, none of them
                still active.
              </p>
          : <p className="release">No bookings yet — this is where they will appear.</p>  /* D6 */
      ) : <ul className="q-msgs">{todays.map((r) => <Row key={r.id} r={r} />)}</ul>}

      <h3>Coming up</h3>
      {upcoming.length === 0
        ? <p className="release">Nothing booked ahead.</p>
        : <ul className="q-msgs">{upcoming.map((r) => <Row key={r.id} r={r} />)}</ul>}

      {undated > 0 && (
        <p className="tech">
          {undated} row{undated === 1 ? '' : 's'} in this table have no start time and cannot be placed
          on a day. They are excluded above rather than hidden.
        </p>
      )}

      {/* SCREEN-INVENTORY §4.a: Google Calendar is the source of truth and this table is a mirror.
          After a mirror_failed the two disagree and this page CANNOT know it. Stated, not hidden. */}
      <p className="tech">
        Mirrored from Google Calendar. If a sync ever failed, the calendar is right and this list is not —
        this board cannot tell you which.
      </p>
    </section>
  );
}
