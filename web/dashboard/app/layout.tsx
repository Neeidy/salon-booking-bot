import type { Metadata } from 'next';
import { Fraunces, Instrument_Sans } from 'next/font/google';
import './globals.css';

// Same font setup as web/site, and for the same reason: next/font downloads the faces at BUILD time
// and serves them from our own origin, so the running page makes no request to fonts.googleapis.com.
// The mockup this page transcribes used a Google Fonts <link>; that is exactly what is NOT carried
// over. ⚠ It also means no font files of our own: an earlier cut copied web/site/public/fonts into
// web/dashboard/public and created a font surface the provenance guard could not see. The copy was
// removed once the framework turned out to solve it; the guard extension stayed.
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
  title: 'Owner dashboard',
  // This surface renders customer PII and sits behind Cloudflare Access. Nothing about it should ever
  // reach a crawler, and `noindex` is the cheap half of saying so — the real control is Access.
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${instrument.variable}`}>
      <body>{children}</body>
    </html>
  );
}
