/**
 * What CAN be proven about the owner write path before the engine exists: the signature itself.
 *
 * The seven live cases in `tests/run-d11.sh` need a published workflow. These do not, and they cover the
 * half that is entirely ours — if the client signs wrongly, every one of those seven would fail for a
 * reason that has nothing to do with the engine.
 *
 * Run: node --test lib/ownerAction.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { verifyForTest, OWNER_ACTIONS, releaseHandoff } from './ownerAction.ts';

const SECRET = 'test-secret-not-a-real-one';
const BODY = '{"action":"release_handoff","record_id":"recTEST","messageId":"m1","ts":1}';
const SIG = createHmac('sha256', SECRET).update(BODY).digest('hex');

test('a correct signature verifies', () => {
  assert.equal(verifyForTest(BODY, SIG, SECRET), true);
});

test('ONE changed byte in the body invalidates it — the control and the treatment differ', () => {
  // The point of the whole mechanism: the signature is over the bytes, so any edit is fatal.
  assert.equal(verifyForTest(`${BODY} `, SIG, SECRET), false);
  assert.equal(verifyForTest(BODY.replace('recTEST', 'recOTHER'), SIG, SECRET), false);
  assert.equal(verifyForTest(BODY.replace('release_handoff', 'delete_all'), SIG, SECRET), false);
});

test('a different secret does not verify', () => {
  assert.equal(verifyForTest(BODY, SIG, `${SECRET}x`), false);
});

test('a truncated or over-long signature is rejected without throwing', () => {
  // timingSafeEqual THROWS on a length mismatch. An unguarded compare would turn a malformed header into
  // a 500 instead of a 403 — a crash where a refusal belongs.
  assert.doesNotThrow(() => verifyForTest(BODY, SIG.slice(0, 10), SECRET));
  assert.equal(verifyForTest(BODY, SIG.slice(0, 10), SECRET), false);
  assert.equal(verifyForTest(BODY, `${SIG}00`, SECRET), false);
  assert.equal(verifyForTest(BODY, '', SECRET), false);
});

test('the allow-list has exactly one verb, and that is the audited property', () => {
  // CRT #11 is auditable because the surface is one verb. A second entry here would need a new audit,
  // so the count is asserted rather than the contents alone.
  assert.equal(OWNER_ACTIONS.length, 1);
  assert.deepEqual([...OWNER_ACTIONS], ['release_handoff']);
});

test('the signed body carries a timestamp — without it a captured request is valid forever', () => {
  const parsed = JSON.parse(BODY) as Record<string, unknown>;
  assert.ok('ts' in parsed, 'ts must be inside the SIGNED body, not a header — a header is editable');
  assert.equal(typeof parsed.ts, 'number');
});

// ── The 200-is-not-the-answer regression (Codex CRT #11, 2026-09-13) ─────────────────────────────────
// A mocked `200 {"ok":false}` used to come back as `{ok:true, reason:'released'}`: the screen said the
// release happened while the engine had said it did not. These four cases exist so that cannot return.
// They stub `fetch`, so nothing here reaches a network, a secret or the engine.
test('a 200 whose body says ok:false is NOT a release', async () => {
  const outcome = await withStubbedEngine({ ok: false, error: 'not_locked' });
  assert.equal(outcome.ok, false);
  assert.equal(outcome.reason, 'refused');
});

test('a 200 with an unrecognised body shape is not trusted', async () => {
  const outcome = await withStubbedEngine({ something: 'else' });
  assert.equal(outcome.ok, false);
  assert.equal(outcome.reason, 'unreachable');
});

test('a DEGRADED success is a success, and says which half failed', async () => {
  const outcome = await withStubbedEngine({ ok: true, degraded: 'alert_undelivered' });
  assert.equal(outcome.ok, true);
  assert.equal(outcome.reason, 'released');
  assert.equal(outcome.degraded, 'alert_undelivered');
});

// The negative control: without it the three assertions above could all be passing for the wrong reason.
test('a plain 200 {ok:true} is still a release — the guard did not break the happy path', async () => {
  const outcome = await withStubbedEngine({ ok: true });
  assert.equal(outcome.ok, true);
  assert.equal(outcome.reason, 'released');
  assert.equal(outcome.degraded, undefined);
});

async function withStubbedEngine(body: unknown) {
  const saved = {
    fetch: globalThis.fetch,
    url: process.env.OWNER_ACTION_URL,
    secret: process.env.OWNER_HMAC_SECRET,
    cfId: process.env.CF_OWNER_ACCESS_CLIENT_ID,
    cfSecret: process.env.CF_OWNER_ACCESS_CLIENT_SECRET,
  };
  process.env.OWNER_ACTION_URL = 'https://example.com/webhook/owner-release';
  process.env.OWNER_HMAC_SECRET = 'test-secret-not-a-real-one';
  process.env.CF_OWNER_ACCESS_CLIENT_ID = 'test-id';
  process.env.CF_OWNER_ACCESS_CLIENT_SECRET = 'test-secret';
  globalThis.fetch = (async () =>
    new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  ) as typeof fetch;
  try {
    return await releaseHandoff('recAAAAAAAAAAAAAA', 'd11-unit-1');
  } finally {
    globalThis.fetch = saved.fetch;
    process.env.OWNER_ACTION_URL = saved.url;
    process.env.OWNER_HMAC_SECRET = saved.secret;
    process.env.CF_OWNER_ACCESS_CLIENT_ID = saved.cfId;
    process.env.CF_OWNER_ACCESS_CLIENT_SECRET = saved.cfSecret;
  }
}
