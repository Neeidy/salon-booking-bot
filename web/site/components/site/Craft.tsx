// L4 · INK BLOCK — CRAFT: STATIC copy (§1 L4). The bot sells nothing here; the shop speaks.
export function Craft() {
  return (
    <section className="ink-block craft" data-ride>
      <div className="wrap-narrow">
        <p className="eyebrow">The craft</p>
        <h2 className="craft-title">Hot towel. Straight razor.<br /><em>A chair that runs on time.</em></h2>
        <p className="craft-body">The assistant keeps the book tight — every cut gets its full time, and your chair is ready the minute you walk in.</p>
        <a className="btn btn-outline-cream" data-secta href="#chat">Book by text</a>
      </div>
    </section>
  );
}
