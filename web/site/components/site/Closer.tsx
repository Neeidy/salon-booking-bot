// L6 · INK BLOCK — CLOSER: copy from config.site + razor motif (§1 L6).
import { config } from '../../lib/config';

export function Closer() {
  const site = config.site!;
  return (
    <section className="ink-block closer" data-ride>
      <div className="wrap closer-row">
        <div>
          <h2 className="closer-title">{site.closerTitle[0]}<br />{site.closerTitle[1]}<span className="dot">.</span></h2>
          <svg className="razor razor-closer" width="330" height="26" viewBox="0 0 330 26" fill="none" aria-hidden="true">
            <path d="M4 17 C 60 7, 120 23, 178 13 C 226 5, 282 19, 326 12" stroke="#B4472E" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
        </div>
        <a className="btn btn-cream" data-secta href="#chat">Reserve your chair</a>
      </div>
    </section>
  );
}
