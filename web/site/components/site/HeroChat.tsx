'use client';
/**
 * Hero demo conversation with FOUR rotating scenarios (booking · cancelling · questions · handoff).
 *
 * WHY ROTATE: most visitors never open the widget. A single scenario makes the bot look like it only
 * takes bookings; the fourth scenario in particular shows its LIMIT — that it hands over to a person —
 * which is the one screen that builds trust without praising the bot.
 *
 * ACCESSIBILITY — deliberate deviation from the mockup, approved 2026-09-03:
 * the mockup marked this region `role="log" aria-live="polite"`. With rotation that would announce four
 * scripted conversations to a screen-reader user every few seconds. This is a pre-written EXAMPLE, not a
 * live log, so the live region is removed and the region is labelled instead. The real widget PANEL keeps
 * role="log" aria-live="polite" — it will receive actual messages in slice 2.
 *
 * Rotation stops entirely under prefers-reduced-motion, and pauses on hover/focus. With JS disabled the
 * first scenario is the only one rendered visible by CSS, so the hero still reads.
 */
import { useEffect, useState } from 'react';
import type { Scenario } from '../../lib/heroScenarios';

const HOLD_MS = 9000;

export function HeroChat({ scenarios, brand }: { scenarios: Scenario[]; brand: string }) {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return; // never rotates
    if (paused) return;
    const id = setTimeout(() => setActive((i) => (i + 1) % scenarios.length), HOLD_MS);
    return () => clearTimeout(id);
  }, [active, paused, scenarios.length]);

  const initials = brand.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

  return (
    <div
      className="chat-window"
      id="chat"
      aria-label="Sample conversation"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="chat-head">
        <span className="chat-avatar" aria-hidden="true">{initials}</span>
        <div className="chat-id">
          <strong className="chat-name">{brand}</strong>
          <span className="chat-status"><span className="online-dot" />online — instant replies</span>
        </div>
      </div>

      {scenarios.map((sc, i) => (
        <div
          key={sc.id}
          className={`chat-body scenario${i === active ? ' is-active' : ''}`}
          data-scenario={sc.id}
          // The inactive scenarios stay in the DOM (so the markup is complete without JS) but are
          // hidden from assistive tech as well as from sight — otherwise a screen reader would read
          // all four conversations back to back as one nonsensical thread.
          aria-hidden={i === active ? undefined : true}
        >
          {sc.bubbles.map((b, j) => (
            <div key={j} className={`msg ${b.from}${b.confirm ? ' bot confirm' : ''}`.replace('bot bot', 'bot')}>
              {b.confirm && <strong>✓</strong>}{b.confirm ? ' ' : ''}{b.text}
              {b.chips && (
                <span className="slots">
                  {b.chips.map((c, k) => <span className={k === 0 ? 'chip chip-on' : 'chip'} key={c}>{c}</span>)}
                </span>
              )}
              <span className="stamp">{b.stamp}</span>
            </div>
          ))}
        </div>
      ))}

      <div className="chat-foot" aria-hidden="true">
        <span className="chat-input">Type a message…</span>
        <span className="chat-send">↑</span>
      </div>
    </div>
  );
}
