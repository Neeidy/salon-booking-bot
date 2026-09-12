/**
 * The single most load-bearing piece of logic on this dashboard, and it is four lines of branching.
 *
 * `conversations.last_alert_class` is written by `Record Alert Class` **only after the Telegram send
 * SUCCEEDS** (Codex #5). So an empty value does not mean "no alert was needed". It means one of two
 * things, and they are not the same thing:
 *
 *   | Airtable                                   | What it actually means                    |
 *   |--------------------------------------------|-------------------------------------------|
 *   | `stage=handoff` + class PRESENT             | the owner WAS told, and when              |
 *   | `stage=handoff` + class EMPTY               | the alert was never produced, OR it was   |
 *   |                                            | produced and FAILED TO DELIVER            |
 *   | `stage=handoff` + class present but STALE   | the newest activity has NO delivery on    |
 *   |                                            | record — closer to unconfirmed than to OK  |
 *
 * **If "no alert" and "the alert never arrived" look the same on screen, the dashboard lies to the
 * owner** — and it lies in the safe-looking direction, which is the worst one: a conversation nobody
 * was told about renders as a conversation nobody needed to be told about. SCREEN-INVENTORY §4.c
 * calls this D9's most critical design condition. An empty field is UNCERTAINTY, never good news.
 *
 * ⚠ A NUMBER WAS USED HERE AS PRODUCT EVIDENCE AND IT WAS NOT ONE. The first version said "of 215
 * conversations at `stage='handoff'`, 115 have an empty `last_alert_class` — the majority, not a corner
 * case". All 215 were later shown to be DRILL residue (`reg-`, `cp2-`, `cx8-`…) and were deleted, so
 * that ratio measured our own test traffic, not customer behaviour (`security-auditor`, 2026-09-12).
 * The justification does not need it: `Record Alert Class` writes this field ONLY after a Telegram
 * send succeeds, so an empty value cannot distinguish "never raised" from "raised and never
 * delivered". That is structural, and it is why the empty case must never render as good news.
 *
 * ⚠ THE INFERENCE HERE WAS BACKWARDS AND IS CORRECTED IN PLACE (`code-reviewer`, 2026-09-12). The
 * throttle is 30 minutes on `class:sender`. A delivery timestamp MORE than 30 minutes behind the
 * conversation's last activity means the throttle window had EXPIRED — a new alert was not suppressed,
 * it simply never happened. So `stale` does not mean "throttled"; it means "the newest activity has no
 * delivery on record", which sits closer to `unconfirmed` than to `notified`.
 * The genuinely suppressed case is the opposite one and it renders as `notified` — which is why the
 * label now says WHEN, not "you are up to date": inside the window a second event can be throttled
 * away, and the only honest statement is the timestamp we actually have.
 */

/** Minutes after which a delivered alert is older than the conversation it describes. */
const STALE_AFTER_MINUTES = 30;

export type AlertState =
  | { kind: 'notified'; className: string; at: string }
  | { kind: 'stale'; className: string; at: string; minutesBehind: number }
  | { kind: 'unconfirmed' };

export function alertState(
  lastAlertClass: string | undefined | null,
  lastAlertAt: string | undefined | null,
  lastUpdated: string | undefined | null,
): AlertState {
  const cls = (lastAlertClass ?? '').trim();
  // No class, or a class with no delivery timestamp: we cannot say the owner was told. Both collapse
  // to the same honest answer rather than to the comfortable one.
  if (!cls) return { kind: 'unconfirmed' };
  const at = (lastAlertAt ?? '').trim();
  if (!at) return { kind: 'unconfirmed' };

  const alertMs = Date.parse(at);
  const convMs = Date.parse((lastUpdated ?? '').trim());
  if (!Number.isFinite(alertMs)) return { kind: 'unconfirmed' };
  if (!Number.isFinite(convMs)) return { kind: 'notified', className: cls, at };

  // Compare first, round for display second: rounding first made a 30.4-minute gap read as exactly 30
  // and fall on the wrong side of the boundary (code-reviewer A2).
  const behindMs = convMs - alertMs;
  const minutesBehind = Math.round(behindMs / 60_000);
  if (behindMs >= STALE_AFTER_MINUTES * 60_000) {
    return { kind: 'stale', className: cls, at, minutesBehind };
  }
  return { kind: 'notified', className: cls, at };
}

/**
 * The sentence the owner reads. Kept beside the logic ON PURPOSE: the whole defect this module exists
 * to prevent is a state and its wording drifting apart, so they are changed in one place or not at all.
 */
export function alertLabel(s: AlertState): string {
  switch (s.kind) {
    case 'notified': {
      // Deliberately not "you have been told about this". Inside the throttle window a later event
      // can be suppressed, so what is known is the time of the LAST delivery and its class.
      // Clamped at zero: if this server's clock sits behind the stored timestamp the subtraction goes
      // negative and the owner reads "last notified -7 min ago", which is not a fact about anything.
      const mins = Math.round((Date.now() - Date.parse(s.at)) / 60_000);
      if (!Number.isFinite(mins)) return `notified — ${s.className}`;
      if (mins < 0) return `last notified just now — ${s.className}`;
      return `last notified ${mins} min ago — ${s.className}`;
    }
    case 'stale':
      // Not "notified": the alert predates the conversation's own last activity, so it describes an
      // EARLIER moment. Saying "notified" here would be true about the past and false about now.
      return `last notified ${s.minutesBehind} min before the latest message — ${s.className}`;
    case 'unconfirmed':
      // Deliberately not "no alert". We do not know that. `Record Alert Class` writes only on a
      // SUCCESSFUL send, so silence here covers both "never raised" and "raised and never delivered".
      return 'notification NOT confirmed';
  }
}

/**
 * Ordering for the queue: the rows nobody can prove were delivered come first.
 *
 * This is not cosmetic. The owner triages from the top, and the rows most likely to have been missed
 * are precisely the ones with no delivery on record.
 */
export function triageRank(s: AlertState): number {
  return s.kind === 'unconfirmed' ? 0 : s.kind === 'stale' ? 1 : 2;
}
