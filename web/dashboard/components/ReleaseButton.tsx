'use client';
/**
 * D11 — the two-step release, built to the behaviour SCREEN-INVENTORY §454 and the design mockup declare:
 * `release-btn` → `confirming` → yes/no, "no accidental clicks".
 *
 * WHY TWO STEPS FOR A REVERSIBLE WRITE: it is reversible in the store and NOT reversible for the customer —
 * releasing a conversation hands it back to the bot mid-handoff, and whatever the human was about to say
 * is replaced by an automated reply. The confirm is about the person on the other end, not the row.
 *
 * ⚠ ITS PROPS ARE A RECORD ID (`rec` + 14, kept by the migration, Q3) AND AN ALREADY-MASKED LABEL. No `sender_key`, masked or not, and
 * no message text. That matters because `check-client-imports.cjs` would catch a server-only IMPORT here
 * and would NOT catch a PII PROP — props land in the RSC payload, in the page source, with no gate firing
 * (CRT #10b). The bound is kept by hand, here, in writing, because nothing else keeps it.
 */
import { useState } from 'react';
import { screenReason } from '../lib/releaseReason.ts';

type Phase = 'idle' | 'confirming' | 'sending' | 'done' | 'failed';

/** Every failure the engine can produce says its own true thing. One generic message is a silence. */
const MESSAGE: Record<string, string> = {
  released: 'Released — the bot will answer the next message.',
  not_locked: 'Nothing to release: this conversation is not in handoff any more.',
  not_found: 'That conversation is no longer in the store.',
  refused: 'The request was refused. Check that this board is signing with the right key.',
  stale: 'That took too long to confirm — press release again.',
  // ⚠ THIS LINE USED TO SAY "Nothing was changed." and that is a claim nobody can make (Codex CRT #11).
  // The request may have reached the engine and written before the answer was lost — an unanswered call and
  // an unobserved success look identical from here. `honesty-demos.md`: a visible gap beats a hidden one,
  // and the gap is the whole point for the person deciding whether to press it again.
  unreachable: 'The engine did not answer, so this board cannot tell whether the release happened. Reload before pressing again.',
  // A 502: the engine reported the release write as failed, or the edge answered on its own. Neither proves
  // the lock is still closed, so the line says "may not" and sends the owner to look before trying again.
  release_failed: 'The release may not have happened (502). Reload and check this conversation before pressing again.',
  // A 503 whose body names the store: the engine could not read it and stopped before any write. This is the
  // one failure that can honestly say nothing changed; every other 503 is `unreachable` above.
  store_unavailable: 'Nothing was written — the store could not be read. Try again in a moment.',
  misconfigured: 'This board is not configured to write. Nothing was sent.',
  bad_request: 'The request was malformed and was not sent.',
  // The route's own same-origin check refused the request before reading it; the engine was never called.
  forbidden: 'This board refused the request as not coming from its own page. Nothing was sent.',
  // A DEGRADED success. The lock IS open — saying only "released" would hide the half that failed, and the
  // owner is the one person who needs to know the notification never arrived.
  released_no_alert: 'Released — but the owner notification could not be delivered, so nobody was told by message.',
  // Any other degraded value — an engine that still reports the old marker failure, or one newer than this board.
  released_degraded: 'Released — but part of the follow-up did not complete. Check the engine alert.',
};

export function ReleaseButton({ recordId, label }: { recordId: string; label: string }) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [reason, setReason] = useState<string>('');

  async function send() {
    setPhase('sending');
    try {
      const res = await fetch('/api/release', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // A fresh id per CLICK, not per render: the engine deduplicates on it, so reusing one would make a
        // deliberate second release look like a replay and silently do nothing.
        body: JSON.stringify({ recordId, messageId: `d11-${Date.now()}-${Math.random().toString(36).slice(2, 8)}` }),
      });
      // The route now answers with a REAL status, so a non-2xx with an unreadable body is still a failure
      // and must not be read as a success by default.
      let data: { ok?: boolean; reason?: string; degraded?: string } = {};
      try { data = (await res.json()) as typeof data; } catch { data = {}; }
      setReason(screenReason(data));
      setPhase(data.ok === true ? 'done' : 'failed');
    } catch {
      setReason('unreachable');
      setPhase('failed');
    }
  }

  if (phase === 'done' || phase === 'failed') {
    return <span className="tech">{MESSAGE[reason] ?? MESSAGE.unreachable}</span>;
  }

  if (phase === 'sending') return <span className="tech">Releasing…</span>;

  if (phase === 'confirming') {
    return (
      <span className="tech">
        Hand {label} back to the bot?{' '}
        <button type="button" onClick={() => void send()}>Yes, release</button>{' '}
        <button type="button" onClick={() => setPhase('idle')}>Cancel</button>
      </span>
    );
  }

  return (
    <button type="button" onClick={() => setPhase('confirming')}>Release to the bot</button>
  );
}
