'use client';
/**
 * The LIVE widget panel — real conversation against the engine's webhook.
 *
 * Replaces the static transcription for slice 2. What stays from the design contract: the panel markup
 * and class names, the reserved Turnstile slot (S3), the W61 frontend welcome (the engine produces no
 * greeting), and `role="log" aria-live="polite"` on the thread — unlike the hero, this one IS a live log
 * and its updates SHOULD be announced.
 *
 * Reply text comes from lib/chatClient: the engine's own text wins whenever it sends any; config
 * templates fill only the two branches where it deliberately sends none.
 */
import { useEffect, useRef, useState } from 'react';
import type { ClientConfig } from '@salon/shared/config';
import {
  sendMessage, getSessionId, newMessageId, FRONTEND_TEXT,
  type ChatReply, type EndpointConfig,
} from '../../lib/chatClient';
import { TurnstileWidget, type TurnstileState } from './TurnstileWidget';

interface Bubble { from: 'bot' | 'user' | 'system'; text: string; stamp: string }

const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export function LiveChatPanel({ config, endpoint }: { config: ClientConfig; endpoint: EndpointConfig }) {
  const name = config.business.name;
  const initials = name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

  // W61 — FRONTEND welcome (K4=B). The engine emits no greeting; this line has no engine counterpart
  // and must never be presented as something the bot said.
  // NOTE: the stamp starts EMPTY on purpose. This is a client component, but Next still renders it on
  // the server for the initial HTML, and a clock value computed in both places produces different text —
  // a hydration mismatch (React #418), which in turn broke the effect that mounts Turnstile. The time is
  // filled in after mount, where server and client can no longer disagree.
  const [thread, setThread] = useState<Bubble[]>([{
    from: 'bot',
    text: `Hi! I'm the ${name} assistant — I can book, change or cancel an appointment, or answer questions. How can I help?`,
    stamp: '',
  }]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [tsState, setTsState] = useState<TurnstileState>('loading');
  const [resetSignal, setResetSignal] = useState(0);
  const sessionId = useRef<string>('');
  const threadRef = useRef<HTMLDivElement>(null);

  // A Turnstile error must not dead-end the visitor. Cloudflare's 600010 family is transient in many
  // environments (a blocked resource, a slow network, an extension), so retry a couple of times before
  // giving up — and never lock the input on account of it: the send path already refuses without a
  // token and says so, which is honest without making the widget unusable until a reload.
  const retries = useRef(0);
  useEffect(() => {
    if (tsState !== 'error' || retries.current >= 2) return;
    retries.current += 1;
    const id = setTimeout(() => setResetSignal((n) => n + 1), 2500);
    return () => clearTimeout(id);
  }, [tsState]);

  useEffect(() => {
    sessionId.current = getSessionId();
    setThread((t) => (t.length === 1 && t[0].stamp === '' ? [{ ...t[0], stamp: now() }] : t));
  }, []);
  useEffect(() => { threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight }); }, [thread, busy]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;

    if (!token) {
      // Fail-closed on OUR side too: without a token the engine returns 403, so say something true
      // rather than firing a request we know will be rejected.
      setThread((t) => [...t, { from: 'system', text: FRONTEND_TEXT.blocked, stamp: now() }]);
      return;
    }

    setThread((t) => [...t, { from: 'user', text, stamp: now() }]);
    setDraft('');
    setBusy(true);
    let reply: ChatReply;
    try {
      reply = await sendMessage(endpoint, config, text, sessionId.current, token, newMessageId());
    } finally {
      setBusy(false);
      setToken(null);
      setResetSignal((n) => n + 1);   // a token is single-use — mint the next one
    }
    if (reply.kind === 'silent') return;      // duplicate_ignored is deliberately screenless (W56)
    setThread((t) => [...t, { from: reply.kind === 'system' ? 'system' : 'bot', text: reply.text, stamp: now() }]);
  }

  return (
    <section className="site-panel" id="site-panel" data-turnstile={tsState} role="dialog" aria-label={`Book by text — ${name}`}>
      <div className="panel-head">
        <span className="panel-avatar" aria-hidden="true">{initials}</span>
        <div className="panel-id">
          <strong className="panel-name">{name}</strong>
          <span className="panel-status"><span className="online-dot" />online — instant replies</span>
        </div>
        <button className="panel-close" type="button" data-close aria-label="Close chat">×</button>
      </div>

      <div className="thread" role="log" aria-live="polite" ref={threadRef}>
        {thread.map((b, i) => (
          // `in` is REQUIRED, not decoration: the transcribed CSS hides `.site-panel .thread .msg`
          // (opacity:0) until it is present — the staged reveal added it for the scripted demo. Live
          // bubbles have no staged reveal, so they must carry it from the start or they render
          // INVISIBLE while still being in the DOM and readable to a text-based test.
          <div className={`msg in ${b.from === 'system' ? 'bot' : b.from}`} key={i}>
            {b.text}<span className="stamp">{b.stamp}</span>
          </div>
        ))}
        {busy && <div className="typing in" aria-hidden="true"><i /><i /><i /></div>}
      </div>

      <TurnstileWidget
        siteKey={endpoint.turnstileSiteKey}
        onToken={setToken}
        onState={setTsState}
        resetSignal={resetSignal}
      />

      <form className="panel-foot" onSubmit={submit}>
        <input
          className="panel-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={tsState === 'error' ? 'Verification is having trouble — retrying…' : 'Type a message…'}
          aria-label="Message"
          disabled={busy}
          maxLength={1000}
        />
        <button className="panel-send" type="submit" aria-label="Send" disabled={busy || !draft.trim()}>↑</button>
      </form>
    </section>
  );
}
