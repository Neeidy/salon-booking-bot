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
import { readFileSync } from 'node:fs';
import { verifyForTest, OWNER_ACTIONS, releaseHandoff } from './ownerAction.ts';
import { POST } from '../app/api/release/route.ts';
import { screenReason } from './releaseReason.ts';

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

// ── A 502 is decided on the STATUS (7-F1 item 1) ───────────────────────────────────────────────────────
// The engine answers a failed release write with `502 {ok:false, error:'release_failed'}`, and the body that
// reached the client in the D3b drill was the edge's `error code: 502` instead. Both must read the same.
test('a 502 is release_failed, whether the engine body survives or the edge replaced it', async () => {
  const engineBody = await withStubbedEngine({ ok: false, error: 'release_failed' }, 502);
  assert.equal(engineBody.ok, false);
  assert.equal(engineBody.reason, 'release_failed');
  assert.equal(engineBody.status, 502);
  const edgeBody = await withStubbedEngine('error code: 502', 502);
  assert.equal(edgeBody.ok, false);
  assert.equal(edgeBody.reason, 'release_failed');
});

// The negative control for the case above: only 502 moved. Every other unmapped status keeps its old reading.
test('a 503 or a 500 is still unreachable — the 502 mapping did not widen', async () => {
  assert.equal((await withStubbedEngine('error code: 503', 503)).reason, 'unreachable');
  assert.equal((await withStubbedEngine({ ok: false }, 500)).reason, 'unreachable');
});

