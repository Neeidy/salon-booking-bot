import type { Metadata } from 'next';
import { Fraunces, Instrument_Sans } from 'next/font/google';
import './globals.css';
import { config, isDemo } from '../lib/config';

// SELF-HOSTED fonts. next/font downloads the files at BUILD time and serves them from our own
// origin — no runtime request to fonts.googleapis.com / fonts.gstatic.com. Same class of fix as the
// GSAP self-host: a public demo page must not depend on, or leak visitor IPs to, a third party.
// Not Vercel-specific; this works on any Next deployment.
// Fraunces is a VARIABLE font: weight and opsz are axes, so no fixed weight list may be given
// (Next rejects that combination). This matches the mockup's own request, which asked for the
// variable ranges opsz 9..144 and wght 400..700 in both styles.
const fraunces = Fraunces({
  subsets: ['latin'],
  axes: ['opsz'],
  style: ['normal', 'italic'],
  display: 'swap',
  variable: '--font-fraunces',
});
const instrument = Instrument_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
  variable: '--font-instrument',
});

export const metadata: Metadata = {
  title: `${config.business.name} — Book by text`,
  description: 'Book by one text message — open slots arrive in the reply, confirmed in seconds.',
  // A demo must not be indexed as if it were a real shop.
  robots: isDemo ? { index: false, follow: false } : undefined,
};

// Progressive-enhancement gate, transcribed from the mockup: the hide-before-reveal rules exist only
// under html.js, and the intro curtain must be decided BEFORE first paint or the hero flashes.
const PRE_PAINT = `document.documentElement.classList.add('js');
try {
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches &&
      !sessionStorage.getItem('ci_intro_seen')) {
    sessionStorage.setItem('ci_intro_seen', '1');
    document.documentElement.classList.add('intro-play');
  }
} catch (e) { /* storage blocked -> no intro, page stays fully usable */ }`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${instrument.variable}`}>
      <head><script dangerouslySetInnerHTML={{ __html: PRE_PAINT }} /></head>
      <body>{children}</body>
    </html>
  );
}
