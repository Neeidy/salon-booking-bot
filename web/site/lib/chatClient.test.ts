/**
 * Reply-mapping tests. Every response body below was extracted from the COMMITTED workflow
 * (n8n/workflow.sanitized.json), not invented — see the table in chatClient.ts.
 *
 * What this proves without touching the network: given exactly what the engine returns, the widget
 * shows the right text and, crucially, never REPLACES engine text with a config fallback.
 * The live drill then proves the engine really returns these shapes.
 *
 * Run: node --test lib/chatClient.test.ts   (from web/site)
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sendMessage, newMessageId, FRONTEND_TEXT, type EndpointConfig } from './chatClient.ts';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const cfg = JSON.parse(readFileSync(join(ROOT, 'config/client.config.example.json'), 'utf8'));
const t = cfg.messageTemplates;
const endpoint: EndpointConfig = { webhookUrl: 'https://example.invalid/webhook/barber-inbound', turnstileSiteKey: 'x' };

/** Stub fetch with one engine response. */
function withResponse(status: number, body: unknown, fn: () => Promise<void>) {
  const real = globalThis.fetch;
  globalThis.fetch = (async () => new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })) as typeof fetch;
  return fn().finally(() => { globalThis.fetch = real; });
}
const send = () => sendMessage(endpoint, cfg, 'hi', 's-1', 'tok', 'm-1');

test('success 200 — shows the ENGINE reply verbatim', async () => {
  await withResponse(200, { channel: 'widget', sender_key: 'widget:s-1', reply: t.bookingConfirmed }, async () => {
    const r = await send();
    assert.equal(r.text, t.bookingConfirmed);
    assert.equal(r.origin, 'engine');
    assert.equal(r.kind, 'bot');
  });
});

test('503 llm_unavailable — engine SENDS text, so it must NOT be replaced by a config fallback', async () => {
  // The trap this guards: applying "503 -> handoff" blindly would overwrite the engine's own wording.
  await withResponse(503, { ok: false, error: 'llm_unavailable', handoff: true, reply: t.handoff }, async () => {
    const r = await send();
    assert.equal(r.origin, 'engine', 'must come from the engine, not from config');
    assert.equal(r.text, t.handoff);
  });
});

test('400 invalid_payload — engine sends NO text → messageTemplates.notUnderstood (K4)', async () => {
  await withResponse(400, { ok: false, error: 'invalid_payload', handoff: true }, async () => {
    const r = await send();
    assert.equal(r.text, t.notUnderstood);
    assert.equal(r.origin, 'config');
    assert.equal(r.status, 400);
  });
});

test('503 state_unavailable — engine sends NO text → messageTemplates.handoff (K4)', async () => {
  await withResponse(503, { ok: false, error: 'state_unavailable', handoff: true }, async () => {
    const r = await send();
    assert.equal(r.text, t.handoff);
    assert.equal(r.origin, 'config');
    assert.equal(r.status, 503);
  });
});

test('200 duplicate_ignored — screenless: no second bubble (W56)', async () => {
  await withResponse(200, { status: 'duplicate_ignored', sender_key: 'widget:s-1' }, async () => {
    const r = await send();
    assert.equal(r.kind, 'silent');
    assert.equal(r.text, '');
  });
});

test('403 turnstile_failed — the security layer speaks, not the shop', async () => {
  await withResponse(403, { ok: false, error: 'turnstile_failed' }, async () => {
    const r = await send();
    assert.equal(r.kind, 'system');
    assert.equal(r.text, FRONTEND_TEXT.blocked);
    assert.equal(r.origin, 'frontend');
  });
});

test('handoff lock 200 — engine text again, not a fallback', async () => {
  await withResponse(200, { ok: true, handoff: true, locked: true, reply: t.handoffLocked }, async () => {
    const r = await send();
    assert.equal(r.text, t.handoffLocked);
    assert.equal(r.origin, 'engine');
  });
});

test('unknown failure with no text — promises a human, never silence', async () => {
  await withResponse(500, { ok: false, error: 'something_new' }, async () => {
    const r = await send();
    assert.equal(r.text, t.handoff);
    assert.equal(r.origin, 'config');
  });
});

test('network failure — a frontend transport message, and it does NOT pretend to be the bot', async () => {
  const real = globalThis.fetch;
  globalThis.fetch = (async () => { throw new Error('offline'); }) as typeof fetch;
  try {
    const r = await send();
    assert.equal(r.kind, 'system');
    assert.equal(r.text, FRONTEND_TEXT.offline);
    assert.equal(r.status, 0);
  } finally { globalThis.fetch = real; }
});

test('the request body carries messageId — without it the engine returns 400 for every message', async () => {
  // Measured against the live endpoint: Validate Payload requires a non-empty message_id, and
  // Normalize Inbound reads `messageId` (or `message_id`) from the widget body. This is also the
  // idempotency key that makes a duplicate delivery collapse to one booking.
  const real = globalThis.fetch;
  let sent: Record<string, unknown> = {};
  globalThis.fetch = (async (_u: unknown, init: RequestInit) => {
    sent = JSON.parse(String(init.body));
    return new Response(JSON.stringify({ reply: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } });
  }) as unknown as typeof fetch;
  try {
    await sendMessage(endpoint, cfg, 'hello', 'sess-9', 'tok-9', 'msg-9');
    assert.equal(sent.sessionId, 'sess-9');
    assert.equal(sent.messageId, 'msg-9');
    assert.equal(sent.text, 'hello');
    assert.equal(sent.turnstileToken, 'tok-9');
  } finally { globalThis.fetch = real; }
});

test('newMessageId returns a fresh id each call (one per send, so duplicates collapse)', () => {
  assert.notEqual(newMessageId(), newMessageId());
});
