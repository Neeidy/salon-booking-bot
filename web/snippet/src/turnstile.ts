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
function whenVisible(el: HTMLElement, timeoutMs = 10000): Promise<boolean> {
  const visible = () => !!el.offsetParent && el.getBoundingClientRect().width > 0;
  if (visible()) return Promise.resolve(true);
  return new Promise((resolve) => {
    let done = false;
    let timedOut = false;
    const finish = () => { if (!done) { done = true; clearInterval(iv); ro.disconnect(); clearTimeout(t); resolve(!timedOut); } };
    const ro = new ResizeObserver(() => { if (visible()) finish(); });
    ro.observe(el);
    // Backstop: a ResizeObserver can miss a display:none -> flex flip in some engines.
    const iv = setInterval(() => { if (visible()) finish(); }, 200);
    // Give up rather than hang. ⚠ Resolving on timeout means we render into a container that never
    // became visible — which is HARMLESS in Invisible mode (measured: a hidden container still mints a
    // token) and UNMEASURED in Managed, where a challenge drawn into a 0-height box may be unsolvable.
    // The earlier comment here claimed this path "reports trouble"; it did not report anything, so it
    // now logs, and the promise says WHICH way it finished instead of hiding the difference.
    const t = setTimeout(() => { timedOut = true; finish(); }, timeoutMs);
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
  let blocked = false;

  onChange('pending');
  loadScript()
    .then(async () => {
      const becameVisible = await whenVisible(slot);
      if (!becameVisible) {
        // Not fatal — Invisible mode works from a hidden container — but it must not be invisible to US.
        console.warn('[widget] the Turnstile slot never became visible; rendering anyway. '
          + 'In Managed mode an interactive challenge here may not be solvable.');
      }
      if (!window.turnstile) throw new Error('turnstile_unavailable');
      widgetId = window.turnstile.render(slot, {
        sitekey: siteKey,
        callback: (t: string) => { token = t; onChange('ready'); },
        'error-callback': () => { token = null; blocked = true; onChange('blocked'); },
        'expired-callback': () => { token = null; onChange('pending'); window.turnstile?.reset(widgetId ?? undefined); },
        'timeout-callback': () => { token = null; onChange('pending'); window.turnstile?.reset(widgetId ?? undefined); },
        theme: 'light',
      });
    })
    .catch(() => { token = null; blocked = true; onChange('blocked'); });

  return {
    token: () => token,
    refresh: () => {
      token = null;
      // Do not overwrite a real failure with "Verifying…": if the challenge is blocked, the visitor
      // needs the honest message to stay on screen rather than an optimistic one that never resolves.
      if (blocked) return;
      onChange('pending');
      if (widgetId && window.turnstile) window.turnstile.reset(widgetId);
    },
  };
}
