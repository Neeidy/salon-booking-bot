'use client';
/**
 * D11 — the two-step release, built to the behaviour SCREEN-INVENTORY §454 and the design mockup declare:
 * `release-btn` → `confirming` → yes/no, "no accidental clicks".
 *
 * WHY TWO STEPS FOR A REVERSIBLE WRITE: it is reversible in Airtable and NOT reversible for the customer —
 * releasing a conversation hands it back to the bot mid-handoff, and whatever the human was about to say
 * is replaced by an automated reply. The confirm is about the person on the other end, not the row.
 *
 * ⚠ ITS PROPS ARE AN AIRTABLE RECORD ID AND AN ALREADY-MASKED LABEL. No `sender_key`, masked or not, and
 * no message text. That matters because `check-client-imports.cjs` would catch a server-only IMPORT here
 * and would NOT catch a PII PROP — props land in the RSC payload, in the page source, with no gate firing
 * (CRT #10b). The bound is kept by hand, here, in writing, because nothing else keeps it.
 */
import { useState } from 'react';

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
  misconfigured: 'This board is not configured to write. Nothing was sent.',
  bad_request: 'The request was malformed and was not sent.',
  // A DEGRADED success. The lock IS open — saying only "released" would hide the half that failed, and the
  // owner is the one person who needs to know the notification never arrived.
  released_no_alert: 'Released — but the owner notification could not be delivered, so nobody was told by message.',
  released_no_marker: 'Released — but the duplicate-guard record was not written, so pressing again could write a second time.',
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
      setReason(data.degraded === 'alert_undelivered' ? 'released_no_alert'
              : data.degraded === 'marker_unwritten' ? 'released_no_marker'
              : data.reason ?? 'unreachable');
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
