// L5 · HOURS & PLACE — hours: CONFIG workingHours (grouped from the data, see lib/config.ts) ·
// address: CONFIG faq.address, FULL SENTENCE verbatim (K7/BULGU-5 — never split into street/city) ·
// parking: CONFIG faq.parking (this is the first surface to use it, sanctioned by §1).
import { config } from '../../lib/config';
import { hoursRows, directionsUrl } from '../../lib/config';

export function HoursPlace() {
  const rows = hoursRows();
  return (
    <section className="hours" id="hours">
      <div className="wrap">
        <p className="eyebrow">Hours &amp; place</p>
        <div className="hours-grid">
          {rows.map((r) => (
            <div className="hours-cell" key={r.label}>
              <h3 className="hours-label">{r.label}</h3>
              <p className={r.closed ? 'hours-value closed' : 'hours-value'}>{r.value}</p>
            </div>
          ))}
        </div>
        {(config.faq?.address || config.faq?.parking) && (
          <div className="place">
            <h3 className="place-label">Find us</h3>
            {config.faq?.address && <p className="place-value">{config.faq.address}</p>}
            {config.faq?.parking && <p className="place-note">{config.faq.parking}</p>}
            {directionsUrl() && (
              <a className="btn btn-ghost place-directions" href={directionsUrl()!} target="_blank" rel="noopener noreferrer">
                Get directions
              </a>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
