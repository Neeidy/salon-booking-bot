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

- **The host NEVER enters a repo file, nor any text destined for a repo file — but it DOES belong in the
  runnable command handed to the operator.** Fill `<HOST>` from `CLAUDE.local.md` when the command is for
  Yigitcan to run; keep it out of every committed artefact, report, screenshot, export **and commit
  message**. ⚠ The commit message is called out by name because it is the ONE channel
  `scripts/check-no-host-leak.sh` cannot see — its own KNOWN LIMITS block says so: *"COMMIT MESSAGES are
  not scanned. Writing the host into a message would reach GitHub with this guard green."* Measured
  2026-09-11: zero occurrences across all reachable history — that is discipline holding, not a control.
  ⚠ *Corrected 2026-09-11: the two bullets here previously said "fill `<HOST>` from `CLAUDE.local.md`" AND
  "never write the host into the chat", which cannot both be obeyed — the rule was unimplementable, and it
  bit during the 6b E2E hand-off, where a placeholder had to be left and the contradiction reported instead
  of followed. What the redaction target actually protects is the REPO (public) and anything that reaches
  it; an ssh command Yigitcan types on his own machine is not that. (`governance-sync.md` §6: a rule that
  contradicts itself is corrected in place, not annotated beside.)*
- If the local port is likely taken (3000 and 3111 are, routinely), propose the alternative port yourself
  and write the URL for that port. Do not make him discover the collision.
- This applies to every address without exception: dev servers, static drill pages, previews, dashboards.
- **Drill/dev servers ALWAYS bind to `127.0.0.1`; access is via the SSH tunnel.** `python3 -m http.server
  <PORT>` defaults to `0.0.0.0` — every interface — so use `--bind 127.0.0.1`. The tunnel above is already
  the access path, so a public bind buys nothing and is pure exposure. **What produced this rule
  (2026-09-11):** a drill server started 2026-09-09 from `tests/snippet` had been listening on `0.0.0.0:8788`
  for two days, owned by a dead session's pid. It was measured first and killed only on Yigitcan's word —
  `ss -ltnp` shows no listener on 8788 since. ⚠ *The first draft of this bullet said "**was** listening" while
  the process was still up; `security-auditor` caught it. The tense is corrected here rather than annotated
  beside, because the condition genuinely changed (`governance-sync.md` §6) — and it is now past tense for the
  opposite reason it was present tense before: the measurement moved, so the sentence moved with it.*

### The rule held for the NEXT bind and did nothing about the ones already up — so there is a sweep now

