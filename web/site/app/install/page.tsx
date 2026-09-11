/**
 * /install — the page a CLIENT reads to put the widget on their own site.
 *
 * Ported from design/mockups/snippet/index.html (design round, 2026-09-02). Two deliberate differences:
 *
 * 1. THE EMBED ADDRESS IS STILL A VISIBLY MARKED PLACEHOLDER. There is no deployment yet (Phase 6
 *    decision D-6b-7: 6b is verified locally against the LIVE engine, and the public release is gated on
 *    6d). Inventing a plausible CDN address would be a fabricated fact on a page whose entire job is to
 *    be copied verbatim.
 * 2. No copy-to-clipboard button. The mockup had one behind a progressive-enhancement gate; here it
 *    would mean turning this into a client component for a convenience, and the string is three lines
 *    long. Fewer moving parts on a page a stranger reads once.
 *
 * Styles are local to this page on purpose: `app/globals.css` is a verbatim transcription of an approved
 * mockup and is a locked visual contract. A new route does not get to edit it.
 */
import { config } from '../../lib/config';

export const metadata = {
  title: 'Widget install — Demo Barber Co.',
  robots: { index: false, follow: false },   // an install doc is not a search result
};

const STYLES = `
.iw{--cream:#F1EEE6;--ink:#16150F;--oxide:#B4472E;--muted:#5C594E;--rule:rgba(22,21,15,.18);
--edge:rgba(22,21,15,.25);background:var(--cream);color:var(--ink);min-height:100vh;
font-family:var(--font-instrument,system-ui),system-ui,sans-serif;font-size:16px;line-height:1.6}
.iw .wrap{max-width:820px;margin:0 auto;padding:clamp(36px,6vw,72px) clamp(20px,4vw,48px) 96px}
.iw .eyebrow{font-size:12px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--oxide)}
.iw h1{font-family:var(--font-fraunces,Georgia),Georgia,serif;font-weight:600;
font-size:clamp(34px,5.5vw,56px);line-height:1.04;letter-spacing:-.015em;margin:10px 0 0}
.iw .lede{color:var(--muted);max-width:60ch;margin-top:14px}
.iw h2{font-family:var(--font-fraunces,Georgia),Georgia,serif;font-weight:600;font-size:24px;
letter-spacing:-.01em;margin:44px 0 12px;padding-top:18px;border-top:1px solid var(--rule)}
.iw p{margin:0 0 12px;max-width:64ch}
.iw ul{margin:0 0 12px 20px;max-width:64ch}
.iw li{margin:6px 0}
.iw pre{background:#fff;border:1.5px solid var(--ink);border-radius:6px;padding:16px 18px;
overflow-x:auto;margin:6px 0 10px}
.iw code{font-family:ui-monospace,'SF Mono',Menlo,monospace;font-size:13.5px}
.iw .ph{background:rgba(180,71,46,.14);color:var(--oxide);font-weight:700;padding:1px 5px;border-radius:3px}
.iw .note{border-left:3px solid var(--oxide);padding:2px 0 2px 16px;margin:14px 0;color:var(--muted)}
.iw .dot{color:var(--oxide)}
`;

export default function InstallPage() {
  const shop = config.business.name;
  return (
    <div className="iw">
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />
      <div className="wrap">
        <p className="eyebrow">Widget install</p>
        <h1>One line on your site<span className="dot">.</span></h1>
        <p className="lede">
          The booking assistant runs as a single script. It draws inside its own isolated container, and
          everything else it puts on your page is listed below — completely, not as a summary.
        </p>

        <h2>The line</h2>
        <pre><code>{'<script src="https://'}<span className="ph">[WIDGET-URL]</span>{'/barber-widget.js" defer></script>'}</code></pre>
        <p>
          Paste it once, just before <code>&lt;/body&gt;</code>. <strong className="ph">[WIDGET-URL]</strong>{' '}
          is your install address — it is issued with your account and is not shown here, because this page
          is a template and a made-up address would be worse than an obvious gap.
        </p>

        <h2>What it does to your page</h2>
        <ul>
          <li>Adds <strong>one element</strong> to your page, a container for the chat panel. Everything the
              widget draws lives inside it, isolated with Shadow DOM: your page&apos;s styles cannot reach in,
              and the widget&apos;s cannot leak out.</li>
          <li>Adds <strong>up to two stylesheets</strong> to <code>&lt;head&gt;</code>, declaring one font face
              each — the second only if a visitor actually opens the panel. Web fonts cannot be declared inside
              an isolated component, so these cannot live with the rest. Both are named so they can never
              replace a font your own site uses.</li>
          <li>Loads <strong>one script from Cloudflare</strong> (<code>challenges.cloudflare.com</code>), which
              is the bot check described below. It is the only third-party code involved.</li>
          <li>Stores <strong>one key in <code>sessionStorage</code></strong> &mdash; the conversation id, so the
              assistant still knows who it is talking to after a visitor moves to another page in the same tab.
              Not a cookie, not an identifier that follows anyone between sites, and gone when the tab closes.
              <em>The visible transcript is not stored:</em> after a page change the panel opens fresh, even
              though the conversation itself continues.</li>
          <li>Defines <strong>one global variable</strong> on the page (plus one that Cloudflare&apos;s own
              script defines), used to avoid loading the bot check twice.</li>
          <li>Listens for the <kbd>Esc</kbd> key while the panel is open, so a visitor can close it. The key
              still reaches your page exactly as it did before.</li>
          <li>That is the whole list. No cookies of ours, no analytics, and it never reads your page&apos;s
              content.</li>
        </ul>

        <h2>Privacy — one thing you must add</h2>
        <p>
          The widget uses <strong>Cloudflare Turnstile</strong> to keep automated traffic away from your
          booking line. Cloudflare requires that sites using it reference the{' '}
          <a href="https://www.cloudflare.com/application-services/products/turnstile/" rel="noreferrer">
            Turnstile Privacy Addendum
          </a>{' '}
          in their own privacy policy. This is a condition of use, not a suggestion — please add it to yours
          before going live.
        </p>

        <h2>Known limits, stated plainly</h2>
        <ul>
          <li><strong>JavaScript disabled:</strong> the widget does not appear at all. Your page is untouched —
              no gap, no broken layout. A script cannot render without scripting.</li>
          <li><strong>A <code>transform</code> or <code>filter</code> on your <code>&lt;body&gt;</code></strong>{' '}
              changes how fixed positioning works in every browser, which moves the launcher. This affects every
              floating widget, not only this one. If your theme does that, tell us and we will place it differently.</li>
          <li><strong>A strict Content-Security-Policy</strong> on your site will block the script until you allow
              our origin and <code>challenges.cloudflare.com</code>.</li>
          <li><strong>Your own CSS can still move or hide the container.</strong> The isolation protects what is
              INSIDE the widget; a rule of yours that targets the container element itself still applies to it,
              by design of the web platform. That is a way to reposition it deliberately — and a thing to check
              if it ever looks misplaced.</li>
          <li><strong>Fonts are served from our origin.</strong> If that is blocked, the widget renders in system
              fonts and keeps working — a blocked font never takes the chat down.</li>
        </ul>

        <h2>What your visitors see</h2>
        <p>
          A launcher in the bottom corner. Opening it starts a conversation with the {shop} assistant, which can
          book, change or cancel an appointment and answer questions about the shop. When it is not sure, it says
          so and hands over to a person rather than guessing.
        </p>

        <div className="note">
          This install page is part of a demo build. The address above is a placeholder until the widget is
          deployed; everything else on this page describes the widget exactly as it behaves today.
        </div>
      </div>
    </div>
  );
}
