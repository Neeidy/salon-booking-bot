/**
 * Cloudflare Turnstile, mounted INSIDE the shadow root.
 *
 * This file is written from what the Phase-6b spike actually measured, not from what the 6a code
 * assumed. Three findings shape it:
 *
 * 1. RENDERING INTO THE SHADOW ROOT WORKS. Measured in a real browser with a real site key: the widget
 *    draws inside an open shadow root and mints a token, in Invisible and in Managed mode, and with a
 *    forced-interactive challenge it is drawn visibly there AND solvable there. No light-DOM overlay is
 *    needed; that fallback was retired on evidence.
 *
 * 2. IFRAME PRESENCE CANNOT BE OBSERVED, so this file never tries. Turnstile hosts its widget in a
 *    CLOSED shadow root: `querySelector('iframe')` returns null while the challenge is plainly on
 *    screen. Any check built on it reports false and means nothing — 6a's harness did exactly that.
 *    What IS observable is whether Cloudflare's container acquired a real box.
 *
 * 3. WAIT FOR A VISIBLE SLOT BEFORE RENDERING. In Invisible mode a hidden container still mints a token,
 *    so this wait is not what makes Invisible work. It is load-bearing for MANAGED: an interactive
 *    challenge drawn into a 0-height box is one the visitor can never solve, and the widget would hang
 *    with no way out. The mode is the client's choice, so the widget must be correct in both.
 *    `offsetParent` is usable here — measured — because the slot sits inside the position:fixed panel,
 *    which is a positioned ancestor within the same shadow tree. It would NOT be usable if the slot were
 *    itself the fixed element (a fixed element's offsetParent is null even when visible).
 *
 * A TOKEN IS SINGLE-USE and the engine gates every request, so a fresh one is minted per message.
 */

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (id?: string) => void;
      remove: (id?: string) => void;
    };
    __barberTurnstileLoading?: Promise<void>;
  }
}

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

/**
 * DELIBERATE EXCEPTION to "no third-party runtime dependency". Turnstile is a challenge SERVICE — its
 * script must run from Cloudflare or there is no bot protection at all. It is the one third-party
 * script the widget loads, and it is the one whose entire purpose is to be third-party.
 */
function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (window.__barberTurnstileLoading) return window.__barberTurnstileLoading;
  window.__barberTurnstileLoading = new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('turnstile_script_blocked'));
    document.head.appendChild(s);
  });
  return window.__barberTurnstileLoading;
}

/** Resolves once the element has a real box, or after `timeoutMs` — never deadlocks. */
function whenVisible(el: HTMLElement, timeoutMs = 10000): Promise<void> {
  const visible = () => !!el.offsetParent && el.getBoundingClientRect().width > 0;
  if (visible()) return Promise.resolve();
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (!done) { done = true; clearInterval(iv); ro.disconnect(); clearTimeout(t); resolve(); } };
    const ro = new ResizeObserver(() => { if (visible()) finish(); });
    ro.observe(el);
    // Backstop: a ResizeObserver can miss a display:none -> flex flip in some engines.
    const iv = setInterval(() => { if (visible()) finish(); }, 200);
    // Give up rather than hang: a widget that never renders is worse than one that reports trouble.
    const t = setTimeout(finish, timeoutMs);
  });
}

export interface TurnstileHandle {
  /** A token, or null while none is available. */
  token(): string | null;
  /** Discard the used token and mint the next one. */
  refresh(): void;
}

export function mountTurnstile(
  slot: HTMLElement,
  siteKey: string,
  onChange: (state: 'pending' | 'ready' | 'blocked') => void,
): TurnstileHandle {
  let token: string | null = null;
  let widgetId: string | null = null;

  onChange('pending');
  loadScript()
    .then(async () => {
      await whenVisible(slot);
      if (!window.turnstile) throw new Error('turnstile_unavailable');
      widgetId = window.turnstile.render(slot, {
        sitekey: siteKey,
        callback: (t: string) => { token = t; onChange('ready'); },
        'error-callback': () => { token = null; onChange('blocked'); },
        'expired-callback': () => { token = null; onChange('pending'); window.turnstile?.reset(widgetId ?? undefined); },
        'timeout-callback': () => { token = null; onChange('pending'); window.turnstile?.reset(widgetId ?? undefined); },
        theme: 'light',
      });
    })
    .catch(() => { token = null; onChange('blocked'); });

  return {
    token: () => token,
    refresh: () => {
      token = null;
      onChange('pending');
      if (widgetId && window.turnstile) window.turnstile.reset(widgetId);
    },
  };
}
