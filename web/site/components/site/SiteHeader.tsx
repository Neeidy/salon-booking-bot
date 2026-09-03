// L1 · STICKY HEADER — brand: CONFIG business.name · nav + CTA label: STATIC (SCREEN-INVENTORY §1 L1)
import { config } from '../../lib/config';

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="wrap header-row">
        <span className="brand">{config.business.name}</span>
        <nav className="site-nav" aria-label="Sections">
          <a className="nav-link" href="#menu">The menu</a>
          <a className="nav-link" href="#hours">Hours</a>
        </nav>
        <a className="btn btn-ink header-cta" href="#chat">Book by text</a>
      </div>
    </header>
  );
}
