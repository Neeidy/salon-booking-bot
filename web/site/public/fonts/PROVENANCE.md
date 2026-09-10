# Font provenance

Not "we looked inside the file and it seemed fine" — a woff2's bytes tell you nothing useful. What is
recorded here is WHERE each file came from, PINNED so the answer cannot drift, and a checksum so the
copy in this repo can be shown to be that file and not another.

Both files are the UPRIGHT VARIABLE face, taken from each project's own repository (the authors'
distribution channel), at a pinned commit — never from a CDN and never from `HEAD`, which moves.

## Fraunces
- source: https://github.com/undercasetype/Fraunces
- path:   fonts/webfonts/variable/Fraunces[SOFT,WONK,opsz,wght].woff2
- commit: 7ccdec31c6028118dce3e47fe864e3744460371d (2025-10-21)
- stored: fraunces-variable.woff2
- size:   205500 bytes (matches the size GitHub's tree API reports for that blob)
- sha256: e6638ea113d0027354a08f957a4068975c8066395a0d0f7bb7861f6409621be3
- licence: SIL OFL-1.1, no Reserved Font Name (read from the project's OFL.txt via the GitHub licence API)

## Instrument Sans
- source: https://github.com/Instrument/instrument-sans
- path:   fonts/webfonts/InstrumentSans[wdth,wght].woff2
- commit: 7fa22308a3d0c94ee2b3cd537a1196b65db34a3e (2023-06-14)
- stored: instrument-sans-variable.woff2
- size:   88784 bytes (matches the size GitHub's tree API reports for that blob)
- sha256: aa72922aafcc0dc18f36ec1d805b0212057dabe8b9d5b8b57f67035aea1b826d
- licence: SIL OFL-1.1, no Reserved Font Name

## Re-verify
    sha256sum web/site/public/fonts/*.woff2

## Why self-hosted at all
The design mockup pulled both from fonts.googleapis.com. Shipping that would put a third party in
front of every visitor of every client this template is sold to, on an EU-framed product — the same
dependency class 6a removed from the site. Self-hosting also makes the licence obligation concrete:
the notice ships with the files (OFL.txt, beside this one).

## Open cost question (raised, not decided)
Fraunces is 205 kB and the widget uses it for exactly two strings: the shop name in the panel header
and the avatar initials. The snippet's own bundle is 16 kB. On someone else's website that ratio
deserves a deliberate answer rather than a default — see ROADMAP §6b.
