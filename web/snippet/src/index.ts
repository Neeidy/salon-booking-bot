/**
 * barber-widget.js — the embeddable snippet.
 *
 * One line on a client's site:  <script src="https://<our-origin>/barber-widget.js" defer></script>
 *
 * ISOLATION CONTRACT (architecture recorded in ARCH-DEC §5, 2026-09-02; proven in the 6b spike):
 *   · Shadow DOM (open) + `:host{all:initial}` — the boundary blocks the host's selectors, `all:initial`
 *     cuts the inherited properties selectors cannot reach.
 *   · The only element added to the host DOM is the shadow host itself. Everything else the widget puts on
 *     the page is enumerated in ARCH-DEC §5 (2026-09-10) and told to clients on /install — it is NOT one
 *     item: two <style> elements (one font face each, the second deferred to first open, because
 *     @font-face cannot live inside a shadow root), Cloudflare's Turnstile <script>, a document-level
 *     Escape listener while the panel is open, one window global guarding a double script load, and one
 *     sessionStorage key. An earlier version of this comment said "ONE documented exception" and was
 *     wrong — a list is only honest when it is complete (security-auditor, 2026-09-10).
 *   · Known limit, inherited by every overlay widget including iframe-based ones: a `transform` or
 *     `filter` on the host's <body> turns position:fixed into position:absolute-in-body.
 *
 * NO-JS STORY, stated honestly: a script tag cannot render without JS, so with JS disabled the host page
 * is simply untouched. That is the correct behaviour for an injected widget — the DEMO SITE keeps the
 * no-JS-open contract, this cannot.
 */
import { sendMessage, getSessionId, newMessageId, welcomeLine, FRONTEND_TEXT, type ChatReply } from '@salon/shared/chat';
import { STYLES } from './styles';
import { injectUiFont, injectDisplayFont, ownOrigin } from './fonts';
import { mountTurnstile } from './turnstile';

/* Baked at build time by build.mjs — see that file for what is included and why so little. */
declare const __BAKED_CONFIG__: {
  business: { name: string };
  messageTemplates: Record<string, string>;
  demoMode: boolean;
};
declare const __WEBHOOK_URL__: string;
declare const __TURNSTILE_SITE_KEY__: string;

const HOST_ID = 'barber-widget-root';

(function main() {
  // Capture our own <script> FIRST: `document.currentScript` is only meaningful while this file is
  // executing synchronously, so it must be read before any possible deferral below.
  const selfSrc = (document.currentScript as HTMLScriptElement | null)?.src
    ?? document.querySelector<HTMLScriptElement>('script[src*="barber-widget"]')?.src
    ?? null;

  // `document.body` does not exist yet when the tag is pasted into <head> without `defer`. /install
  // gives the correct line, but the one thing a one-line product cannot control is where somebody
  // pastes it — and the old code threw `Cannot read properties of null (reading 'appendChild')` there.
  // On a client's own site that surfaces as a cross-origin "Script error." with no widget and no cause
  // (measured by code-reviewer, 2026-09-11). Waiting is the entire fix.
  if (document.body) boot(selfSrc);
  else document.addEventListener('DOMContentLoaded', () => boot(selfSrc), { once: true });
})();

