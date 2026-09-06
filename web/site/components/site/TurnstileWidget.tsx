'use client';
/**
 * Cloudflare Turnstile — renders the challenge and hands back a token.
 *
 * ⚠ DELIBERATE EXCEPTION to this phase's "no third-party runtime dependency" rule. GSAP and the fonts
 * were pulled off CDNs and self-hosted; Turnstile CANNOT be. It is a challenge SERVICE — the script must
 * run from Cloudflare or there is no bot protection at all. So the public page keeps exactly one
 * third-party script, and it is the one whose whole purpose is to be third-party. Recorded in ARCH-DEC.
 *
 * TOKEN LIFECYCLE: a Turnstile token is SINGLE-USE and short-lived, and the engine runs its gate on
 * EVERY request — so a fresh token is needed per message, not per session. After each send we reset the
 * widget to mint the next one.
 */
import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (id?: string) => void;
      remove: (id?: string) => void;
    };
    __turnstileScriptLoading?: Promise<void>;
  }
}

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (window.__turnstileScriptLoading) return window.__turnstileScriptLoading;
  window.__turnstileScriptLoading = new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Turnstile script failed to load'));
    document.head.appendChild(s);
  });
  return window.__turnstileScriptLoading;
}

export type TurnstileState = 'loading' | 'ready' | 'error';

export function TurnstileWidget({
  siteKey,
  onToken,
  onState,
  resetSignal,
}: {
  siteKey: string;
  onToken: (token: string | null) => void;
  onState: (s: TurnstileState) => void;
  /** Increment to mint a fresh token after a send. */
  resetSignal: number;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const idRef = useRef<string | null>(null);
  const [mounted, setMounted] = useState(false);

  /**
   * Wait until the slot is actually VISIBLE before rendering.
   * MEASURED (2026-09-06): the panel starts `display:none`, so on mount the slot is 0x0. Turnstile
   * accepted the render call, marked the container as used ("already been rendered in this container")
   * and produced NO iframe and NO token — a silent dead widget. Rendering into a hidden container is
   * the defect; waiting for a real box is the fix.
   */
  function whenVisible(el: HTMLElement): Promise<void> {
    // offsetParent is null exactly when the element (or an ancestor) is display:none — which is the
    // real condition we care about. An earlier version waited for height > 0 and DEADLOCKED: the slot
    // only gains height once Turnstile fills it, so it waited for the thing it was gating.
    const visible = () => !!el.offsetParent && el.getBoundingClientRect().width > 0;
    if (visible()) return Promise.resolve();
    return new Promise((resolve) => {
      const ro = new ResizeObserver(() => { if (visible()) { ro.disconnect(); resolve(); } });
      ro.observe(el);
      // The panel is opened by the transcribed motion engine (a class change), not by React, so also
      // poll as a backstop — a ResizeObserver can miss a display:none -> flex flip in some engines.
      const iv = setInterval(() => { if (visible()) { clearInterval(iv); ro.disconnect(); resolve(); } }, 250);
    });
  }

  useEffect(() => {
    let cancelled = false;
    onState('loading');
    loadScript()
      .then(async () => {
        if (cancelled || !hostRef.current) return;
        await whenVisible(hostRef.current);
        if (cancelled || !hostRef.current || !window.turnstile) return;
        idRef.current = window.turnstile.render(hostRef.current, {
          sitekey: siteKey,
          callback: (token: string) => { onToken(token); onState('ready'); },
          'error-callback': () => { onToken(null); onState('error'); },
          'expired-callback': () => { onToken(null); window.turnstile?.reset(idRef.current ?? undefined); },
          'timeout-callback': () => { onToken(null); window.turnstile?.reset(idRef.current ?? undefined); },
          theme: 'light',
        });
        setMounted(true);
      })
      .catch(() => { if (!cancelled) { onToken(null); onState('error'); } });
    return () => {
      cancelled = true;
      if (idRef.current && window.turnstile) window.turnstile.remove(idRef.current);
      idRef.current = null;
    };
    // siteKey is build-time constant; the callbacks are stable refs from the parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteKey]);

  useEffect(() => {
    if (!mounted || resetSignal === 0) return;
    onToken(null);
    window.turnstile?.reset(idRef.current ?? undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetSignal]);

  // The reserved slot the approved design already carries (S3): Cloudflare draws its own widget here.
  return <div className="turnstile-slot on" ref={hostRef} />;
}
