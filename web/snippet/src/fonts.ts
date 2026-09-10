/**
 * Fonts — the ONE deliberate hole in the isolation contract, and it is named rather than hidden.
 *
 * WHY A HOLE AT ALL: `@font-face` is ignored inside a shadow root. The rules must sit in the host
 * DOCUMENT for the faces to resolve, so this module writes a <style> element into `document.head`.
 * That is the widget touching the page it promised not to touch. It is one element, it is idempotent,
 * and it declares nothing but two font families — but "the widget cannot leak out" is only true with
 * this exception written down (ARCH-DEC §5, 2026-09-09).
 *
 * WHY THE NAMES ARE NAMESPACED: a document-level `@font-face{font-family:'Fraunces'}` would REDEFINE
 * that family for the whole host page. If the client's own site already uses Fraunces — plausible, it
 * is a popular free face — our file would silently replace theirs, in their headings, on their pages.
 * `BarberWidget Fraunces` cannot collide with anything.
 *
 * WHY SELF-HOSTED: the mockup pulled these from fonts.googleapis.com. Shipping that would put a third
 * party in front of every visitor of every client we sell to, on an EU-framed product — the same class
 * of dependency 6a removed from the site (GSAP, the fonts). Licence checked before deciding, not after:
 * Fraunces and Instrument Sans are both SIL OFL-1.1 with NO Reserved Font Name, and the licence grants
 * embedding and redistribution explicitly; `web/site/public/fonts/OFL.txt` ships the notice the licence
 * requires. (Read from each project's OFL.txt via the GitHub licence API, 2026-09-09.)
 *
 * FAILURE IS COSMETIC, BY DESIGN: every family below ends in a real fallback. If the font files 404 —
 * a client copies the snippet tag but blocks our origin, say — the widget renders in a serif and a
 * system sans instead of disappearing. A blocked font must never take the chat down.
 *
 * TWO INJECTIONS, NOT ONE — and the split is about whose bandwidth pays.
 *   · Instrument Sans (88 kB) is the UI: every bubble, the composer, the launcher. Injected at mount.
 *   · Fraunces (205 kB) draws exactly TWO strings — the shop name in the panel header and the avatar
 *     initials. That is 13× the whole widget bundle (16 kB) for two strings, paid for by the CLIENT's
 *     site, for something their visitor did not ask for. But the widget starts CLOSED: until someone
 *     opens the panel, nobody can see either string. So Fraunces is injected on FIRST PANEL OPEN.
 *     A visitor who never engages pays ZERO, and the locked typography is not altered in any way.
 *   Accepted cost: one face swap on that first open, fallback → Fraunces. Measured, see ROADMAP §6b.
 */

/** Namespaced families + honest fallbacks. Used by styles.ts inside the shadow root. */
export const FONT_DISPLAY = `'BarberWidget Fraunces',Georgia,'Times New Roman',serif`;
export const FONT_UI = `'BarberWidget Sans',system-ui,-apple-system,'Segoe UI',sans-serif`;

const UI_MARKER = 'data-barber-widget-font-ui';
const DISPLAY_MARKER = 'data-barber-widget-font-display';

/**
 * Where this script was served from. The snippet is loaded cross-origin by design (the client's page is
 * not our origin), so font URLs must be ABSOLUTE against our own host, never relative to the host page.
 */
export function ownOrigin(scriptSrc: string | null): string | null {
  if (!scriptSrc) return null;
  try { return new URL(scriptSrc, location.href).origin; } catch { return null; }
}

/** Variable fonts: one file each, weight ranges rather than a file per weight. */
function faceRule(origin: string, family: string, file: string, weights: string): string {
  return `@font-face{font-family:'${family}';src:url('${origin}/fonts/${file}') format('woff2');`
    + `font-weight:${weights};font-style:normal;font-display:swap}`;
}

function inject(marker: string, css: string): void {
  if (document.querySelector(`style[${marker}]`)) return;   // idempotent: two script tags, one <style>
  const style = document.createElement('style');
  style.setAttribute(marker, '');
  style.textContent = css;
  document.head.appendChild(style);
}

/** The UI face — needed the moment the launcher renders. */
export function injectUiFont(origin: string | null): void {
  if (!origin) return;                                     // no origin → keep the fallbacks
  inject(UI_MARKER, faceRule(origin, 'BarberWidget Sans', 'instrument-sans-variable.woff2', '400 600'));
}

/** The display face — deferred until the panel is opened for the first time. See the header note. */
export function injectDisplayFont(origin: string | null): void {
  if (!origin) return;
  inject(DISPLAY_MARKER, faceRule(origin, 'BarberWidget Fraunces', 'fraunces-variable.woff2', '400 700'));
}