⚠ **This is the THIRD instance, not the first.** `0.0.0.0:8788` (2026-09-09, two days) → `0.0.0.0:8789`
→ **`*:3001`, a `web/site` dev server from a dead session, listening for 37 hours** (2026-09-10 22:28 →
2026-09-12 11:5x, killed on Yigitcan's word; `ss` shows no listener on 3001 since). Each was found by
accident while doing something else. **A rule phrased as "always bind loopback" governs the next bind
only** — nothing ever looked at what was already listening, so instances accumulated silently under a
rule that was, on its own terms, being followed.

**The sweep gate: `bash scripts/check-listeners.sh`.** It FAILS (exit 1) on a wildcard-bound listener
whose process is visible to this user — `ss -ltnpH` hides other users' processes, so "attributable" is
the precise, portable form of "ours", and all three orphans were exactly that.
⚠ **This sentence was FALSE for the first hours of the script's life and both L2 auditors measured it
independently.** The live invocation was `ss -ltnH` — without `-p`, and `ss` then prints no process
column at all, so the attribution test could never be true and `exit 1` was dead code: the gate
printed OK for the exact orphans it was written for. Its selftest passed because all three failing
fixtures had been copied from an `ss -ltnp` run — a shape the live command could not produce. A
control that cannot produce the defect proves nothing, and that is this repo's own rule, broken in the
script written to enforce another one. **Re-derived from a real run:** an inert wildcard socket, bound
for four seconds and serving nothing, made the live path exit **1**, naming the port and the process;
after it closed, the same command exits **0**. The flag is now asserted by the selftest itself. Every other wildcard bind
(on this machine: three long-running system daemons) is LISTED and never failed on, per Yigitcan's instruction of
2026-09-12: *"ÖLDÜRME — listele, ben karar veririm."* Run it at the start of a session and before a push.

⚠ **What the gate does NOT tell you, stated because the — for once — reassuring half of the 3001
measurement came from outside this machine:** it measures the **bind**, never **reachability**. From
Yigitcan's own network `curl` to that port returned `000` (timeout), so the page was not in fact being
served to the internet for those 37 hours — a near-miss, not an exposure.

⚠⚠ **THE MECHANISM IS NAMED NOW, AND THE SENTENCE THAT STOOD HERE FOR A DAY WAS WRONG — IN A PUBLIC
REPO, ABOUT A SECURITY CONTROL.** It named three firewall tools and declared all of them absent from
this machine, concluding that *"'the firewall held' is a story, not a measurement."* The conclusion's
second half was true. **The premise was an artefact of my own `PATH`:**
`command -v` as a non-root user does not search `/usr/sbin` or `/sbin`, so "not found" meant "not on my
PATH", and it was written down as "not on this machine".

**Measured 2026-09-13, four ways that each answer on their own:** the firewall BINARIES are present
(under `/usr/sbin`, which a login shell does not search) · its **service unit is loaded and ACTIVE** ·
its config file declares it **enabled** · and the kernel has a **reject module loaded with a non-zero
refcount**, i.e. at least one reject rule exists. So **a host firewall is installed, enabled and
running** — a named mechanism, consistent with the timeout the external probe measured.

⚠ *The specific package names, unit names, ports and file paths are deliberately NOT written here. On a
PUBLIC repo, a precise description of a reachable host's firewall stack is a service inventory for a
stranger — the same class `security-auditor` removed in the 2026-09-12 M3 finding, and flagged again
here. The transferable lesson below needs none of them.*

**Two things it still does NOT license, and they are the reason this paragraph is long:**
1. *Named is not the same as READ.* The ruleset itself is root-only — three separate read routes were
   tried and all three refused. What is recorded from a root run belongs to Yigitcan
   and is labelled **"root output, operator ran it"**, never "measured".
2. *A firewall being up is not proof it is what stopped THAT port.* Default-deny and "3001 simply was
   not on the allow list" produce the identical timeout and are different facts — one is a wall, the
   other is a door that happened to be shut.
   ⚠ *An earlier draft of this sentence said the policy "is recorded below". It was not, and nothing
   below said so — a present-tense claim about a record that did not exist, inside the paragraph whose
   whole subject is not claiming more than was measured (`security-auditor` M3, 2026-09-13). It is
   recorded now, and the distinction it drew is exactly what the answer turned on.*

### The policy — **root output, Yigitcan ran it 2026-09-12. NOT my measurement.**

**Incoming connections on the build host are DENIED BY DEFAULT.** The `*:3001` exposure was closed by
that default, **not** by the absence of a port-specific rule — the wall, not the shut door.

**The consequence is the part worth keeping, and it cuts against the comfortable reading:** binding
drill and dev servers to `127.0.0.1` is NOT the only defence, and it is NOT thereby redundant. It is the
**second layer, and it stays** — precisely BECAUSE a default-deny is one `allow` rule away from being
switched off for any port, by anyone, at any time, for a reason that will sound good on the day. Two
independent controls, both standing. A control you drop because another one currently covers it is a
control you have traded for someone else's future decision.

⚠ *Deliberately NOT written here, in this file or any other: the firewall tool, package or unit name ·
the list or count of open ports · the logging level, profile policy or file paths.* **The reason is not
squeamishness, it is maintenance:** an inventory has to be kept in sync forever, and on the day it is
not, the repo once again carries a FALSE sentence about a security control — which is the exact defect
this round paid for twice. A fact that cannot go stale is worth more than a list that can.

**The general lesson, which outlives this machine:** *a negative result about a TOOL is a claim about
your environment, not about the box.* Before writing "X is not installed", ask which PATH answered.
This is the same family as the empty-search rule in `reporting.md` — the instrument was the defect
again, and this time the instrument was `$PATH`.
⚠ *The port number and the daemon's name used to be written out here and were removed on 2026-09-12
(`security-auditor` M3): on a PUBLIC repo, naming which services listen on every interface of a host
whose apex this same file says is NOT behind Cloudflare's proxy is a service inventory for a stranger.
`check-no-host-leak.sh` cannot catch this — it scans host VALUES, not service FACTS — so it is a
discipline, like the commit-message case above, and it is written down for the same reason.*

## ⛔ SSH NEVER GOES TO A CLOUDFLARE-PROXIED HOSTNAME — and here is WHY, so it is not re-derived

```
ssh yigit@<the n8n hostname>        ✗ cannot work   — proxied
ssh yigit@<the dashboard hostname>  ✗ cannot work   — proxied
ssh yigit@<SSH_ORIGIN_HOST>         ✓ the machine itself
```

*(The wrong examples are written as placeholders on purpose. The first draft of this block spelled the
real proxied hostname out — and `check-no-host-leak.sh`, extended ten minutes earlier in the same round,
went RED on it: the production host, in a TRACKED file, in a PUBLIC repo, inside the rule about hosts.
The guard caught the hand that had just widened it. A counter-example does not need the real value to
teach the shape.)*

**The reason, which is the whole point of this section:** those **hostnames** are **Cloudflare-proxied**.
Their DNS resolves to Cloudflare's edge, and the edge proxies **HTTP(S) only** — SSH is not HTTP and does
not traverse it. *(Measured on this machine: the n8n hostname resolves to two addresses inside Cloudflare's published
IPv4 ranges, never to the origin. ⚠ **The APEX is a different case and an earlier draft of this very
paragraph got it wrong** — it said the apex was proxied; `dig` says the apex has a single A record that is
NOT in Cloudflare's ranges, i.e. the zone is hosted at Cloudflare but the apex is DNS-only while the
sub-domains are proxied. Corrected in place, because this section's own thesis is that the REASON is the
part that survives — a wrong reason is re-derived wrongly forever. Practical consequence that does NOT
change: ssh goes to the origin, never to a proxied name. Consequence that DOES: do not assume the apex
sits behind Cloudflare's WAF or rate-limiting. The "HTTP(S) only" half is Cloudflare product behaviour and
was **not measured here** — consistent with everything that was, but proving it would mean opening a
connection to their edge.)* Those names are addresses of the **HTTP surface**, not of the **machine**. SSH always goes to
the **origin**, whose value lives in `CLAUDE.local.md` as `SSH_ORIGIN_HOST` (gitignored; it is a redaction
target and `scripts/check-no-host-leak.sh` scans for it like any other).

**Why the reason is written and not just the rule:** this was got wrong **three times in one session**,
each time by re-deriving it from "the host we always use". A rule without its reason is re-derived on the
next contact, and re-derived the same wrong way. The reason is the only part that survives.

### Pre-flight before handing over ANY tunnel command
Do not compose the host from memory or from the n8n URL. Read it:

```bash
sed -n 's/^SSH_ORIGIN_HOST=[[:space:]]*\([^[:space:]]*\).*/\1/p' CLAUDE.local.md
```

(That is the SAME parse `scripts/check-no-host-leak.sh` uses — deliberately, so the value the guard
protects and the value handed to Yigitcan can never be two different readings of one line.)

If that returns nothing, say so and stop — do not substitute the proxied hostname "for now". The tunnel
command a proxied name produces is not a slow path or a partial answer; it simply cannot connect, and it
costs Yigitcan a turn discovering that.

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
