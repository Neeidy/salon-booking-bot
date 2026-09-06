/**
 * Widget transport — the browser's side of POST <NEXT_PUBLIC_WEBHOOK_URL>.
 *
 * THE REPLY-TEXT RULE (derived from the committed workflow, not from the plan's summary):
 * the engine's widget body is the VERBATIM original response (a contract locked in CP4b-1, "the widget
 * body stays bit-identical"), so what comes back varies by branch:
 *   • success            200 { channel, sender_key, reply }                      → reply PRESENT
 *   • handoff / lock     200 { ok, handoff, reply }                              → reply PRESENT
 *   • spend-cap          200 { ok, handoff, reply }                              → reply PRESENT
 *   • llm/lead/calendar  503 { ok:false, error:…, reply }                         → reply PRESENT
 *   • invalid payload    400 { ok:false, error:'invalid_payload', handoff:true }  → NO reply
 *   • state unavailable  503 { ok:false, error:'state_unavailable', handoff:true }→ NO reply
 *   • duplicate          200 { status:'duplicate_ignored' }                       → NO reply, NO screen
 *   • turnstile / sig    403 { ok:false, error:'turnstile_failed' }               → NO reply
 *
 * So the rule is: WHENEVER THE ENGINE SENDS TEXT, SHOW THAT TEXT. Only fill in from config where the
 * engine deliberately sends none. Applying the UX-ARCH K4 table literally to every failure would have
 * REPLACED the engine's own wording (e.g. llm_unavailable's reply) with a generic mapping — losing
 * information the bot meant to give.
 */
import type { ClientConfig } from '@salon/shared/config';

export type ReplyKind = 'bot' | 'system' | 'silent';
export interface ChatReply {
  kind: ReplyKind;
  /** Text to render. Empty when kind === 'silent'. */
  text: string;
  /** Where the text came from — for the drills and for honest reporting, never shown to a visitor. */
  origin: 'engine' | 'config' | 'frontend';
  status: number;
  error?: string;
}

export interface EndpointConfig { webhookUrl: string; turnstileSiteKey: string }

/** Fixed frontend strings — the transport/security layer speaking, not the shop (SCREEN-INVENTORY §2.10.1). */
export const FRONTEND_TEXT = {
  blocked: "We couldn't verify this browser. Please reload the page and try again.",
  offline: "That didn't reach us — check your connection and try again.",
  timeout: "That took too long to answer. Please try again.",
  unexpected: 'Something went wrong on our side. Please try again in a moment.',
} as const;

/** A client-generated conversation id. Session-token strength, NOT verified identity (accepted T1 limit). */
/**
 * Per-message id — the IDEMPOTENCY key. `Validate Payload` requires a non-empty `message_id`, so a widget
 * that omits it gets 400 invalid_payload for every message (measured against the live endpoint before
 * this was added). `Normalize Inbound` reads `messageId` or `message_id` from the widget body.
 * A fresh id per SEND (not per retry) is what makes a duplicate delivery collapse to one booking.
 */
export function newMessageId(): string {
  return 'm-' + (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36));
}

export function getSessionId(): string {
  const KEY = 'barber_widget_session';
  try {
    const existing = sessionStorage.getItem(KEY);
    if (existing) return existing;
    const id = 'w-' + (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36));
    sessionStorage.setItem(KEY, id);
    return id;
  } catch {
    // Storage blocked → a per-load id. The conversation still works; it just does not survive a reload.
    return 'w-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }
}

export function readEndpointConfig(): EndpointConfig | null {
  const webhookUrl = process.env.NEXT_PUBLIC_WEBHOOK_URL;
  const turnstileSiteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  if (!webhookUrl || !turnstileSiteKey) return null;   // caller degrades visibly, never silently
  return { webhookUrl, turnstileSiteKey };
}

