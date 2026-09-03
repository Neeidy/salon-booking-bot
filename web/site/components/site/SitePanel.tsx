// THE WIDGET PANEL — the Tur A interior embedded in the site (Stage 2), closed on load; the L8 pill
// is its launcher. TRANSCRIBED VERBATIM from design/mockups/site/index.html (§1) — class names and
// data-* hooks included, because the motion engine binds to them (`[data-close]`, `data-step`,
// `data-typing`, `.thread`). Getting these wrong is not cosmetic: it threw inside the engine and
// React unmounted the whole page.
//
// The conversation is MOCK demo data; every BOT line is engine-verbatim and labelled with its source:
//   W61 frontend welcome (K4) · W10 messageTemplates.askService · W11 messageTemplates.askDateTime
//   W12 literal in `Compute Availability` · W13 messageTemplates.bookingConfirmed
// Making this panel LIVE (real endpoint, Turnstile, the 65 W-states) is slice 2 — not done here.
import { config } from '../../lib/config';

export function SitePanel() {
  const name = config.business.name;
  const initials = name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
  const serviceList = config.services.map((s) => s.name).join(' / ');
  return (
    <section className="site-panel" id="site-panel" role="dialog" aria-label={`Book by text — ${name}`}>
      <div className="panel-head">
        <span className="panel-avatar" aria-hidden="true">{initials}</span>
        <div className="panel-id">
          <strong className="panel-name">{name}</strong>
          <span className="panel-status"><span className="online-dot" />online — instant replies</span>
        </div>
        <button className="panel-close" type="button" data-close aria-label="Close chat">×</button>
      </div>
      <div className="thread" role="log" aria-live="polite">
        {/* W61 · FRONTEND-ONLY welcome (K4) — the engine produces no greeting; business.name from config */}
        <div className="msg bot" data-step="0">Hi! I&apos;m the {name} assistant — I can book, change or cancel an appointment, or answer questions. How can I help?<span className="stamp">14:00</span></div>
        <div className="msg user" data-step="1">Hi — do you have anything Friday afternoon?<span className="stamp">14:00</span></div>
        {/* W10 · messageTemplates.askService · node: Slot Gate. Chips from config services[]. */}
        <div className="pair">
          <div className="typing" data-typing="2" aria-hidden="true"><i /><i /><i /></div>
          <div className="msg bot" data-step="2">Which service would you like? ({serviceList})
            <span className="slots">
              {config.services.map((s, i) => (
                <span className={i === 0 ? 'chip chip-on' : 'chip'} key={s.id}>{s.name} · €{s.priceEUR}</span>
              ))}
            </span>
            <span className="stamp">14:00</span>
          </div>
        </div>
        <div className="msg user" data-step="3">Haircut<span className="stamp">14:01</span></div>
        {/* W11 · messageTemplates.askDateTime · node: Slot Gate */}
        <div className="pair">
          <div className="typing" data-typing="4" aria-hidden="true"><i /><i /><i /></div>
          <div className="msg bot" data-step="4">What day and time works for you?<span className="stamp">14:01</span></div>
        </div>
        <div className="msg user" data-step="5">Friday at 15:30<span className="stamp">14:02</span></div>
        {/* W12 · literal in `Compute Availability` */}
        <div className="pair">
          <div className="typing" data-typing="6" aria-hidden="true"><i /><i /><i /></div>
          <div className="msg bot" data-step="6">Haircut, Friday 4 Sep 15:30 — shall I book it? (yes / no)
            <span className="slots">
              <span className="chip chip-on">yes</span>
              <span className="chip">no</span>
            </span>
            <span className="stamp">14:02</span>
          </div>
        </div>
        <div className="msg user" data-step="7">yes<span className="stamp">14:02</span></div>
        {/* W13 · messageTemplates.bookingConfirmed · node: Build Booked State */}
        <div className="pair">
          <div className="typing" data-typing="8" aria-hidden="true"><i /><i /><i /></div>
          <div className="msg bot confirm" data-step="8"><strong>✓</strong> You&apos;re booked: Haircut, Friday 4 Sep 15:30. See you then!<span className="stamp">14:03</span></div>
        </div>
      </div>
      <div className="panel-foot" aria-hidden="true">
        <span className="panel-input">Type a message…</span>
        <span className="panel-send">↑</span>
      </div>
    </section>
  );
}
