'use client';
// Runs the transcribed motion engine once on mount, feeding it the SELF-HOSTED gsap from npm instead
// of the mockup's cdnjs <script> tags. No third-party runtime request: gsap is bundled and served
// from our own origin (ROADMAP named item, Tur B 2026-09-02).
//
// The engine reads window.gsap / window.ScrollTrigger and degrades gracefully when they are missing,
// so this stays a progressive enhancement — the page is complete without it.
import { useEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { runMotionEngine } from './motion-engine.js';

export function SiteMotion() {
  useEffect(() => {
    // The mockup's contract is "the page is fully functional if any of these fail". In a plain HTML
    // page a throwing script just stops; inside a React effect an uncaught throw unmounts the ROOT and
    // BLANKS THE PAGE — which is exactly what happened when the panel was missing a [data-close] hook.
    // The animation layer must never be able to take the content down with it.
    try {
      const w = window as unknown as Record<string, unknown>;
      w.gsap = gsap;
      w.ScrollTrigger = ScrollTrigger;
      runMotionEngine();
    } catch (err) {
      // Visible, never silent: the page keeps working, the failure is reported.
      console.error('[site] motion engine failed — page continues without animation:', err);
    }
  }, []);
  return null;
}
