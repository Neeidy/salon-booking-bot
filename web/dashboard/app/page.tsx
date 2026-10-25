/**
 * The ONE place that reads. Every panel below is a SERVER component and receives a slice as a plain
 * prop — no panel fetches, and there is no per-row request anywhere on this page.
 *
 * WHY THAT IS A HARD RULE AND NOT A PREFERENCE: the BOT SHARES THE STORE. On Airtable that meant a
 * base-wide 5 requests/second with a 30-second penalty on overrun; on Postgres (since D5) it means the
 * cluster's connections and its work, which `store.ts` bounds with a pool of four. A dashboard that fans
 * out per row competes with customers booking. Four reads, once, here.
 *
 * ⚠ EVERY COMPONENT ON THIS PAGE IS A SERVER COMPONENT, INCLUDING THE HANDOFF QUEUE, AND THAT IS A
 * SECURITY PROPERTY RATHER THAN AN ARCHITECTURE PREFERENCE. Next serialises a CLIENT component's props
 * into the RSC payload, which is plain text inside the HTML — so PII handed to a client component is
 * in the page source whether or not a pixel ever shows it. Measured on `web/site`: the whole client
 * config sits in its built `index.html` for exactly this reason (CRT #10b). Keeping these on the
 * server means the text renders into a page that only an authenticated owner can fetch, and never
 * into a payload.
 *
 * ⚠ AND THE GATE CANNOT ENFORCE THAT LAST PART. `scripts/check-client-imports.cjs` walks IMPORTS; it
 * does not see PROPS. If someone later adds `'use client'` to a panel, or passes a row DOWN to a
 * client child, nothing fails. The rule is written here, in the file where it would be broken.
 */
import { readAppointments, readLeads, readHandoffQueue, readSpend, resetBudget, budgetUsed,
  BUDGET_PER_PAGE, StoreError, ConfigError } from '../lib/store.ts';
import { AppointmentsPanel } from '../components/AppointmentsPanel.tsx';
import { LeadsPanel } from '../components/LeadsPanel.tsx';
import { HandoffQueue } from '../components/HandoffQueue.tsx';
import { SystemHealth } from '../components/SystemHealth.tsx';
import { Unavailable } from '../components/States.tsx';
import { exportLinks } from '../lib/exportCsv.ts';

// No caching and no revalidation: this page is a live board, and a cached PII surface behind an
// authenticated gate is a copy of that surface with weaker access rules.
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function DashboardPage() {
  resetBudget();
  let data;
  try {
    // In parallel — four independent reads, one round trip's worth of latency, still four requests.
    const [appointments, leads, queue, spend] = await Promise.all([
      readAppointments(), readLeads(), readHandoffQueue(), readSpend(),
    ]);
    data = { appointments, leads, queue, spend };
  } catch (e) {
    // D19/D20. A dashboard that renders empty panels on a failed read tells the owner their shop had
    // no bookings, which is the worst available lie. Fail VISIBLY instead.
    const busy = e instanceof StoreError && e.busy;
    // A missing credential or a role that can write throws BEFORE any read, so "the service did not answer"
    // would name a service we never called and point the operator at the wrong thing entirely.
    const misconfigured = e instanceof ConfigError;
    // A11: `String(e)` put an arbitrary internal message on the page — a driver message can carry
    // the database host. The full error goes to the server log; the page gets
    // a shape, not a payload.
    console.error('[dashboard] read failed:', e);
    const detail = e instanceof StoreError ? `${e.table}: ${e.code}` : (e instanceof Error ? e.name : 'unknown error');
    return <Unavailable busy={busy} misconfigured={misconfigured} detail={detail} />;
  }

  const used = budgetUsed();
  // Empty unless DASHBOARD_EXPORT_ENABLED=1: the routes answer 404 while it is off, so no link may point at them.
  // A release gate until the Phase 7-2 Codex audit (lib/exportCsv.ts), not an access control.
  const downloads = exportLinks();

  return (
    <>
      <div className="grain" aria-hidden="true" />
      {/* A7: the visible ribbon lives on `.mock-ribbon span`; text placed straight in the div rendered as
          plain words in an empty box. And it is NOT aria-hidden any more — honesty-demos.md asks for the
          mock to be MARKED, and a marker a screen reader cannot reach is not a marker. */}
      <div className="mock-ribbon"><span>DEMO DATA</span></div>

      <header className="topbar">
        <div className="wrap topbar-row">
          <div className="brand">Owner dashboard</div>
          <div className="topbar-right">
            <span className="tech">
              {/* A8: this said "of 4" as a literal while BUDGET_PER_PAGE was exported and unused —
                  one number, two copies, the shape contract-integrity.md exists for. */}
              {used} of {BUDGET_PER_PAGE} database reads · one read per panel · no auto-refresh
            </span>
            {downloads.length > 0 && (
              <span className="tech">
                {downloads.map((d, i) => (
                  <span key={d.href}>{i > 0 ? ' · ' : ''}<a href={d.href} download>{d.label}</a></span>
                ))}
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="wrap">
        {/* The queue comes FIRST. It is the one panel that asks the owner to do something, and the
            rows nobody can prove were delivered sort to the top of it. */}
        <HandoffQueue page={data.queue} />
        <AppointmentsPanel page={data.appointments} />
        <LeadsPanel page={data.leads} />
        <SystemHealth page={data.spend} />
      </main>
    </>
  );
}
