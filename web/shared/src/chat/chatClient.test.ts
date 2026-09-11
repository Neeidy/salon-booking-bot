/**
 * Reply-mapping tests. Every response body below was extracted from the COMMITTED workflow
 * (n8n/workflow.sanitized.json), not invented — see the table in chatClient.ts.
 *
 * What this proves without touching the network: given exactly what the engine returns, the widget
 * shows the right text and, crucially, never REPLACES engine text with a config fallback.
 * The live drill then proves the engine really returns these shapes.
 *
 * Run: node --test src/chat/chatClient.test.ts   (from web/shared), or `npm test -w @salon/shared`.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sendMessage, newMessageId, FRONTEND_TEXT, type EndpointConfig } from './chatClient.ts';

// repo root: web/shared/src/chat -> up FOUR. (It was '../../..' while this file lived in
// web/site/lib; the move to @salon/shared added a directory level.)
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
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

/**
 * ⚠ THIS TEST USED TO ASSERT THE OPPOSITE, and it was the defect written down as a guarantee.
 * It required a 500 to answer in the SHOP's voice with `messageTemplates.handoff` — "I'm passing you to
 * a team member". Nobody is passed to anyone: a 5xx from the edge never reached the engine, so
 * `Build Owner Alert` (which lives INSIDE the workflow) never ran and no human was told. That is the
 * `handoff.md` rule "Infrastructure failure ≠ conversational handoff" broken on the frontend after the
 * engine side had already paid to close it (CP5a D-d). `code-reviewer` measured it on 502 / 429 / 500 /
 * empty-reply, all four identical. The config fallback now stays ONLY on the engine's own 400 and 503
 * branches, which are real conversational moments where the owner IS pinged.
 */
test('unknown NON-OK status — the transport speaks, and never promises a human nobody told', async () => {
  for (const status of [500, 502, 504]) {
    await withResponse(status, { ok: false, error: 'something_new' }, async () => {
      const r = await send();
      assert.equal(r.kind, 'system', `${status} must not wear the shop's voice`);
      assert.equal(r.text, FRONTEND_TEXT.unexpected);
      assert.equal(r.origin, 'frontend');
      assert.notEqual(r.text, t.handoff, `${status} must not promise a human`);
    });
  }
});

/**
 * W59 had a DECIDED text in SCREEN-INVENTORY §2.10.1 and no implementation — a 429 fell into the
 * catch-all and advised a reload, which is the one thing that does not help a rate-limited visitor.
 */
test('429 is the edge rate-limit (W59) and says WAIT, not "try again in a moment"', async () => {
  await withResponse(429, { ok: false, error: 'rate_limited' }, async () => {
    const r = await send();
    assert.equal(r.kind, 'system');
    assert.equal(r.text, FRONTEND_TEXT.rateLimited);
    assert.notEqual(r.text, FRONTEND_TEXT.unexpected);
  });
});

test('a 2xx the contract does not describe still answers — silence is never the outcome', async () => {
  await withResponse(200, { ok: true, something: 'unmapped' }, async () => {
    const r = await send();
    assert.equal(r.kind, 'system');
    assert.equal(r.text, FRONTEND_TEXT.unexpected);
    assert.ok(r.text.length > 0);
  });
});

/**
 * K2 = C (show the lock line once, then accept quietly) is driven ENTIRELY by this flag, and nothing
 * asserted it — `grep -n locked chatClient.test.ts` matched only a body literal (code-reviewer #11).
 * A structural signal with no test is one refactor away from silently becoming `undefined`, and the
 * failure mode is invisible: the lock line simply repeats on every message.
 */
test('locked is carried through as a STRUCTURAL flag, not inferred from the words', async () => {
  await withResponse(200, { ok: true, handoff: true, locked: true, reply: t.handoffLocked }, async () => {
    const r = await send();
    assert.equal(r.locked, true);
  });
  // and it is absent — not merely falsy by accident — on an ordinary reply
  await withResponse(200, { channel: 'widget', reply: t.bookingConfirmed }, async () => {
    const r = await send();
    assert.equal(r.locked, false);
  });
});

/**
 * `messageTemplates` has NO required keys in the committed schema, so a config can pass every gate and
 * still be missing the two the widget must supply. Before `fill()` that rendered `undefined` — an empty
 * bubble, the exact opposite of the contract. `build.mjs` fails the snippet build for it; this is the
 * runtime net for every other consumer, and it had no test.
 */
test('a missing template never renders undefined — fill() substitutes an honest sentence', async () => {
  const bare = { messageTemplates: {} } as typeof cfg;
  await withResponse(400, { ok: false, error: 'invalid_payload', handoff: true }, async () => {
    const r = await sendMessage(endpoint, bare, 'hi', 's-1', 'tok', 'm-1');
    assert.equal(r.text, FRONTEND_TEXT.noText);
    assert.notEqual(r.text, 'undefined');
  });
});

/**
 * The timeout branch had no test: the existing network test throws a generic Error, which takes the
 * `offline` path. Only an AbortError reaches `timeout`, and that is the branch the 60 s ceiling exists
 * for — the one measured turn where the client gave up on work the engine went on to finish.
 */
test('an aborted request reads as a TIMEOUT, not as being offline', async () => {
  const real = globalThis.fetch;
  globalThis.fetch = (async () => {
    const e = new Error('The operation was aborted.');
    e.name = 'AbortError';
    throw e;
  }) as typeof fetch;
  try {
    const r = await send();
    assert.equal(r.text, FRONTEND_TEXT.timeout);
    assert.notEqual(r.text, FRONTEND_TEXT.offline);
    assert.equal(r.status, 0);
  } finally { globalThis.fetch = real; }
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
