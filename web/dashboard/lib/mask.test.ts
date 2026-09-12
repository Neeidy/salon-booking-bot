/**
 * Every masking claim in mask.ts, asserted. The point is not that masking "works" — it is that the
 * masked output CANNOT be turned back into the input, and that is a property, not an example. So the
 * suite checks both directions: the shape the owner needs is present, and the value is gone.
 *
 * Run: node --test lib/mask.test.ts   (Node strips the types; nothing is compiled)
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { maskPhone, maskName, maskSenderKey, maskFreeText, assertMasked } from './mask.ts';

// Fixtures are FAKE. A real number in a test file is a real number in a public repo.
const FAKE_AT = '+43 660 1234567';
const FAKE_WIDGET = 'widget:w-4f3a91c27e5b8d016a';
const FAKE_WA = 'whatsapp:+436601234567';

test('maskPhone keeps the country prefix and the last two digits, and nothing else', () => {
  const out = maskPhone(FAKE_AT);
  assert.equal(out, '+43…67');
  assert.ok(!out.includes('1234'), 'the body of the number must be gone');
});

test('maskPhone: the middle is NOT recoverable — different numbers with the same ends collide', () => {
  // This is the property that matters. If two different numbers produced different masks, the mask
  // would be leaking the thing it hides.
  assert.equal(maskPhone('+43 660 1111167'), maskPhone('+43 111 9999967'));
});

test('maskPhone handles junk without throwing and without inventing data', () => {
  assert.equal(maskPhone(''), '—');
  assert.equal(maskPhone(undefined), '—');
  assert.equal(maskPhone(null), '—');
  assert.equal(maskPhone('12'), '••');
  // A10: the threshold is 8, not 4. At six digits the old rule showed four of them and the collision
  // property asserted above stopped holding.
  assert.equal(maskPhone('066012'), '••••••');
});

test('maskName keeps the first name and reduces the rest to initials', () => {
  assert.equal(maskName('Anna Maria Schmidt'), 'Anna M. S.');
  assert.equal(maskName('Jonas'), 'Jonas');
  assert.equal(maskName('  '), '—');
});

test('maskName does not split a multi-byte initial in half', () => {
  // `[...p][0]` rather than `p[0]`: a surrogate pair sliced by index produces a replacement char.
  assert.equal(maskName('Åsa Ödegård'), 'Åsa Ö.');
  assert.equal(maskName('Li 😀mon'), 'Li 😀.');
});

test('maskSenderKey keeps the CHANNEL in clear — it is a fixed literal and it is what the owner needs', () => {
  assert.ok(maskSenderKey(FAKE_WIDGET).startsWith('widget:'));
  assert.ok(maskSenderKey(FAKE_WA).startsWith('whatsapp:'));
});

test('maskSenderKey destroys the credential half', () => {
  const out = maskSenderKey(FAKE_WIDGET);
  assert.equal(out, 'widget:w-4f3a…');
  assert.ok(!out.includes('91c27e5b8d016a'), 'the session-token body must be gone');
  // security-secrets.md: a FULL sender_key is a bearer credential. The mask must not be reversible.
  assert.ok(out.length < FAKE_WIDGET.length);
});

test('maskSenderKey treats a phone-shaped id as a phone', () => {
  assert.equal(maskSenderKey(FAKE_WA), 'whatsapp:+43…67');
});

test('maskSenderKey on a malformed value still masks rather than passing it through', () => {
  const out = maskSenderKey('no-colon-at-all-1234567890');
  assert.ok(out.endsWith('…'));
  assert.ok(!out.includes('1234567890'));
});

test('maskFreeText MASKS a phone the customer typed into the chat — it used to only truncate', () => {
  const out = maskFreeText('you can reach me on 0660 123 45 67 thanks');
  assert.ok(!out.includes('0660 123 45 67'), out);
  assert.match(out, /…/);
  assert.equal(assertMasked(out, 'text'), out);
});

test('maskFreeText masks an email, keeping the domain so the owner still recognises it', () => {
  const out = maskFreeText('write to anna.schmidt@example.com please');
  assert.ok(!out.includes('anna.schmidt@'), out);
  assert.match(out, /a…@example\.com/);
});

test('maskFreeText leaves ordinary numbers alone — a time or a price is not PII', () => {
  const out = maskFreeText('can I come at 10:30 on the 5th, is it 25 euro?');
  assert.match(out, /10:30/);
  assert.match(out, /25 euro/);
});

test('maskFreeText masks FIRST and truncates second', () => {
  // Truncating first would cut a phone number in half and leave a fragment the masker no longer
  // recognises — which is how a "masked" field leaks half a number.
  const long = `${'x'.repeat(140)} call 0660 123 45 67`;
  const out = maskFreeText(long, 160);
  assert.ok(!out.includes('123 45 67'), out);
});

test('maskFreeText keeps message boundaries visible instead of melting five messages into one', () => {
  assert.match(maskFreeText('first message\nsecond message'), / · /);
});

test('maskFreeText truncates on a word boundary and marks the cut', () => {
  const long = 'hello I would like to book a haircut for friday afternoon if you have anything free';
  const out = maskFreeText(long, 30);
  assert.ok(out.length <= 31, out);
  assert.ok(out.endsWith('…'));
  assert.ok(!out.endsWith(' …'));
});

test('maskName no longer returns a single token untouched — a phone typed as a NAME is masked', () => {
  // schemas/intent.schema.json declares customerName as a free string with no pattern: it is whatever
  // the model pulled out of the customer's sentence, and people type their number into that field.
  assert.ok(!maskName('+436601234567').includes('6601234'));
  assert.match(maskName('anna.schmidt@example.com'), /a…@example\.com/);
  assert.equal(maskName('Anna Maria Schmidt'), 'Anna M. S.');
  assert.equal(assertMasked(maskName('+436601234567'), 'name'), maskName('+436601234567'));
});

test('maskName masks a phone written WITH SEPARATORS — the first S3 fix was narrower than the defect', () => {
  // Every one of these passed through untouched, and `assertMasked` passed them too, because the
  // trigger was five CONSECUTIVE digits and a separated number never has five in a row.
  for (const typed of ['0660-123-4567', '0660.123.4567', '+43-660-123-4567', '0660/123/4567',
                       '(0660) 123 4567']) {
    const out = maskName(typed);
    assert.ok(!/\d{4}/.test(out), `${typed} -> ${out}`);
    assert.equal(assertMasked(out, 'name'), out);
  }
  // …and a name with a small number in it is still a name.
  assert.equal(maskName('Anna Maria Schmidt'), 'Anna M. S.');
  assert.equal(maskName('Jonas 1990'), 'Jonas 1.');
});

test('maskSenderKey MASKS the shape that merely LOOKS masked — the old formula\'s own defect', () => {
  // THE CASE THE FIRST IDEMPOTENCY FIX WAVED THROUGH. `LEFT(key,16) & "…"` returned the WHOLE key with
  // an ellipsis glued on whenever the key was short enough — 91 of 592 rows — so "contains an ellipsis"
  // is not evidence of anything. A shape test replaced the character test; this case is what proves it.
  const looksMasked = 'widget:w-4f3a91c2b7d1e5f9a0c3d2e1…';
  const out = maskSenderKey(looksMasked);
  assert.notEqual(out, looksMasked, 'a full key with an ellipsis must NOT round-trip');
  assert.equal(out, 'widget:w-4f3a…');
  assert.ok(!out.includes('91c2b7d1'));
  // …and the same for the wrong-end whatsapp truncation the old formula produced.
  assert.ok(!maskSenderKey('whatsapp:+436601…').includes('6601'));
});

test('maskSenderKey masks a WhatsApp id with no leading plus — the provider does not guarantee one', () => {
  // `Normalize Inbound` builds `whatsapp:${senderId}` from the provider's MSISDN. Keying the phone
  // branch on a `+` sent a bare national number down the prefix branch and printed six of its digits.
  const out = maskSenderKey('whatsapp:436601234567');
  assert.equal(out, 'whatsapp:43…67');
  assert.ok(!out.includes('6601'));
});

test('maskSenderKey is IDEMPOTENT — re-masking a masked value must not eat it', () => {
  // Without this the call site cannot apply the mask unconditionally: a second pass over a masked
  // phone sees four digits, falls under maskPhone's threshold, and returns an unidentifiable row.
  for (const already of ['widget:w-4f3a…', 'whatsapp:+43…67', '—']) {
    assert.equal(maskSenderKey(already), already);
  }
  assert.equal(maskSenderKey(maskSenderKey(FAKE_WA)), maskSenderKey(FAKE_WA));
  assert.equal(maskSenderKey(maskSenderKey(FAKE_WIDGET)), maskSenderKey(FAKE_WIDGET));
});

test('a FULL widget sender_key is destroyed by maskSenderKey — the lane assertMasked cannot see', () => {
  // security-auditor M1: a full `widget:w-<uuid>` has no 5-digit run and no `@`, so the render-time
  // check passes it. The component therefore re-masks EVERY row rather than only rows that fail.
  const full = 'widget:w-3f2a1b8c-9d4e-4f7a-b1c2-d3e4f5a6b7c8';
  assert.equal(assertMasked(full, 'sender'), full);      // the limit, unchanged and asserted
  const out = maskSenderKey(full);                        // what the call site actually renders
  assert.equal(out, 'widget:w-3f2a…');
  assert.ok(!out.includes('9d4e'));
  // and the component's flag fires precisely because the value differs from its own re-masking
  assert.notEqual(out, full);
});

test('assertMasked refuses a digit run AND a full email — and admits what it cannot see', () => {
  assert.throws(() => assertMasked('whatsapp:+436601234567', 'sender'), /refusing to render/);
  assert.throws(() => assertMasked('anna.schmidt@example.com', 'name'), /email address/);
  assert.equal(assertMasked('widget:w-4f3a…', 'sender'), 'widget:w-4f3a…');
  // The limit, asserted so the docstring cannot quietly grow past it: a full widget sender_key has no
  // digit run and no @, so this guard does NOT catch it (security-auditor S6). maskSenderKey does.
  assert.equal(assertMasked('widget:w-4f3a91c2d7e6b5a4', 'sender'), 'widget:w-4f3a91c2d7e6b5a4');
});

test('assertMasked accepts every mask this module produces — it must not fire on correct output', () => {
  // A guard that rejects its own module's output is a guard that gets removed.
  for (const v of [maskPhone(FAKE_AT), maskSenderKey(FAKE_WIDGET), maskSenderKey(FAKE_WA),
                   maskName('Anna Maria Schmidt'), maskName('+436601234567'),
                   maskFreeText('call me on 0660 123 45 67 or anna@example.com')]) {
    assert.equal(assertMasked(v, 'self'), v);
  }
});
