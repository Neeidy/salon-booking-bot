// L4 · INK BLOCK — CRAFT: copy from config.site (§1 L4). The bot sells nothing here; the shop speaks —
// which is why craftBody must never mention the assistant.
import { config } from '../../lib/config';

export function Craft() {
  const site = config.site!;
  return (
    <section className="ink-block craft" data-ride>
      <div className="wrap-narrow">
        <p className="eyebrow">The craft</p>
        <h2 className="craft-title">{site.craftTitle[0]}<br /><em>{site.craftTitle[1]}</em></h2>
        <p className="craft-body">{site.craftBody}</p>
        <a className="btn btn-outline-cream" data-secta href="#chat">Book by text</a>
      </div>
    </section>
  );
}
