# Every cross-origin request the snippet makes

**Why this file exists.** The snippet is ALWAYS loaded cross-origin — that is the product. On its first
real load, the fonts turned out to be blocked by CORS and the widget silently fell back to system faces
on what would have been every client site. A same-origin test could never have shown it.

`@font-face` is not the only sub-resource fetched in CORS mode, so the fix is not "add a header to the
fonts" — it is this list. **Anything added to the snippet that touches the network gets a row here, with
its request mode and whether the other end sends the header that mode needs.** Checked on the first
cross-origin browser load of any change that adds one.

Compiled two ways and cross-checked: statically from the source (every `fetch`, `.src =`, `url()`,
`@import`, `<img>`, `<iframe>`), and dynamically from `performance.getEntriesByType('resource')` on a
real load from a foreign origin.

| # | Request | Initiated by | Request mode | Needs `Access-Control-Allow-Origin`? | Status |
|---|---|---|---|---|---|
| 1 | `<our origin>/barber-widget.js` | `<script src>` on the client's page | **not CORS** — a classic script is exempt | no | ✅ loads. *No header added, deliberately: adding one on speculation would be a claim we never tested.* |
| 2 | `<our origin>/fonts/instrument-sans-variable.woff2` | `@font-face src:url()` | **CORS, always** — a font fetch is CORS-mode regardless of origin | **yes** | ✅ served `ACAO: *` by `web/site/next.config.mjs`. **Was BLOCKED before that; this is the defect this file exists for.** |
| 3 | `<our origin>/fonts/fraunces-variable.woff2` | `@font-face src:url()`, injected on first panel open | **CORS, always** | **yes** | ✅ same header, same config entry |
| 4 | `challenges.cloudflare.com/turnstile/v0/api.js` | `<script src>` we append to `document.head` | **not CORS** — classic script | no | ✅ loads. Third party by necessity: a challenge service must run its own script. |
| 5 | `challenges.cloudflare.com/cdn-cgi/challenge-platform/…` | Turnstile's own iframe, not us | Cloudflare's business | n/a | ✅ observed; we neither request nor control it |
| 6 | `<engine>/webhook/barber-inbound` — the message POST | `fetch()` in `@salon/shared/chat` | **CORS** | **yes** | ✅ measured 2026-09-02 and re-measured 2026-09-09: preflight `OPTIONS` → 204, `ACAO` reflects the requesting origin, and the real POST carries it too. No proxy needed. |
| 7 | same URL — the self-diagnosis probe | `fetch(…, {mode:'no-cors'})` after a failed send | **no-cors**, opaque by design | no | ✅ works without a header; that is the point — it distinguishes "reached the server" from "never left the browser". Its engine-side behaviour is a separate open item (`tests/regression-suite.md`, T2e). |

## Reading the measurement
On a foreign origin every row above reports `transferSize: 0` in the Resource Timing API. That is **not**
a blocked request: without `Timing-Allow-Origin` the browser hides sizes cross-origin. Judge success by
whether the resource actually took effect — a font by `document.fonts.check()` plus a rendered width
difference against the fallback, a script by its global appearing — never by a size field.

## Not present today (checked, so the absence is a measurement rather than an assumption)
No `<img>`, no `<iframe>` of our own, no `@import`, no `background-image`, no JSON/config fetch — the
config is baked into the bundle at build time. The only `url()` in the stylesheet is the `@font-face` src.
**If any of these appears later, it belongs in the table above before it ships.**
