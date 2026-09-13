/**
 * The handoff-lock display rule, as a PURE function — one of TWO deliberate copies.
 *
 * WHY IT IS A COPY AT ALL. The site panel (React, `web/site`) and this widget (vanilla, shadow DOM) draw
 * the same conversation with different machinery, and `@salon/shared` deliberately holds no UI state —
 * it is imported by the snippet whose bundle is a contract surface. So the rule is mirrored, and
 * `contract-integrity.md` permits a hand-mirrored copy ONLY with a drift guard committed alongside it:
 * that guard is `tests/unit/locked-once-parity.test.cjs`, which runs BOTH copies over the same sequences
 * and fails if either one moves. Changing this file alone turns the suite red; changing the site's copy
 * alone turns it red too. That is the whole reason this is a function and not four lines inline.
 *
 * ⚠ WHAT THE GUARD DOES **NOT** COVER, said here because the sentence above invites the opposite
 * reading: it guards THIS FILE against its twin, not the two CALL SITES against each other. Deleting
 * `handoffShown = lock.nowShown;` from one caller leaves the suite green (measured, `code-reviewer`
 * 2026-09-13). Returning both decisions instead of just `draw` is what shrank that surface — the caller
 * now performs a mechanical assignment rather than re-deriving a condition — but it did not remove it.
 * Carried as an owned open item rather than left implied.
 *
 * WHAT THE RULE IS. The handoff lock answers EVERY message with the same sentence. Showing it once is
 * the point; showing it five times reads as a broken bot. The signal is the engine's STRUCTURAL `locked`
 * flag — never a comparison of its words against a baked template, because those two configs live in
 * different places and have drifted before (CP5a).
 *
 * ⚠ IT RETURNS BOTH DECISIONS ON PURPOSE. "Draw this line?" and "does this line consume the one-shot?"
 * are different questions, and the first version answered only the first — leaving each caller to
 * re-derive the second with `if (reply.locked) shown = true`, which is a precondition copied into four
 * places. `handoff.md`'s own lesson, one layer up: two copies of a condition drift.
 *
 * ⚠⚠ A `system` LINE IS NEVER SUPPRESSED, AND THIS WAS A REAL HOLE (`security-auditor` M2, 2026-09-13).
 * `chatClient.ts`'s unmapped-response branch returns `kind:'system'` AND carries `locked` through. That
 * path is reachable: `messageTemplates` has no required keys in the committed schema, so a client config
 * missing `handoffLocked` yields `200 + locked:true` with no reply text, which lands in exactly that
 * branch. The visitor then got "something went wrong" once and **total silence on every later message** —
 * `handoff.md` forbids leaving the customer in silence, and `n8n-conventions.md` forbids invisible
 * failures. A transport line is the TRANSPORT speaking, not the shop repeating itself, so it is always
 * drawn and it never burns the one-shot.
 *
 * ⚠ THE OTHER BOUND, easy to get wrong: the flag suppresses only FURTHER LOCK LINES. A normal reply
 * arriving after a lock must still be drawn. A single `if (shown) return` one line too high silences the
 * conversation instead of de-duplicating it.
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
