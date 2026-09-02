/* barber-widget.js — TUR B-2 · the embeddable snippet (DESIGN MOCKUP).
 *
 * What this is: the file a client's site loads with ONE line:
 *   <script src="https://<cdn>/barber-widget.js" defer></script>
 * It mounts the Tur A widget on ANY host page. This mockup version plays the Tur A
 * booking Flow A as a staged MOCK conversation — it makes NO network calls
 * (NOT-BUILD: no real API; the live POST wiring is the Phase 6 build).
 *
 * ISOLATION — the architecture decision of this tour (recorded in ARCH-DEC §5, 2026-09-02):
 *   Chosen: SHADOW DOM (open) + :host{all:initial} + fonts injected at DOCUMENT level.
 *   · Host CSS cannot reach the widget: the shadow boundary blocks selectors, and
 *     all:initial cuts INHERITED properties (font-family, line-height, color,
 *     box-sizing…) at the root. Every style the widget needs is re-declared inside.
 *   · The widget cannot leak out: all its rules live inside the shadow root.
 *   · Fonts: @font-face does not work inside a shadow root, so the snippet injects the
 *     Google Fonts <link> into document.head (guarded against double-insert). Font
 *     FACES are document-level; font USAGE stays inside the shadow.
 *   Rejected: IFRAME — a fixed launcher + panel needs a viewport-covering iframe
 *     (pointer-events juggling, postMessage bridge, duplicated font loads) or constant
 *     resize choreography; heavy for what isolation buys here.
 *   Rejected: aggressive class-namespace + all:revert on a container — host rules with
 *     !important still pierce; weaker guarantee for the same effort.
 *   Known limits (named, not hidden):
 *   · A host `transform`/`filter` on <body> turns position:fixed into
 *     position:absolute-in-body (browser behavior, hits every overlay widget incl.
 *     iframe-based ones at the placement level).
 *   · Cloudflare Turnstile inside shadow DOM must be validated in the Phase 6 build;
 *     the panel reserves a challenge slot (S3) — fallback if needed: render the
 *     challenge in a light-DOM overlay positioned over the panel.
 *
 * Widget interior: LOCKED IN TUR A — the thread below is byte-identical to
 * design/mockups/widget/booking.html Flow A (W61 · W1 · W10 · W11 · W12 · W13).
 * Texts come from config messageTemplates / engine literals; sources are annotated as
 * HTML comments inside the template. NOT redesigned here.
 *
 * Accessibility: launcher <button> with aria-expanded/controls · panel role="dialog" ·
 * thread role="log" aria-live="polite" · focus returns to launcher on close ·
 * prefers-reduced-motion honored (no staged reveal, everything instant) · ≤480px the
 * panel becomes a full-width bottom sheet. With JS disabled the snippet never runs:
 * the host page is simply untouched (a script tag cannot render without JS — the
 * honest no-JS story for an injected widget; the DEMO SITE's inline widget keeps the
 * no-JS-open contract).
 */
