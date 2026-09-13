/**
 * The handoff-lock display rule — the SITE's copy. See `web/snippet/src/lockedOnce.ts` for the full
 * reasoning and for why there are two (`tests/unit/locked-once-parity.test.cjs` fails if EITHER copy
 * moves on its own).
 *
 * This copy exists because the site panel had NO lock handling at all: `LiveChatPanel` never read
 * `reply.locked`, so a locked conversation repeated the same handoff sentence on every message while the
 * snippet showed it once — the two surfaces had silently diverged (6b carry-over, closed in CP 6c-3).
 *
 * The two bounds that are NOT obvious and must stay identical in both copies:
 *   - a `system` line is the TRANSPORT speaking and is never suppressed (and never burns the one-shot);
 *     the unmapped-response branch of `chatClient.ts` returns `kind:'system'` WITH `locked` set, and
 *     suppressing it left the visitor in silence (`security-auditor` M2, 2026-09-13);
 *   - the flag suppresses only further LOCK lines — a normal reply after a lock is still drawn.
 *
 * ⚠ The parity guard covers THESE TWO FILES, not the two call sites: removing
 * `handoffShown.current = lock.nowShown;` from `LiveChatPanel` leaves the suite green (measured).
 */
export interface LockDecision {
  /** Draw this reply at all? */
  draw: boolean;
  /** The value the caller's one-shot flag should carry AFTER this reply. */
  nowShown: boolean;
}

export function lockLineDecision(
  reply: { locked?: boolean; kind?: string },
  alreadyShown: boolean,
): LockDecision {
  // The transport speaking. Always drawn, never consumes the one-shot.
  if (reply.kind === 'system') return { draw: true, nowShown: alreadyShown };
  // Not a lock line at all.
  if (!reply.locked) return { draw: true, nowShown: alreadyShown };
  // A lock line: drawn only the first time, and only a DRAWN one burns the one-shot.
  if (alreadyShown) return { draw: false, nowShown: true };
  return { draw: true, nowShown: true };
}