function boot(selfSrc: string | null) {
  // The guard lives HERE, not in main(): two tags pasted into <head> would both defer to
  // DOMContentLoaded and both arrive with the host still absent, so a check made before the wait
  // would let two widgets through.
  if (document.getElementById(HOST_ID)) return;      // double-insert guard: two script tags, one widget

  const cfg = __BAKED_CONFIG__;
  const name = cfg.business.name;
  const endpoint = { webhookUrl: __WEBHOOK_URL__, turnstileSiteKey: __TURNSTILE_SITE_KEY__ };

  const host = document.createElement('div');
  host.id = HOST_ID;
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: 'open' });

  const initials = name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
  const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));

  root.innerHTML = `<style>${STYLES}</style>
<button class="launcher" type="button" aria-expanded="false" aria-controls="bw-panel">
  <span class="online-dot"></span><span>Book by text</span>
</button>
<section class="panel" id="bw-panel" role="dialog" aria-label="Book by text — ${esc(name)}">
  <div class="panel-head">
    <span class="panel-avatar" aria-hidden="true">${esc(initials)}</span>
    <div class="panel-id">
      <strong class="panel-name">${esc(name)}</strong>
      <span class="panel-status"><span class="online-dot"></span>online — instant replies</span>
    </div>
    ${cfg.demoMode ? '<span class="demo-tag" title="This assistant is running on demo data">Demo</span>' : ''}
    <button class="panel-close" type="button" aria-label="Close chat">×</button>
  </div>
  <div class="thread" role="log" aria-live="polite" data-thread></div>
  <div class="turnstile-slot" data-slot></div>
  <div class="composer">
    <input class="composer-input" data-input type="text" autocomplete="off" maxlength="1000"
           aria-label="Type a message" placeholder="Verifying…" disabled>
    <button class="composer-send" data-send type="button" aria-label="Send" disabled>↑</button>
  </div>
</section>`;

  const origin = ownOrigin(selfSrc);
  injectUiFont(origin);   // the display face waits for the first panel open — see fonts.ts

  const launcher = root.querySelector<HTMLButtonElement>('.launcher')!;
  const panel = root.querySelector<HTMLElement>('.panel')!;
  const closeBtn = root.querySelector<HTMLButtonElement>('.panel-close')!;
  const thread = root.querySelector<HTMLElement>('[data-thread]')!;
  const slot = root.querySelector<HTMLElement>('[data-slot]')!;
  const input = root.querySelector<HTMLInputElement>('[data-input]')!;
  const sendBtn = root.querySelector<HTMLButtonElement>('[data-send]')!;

  const sessionId = getSessionId();
  let sending = false;
  let handoffShown = false;      // K2 = C: show the lock reply ONCE, then accept quietly

  const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  function bubble(from: 'bot' | 'user' | 'system', text: string, action?: { label: string; run: () => boolean }) {
    // A blank bubble is worse than an honest sentence: it reads as the bot answering with nothing.
    // Reachable whenever a `messageTemplates` key is absent — the schema requires none of them.
    if (!text) text = FRONTEND_TEXT.noText;
    const el = document.createElement('div');
    el.className = `msg ${from}`;
    el.textContent = text;
    if (action) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'retry';
      btn.textContent = action.label;
      // Remove the bubble ONLY if the retry actually starts. It used to remove first and call after —
      // so a click while the composer was still waiting for a fresh Turnstile token silently did nothing
      // AND destroyed the only way back (measured 2026-09-10). A button that can do nothing must at
      // least leave itself on screen.
      btn.addEventListener('click', () => {
        if (action.run()) { el.remove(); return; }
        // Staying on screen was the earlier fix and it was right — but a click that changes NOTHING
        // reads as a dead control. Measured 2026-09-11 (code-reviewer): bubbles 5→5, POSTs 1→1,
        // placeholder unchanged, no typing indicator; the only signal was the greyed-out composer,
        // which is easy to miss while looking at the button you just pressed. Say why, once. The
        // sentence points DOWN rather than naming a cause, because `canSend()` refuses for three
        // different reasons (no token yet, blocked, another send in flight) and the composer below
        // already states which one.
        if (!el.querySelector('.retry-note')) {
          const note = document.createElement('span');
          note.className = 'retry-note';
          note.textContent = 'Not ready to send yet — see the box below.';
          btn.insertAdjacentElement('afterend', note);
        }
      });
      el.appendChild(document.createElement('br'));
      el.appendChild(btn);
    }
    const stamp = document.createElement('span');
    stamp.className = 'stamp';
    stamp.textContent = clock();
    el.appendChild(stamp);
    thread.appendChild(el);
    thread.scrollTop = thread.scrollHeight;
  }

  function typing(on: boolean) {
    const existing = thread.querySelector('.typing');
    if (!on) { existing?.remove(); return; }
    if (existing) return;
    const el = document.createElement('div');
    el.className = 'typing';
    el.setAttribute('aria-hidden', 'true');
    el.innerHTML = '<i></i><i></i><i></i>';
    thread.appendChild(el);
    thread.scrollTop = thread.scrollHeight;
  }

  bubble('bot', welcomeLine(name));

  /* ── Turnstile ────────────────────────────────────────────────────────────────────────────────
     The composer stays disabled until a token exists. That is not politeness: letting a visitor type
     into a box that cannot deliver is the silent failure this repo forbids.
     ⚠ The earlier wording said a send without a token is "a guaranteed 403". It is not guaranteed by
     the engine — `Turnstile Gate` is conditional on `channel === 'widget'` AND
     `config.channels.widget.turnstile.enabled === true`, so the 403 depends on a client's config flag.
     The DECISION is unchanged and correct either way; only the justification was overstated. */
  let ts = { token: () => null as string | null, refresh: () => {} };

  /**
   * THE WAIT NEEDS A WAY OUT — and the way out must not speak before there is anything to wait for.
   *
   * The gap, structurally (the search, shown, because this is a claim about shape):
   *     turnstile.ts:110  callback: (t) => { token = t; onChange('ready'); }   ← the ONLY 'ready'
   *     turnstile.ts:98/112/113/126 'pending'   ·   111/117 'blocked'
   *     index.ts    setGate('pending') at mount and on every send   ·   'blocked' in the refresh catch
   * One producer of `ready`, and `pending` has no timeout of its own, so a `reset()` whose callback
   * never arrives leaves the composer dead behind "Verifying…" with nothing on screen. That is the
   * dead composer `tests/snippet/DRILLS.md` lists as a MUST-NOT-RUN.
   *
   * ⚠ THIS IS THE SECOND ATTEMPT. The first shipped for one round and was reverted: the timer armed
   * from the `setGate('pending')` at MOUNT, while Turnstile is only mounted on the FIRST PANEL OPEN,
   * so it fired for every visitor who browsed 20 s before clicking — announcing that it was "still
   * checking this browser" with `turnstileRendered: 0`, i.e. before running a single line of
   * verification code. Its negative control HAD been run and HAD passed; it swept only the `sending`
   * axis, and the defect was on an axis nobody had thought to vary.
   *
   * THREE CONDITIONS, each answering one axis:
   *   `mounted`   — Turnstile has actually been asked for a token. Without it the timer measures the
   *                 visitor's browsing speed, not Cloudflare's.
   *   `!sending`  — an in-flight send also parks the gate at `pending`, but that wait belongs to the
   *                 ENGINE (up to the 60 s transport timeout) and already shows a typing indicator.
   *   one-shot, RE-ARMED on `ready` — say it once per stall, not once per page. The first version
   *                 burned its only shot on the false alarm and then had nothing left for the real one.
   *
   * ⚠ Scope, unchanged and honest: this does not REPAIR the wait — only Cloudflare can. It turns a
   * silent no-exit into a stated one. Two different thresholds; only the second is crossed here.
   */
  const VERIFY_STUCK_MS = 20000;
  // Declared HERE, above `setGate`, not next to the panel code: `setGate('pending')` runs immediately
  // below and reading `mounted` from its temporal dead zone would throw before the widget ever drew.
  let mounted = false;
  let gateTimer: ReturnType<typeof setTimeout> | undefined;
  let stuckShown = false;

  function setGate(state: 'pending' | 'ready' | 'blocked') {
    const ok = state === 'ready';
    input.disabled = !ok;
    sendBtn.disabled = !ok || sending;
    input.placeholder = state === 'blocked'
      // The old line said "Verification didn't load". Measured with Cloudflare's always-block test key:
      // the challenge DID load (the slot took a 388x73 box) and then REFUSED — and for a visitor who
      // has actually been flagged, "reload the page" fixes nothing. This wording is true either way.
      ? "Couldn't verify this browser — reload to try again"
      : ok ? 'Type a message…' : 'Verifying…';

    clearTimeout(gateTimer);
    if (ok) stuckShown = false;          // a stall that ended may happen again, and must be sayable again
    if (state === 'pending' && !sending && mounted) {
      gateTimer = setTimeout(() => {
        input.placeholder = 'Still verifying — reload the page';
        if (!stuckShown) { stuckShown = true; bubble('system', FRONTEND_TEXT.verifyStuck); }
      }, VERIFY_STUCK_MS);
    }
  }
  setGate('pending');

  /**
   * RETRY IS NOT A NEW MESSAGE — it is the SAME payload sent again, with the SAME `messageId`.
   *
   * The engine dedupes on `message_id`; this is what that mechanism is for. Measured on 2026-09-10: a
   * turn that timed out CLIENT-side had been fully processed by the engine anyway, so the visitor was
   * told to try again about work that had succeeded. Re-typing produces a NEW id, which dedupe cannot
   * collapse — on a `yes` turn that is a second write attempt against a booking that already exists.
   * Reusing the id removes that whole class without touching the engine.
   *
   * ⚠ BOUND, because the earlier wording ("closes that path") claimed more than the engine guarantees.
   * Read from the committed workflow's connection graph, not assumed:
   *     Check Processed   <- Validate Payload                        (start of the turn)
   *     Record Processed  <- Save State, Save State (Post-Write)     (end of the turn)
   * The id is written only once a turn has COMPLETED. So a retry fired while the first turn is still
   * in flight finds `Check Processed` empty and is processed as a second turn — dedupe does not engage
   * there. What bounds that remaining case is not this file: `Build Event Request` derives a
   * deterministic Calendar event id from the booking key, so the second write collides (409) instead of
   * creating a second appointment. Narrower claim, and the one that is actually measured.
   *
   * The distinction is a STATE, never a guess: `send(retry)` replays a specific failed payload, and it
   * is only ever reached through the button on that failure's own bubble. Anything the visitor types is
   * a new message with a new id, always.
   *
   * The Turnstile token is NOT reused — it is single-use and the timed-out request already spent it.
   * A retry carries the same messageId and a FRESH token; the two are independent.
   */
  /** The single precondition for sending. Both `send()` and the retry button ask THIS, never a copy of it. */
  function canSend(text: string): boolean {
    return !!text && !sending && !!ts.token();
  }

  async function send(retry?: { text: string; messageId: string }): Promise<void> {
    const text = retry ? retry.text : input.value.trim();
    const messageId = retry ? retry.messageId : newMessageId();
    const token = ts.token();
    if (!canSend(text) || !token) return;

    sending = true;
    setGate('pending');
    if (!retry) { bubble('user', text); input.value = ''; }   // the user bubble is already on screen
    typing(true);

    let reply: ChatReply;
    try {
      reply = await sendMessage(endpoint, cfg, text, sessionId, token, messageId);
    } catch {
      // sendMessage handles its own failures; this is the belt-and-braces path so a throw can never
      // leave the composer permanently disabled with no explanation on screen.
      reply = { kind: 'system', text: FRONTEND_TEXT.unexpected, origin: 'frontend', status: 0 };
    } finally {
      typing(false);
      sending = false;
      // The token is spent; mint the next one. Wrapped because this calls into Cloudflare's script, and a
      // throw here would escape `send()` before anything is drawn — leaving the composer disabled with no
      // explanation, which is the state the try/catch above exists to make impossible.
      try { ts.refresh(); } catch { setGate('blocked'); }
    }

    // A TRANSPORT failure (status 0: timeout, or the request never left the browser) is the one case
    // where the engine's view and the visitor's may differ. Offer a real retry of the same payload
    // rather than leaving them to retype, which would be a different message.
    if (reply.status === 0 && reply.origin === 'frontend') {
      bubble('system', reply.text, {
        label: 'Try again',
        // ONE gate: ask canSend(), the same predicate send() uses. Two copies of a precondition drift, and
        // a new condition inside send() would leave this removing the bubble for a send that never starts
        // — the defect fixed earlier today, re-created one level up (code-reviewer, 2026-09-10).
        run: () => { if (!canSend(text)) return false; void send({ text, messageId }); return true; },
      });
      return;
    }
    // A duplicate is deliberately screenless (W56) — EXCEPT after a retry. There the engine is telling us
    // it already handled this message, and it sends NO reply to tell the visitor anything with: measured
    // from the committed workflow, `Idempotent Replay` returns `{status, sender_key}` and nothing else, so
    // the original answer is unrecoverable. Staying silent would leave someone who pressed "Try again"
    // watching their message vanish — the exact silence this mechanism exists to prevent.
    if (reply.kind === 'silent') {
      if (retry) bubble('system', FRONTEND_TEXT.alreadyReceived);
      return;
    }
    // K2 = C — the handoff lock answers every message with the same line, so show it once. Detected by the
    // engine's STRUCTURAL `locked` flag, never by comparing its words with our baked template: those two
    // configs live in different places and have drifted before (CP5a).
    if (reply.locked) {
      if (handoffShown) return;
      handoffShown = true;
    }
    bubble(reply.kind === 'system' ? 'system' : 'bot', reply.text);
  }

  sendBtn.addEventListener('click', () => { void send(); });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); void send(); } });

  /**
   * Escape closes the panel from ANYWHERE while it is open.
   *
   * It used to be bound to the shadow root, which meant it only fired while focus happened to be inside
   * the widget — measured: with focus on one of the host page's own links, Escape did nothing and the
   * panel stayed open. A visitor who opens the panel, clicks back onto the page and presses Escape is
   * an ordinary visitor, not an edge case.
   *
   * SECOND NAMED TOUCH OF THE HOST DOCUMENT (the first is the @font-face <style>, see fonts.ts): a
   * document-level keydown listener. It is deliberately minimal — attached only while the panel is open,
   * removed on close, acts on one key, and NEVER calls preventDefault or stopPropagation, so the host
   * page's own Escape handling continues to work exactly as it did before the widget was added.
   */
  const onDocKeydown = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && panel.classList.contains('is-open')) setOpen(false);
  };

  function setOpen(open: boolean) {
    panel.classList.toggle('is-open', open);
    launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      // The display face is only ever seen inside the open panel, so a visitor who never opens it pays
      // nothing for a 205 kB file. Idempotent, so re-opening does not re-inject.
      injectDisplayFont(origin);
      // Mount Turnstile only once, and only after the panel is open — the slot needs a real box before
      // Cloudflare draws into it (see turnstile.ts, finding 3).
      if (!mounted) { mounted = true; ts = mountTurnstile(slot, endpoint.turnstileSiteKey, setGate); }
      // A disabled input cannot take focus, and the composer is disabled until Turnstile yields a
      // token — so focusing it unconditionally leaves a keyboard user stranded outside the panel
      // (measured: focus stayed on the launcher and the next Tab left the widget entirely).
      (input.disabled ? closeBtn : input).focus();
      document.addEventListener('keydown', onDocKeydown);
    } else {
      document.removeEventListener('keydown', onDocKeydown);
      launcher.focus();            // focus returns to the launcher, never to nowhere
    }
  }

  launcher.addEventListener('click', () => setOpen(!panel.classList.contains('is-open')));
  closeBtn.addEventListener('click', () => setOpen(false));
}