(function () {
  'use strict';
  if (document.getElementById('barber-widget-root')) return; // double-insert guard

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- fonts: document-level injection (faces cannot live inside a shadow root) ---- */
  if (!document.querySelector('link[data-barber-widget-fonts]')) {
    var pre1 = document.createElement('link');
    pre1.rel = 'preconnect'; pre1.href = 'https://fonts.googleapis.com';
    var pre2 = document.createElement('link');
    pre2.rel = 'preconnect'; pre2.href = 'https://fonts.gstatic.com'; pre2.crossOrigin = '';
    var css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..700;1,9..144,400..700&family=Instrument+Sans:wght@400;500;600&display=swap';
    css.setAttribute('data-barber-widget-fonts', '');
    document.head.appendChild(pre1);
    document.head.appendChild(pre2);
    document.head.appendChild(css);
  }

  /* ---- shadow host — the ONLY element the snippet adds to the host DOM ---- */
  var hostEl = document.createElement('div');
  hostEl.id = 'barber-widget-root';
  document.body.appendChild(hostEl);
  var root = hostEl.attachShadow({ mode: 'open' });

  /* ---- everything below lives INSIDE the shadow boundary ---- */
  root.innerHTML =
  '<style>' +
  /* :host{all:initial} — cuts inherited host styles (font, line-height, color, box-sizing). */
  ':host{all:initial}' +
  /* Cream & Ink tokens — locked (Tur A). Values byte-equal to the approved variants. */
  ':host{--cream:#F1EEE6;--ink:#16150F;--oxide:#B4472E;--oxide-soft:#D98B66;--muted:#5C594E;--stamp:#C9C4B4;' +
  '--hairline:rgba(22,21,15,.14);--rule:rgba(22,21,15,.18);--frame:rgba(22,21,15,.35);--edge:rgba(22,21,15,.25);' +
  '--ease:cubic-bezier(.22,.61,.36,1);--font-display:\'Fraunces\',serif;--font-ui:\'Instrument Sans\',system-ui,sans-serif}' +
  '*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}' +
  /* z-index: classic overlay-widget ceiling so an ambitious host header cannot cover us */
  '.launcher{position:fixed;right:26px;bottom:24px;z-index:2147483000;display:inline-flex;align-items:center;gap:10px;' +
  'background:var(--ink);color:var(--cream);border:none;cursor:pointer;border-radius:999px;' +
  'font-family:var(--font-ui);font-size:14.5px;font-weight:600;padding:14px 24px;' +
  'box-shadow:0 16px 38px -14px rgba(22,21,15,.55);transition:transform .3s var(--ease)}' +
  '.launcher:hover{transform:translateY(-2px)}' +
  '.launcher:active{transform:scale(.97)}' +
  '.launcher:focus-visible,.panel-close:focus-visible{outline:2px solid var(--oxide);outline-offset:3px}' +
  '.online-dot{width:8px;height:8px;border-radius:50%;background:var(--oxide-soft);display:inline-block;flex-shrink:0}' +
  '.panel .online-dot{width:7px;height:7px;background:var(--oxide);animation:dotpulse 2.6s var(--ease) 1.6s infinite}' +
  '.panel{position:fixed;right:26px;bottom:88px;z-index:2147483000;width:390px;max-width:calc(100vw - 32px);' +
  'background:var(--cream);border:1.5px solid var(--ink);border-radius:6px;' +
  'box-shadow:8px 8px 0 rgba(22,21,15,.12),0 30px 60px -30px rgba(22,21,15,.5);overflow:hidden;' +
  'display:flex;flex-direction:column;transform-origin:bottom right;' +
  'font-family:var(--font-ui);font-size:16px;line-height:1.6;color:var(--ink);-webkit-font-smoothing:antialiased}' +
  '.panel:not(.is-open){display:none}' +
  '.panel.is-open{animation:panelin .32s var(--ease) both}' +
  '@keyframes panelin{from{opacity:0;transform:translateY(14px) scale(.98)}to{opacity:1;transform:none}}' +
  '.panel-head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--frame)}' +
  '.panel-avatar{width:38px;height:38px;border-radius:50%;background:var(--ink);color:var(--cream);display:flex;' +
  'align-items:center;justify-content:center;font-family:var(--font-display);font-weight:600;font-size:14px;flex-shrink:0}' +
  '.panel-id{line-height:1.35;flex:1;min-width:0}' +
  '.panel-name{display:block;font-family:var(--font-display);font-weight:600;font-size:16px;letter-spacing:-.01em}' +
  '.panel-status{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px}' +
  '.panel-close{width:30px;height:30px;border-radius:50%;font-size:19px;line-height:1;color:var(--muted);flex-shrink:0;' +
  'display:flex;align-items:center;justify-content:center;background:none;border:none;cursor:pointer;font-family:var(--font-ui);' +
  'transition:background .15s var(--ease),color .15s var(--ease)}' +
  '.panel-close:hover{background:rgba(22,21,15,.08);color:var(--ink)}' +
  '.thread{padding:18px;display:flex;flex-direction:column;gap:12px;max-height:min(60vh,440px);overflow-y:auto}' +
  '.msg{max-width:88%;padding:11px 15px;font-size:14.5px;line-height:1.5}' +
  '.msg.user{align-self:flex-end;max-width:84%;background:var(--ink);color:var(--cream);border-radius:16px 16px 4px 16px}' +
  '.msg.bot{align-self:flex-start;background:#FFF;border:1px solid var(--edge);border-radius:16px 16px 16px 4px}' +
  '.msg.confirm{border-left:3px solid var(--oxide)}' +
  '.msg.confirm strong{color:var(--oxide)}' +
  '.stamp{display:block;font-size:10.5px;margin-top:5px;color:var(--muted)}' +
  '.msg.user .stamp{color:var(--stamp)}' +
  '.chips{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}' +
  '.chips + .stamp{margin-top:8px}' +
  '.chip{font-size:13px;font-weight:600;padding:6px 13px;border-radius:999px;border:1px solid rgba(22,21,15,.3);white-space:nowrap}' +
  '.chip-on{border-color:var(--ink);background:var(--ink);color:var(--cream)}' +
  '.pair{position:relative;align-self:flex-start;max-width:88%}' +
  '.pair .msg{max-width:100%}' +
  '.typing{position:absolute;top:0;left:0;z-index:1;display:none;gap:5px;background:#FFF;border:1px solid var(--edge);' +
  'border-radius:16px 16px 16px 4px;padding:12px 15px}' +
  '.typing.on{display:flex}' +
  '.typing i{width:6px;height:6px;border-radius:50%;background:var(--muted);display:block;animation:dotb 1.1s infinite}' +
  '.typing i:nth-child(2){animation-delay:.15s}' +
  '.typing i:nth-child(3){animation-delay:.3s}' +
  /* S3 · Turnstile slot — Cloudflare draws its own widget; the panel RESERVES this space.
     Hidden until the challenge is actually required (managed/invisible mode most turns). */
  '.turnstile-slot{display:none;padding:10px 18px;border-top:1px solid var(--frame)}' +
  '.turnstile-slot.on{display:block}' +
  '.panel-foot{display:flex;align-items:center;gap:10px;padding:13px 18px;border-top:1px solid var(--frame)}' +
  '.panel-input{flex:1;font-size:14px;color:var(--muted);background:#FFF;border:1px solid var(--edge);border-radius:999px;padding:10px 16px}' +
  '.panel-send{width:38px;height:38px;border-radius:50%;background:var(--ink);color:var(--cream);font-size:16px;' +
  'display:flex;align-items:center;justify-content:center;flex-shrink:0}' +
  '.staged .msg{opacity:0;transform:translateY(8px);transition:opacity .4s var(--ease),transform .4s var(--ease)}' +
  '.staged .msg.in{opacity:1;transform:none}' +
  '.staged .msg.in .chip-on{animation:chippop .5s var(--ease) .15s both}' +
  '@keyframes chippop{0%{transform:scale(.85)}55%{transform:scale(1.12)}100%{transform:scale(1)}}' +
  '@keyframes dotb{0%,60%,100%{transform:translateY(0);opacity:.45}30%{transform:translateY(-4px);opacity:1}}' +
  '@keyframes dotpulse{0%,100%{transform:scale(1)}14%{transform:scale(1.5)}30%{transform:scale(1)}}' +
  '@media (max-width:480px){.panel{left:12px;right:12px;bottom:82px;width:auto;max-width:none}.thread{max-height:52vh}}' +
  '@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none !important;transition:none !important}' +
  '.staged .msg{opacity:1 !important;transform:none !important}.typing{display:none !important}}' +
  '</style>' +

  /* S1 · closed launcher — the ONLY thing visible on the host page until clicked */
  '<button class="launcher" type="button" aria-expanded="false" aria-controls="bw-panel">' +
  '<span class="online-dot"></span><span>Book by text</span></button>' +

  '<section class="panel" id="bw-panel" role="dialog" aria-label="Book by text — Demo Barber Co.">' +
  '<div class="panel-head">' +
  '<span class="panel-avatar" aria-hidden="true">DB</span>' +
  '<div class="panel-id">' +
  /* CONFIG: business.name */
  '<strong class="panel-name">Demo Barber Co.</strong>' +
  '<span class="panel-status"><span class="online-dot"></span>online — instant replies</span>' +
  '</div>' +
  '<button class="panel-close" type="button" aria-label="Close chat">×</button>' +
  '</div>' +
  '<div class="thread staged" role="log" aria-live="polite">' +
  /* Thread = Tur A booking.html Flow A, byte-identical. Sources: */
  '<!-- W61 · FRONTEND-ONLY welcome (K4) · SOURCE: SCREEN-INVENTORY §2.1 W61 ({business.name} from config) -->' +
  '<div class="msg bot" data-step="0">Hi! I\'m the Demo Barber Co. assistant — I can book, change or cancel an appointment, or answer questions. How can I help?<span class="stamp">14:00</span></div>' +
  '<!-- MOCK user input -->' +
  '<div class="msg user" data-step="1">Hi — do you have anything Friday afternoon?<span class="stamp">14:00</span></div>' +
  '<!-- W10 · SOURCE: messageTemplates.askService · node: Slot Gate. Chips from config services[]. -->' +
  '<div class="pair"><div class="typing" data-typing="2" aria-hidden="true"><i></i><i></i><i></i></div>' +
  '<div class="msg bot" data-step="2">Which service would you like? (Haircut / Beard Trim / Haircut + Beard)' +
  '<span class="chips"><span class="chip chip-on">Haircut · €25</span><span class="chip">Beard Trim · €15</span><span class="chip">Haircut + Beard · €35</span></span>' +
  '<span class="stamp">14:00</span></div></div>' +
  '<!-- MOCK user input -->' +
  '<div class="msg user" data-step="3">Haircut<span class="stamp">14:01</span></div>' +
  '<!-- W11 · SOURCE: messageTemplates.askDateTime · node: Slot Gate -->' +
  '<div class="pair"><div class="typing" data-typing="4" aria-hidden="true"><i></i><i></i><i></i></div>' +
  '<div class="msg bot" data-step="4">What day and time works for you?<span class="stamp">14:01</span></div></div>' +
  '<!-- MOCK user input -->' +
  '<div class="msg user" data-step="5">Friday at 15:30<span class="stamp">14:02</span></div>' +
  '<!-- W12 · SOURCE: literal in Compute Availability — `${svcName}, ${fmt} — shall I book it? (yes / no)` -->' +
  '<div class="pair"><div class="typing" data-typing="6" aria-hidden="true"><i></i><i></i><i></i></div>' +
  '<div class="msg bot" data-step="6">Haircut, Friday 4 Sep 15:30 — shall I book it? (yes / no)' +
  '<span class="chips"><span class="chip chip-on">yes</span><span class="chip">no</span></span>' +
  '<span class="stamp">14:02</span></div></div>' +
  '<!-- MOCK user input -->' +
  '<div class="msg user" data-step="7">yes<span class="stamp">14:02</span></div>' +
  '<!-- W13 · SOURCE: messageTemplates.bookingConfirmed · node: Build Booked State -->' +
  '<div class="pair"><div class="typing" data-typing="8" aria-hidden="true"><i></i><i></i><i></i></div>' +
  '<div class="msg bot confirm" data-step="8"><strong>✓</strong> You\'re booked: Haircut, Friday 4 Sep 15:30. See you then!<span class="stamp">14:03</span></div></div>' +
  '</div>' +
  /* S3 · reserved Turnstile challenge area (hidden until the challenge is required) */
  '<div class="turnstile-slot" aria-hidden="true"></div>' +
  '<div class="panel-foot" aria-hidden="true">' +
  '<span class="panel-input">Type a message…</span>' +
  '<span class="panel-send">↑</span>' +
  '</div>' +
  '</section>';

  /* ---- behavior: launcher toggle + one-shot staged reveal (MOCK — no network) ---- */
  var launcher = root.querySelector('.launcher');
  var panel = root.querySelector('.panel');
  var closeBtn = root.querySelector('.panel-close');
  var played = false;

  function play() {
    if (played) return;
    played = true;
    var thread = panel.querySelector('.thread');
    var msgs = thread.querySelectorAll('.msg');
    if (reduced) { msgs.forEach(function (m) { m.classList.add('in'); }); return; }
    var t = 350;
    msgs.forEach(function (m) {
      var step = m.getAttribute('data-step');
      var typing = thread.querySelector('.typing[data-typing="' + step + '"]');
      if (typing) {
        (function (ty, on, off) {
          setTimeout(function () { ty.classList.add('on'); }, on);
          setTimeout(function () { ty.classList.remove('on'); }, off);
        })(typing, t, t + 900);
        t += 900;
      }
      (function (mm, at) {
        setTimeout(function () {
          mm.classList.add('in');
          thread.scrollTop = thread.scrollHeight;
        }, at);
      })(m, t);
      t += m.classList.contains('user') ? 700 : 900;
    });
  }

  function setOpen(open) {
    panel.classList.toggle('is-open', open);
    launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) play();
  }

  launcher.addEventListener('click', function () {
    setOpen(!panel.classList.contains('is-open'));
  });
  closeBtn.addEventListener('click', function () {
    setOpen(false);
    launcher.focus();
  });
})();