export async function sendMessage(
  endpoint: EndpointConfig,
  cfg: ClientConfig,
  text: string,
  sessionId: string,
  turnstileToken: string,
  messageId: string,
  timeoutMs = 20000,
): Promise<ChatReply> {
  const t = cfg.messageTemplates as Record<string, string>;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(endpoint.webhookUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sessionId, messageId, text, turnstileToken }),
      signal: ctrl.signal,
    });
  } catch (e) {
    // Distinguish the failure instead of collapsing every throw into "check your connection".
    // A timeout, a CORS rejection and a blocking extension are three different problems, and one
    // message for all three hides which one the visitor (or we) actually hit. The customer still sees
    // one plain sentence; the DETAIL goes to the console, where a drill can read it.
    const err = e as Error;
    const aborted = err?.name === 'AbortError';
    // SELF-DIAGNOSIS. A thrown fetch has two very different causes and the browser refuses to tell them
    // apart for security reasons. A follow-up `no-cors` probe does tell them apart: it resolves (opaque)
    // whenever the request actually REACHED a server, and throws only when it never left the machine.
    //   reached=true  -> the response carried no CORS headers (e.g. an edge block/challenge page)
    //   reached=false -> blocked before the wire (extension, DNS, offline, firewall)
    if (!aborted) {
      void fetch(endpoint.webhookUrl, { method: 'POST', mode: 'no-cors', body: '{}' })
        .then(() => console.error('[widget] diagnosis: request REACHED the server, but its response had no '
          + 'CORS headers — typically an edge block/rate-limit or challenge page, not a connection problem.'))
        .catch((e2) => console.error('[widget] diagnosis: request NEVER LEFT the browser '
          + `(${(e2 as Error)?.name}) — an extension, DNS, firewall or offline network.`));
    }
    // Log the PATH, never the full URL: the host is a redaction target in this project, and a console
    // line ends up in screenshots and bug reports. (That is not hypothetical — it is exactly how the
    // host reached a screenshot during the first live run.) The path carries all the diagnostic value.
    let path = '(unparseable endpoint)';
    try { path = new URL(endpoint.webhookUrl).pathname; } catch { /* keep the placeholder */ }
    console.error('[widget] send failed:', aborted ? 'timeout' : (err?.name || 'unknown'), err?.message || '', {
      path, hadToken: Boolean(turnstileToken),
    });
    return {
      kind: 'system',
      text: aborted ? FRONTEND_TEXT.timeout : FRONTEND_TEXT.offline,
      origin: 'frontend',
      status: 0,
      error: aborted ? 'timeout' : `fetch_failed:${err?.name || 'unknown'}`,
    };
  } finally {
    clearTimeout(timer);
  }

  let body: Record<string, unknown> = {};
  try { body = (await res.json()) as Record<string, unknown>; } catch { /* non-JSON → handled below */ }

  const error = typeof body.error === 'string' ? body.error : undefined;

  // 1. The engine sent text → show exactly that, whatever the status.
  if (typeof body.reply === 'string' && body.reply.length > 0) {
    return { kind: 'bot', text: body.reply, origin: 'engine', status: res.status, error };
  }
  // 2. Deliberately screenless: a duplicate delivery must not produce a second bubble (W56).
  if (body.status === 'duplicate_ignored') {
    return { kind: 'silent', text: '', origin: 'engine', status: res.status };
  }
  // 3. The engine sent no text. Fill in from CONFIG — the same templates the WhatsApp side sends for
  //    these two branches, so both channels speak with one voice (UX-ARCHITECTURE §9 K4).
  if (res.status === 400 && error === 'invalid_payload') {
    return { kind: 'bot', text: t.notUnderstood, origin: 'config', status: 400, error };
  }
  if (res.status === 503 && error === 'state_unavailable') {
    return { kind: 'bot', text: t.handoff, origin: 'config', status: 503, error };
  }
  // 4. Perimeter rejections are the security layer speaking, not the shop.
  if (res.status === 403) {
    return { kind: 'system', text: FRONTEND_TEXT.blocked, origin: 'frontend', status: 403, error };
  }
  // 5. Anything else with no text: promise a human rather than invent a reply. Never leave silence.
  return { kind: 'bot', text: t.handoff, origin: 'config', status: res.status, error };
}