// ReleaseButton is a client component and cannot import this server-only module, so the two lists are kept
// apart by construction. A reason without its own line falls back to the "did not answer" text, which is a
// different claim; this reads both SOURCES and fails on any reason the screen has no sentence for.
test('every reason this module can return has its own line in ReleaseButton', () => {
  const here = readFileSync(new URL('./ownerAction.ts', import.meta.url), 'utf8');
  const union = here.match(/reason: ((?:'[a-z_]+'(?: \| )?)+);/);
  assert.ok(union, 'the ReleaseOutcome reason union was not found in ownerAction.ts');
  const reasons = [...union[1].matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
  const button = readFileSync(new URL('../components/ReleaseButton.tsx', import.meta.url), 'utf8');
  const missing = reasons.filter((r) => !new RegExp(`^\\s+${r}: '`, 'm').test(button));
  assert.ok(reasons.includes('release_failed'), 'the union no longer holds release_failed');
  assert.deepEqual(missing, []);
});

// ── A 503 says WHICH 503 only through its body (7-2 Tur 2, O3/S2) ─────────────────────────────────────────
// The engine's `503 {ok:false, error:'store_unavailable'}` is answered before any write: the store could not be
// read, so nothing was written. Every other 503 (the edge's page, a bare one, `replay_check_unavailable`) proves
// nothing about whether a write happened and stays `unreachable`.
test('a 503 whose body is {ok:false, error:store_unavailable} is store_unavailable', async () => {
  const outcome = await withStubbedEngine({ ok: false, error: 'store_unavailable' }, 503);
  assert.equal(outcome.ok, false);
  assert.equal(outcome.status, 503);
  assert.equal(outcome.reason, 'store_unavailable');
});

test('every OTHER 503 is still unreachable — the body is the discriminator, not the status', async () => {
  for (const body of ['error code: 503', '', { ok: false, error: 'replay_check_unavailable' }, { ok: false },
                      { error: 'store_unavailable' }, { ok: true, error: 'store_unavailable' }]) {
    assert.equal((await withStubbedEngine(body, 503)).reason, 'unreachable', JSON.stringify(body));
  }
  // The same body on another status is not store_unavailable either: it is the 503 contract, not a word match.
  assert.equal((await withStubbedEngine({ ok: false, error: 'store_unavailable' }, 500)).reason, 'unreachable');
});

// ── The release route refuses a cross-site or non-JSON request before it reads or signs anything (CRT #9) ──
// A `text/plain` POST is a CORS "simple request": a page on another origin can send it with the owner's cookie
// and no preflight. Codex sent one to the real route and got a signed release. These cases drive the real route
// with a stubbed engine and count the engine calls; `bodyUsed` shows whether the body was even read.
test('the release route: text/plain, or any Sec-Fetch-Site other than same-origin, is 403 before the body is read', async () => {
  const VALID = '{"recordId":"recAAAAAAAAAAAAAA","messageId":"d11-unit-2"}';
  for (const headers of [
    { 'Content-Type': 'text/plain', 'Sec-Fetch-Site': 'same-origin' },
    { 'Content-Type': 'text/plain;charset=UTF-8' },
    { 'Content-Type': 'application/x-www-form-urlencoded' },
    { 'Content-Type': 'application/jsonx', 'Sec-Fetch-Site': 'same-origin' },
    { 'Content-Type': 'application/json', 'Sec-Fetch-Site': 'cross-site' },
    { 'Content-Type': 'application/json', 'Sec-Fetch-Site': 'same-site' },
    { 'Content-Type': 'application/json', 'Sec-Fetch-Site': 'none' },
  ]) {
    const r = await callReleaseRoute(headers, VALID);
    assert.equal(r.status, 403, JSON.stringify(headers));
    assert.deepEqual(r.json, { ok: false, reason: 'forbidden' });
    assert.equal(r.engineCalls, 0, `${JSON.stringify(headers)} reached the engine`);
    assert.equal(r.bodyUsed, false, `${JSON.stringify(headers)}: the body was read before the refusal`);
  }
});

test('the release route: application/json without Sec-Fetch-Site passes the check and meets the old validation', async () => {
  // Positive control: `{}` gets the EXISTING 400, not the new 403 — so it got past the check — and writes nothing.
  const r = await callReleaseRoute({ 'Content-Type': 'application/json' }, '{}');
  assert.equal(r.status, 400);
  assert.deepEqual(r.json, { ok: false, reason: 'bad_request' });
  assert.equal(r.engineCalls, 0);
});

test('the release route: a parameterised or differently-cased application/json from same-origin is a release', async () => {
  const VALID = '{"recordId":"recAAAAAAAAAAAAAA","messageId":"d11-unit-3"}';
  for (const ct of ['application/json; charset=utf-8', 'Application/JSON', ' application/json ;charset=UTF-8']) {
    const r = await callReleaseRoute({ 'Content-Type': ct, 'Sec-Fetch-Site': 'same-origin' }, VALID);
    assert.equal(r.status, 200, ct);
    assert.deepEqual(r.json, { ok: true, reason: 'released' });
    assert.equal(r.engineCalls, 1, ct);
  }
});

test('the release route reports store_unavailable as a 503 with that reason', async () => {
  const r = await callReleaseRoute({ 'Content-Type': 'application/json', 'Sec-Fetch-Site': 'same-origin' },
    '{"recordId":"recAAAAAAAAAAAAAA","messageId":"d11-unit-4"}', { ok: false, error: 'store_unavailable' }, 503);
  assert.equal(r.status, 503);
  assert.deepEqual(r.json, { ok: false, reason: 'store_unavailable' });
});

test('ReleaseButton sends application/json to the relative /api/release — what the route now requires', () => {
  const button = readFileSync(new URL('../components/ReleaseButton.tsx', import.meta.url), 'utf8');
  assert.match(button, /fetch\('\/api\/release',\s*\{\s*method: 'POST',\s*headers: \{ 'Content-Type': 'application\/json' \}/);
});

// The staged engine no longer answers `degraded:'marker_unwritten'`, but the committed ones still do (the parked
// original, the live copy until the edit is deployed, and the rollback path). So the screen keeps no sentence
// for that one value, and NO degraded value may ever read as a plain release: an unknown one gets a hedged line.
test('a degraded answer never reads as a plain release — known or unknown', () => {
  assert.equal(screenReason({ ok: true, reason: 'released', degraded: 'alert_undelivered' }), 'released_no_alert');
  for (const degraded of ['marker_unwritten', 'something_new', ' ', 1, true, {}]) {
    assert.equal(screenReason({ ok: true, reason: 'released', degraded }), 'released_degraded', JSON.stringify(degraded));
  }
  // Control: no degraded field, or an empty / null one, is the plain release it always was.
  for (const degraded of [undefined, null, '']) {
    assert.equal(screenReason({ ok: true, reason: 'released', degraded }), 'released', JSON.stringify(degraded));
  }
  assert.equal(screenReason({ ok: false, reason: 'not_locked' }), 'not_locked');
  assert.equal(screenReason({}), 'unreachable');
});

test('every reason screenReason can return has its own line in ReleaseButton, and none names the marker', () => {
  const button = readFileSync(new URL('../components/ReleaseButton.tsx', import.meta.url), 'utf8');
  const lib = readFileSync(new URL('./releaseReason.ts', import.meta.url), 'utf8');
  for (const r of ['released_no_alert', 'released_degraded', 'unreachable']) {
    assert.match(button, new RegExp(`^\\s+${r}: '`, 'm'), `${r} has no sentence`);
  }
  // No dedicated path: neither the old reason nor a branch on the value (a comment may still name it).
  assert.doesNotMatch(button + lib, /released_no_marker|===\s*'marker_unwritten'/);
  assert.match(button, /setReason\(screenReason\(data\)\)/, 'the button must use the tested mapping');
});

test('the release route: a missing Content-Type, or a header sent twice, is 403', async () => {
  const VALID = '{"recordId":"recAAAAAAAAAAAAAA","messageId":"d11-unit-5"}';
  // Bytes, not a string: a string body makes Request invent `text/plain;charset=UTF-8`.
  const none = await callReleaseRoute({ 'Sec-Fetch-Site': 'same-origin' }, new TextEncoder().encode(VALID));
  assert.equal(none.status, 403);
  assert.equal(none.engineCalls, 0);
  // Headers.get() joins repeats with ", ", so a second value rides along inside the first one's string.
  const twiceType = new Headers([['Content-Type', 'application/json'], ['Content-Type', 'text/plain'], ['Sec-Fetch-Site', 'same-origin']]);
  const twiceSite = new Headers([['Content-Type', 'application/json'], ['Sec-Fetch-Site', 'same-origin'], ['Sec-Fetch-Site', 'cross-site']]);
  for (const h of [twiceType, twiceSite]) {
    const r = await callReleaseRoute(h, VALID);
    assert.equal(r.status, 403, JSON.stringify([...h]));
    assert.equal(r.engineCalls, 0);
    assert.equal(r.bodyUsed, false);
  }
});

async function callReleaseRoute(headers: HeadersInit, body: string | Uint8Array<ArrayBuffer>, engineBody: unknown = { ok: true }, engineStatus = 200) {
  let engineCalls = 0;
  const savedFetch = globalThis.fetch;
  const savedEnv = { ...process.env };
  process.env.OWNER_ACTION_URL = 'https://example.com/webhook/owner-release';
  process.env.OWNER_HMAC_SECRET = 'test-secret-not-a-real-one';
  process.env.CF_OWNER_ACCESS_CLIENT_ID = 'test-id';
  process.env.CF_OWNER_ACCESS_CLIENT_SECRET = 'test-secret';
  globalThis.fetch = (async () => {
    engineCalls += 1;
    return new Response(JSON.stringify(engineBody), { status: engineStatus, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  const request = new Request('http://dashboard.invalid/api/release', { method: 'POST', headers, body });
  try {
    const res = await POST(request);
    return { status: res.status, json: await res.json() as unknown, engineCalls, bodyUsed: request.bodyUsed };
  } finally {
    globalThis.fetch = savedFetch;
    for (const k of ['OWNER_ACTION_URL', 'OWNER_HMAC_SECRET', 'CF_OWNER_ACCESS_CLIENT_ID', 'CF_OWNER_ACCESS_CLIENT_SECRET']) {
      if (savedEnv[k] === undefined) delete process.env[k]; else process.env[k] = savedEnv[k];
    }
  }
}

async function withStubbedEngine(body: unknown, status = 200) {
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
  // A string body is sent as-is (the edge's plain-text page); anything else as JSON.
  globalThis.fetch = (async () =>
    typeof body === 'string'
      ? new Response(body, { status, headers: { 'Content-Type': 'text/plain' } })
      : new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
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
