# remote-operator

**Purpose:** Claude runs ON the server; Yigitcan's browser is somewhere ELSE. A `localhost:PORT` that
is correct for one of them is meaningless for the other.
⚠ **This is about ADDRESSES, not about who owns a browser.** The server has a headless Chromium and it is
Claude's to drive — see "The capability FACT" at the bottom. Do not read this Purpose as permission to
hand him a drill; the tunnel rule and the who-runs-what rule are separate.

## The rule
**Every message that gives Yigitcan a browser address MUST carry the SSH tunnel command directly above
it — the real port, never a placeholder:**

```
ssh -N -L <PORT>:localhost:<PORT> yigit@<HOST>
http://localhost:<PORT>/...
```

- Fill `<HOST>` from `CLAUDE.local.md`. **Never write the host into the chat** — it is a redaction target.
- If the local port is likely taken (3000 and 3111 are, routinely), propose the alternative port yourself
  and write the URL for that port. Do not make him discover the collision.
- This applies to every address without exception: dev servers, static drill pages, previews, dashboards.

## Why
Without the tunnel the address resolves on HIS machine — to nothing, or worse, to a different app of his,
which looks like a broken build rather than a missing tunnel. It cost five round trips in one session
(ports 8788, 8789, 3001, 4311, 3000), each one a wasted turn on a problem that was never in the product.

## Related: do not send him a drill you can run yourself
The dividing question is single: **does this drill need a real Turnstile token?**
- **Needs one → his browser.** Live conversation, a real booking, idempotency on a real message.
- **Does not → run it yourself, headless.** Anything that is DOM, CSS, layout, events or asset loading:
  double-insert, JS disabled, mobile width, Esc and focus order, font loading and face swap, panel
  open/close, z-index, launcher placement.

Sending him a drill you could have run yourself spends one of his turns for nothing.


## The capability FACT: this machine HAS a browser, and it is Claude's to drive

⚠ **Recorded because "I have no browser" was claimed in this session and was FALSE.** A subagent found the
binaries under `~/.cache/ms-playwright` and ran the token-free drills against them; the build had asserted
the opposite without ever looking. **A claim about your OWN capability is a claim like any other** —
`reporting.md` does not exempt it because the subject is you. It is in fact the worst kind to leave
unmeasured: an untrue guard-comment misleads the next reviewer, but an untrue capability claim silently
moves work onto Yigitcan's turns, and nobody ever sees the cost.

**Measured 2026-09-11 on this machine, all three routes:**

    BIN=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome   # also: chromium-1228

| Route | Command | What the run actually returned |
|---|---|---|
| DOM · JS · computed style | `"$BIN" --headless --no-sandbox --disable-gpu --dump-dom "file://…"` | executed the page's JS, attached an **open shadow root**, and read `rgb(1, 2, 3)` back out of `getComputedStyle` inside it |
| Full CDP control | `"$BIN" --headless --no-sandbox --remote-debugging-port=9333 --user-data-dir=…` | `/json/version` answered: **Chrome 153.0.8010.12, protocol 1.3** — i.e. request blocking, synthetic input and tracing are all on the table |
| Screenshot | `"$BIN" --headless --no-sandbox --screenshot=shot.png --window-size=390,700 "file://…"` | a **3791-byte PNG at mobile width** |

**One real limit, stated so it is not rediscovered:** the `playwright` **npm module** is NOT installed —
`require.resolve('playwright')` throws, nothing global, nothing in `node_modules`. Only the browser
**binaries** are cached. The route is raw Chromium as above (or the `playwright` MCP tools when a session
has them), never `require('playwright')`.

**Therefore — the split is now a fact, not an estimate.** Everything that is DOM, CSS, layout, events,
isolation, responsive, accessibility, asset loading or request blocking is **Claude's to run**. Yigitcan's
browser is for the cases that need a **REAL TURNSTILE TOKEN** and nothing else: E2E-1/2/3 and a live
conversation (`tests/snippet/DRILLS.md`). The one thing still genuinely out of reach is a Turnstile
challenge in this headless Chromium (error 600010, measured repeatedly) — that limit is real; "no browser"
never was.

Before writing "I can't", run the check. This section exists because that was not done.
