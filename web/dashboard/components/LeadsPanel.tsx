/**
 * D7 · D8 — leads. SERVER component (see app/page.tsx): every field here is PII.
 *
 * The phone is masked to a country prefix and two digits. That is enough to match a row against a
 * message on the owner's own phone and not enough to dial it from a screenshot — which is the threat
 * that actually applies to a back-office screen someone photographs to send a colleague.
 */
import type { Page } from '../lib/airtable.ts';
import type { Lead } from '../lib/types.ts';
import { maskName, maskPhone, assertMasked } from '../lib/mask.ts';

export function LeadsPanel({ page }: { page: Page<Lead> }) {
  return (
    <section className="panel" aria-labelledby="leads-h">
      <div className="q-head">
        <h2 id="leads-h">Leads</h2>
        {page.truncated && <span className="tech">showing the first {page.rows.length} — there are more</span>}
      </div>

      {page.rows.length === 0 ? (
        /* D8 — distinct from D5/D6/D12. Nobody has left their details, which is neither good nor bad. */
        <p className="release">No one has left their details in this window.</p>
      ) : (
        <ul className="q-msgs">
          {page.rows.map((r) => (
            <li key={r.id} className="row">
              <strong>{assertMasked(maskName(r.name), 'lead name')}</strong>
              <span>{assertMasked(maskPhone(r.phone), 'lead phone')}</span>
              <span className="sw">{r.status ?? 'new'}</span>
              <span className="tech">{r.source ?? '—'}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
