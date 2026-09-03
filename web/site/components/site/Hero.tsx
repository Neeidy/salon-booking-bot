// L2 · HERO — headline/sub/eyebrow: STATIC · chat content: the SAME engine literals as the widget
// (locked in Tur A). The conversation is MOCK demo data; the bot lines are engine-verbatim:
//   W12 · literal in `Compute Availability`  ·  W13 · messageTemplates.bookingConfirmed
// Do not invent bot copy here — that was BULGU-4 and it is what this transcription protects against.
import { config } from '../../lib/config';

export function Hero() {
  const initials = config.business.name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
  return (
    <section className="hero">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <p className="eyebrow">Premium barbershop — book by text</p>
          <h1 className="hero-title">
            <span className="line"><span className="line-inner ha">Sit back.</span></span>
            <span className="line line-accent"><em className="line-inner ha" data-text="We'll handle">We&apos;ll handle</em></span>
            <span className="line"><span className="line-inner ha">the rest<span className="dot">.</span></span></span>
          </h1>
          <svg className="razor razor-hero" width="330" height="26" viewBox="0 0 330 26" fill="none" aria-hidden="true">
            <path className="ha" d="M4 17 C 60 7, 120 23, 178 13 C 226 5, 282 19, 326 12" stroke="#B4472E" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
          <p className="hero-sub">Book by one text message — open slots arrive in the reply, confirmed in seconds.</p>
          <div className="hero-ctas">
            <a className="btn btn-ink" data-secta href="#chat">Book by text</a>
            <a className="btn btn-ghost" href="#menu">See the menu</a>
          </div>
        </div>

        <div className="chat-window" id="chat" aria-label="Sample booking conversation">
          <div className="chat-head">
            <span className="chat-avatar" aria-hidden="true">{initials}</span>
            <div className="chat-id">
              <strong className="chat-name">{config.business.name}</strong>
              <span className="chat-status"><span className="online-dot" />online — instant replies</span>
            </div>
          </div>
          <div className="chat-body" role="log" aria-live="polite">
            <div className="msg user" data-step="1">Can I get a haircut Friday at 15:30?<span className="stamp">14:02</span></div>
            <div className="pair">
              <div className="typing" data-typing="2" aria-hidden="true"><i /><i /><i /></div>
              <div className="msg bot" data-step="3">Haircut, Friday 4 Sep 15:30 — shall I book it? (yes / no)
                <span className="slots">
                  <span className="chip chip-on">yes</span>
                  <span className="chip">no</span>
                </span>
                <span className="stamp">14:02</span>
              </div>
            </div>
            <div className="msg user" data-step="4">yes<span className="stamp">14:03</span></div>
            <div className="pair">
              <div className="typing" data-typing="5" aria-hidden="true"><i /><i /><i /></div>
              <div className="msg bot confirm" data-step="6"><strong>✓</strong> You&apos;re booked: Haircut, Friday 4 Sep 15:30. See you then!<span className="stamp">14:03</span></div>
            </div>
          </div>
          <div className="chat-foot" aria-hidden="true">
            <span className="chat-input">Type a message…</span>
            <span className="chat-send">↑</span>
          </div>
        </div>
      </div>
    </section>
  );
}
