// L3 · MENU — fully CONFIG-DRIVEN: services[].{name,durationMin,priceEUR}. The mockup hard-coded
// three rows; a client with two or five services now gets two or five without a code change.
import { config } from '../../lib/config';

export function Menu() {
  return (
    <section className="menu" id="menu">
      <div className="wrap-narrow">
        <p className="eyebrow">The menu</p>
        <h2 className="section-title">Prices, plain as print<span className="dot">.</span></h2>
        <ul className="menu-list">
          {config.services.map((s) => (
            <li key={s.id} data-reveal="left">
              <div className="menu-row">
                <span className="menu-name">{s.name}</span>
                <span className="leader" aria-hidden="true" />
                <span className="menu-time">~{s.durationMin} min</span>
                <span className="menu-price">€{s.priceEUR}</span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
