// L8 · FLOATING PILL (widget launcher; yields while a section CTA is on screen) · L9 · INTRO CURTAIN
// (once per session, click-to-skip, absent under reduced-motion) · grain + ink canvas overlays.
// All STATIC behaviour, driven by the transcribed motion engine.
export function SiteChrome() {
  return (
    <>
      <button className="fab" type="button" id="widget-launcher" aria-expanded="false" aria-controls="site-panel">
        <span className="online-dot" /><span>Book by text</span>
      </button>
      <div className="grain" aria-hidden="true" />
      <canvas className="ink-canvas" aria-hidden="true" />
      <div className="intro" role="presentation" aria-hidden="true">
        <div className="intro-half top" />
        <div className="intro-half bottom" />
        <svg className="intro-razor" viewBox="0 0 1000 26" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 16 C 200 6, 380 24, 560 12 C 720 2, 880 20, 1000 10" pathLength="100" stroke="#B4472E" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </svg>
      </div>
    </>
  );
}
