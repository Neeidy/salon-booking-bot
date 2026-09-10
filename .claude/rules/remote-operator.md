# remote-operator

**Purpose:** Claude runs ON the server; Yigitcan runs a browser somewhere ELSE. A `localhost:PORT` that
is correct for one of them is meaningless for the other.

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
