/**
 * Widget transport — the browser's side of POST <webhook URL>.
 *
 * WHY IT LIVES IN @salon/shared: two different front ends speak to the same engine — the Next.js
 * site (`web/site`) and the embeddable snippet (`web/snippet`, plain TS bundled by esbuild). The
 * reply-mapping rule below is a CONTRACT with the engine; a second hand-written copy of it is
 * exactly the drift `contract-integrity.md` forbids, so both consumers import this one.
 *
 * CONSTRAINT — this module must stay framework-free and browser-safe. No React, no Next, no
 * `process.env`, no Node built-ins. `readEndpointConfig()` used to live here and was moved to
 * `web/site/lib/endpoint.ts` for exactly that reason: it read `process.env.NEXT_PUBLIC_*`, which
 * is a Next build-time convention and means nothing inside the snippet bundle. Each front end
 * resolves its own endpoint and passes it in.
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
// The TYPE comes from the GENERATED types module, not from the loader. The loader is server/build-time
// only (it reads the filesystem and touches `process`), and importing it here — even for a type — pulls
// it into this browser-safe module's type graph. Found by adding a type-check to the snippet package:
// tsc followed the import and failed on `process`. A subpath boundary that only the prose respects is
// not a boundary.
import type { ClientConfig } from '@salon/shared/config/types';

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

/**
 * W61 — the FRONTEND welcome (SCREEN-INVENTORY §8 K4 = B). The engine produces no greeting, so this
 * line has no engine counterpart and writes no state. It lives HERE, not in a component, because both
 * front ends open with it: two copies would drift into two different first impressions of the same
 * shop, which is the drift `contract-integrity.md` exists to prevent.
 */
export function welcomeLine(businessName: string): string {
  return `Hi! I'm the ${businessName} assistant — I can book, change or cancel an appointment, or answer questions. How can I help?`;
}

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

export async function sendMessage(
  endpoint: EndpointConfig,
  // Only messageTemplates is read. Narrowed from ClientConfig so the snippet can pass the minimal
  // subset it bakes in, instead of shipping the whole config to every visitor of every client.
  cfg: Pick<ClientConfig, 'messageTemplates'>,
  text: string,
  sessionId: string,
  turnstileToken: string,
  messageId: string,
  // DERIVED FROM MEASUREMENT, not chosen. Engine turns observed on 2026-09-09/10: 27.2 s, 30.2 s and
  // 39.6 s, plus a first-of-session turn that exceeded the old 20 s ceiling and was aborted while the
  // engine went on to complete it — the client said 'failed' about work that had succeeded. A timeout
  // BELOW the slowest observed successful turn does not protect anyone; it manufactures false failures.
  // 39.6 s x1.5 = ~60 s: the sample is small (one machine, one network) and its slowest case was a cold
  // start, so some headroom is honest; x2 would outlast the patience of a visitor who would rightly
  // conclude the thing is broken. This must also stay ABOVE the engine's own worst-case path, or the
  // client always gives up first and every slow-but-fine turn looks like an outage.
  timeoutMs = 60000,
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
