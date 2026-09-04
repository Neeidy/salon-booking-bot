// L2 · HERO — copy from config.site (the shop's own voice), chat = four rotating engine-sourced
// scenarios (lib/heroScenarios.ts). The oxide period after the last headline line is MARKUP, not text,
// which is why config.site.headline[2] carries no full stop.
import { config } from '../../lib/config';
import { heroScenarios } from '../../lib/heroScenarios';
import { HeroChat } from './HeroChat';

export function Hero() {
  const site = config.site!;
  return (
    <section className="hero">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <p className="eyebrow">{site.tagline}</p>
          <h1 className="hero-title">
            <span className="line"><span className="line-inner ha">{site.headline[0]}</span></span>
            <span className="line line-accent"><em className="line-inner ha" data-text={site.headline[1]}>{site.headline[1]}</em></span>
            <span className="line"><span className="line-inner ha">{site.headline[2]}<span className="dot">.</span></span></span>
          </h1>
          <svg className="razor razor-hero" width="330" height="26" viewBox="0 0 330 26" fill="none" aria-hidden="true">
            <path className="ha" d="M4 17 C 60 7, 120 23, 178 13 C 226 5, 282 19, 326 12" stroke="#B4472E" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
          <p className="hero-sub">{site.subline}</p>
          <div className="hero-ctas">
            <a className="btn btn-ink" data-secta href="#chat">Book by text</a>
            <a className="btn btn-ghost" href="#menu">See the menu</a>
          </div>
        </div>
        <HeroChat scenarios={heroScenarios(config)} brand={config.business.name} />
      </div>
    </section>
  );
}
