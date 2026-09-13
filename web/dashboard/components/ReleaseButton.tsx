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
  unreachable: 'The engine did not answer. Nothing was changed.',
  misconfigured: 'This board is not configured to write. Nothing was sent.',
  bad_request: 'The request was malformed and was not sent.',
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
      const data = (await res.json()) as { ok?: boolean; reason?: string };
      setReason(data.reason ?? 'unreachable');
      setPhase(data.ok ? 'done' : 'failed');
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
