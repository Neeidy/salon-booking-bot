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
  if (document.getElementById(HOST_ID)) return;      // double-insert guard: two script tags, one widget

  const cfg = __BAKED_CONFIG__;
  const name = cfg.business.name;
  const t = cfg.messageTemplates;
  const endpoint = { webhookUrl: __WEBHOOK_URL__, turnstileSiteKey: __TURNSTILE_SITE_KEY__ };

  // Capture our own <script> before anything else can change document.currentScript.
  const selfSrc = (document.currentScript as HTMLScriptElement | null)?.src
    ?? document.querySelector<HTMLScriptElement>('script[src*="barber-widget"]')?.src
    ?? null;

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
    <button class="panel-close" type="button" aria-label="Close chat">×</button>
  </div>
  <div class="thread" role="log" aria-live="polite" data-thread></div>
  <div class="turnstile-slot" data-slot></div>
  <div class="composer">
    <input class="composer-input" data-input type="text" autocomplete="off"
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
      btn.addEventListener('click', () => { if (action.run()) el.remove(); });
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
     The composer stays disabled until a token exists. That is not politeness: the engine gates every
     request, so a send without one is a guaranteed 403, and letting a visitor type into a box that
     cannot deliver is the silent failure this repo forbids. */
  let ts = { token: () => null as string | null, refresh: () => {} };
  function setGate(state: 'pending' | 'ready' | 'blocked') {
    const ok = state === 'ready';
    input.disabled = !ok;
    sendBtn.disabled = !ok || sending;
    input.placeholder = state === 'blocked'
      ? "Verification didn't load — reload the page"
      : ok ? 'Type a message…' : 'Verifying…';
  }
  setGate('pending');

  /**
   * RETRY IS NOT A NEW MESSAGE — it is the SAME payload sent again, with the SAME `messageId`.
   *
   * The engine already dedupes on `message_id`; this is what that mechanism is for. Measured on
   * 2026-09-10: a turn that timed out CLIENT-side had been fully processed by the engine anyway, so the
   * visitor was told to try again about work that had succeeded. Re-typing produces a NEW id, which
   * dedupe cannot collapse — on a `yes` turn that is a second write attempt against a booking that
   * already exists. Reusing the id closes that path without touching the engine.
   *
   * The distinction is a STATE, never a guess: `send(retry)` replays a specific failed payload, and it
   * is only ever reached through the button on that failure's own bubble. Anything the visitor types is
   * a new message with a new id, always.
   *
   * The Turnstile token is NOT reused — it is single-use and the timed-out request already spent it.
   * A retry carries the same messageId and a FRESH token; the two are independent.
   */
  async function send(retry?: { text: string; messageId: string }): Promise<boolean> {
    const text = retry ? retry.text : input.value.trim();
    const messageId = retry ? retry.messageId : newMessageId();
    const token = ts.token();
    // Returns false when the send could not START — no text, one already in flight, or no fresh token
    // yet. The caller needs that answer: the retry affordance must not be discarded on a no-op.
    if (!text || sending || !token) return false;

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
      ts.refresh();                 // the token is spent — mint the next one before the next message
    }

    // A TRANSPORT failure (status 0: timeout, or the request never left the browser) is the one case
    // where the engine's view and the visitor's may differ. Offer a real retry of the same payload
    // rather than leaving them to retype, which would be a different message.
    if (reply.status === 0 && reply.origin === 'frontend') {
      bubble('system', reply.text, {
        label: 'Try again',
        // Synchronous answer: has the retry begun? A fresh token may not have arrived yet, and in that
        // case the bubble stays so the visitor can press again a moment later.
        run: () => { const started = !!ts.token() && !sending; if (started) void send({ text, messageId }); return started; },
      });
      return true;
    }
    if (reply.kind === 'silent') return true;                  // W56 duplicate: no second bubble, but the send DID happen
    // K2 = C — the handoff lock answers every message with the same line. Show it once; after that the
    // visitor may keep typing (a human will read it) without the same bubble stacking up.
    if (reply.text === t.handoffLocked) {
      if (handoffShown) return true;                           // suppressed on screen; the send still happened
      handoffShown = true;
    }
    bubble(reply.kind === 'system' ? 'system' : 'bot', reply.text);
    return true;
  }

  sendBtn.addEventListener('click', () => { void send(); });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); void send(); } });

  let mounted = false;
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
})();
