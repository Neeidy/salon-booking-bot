# salon-booking-bot

**A config-driven salon booking chatbot — one message in, a booked appointment or a captured lead out.**

![status](https://img.shields.io/badge/status-learning%20%2F%20demo%20build-orange)
![phase](https://img.shields.io/badge/phase-2%20of%208%20(core%20bot)-blue)
![engine](https://img.shields.io/badge/engine-n8n%20self--hosted-EA4B71)
![llm](https://img.shields.io/badge/LLM-Claude%20Haiku%204.5-8A63D2)
![license](https://img.shields.io/badge/license-MIT-green)

> **Honest status:** this is a **demo / learning build**, not a system serving paying customers.
> Phases 0–1 are done, Phase 2 (the core bot) is nearly complete, Phases 3–8 are not built yet.
> Everything below marked ✅ has been built **and verified from execution logs**; everything marked
> 🔜 is designed and locked but **not shipped**. No invented metrics, no fake traffic.

---

## The one job

A barbershop loses bookings because messages arrive while the owner is cutting hair. This bot answers
instantly, in the shop's voice, and turns each message into one of two outcomes:

**a booked appointment** — or — **a captured lead + a human handoff**

…with **zero owner effort** and **zero double-bookings**. It is a **template**: a new client means a new
config file and new credentials, *not* new code.

---

## How it works

```
                    ┌─────────────── config-gated channels ───────────────┐
   WhatsApp ────────┤                                                     │
   Web widget ──────┤   →  NORMALIZE  →  one channel-agnostic brain       │
   Instagram (off) ─┘      {channel, sender_key, text}                    │
                    └─────────────────────────────────────────────────────┘
                                          │
   ┌──────────────────────────────────────▼──────────────────────────────────────┐
   │  1  Validate payload            invalid → 400                               │
   │  2  Load conversation state     Airtable, keyed by "{channel}:{id}"         │
   │  3  Handoff lock  🔜             a human took over → bot stays quiet         │
   │  4  Guards                      kill-switch · max-turns  → 0 LLM cost       │
   │  5  LLM intent extraction       Claude, structured JSON output              │
   │  6  Validate against schema     ajv compiled from the committed contract    │
   │  7  Confidence & intent gate    < 0.7 or cancel/unknown → human             │
   │  8  Route (deterministic)       book · FAQ · lead · handoff                 │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
        book → collect service/date/time (multi-turn, deterministic)
        FAQ  → answered from config — the LLM never writes the answer
        lead → written to Airtable
                                          │
                              reply returns to the origin channel
```

*Steps marked 🔜 are designed and in progress, not yet shipped.*

**The LLM has exactly one job: understanding.** It converts messy free text into a structured intent.
It never writes a customer-facing answer, never chooses an action, and holds no write permissions.
Prices, hours and services come from config; routing is `IF`/`Switch`. That is why the bot **cannot
quote a wrong price** — the answer path contains no model.

---

## What works today ✅

| Capability | Detail |
|---|---|
| **Multi-channel intake** | WhatsApp + widget shapes normalized to one internal format; channels toggle in config |
| **Conversation memory** | Per-sender state in Airtable (`stage`, slots, turn count) — survives restarts |
| **Intent understanding** | Claude Haiku 4.5, temperature 0, native structured outputs |
| **Contract validation** | Model output validated by an ajv validator **compiled from the committed schema** — no hand-written copy that can drift |
| **Multi-turn booking collect** | "I want a haircut" → "what day and time?" → merged into a complete request |
| **Deterministic FAQ** | Price / hours / services / address answered from config, never from the model |
| **Lead capture** | Non-booking interest written to Airtable with channel + message |
| **Human handoff, 5 distinct classes** | guard-trip (transient) · infrastructure down (503) · genuine handoff (writes state) · clarify (first uncertain turn, no lock) · extraction-transient (our schema broke, owner alerted, no lock) — never merged |
| **Visible failures** | Four separate error responses: `invalid_payload` · `state_unavailable` · `llm_unavailable` · `lead_unavailable` |
| **Spend brakes before the LLM** | Kill-switch and max-turns run *before* any paid call — a tripped guard costs nothing |
| **Embeddable widget, one script tag** | A single self-contained IIFE (well under 20 kB; `npm run build -w @salon/snippet --prefix web` prints the current size — no byte count is pinned in prose here, because one went stale inside a single round) that mounts a booking chat inside a Shadow DOM on someone else's site. Isolation measured in both directions against a deliberately hostile host page — see the case study below, including what it knowingly does not do |

## Designed, locked, not built yet 🔜

The **full safety suite** (cost cap, endpoint rate-limiting, injection hardening) · the **owner dashboard**
(read-only + handoff queue, Phase 6c) · a **config-only second client**.

_(Built since this line was first written: booking write + no-double-book, cancel, reschedule and the
**reminder engine** — Phase 3; WhatsApp **inbound** (HMAC-verified) + **outbound transport** — Phase 4,
dry-run/sandbox-proven. The reminder engine runs end-to-end and is proven in dry-run; **live WhatsApp
template delivery opens with one config flag** once a client's WhatsApp Business number is provisioned —
that number and its message templates are the customer's to supply, per-client onboarding.)_

---

## Engineering decisions worth reading

**Deterministic before AI.** A model is used only where a rule genuinely cannot decide. Asking an LLM
"what does a haircut cost?" is slower, costlier and less reliable than reading one config field.

**The schema is the single source of truth.** The validator inside the flow is *generated* from
`schemas/intent.schema.json` by a script, with a drift check. Two hand-maintained copies of the same
contract always diverge; a generated one cannot.

**Never trust a 200.** Structured output is only guaranteed when the model stops normally, so
`stop_reason` is checked first, enum casing is normalized, and any unexpected shape becomes a handoff
instead of a crash.

**An outage must not look like a handoff.** If the LLM or the database is down the customer still gets a
polite message, but the machine-side response is distinct (`503` + an error flag) so the owner can be
alerted. An outage that looks normal is an outage nobody fixes.

**Availability has one source of truth.** Google Calendar owns free/busy; Airtable mirrors it. Writes go
to the calendar first. Two sources of truth mean double bookings.

**Config / code / secret are separate.** The engine is identical for every client. A new client is a new
`client.config.json` plus new credentials — the workflow does not change.

---

## Case study — the embeddable widget (Phase 6b)

**The problem.** A booking bot is worth nothing if the shop's own website cannot carry it. The promise is
one line — `<script src="…/barber-widget.js" defer></script>` — on a site we do not control, whose CSS we
have never seen, without breaking anything the client already has.

**The approach.** An open Shadow DOM with `:host{all:initial}`: the boundary stops the host's selectors,
`all:initial` cuts the inherited properties selectors cannot reach. Verified in both directions against a
test page built to be hostile on purpose — `content-box!important`, an inherited Georgia at line-height
2.2, colliding `.panel`/`.msg`/`.chip` class names, a `z-index:99999` sticky header, a global
`button{…!important}`, and a leak canary. The page's own elements are byte-identical before and after the
widget mounts.

**What it puts on the host page — the complete list, because "it cannot leak out" is only true with the
exceptions written down.** Two `<style>` elements in `document.head` carrying one `@font-face` each
(`@font-face` is ignored inside a shadow root, so the rules must live in the document; the families are
namespaced — `BarberWidget Fraunces` — because an un-namespaced `@font-face` would silently replace a
client's own Fraunces in their own headings) · Cloudflare's Turnstile script, the single third-party
dependency and the one whose entire purpose is to be third-party · one `document` keydown listener,
attached only while the panel is open, acting on one key, never calling `preventDefault` — the host page's
own Escape handler still fires exactly once · one `window` global guarding a double script load · one
`sessionStorage` key · a one-shot `DOMContentLoaded` listener, added *only* when the tag sits where
`document.body` does not exist yet · and, if the client opted in, the `#barber-widget-fallback` element is
hidden on mount. ⚠ **This list has been wrong twice** — it once claimed a single exception, and it later
omitted the last two items (Codex, CRT #13). A list is only honest when it is complete, and the way it
goes wrong is by being written once and not re-derived.

**And what it READS, because "it never reads your page" was an overclaim too.** It reads its own `<script>`
tag to learn which origin to load fonts from, its own container id, its own injected `<style>` markers, and
the fallback id above. It does **not** read the page's content — no text, no forms, no input values, no
cookies, no storage of the host's. The narrow sentence is the true one.

**The isolation limit, stated rather than implied: Shadow DOM is style encapsulation, not a security
boundary.** The root is open, which is normal and documented browser behaviour — and it means the widget's
content is reachable by *every* script already running on the host page, the client's own analytics
included. Nothing a widget can do from inside the page changes that; the only real answer is a
cross-origin iframe, and that architecture was considered and **deliberately not built in v1** (it is on
the NOT-build list: it costs viewport control, pointer-events and a `postMessage` bridge, and the 6b spike
removed its last justification by proving Turnstile renders and solves inside the shadow root). A client
whose threat model requires isolation from scripts on their own page should not embed this widget — they
need the iframe build. Written here rather than in a footnote, because it is a property of the product.

**Three things the first real load taught us, all of them about honesty rather than code.**
An edge failure the engine never saw was answering in the shop's voice — *"I'm passing you to a team
member"* — when nobody had been told, because the owner-alert lives inside the workflow that never ran;
the transport now speaks as itself. A client-side timeout abandoned the response but not the engine, so
the visitor was told to try again about work that had already succeeded. And a 20 s "still verifying"
watchdog was built, measured, shipped for one round, then **reverted and rebuilt**, because its negative
control had swept only the axis its author happened to think of.

**What it knowingly does not do — named here rather than left for a reader to find.**

| Gap | Status |
|---|---|
| The stuck-verification watchdog is drilled on five axes, but **five more are not swept**: a real Cloudflare site key (the accept direction needs a real human token), a genuinely slow network where Turnstile legitimately needs >20 s, a backgrounded tab where browsers throttle timers, a token arriving at the exact deadline, and two widgets on one page | named in [`tests/snippet/DRILLS.md`](tests/snippet/DRILLS.md) |
| The `Try again` note stays on screen after the token arrives and the composer is usable again — a true sentence that has become stale | open |
| The **site** panel does not read the engine's `locked` flag, so on the site the handoff-lock line repeats on every message; the snippet shows it once | open, Phase 6c |
| The visible transcript is lost when a visitor moves to another page in the same tab. The conversation itself continues — the session id survives — so the engine may be waiting on a confirmation the visitor can no longer see | open, Phase 7 |
| `messageTemplates` has **no required keys** in the committed schema, so a config can pass every gate while missing a message the widget must supply. The snippet's build now fails by name for the two it reads; the schema gap itself is still open | open, Phase 7 |
| An idempotent replay returns no text, so after a client timeout the engine's real answer (*"You're booked: …"*) is unrecoverable. The visitor now gets an honest interim message — **the silence was fixed, the information was not** | open, Phase 7 |
| **The drills are one-off manual measurements, not a regression harness.** Each is recorded against the bundle it was taken on; nothing re-runs on a change. An executable browser harness is not written | open, 6c / Phase 7 |
| Cloudflare's Turnstile script is loaded **without SRI and without a version pin** — Cloudflare does not publish a pinned, integrity-hashed distribution for it, so this is an **accepted supply-chain exception**, not an unsolved task. It is the one third-party script, and its whole purpose is to be third-party | accepted, named |
| `style-src 'none'` / nonce-only CSP and **Trusted Types** are incompatible — the widget injects its stylesheet inline and assigns markup via `innerHTML` inside its own component | known limit, documented on `/install` |
| The double-insert guard keys on one element id; a host page that already uses that id, or a mount that fails part-way, is untested | open, 6c |

**Where a human is still required.** Anything needing a real Turnstile token — a live conversation, a real
booking and its cleanup. Everything else (DOM, CSS, layout, events, isolation, responsive, request
blocking) is drilled headless, and the drill sheet says which is which.

---

## Repo map

| Path | What |
|---|---|
| [`n8n/`](n8n/) | the engine — **sanitized** workflow export only |
| [`schemas/`](schemas/) | JSON Schemas — the intent contract and the client config contract |
| [`prompts/`](prompts/) | versioned LLM prompts (the canonical system prompt) |
| [`scripts/`](scripts/) | validator compiler + drift check · repo map generator |
| [`config/`](config/) | per-client `client.config.json` (mock example committed) |
| [`docs/`](docs/) | architecture decisions · data model · live roadmap · repo map |
| [`design/`](design/) | Phase-1 mockups + flow diagram |
| [`tests/`](tests/) | golden-set intents · jailbreak / injection cases |
| [`web/`](web/) | frontend surfaces — `site/` (Next.js demo), `snippet/` (the embeddable widget), `shared/` (one transport, both front ends) |
| [`.claude/`](.claude/) | the rules this repo is actually built under |

**Stack** — n8n (self-hosted) · Anthropic Claude Haiku 4.5 · Airtable · Google Calendar ·
Zernio (WhatsApp Business API) · Next.js on Vercel.

---

## Security

This repository is **public**, so it is built as if it were.

- No secrets, no customer PII in git — real values live in n8n Credentials. Only
  `n8n/workflow.sanitized.json` is committed; base, table and credential IDs are placeholders.
- Every push runs a secret/PII scan.
- The n8n editor is never exposed to the internet; only webhook endpoints are.
- The owner dashboard will be authenticated — it shows PII and a destructive cancel.
- **A finding from this build, recorded honestly:** the LLM webhook was discovered publicly reachable
  with no rate limit or spend cap. It was taken offline immediately and re-publishing is gated behind
  the Phase-5 brakes. Documented in [`docs/ARCHITECTURE-DECISIONS.md`](docs/ARCHITECTURE-DECISIONS.md).
- **The date guard, and what it does NOT cover (honest limit, 2026-09-09).** The engine — not the model —
  resolves the booking day: the LLM's date is a disagreement signal, never a value. That closed a real
  wrong-day booking (the model answered a Saturday for "friday morning" at `confidence=0.92`, reproduced
  live again during the final drill and overridden). **Four things it still does not do, each with a
  reproduction in [`docs/ROADMAP.md`](docs/ROADMAP.md):** a week shift the sentence carries but the model's
  wording does not is NOT detected (the confirmation step showing weekday + full date is the only backstop);
  a day named in a form outside the recognised vocabulary ("the 20th", "next weekend", non-English) can still
  let a previously stored date stand; the separator fold covers the dash and slash families, not every
  Unicode look-alike; and on a confirmation turn a change request that cannot be resolved writes the date the
  customer was shown. These are demo-grade limits on a template with **zero real customers** — named here
  rather than left for a reader to discover.
- **The extraction-retry path has never been TRIGGERED in production (honest limit).** Precisely: in the live
  drill `Extraction Transient?` executed on every turn and took its FALSE branch every time, while
  `Repeat Extraction Failure?` and `Build Extraction-Retry State` never executed at all. So one node has run
  and never fired, and two have never run. **That per-turn execution count is itself UNVERIFIED here:** its
  only basis is the previous round's drill write-up — the execution log is not committed, so a reader cannot
  re-derive it from this repo. *(An earlier wording said "three safety nodes have never run",
  which the drill record contradicts — "the node never executed" and "its real trigger was never exercised"
  are different claims and only the second is true of all three.)* The trigger — the model omitting a required
  schema KEY — cannot be induced on demand against a live model, so the path has unit and mutation evidence
  only. The drill proved the surrounding behaviour did not regress, nothing more.
- **Cancel identity (honest limit):** a customer can only cancel their OWN booking — cancel looks up
  appointments by the channel-authenticated `sender_key`, never a customer-supplied booking id, so IDOR
  is structurally impossible. On the widget, though, `sender_key` derives from a **client-supplied
  `sessionId`** — session-token strength, not a verified identity. A real signed widget session (Phase 6)
  plus endpoint rate-limiting (Phase 5) harden this; recorded in `docs/ARCHITECTURE-DECISIONS.md` §5.

---

## From demo to real

Everything runs today on mock config and a test endpoint. Going live for a client means their real
WhatsApp number, their calendar and their Airtable base — **no code change**, a new config file and new
credentials.

---

## Documentation

**[MASTER-BRIEF.md](MASTER-BRIEF.md)** — the current architecture ·
**[docs/ROADMAP.md](docs/ROADMAP.md)** — live phase status ·
**[docs/ARCHITECTURE-DECISIONS.md](docs/ARCHITECTURE-DECISIONS.md)** — every decision and why it changed ·
**[docs/DATA-MODEL.md](docs/DATA-MODEL.md)** — the data model.

MIT licensed. Built by [Neeidy](https://github.com/Neeidy) as a portfolio project in AI automation.
