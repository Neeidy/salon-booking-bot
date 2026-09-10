/**
 * Next config — exists for exactly one reason: the embeddable snippet's fonts are fetched CROSS-ORIGIN.
 *
 * MEASURED on the snippet's first real load (2026-09-09), on a hostile host page served from a different
 * port to this app:
 *
 *   Access to font at 'http://localhost:3001/fonts/instrument-sans-variable.woff2'
 *   from origin 'http://localhost:8788' has been blocked by CORS policy:
 *   No 'Access-Control-Allow-Origin' header is present on the requested resource.
 *
 * A `<script src>` is not CORS-restricted, so the widget itself loaded fine — but a font fetched by
 * `@font-face` ALWAYS uses CORS mode, whatever the origin. Without this header the snippet silently
 * renders in its fallback stack on EVERY client site, which is the entire product. A same-origin test
 * could never have shown it: the site's own pages fetch these fonts from their own origin and pass.
 *
 * `*` is correct here and not a loosening: these are public, licence-permitted static font files with no
 * credentials attached. There is nothing to protect and no cookie to leak.
 *
 * NOT added: a CORS header on barber-widget.js itself. Measured — a classic `<script src>` does not need
 * one, and it loaded cross-origin without complaint. It WOULD be needed if the install page ever
 * recommends Subresource Integrity, since `integrity` + `crossorigin` turns the script fetch into a CORS
 * request; that is a decision the install page has not made, so the header is not added on speculation.
 *
 * Per docs/ (this Next version's own reference): "Headers are checked before the filesystem which
 * includes pages and /public files."
 */
const nextConfig = {
  async headers() {
    return [
      {
        source: '/fonts/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
          // A year, but NOT `immutable`. The filenames are stable (`fraunces-variable.woff2`), not
          // content-addressed, so there is no cache-bust if a face is ever replaced — and `immutable`
          // tells the browser never to revalidate, which would strand a returning visitor on the old file
          // for up to a year. Long max-age is right for a font; claiming immutability of a mutable path
          // is not (security-auditor, 2026-09-10). Add a content hash to the filename before adding it back.
          { key: 'Cache-Control', value: 'public, max-age=31536000' },
        ],
      },
    ];
  },
};

export default nextConfig;
