// L7 · FOOTER — demo notice: STATIC, shown only on a DEMO build (honesty-demos.md) · brand: CONFIG
// business.name · place: DERIVED from CONFIG faq.address (§1 L7). If the derivation cannot find a
// clean address the brand stands alone — never a mangled fragment on a public page.
import { config, isDemo, shortAddress } from '../../lib/config';

export function SiteFooter() {
  const place = shortAddress();
  return (
    <footer className="site-footer">
      <div className="wrap footer-row">
        {isDemo && <span>DEMO — mock data, no real customer information.</span>}
        <span>{config.business.name}{place ? ` · ${place}` : ''}</span>
      </div>
    </footer>
  );
}
