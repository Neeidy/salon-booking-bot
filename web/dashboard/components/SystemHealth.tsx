/**
 * D13 · D14 · D15 · D16 · D17 — system health. SERVER component (see app/page.tsx).
 *
 * ⚠ D16 ("recent errors") is rendered as a card that says it HAS NO SOURCE, and that is the whole
 * point of it. n8n's execution log is not queryable from outside, so any list here would be invented.
 * An empty panel would read as "no errors"; a fabricated one would be worse. SCREEN-INVENTORY §4.d
 * marks this 🕳 and the screen says so out loud.
 *
 * ⚠ The switches are NOT read live. They are hard-coded literals inside the n8n `Load Config` node,
 * so nothing here can query them, and showing them from a copy would be a second truth that drifts
 * the day someone edits the node. What this panel shows is spend, which IS in Airtable.
 */
import type { Page } from '../lib/airtable.ts';
import type { SpendRow } from '../lib/types.ts';
import { shopConfig } from '../lib/shopConfig.ts';

// K6 (code-reviewer, 2026-09-12): this was `const CAP_USD = 10` — in the very file whose comment
// explains why the safety switches are NOT shown from a copy. It made the copy it had just argued
// against, and the "of $10.00" on screen would have gone quietly wrong the day the cap changed.

export function SystemHealth({ page }: { page: Page<SpendRow> }) {
  const { llmCostCapUsd: cap, timezone } = shopConfig();
  const row = page.rows[0];
  const spent = typeof row?.cost_usd === 'number' ? row.cost_usd : null;
  // `cap === 0` divided to NaN and produced `width: NaN%` — no bar at all. ⚠ The first fix sent that
  // case to 0 instead, which swapped a missing bar for a LIE: `$5.00 of $0.00` beside an EMPTY meter,
  // reading as "nothing spent" in the kill-switch-adjacent case where the meter matters most
  // (`code-reviewer`, third pass). A zero cap with any spend at all is 100% over, not 0%.
  const pct = spent === null || cap === null
    ? 0
    : cap <= 0
      ? (spent > 0 ? 100 : 0)
      : Math.min(100, Math.round((spent / cap) * 100));

  /**
   * `bot_metrics.updated_at` is UTC (`docs/DATA-MODEL.md`). It was printed raw and UNLABELLED while
   * every other clock on this board is in the shop's timezone — `booking-integrity.md` says store in
   * UTC, display in the configured timezone (`code-reviewer` #5, 2026-09-12).
   */
  const updatedAt = (iso: string | undefined): string => {
    const t = Date.parse(iso ?? '');
    if (!Number.isFinite(t)) return '—';
    return new Date(t).toLocaleString('en-GB', {
      timeZone: timezone, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
      // The zone is NAMED, not just applied: the comment above says the value was "raw and
      // UNLABELLED", and converting it without saying which clock it is would leave half of that true.
      timeZoneName: 'short',
    });
  };

  return (
    <section className="panel" aria-labelledby="health-h">
      <h2 id="health-h">System</h2>

      <div className="kpi-grid">
        <div className="kpi">
          <span className="tech">LLM spend, this period</span>
          {spent === null ? (
            /* Not "$0.00". No row for this period means nothing has been recorded, and a zero would
               claim a measurement that was never taken. */
            <strong>not recorded yet</strong>
          ) : (
            <>
              {/* No denominator is invented when the config carries no cap — the number shown is the
                  one that was measured, and nothing else. */}
              <strong>${spent.toFixed(2)}{cap === null ? '' : ` of $${cap.toFixed(2)}`}</strong>
              {/* A7: the mockup styles `.meter i`, not `.meter span`. With a <span> the bar never drew
                  at all — an empty pill that read as "no spend". */}
              {cap !== null && <div className="meter"><i style={{ width: `${pct}%` }} /></div>}
              <span className="tech">period {row?.period_key ?? '—'} · updated {updatedAt(row?.updated_at)}</span>
            </>
          )}
        </div>

        <div className="kpi">
          <span className="tech">Recent errors</span>
          {/* D16 — the hole, named. */}
          <strong>no source</strong>
          <span className="tech">
            The bot&rsquo;s execution log lives inside n8n and cannot be queried from here. This card is
            empty because there is nothing to read, not because nothing went wrong.
          </span>
        </div>

        <div className="kpi">
          <span className="tech">Safety switches</span>
          <strong>not readable</strong>
          <span className="tech">
            Kill-switch, dry-run and the alert toggle are literals inside the engine&rsquo;s config node.
            Showing them from a copy here would drift the first time one is changed.
          </span>
        </div>
      </div>
    </section>
  );
}
