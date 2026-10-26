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
import { MASKED, UNMASKED } from './mask.golden.ts';

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

test('maskFreeText keeps message boundaries as newlines instead of melting five messages into one (M1)', () => {
  // The ` · ` join of R1b put two lines into one, and the run counter then read digits across messages.
  assert.equal(maskFreeText('first message\nsecond message'), 'first message\nsecond message');
  assert.equal(maskFreeText('first  message \n\n\n  second\tmessage'), 'first message\nsecond message');
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

// ── Codex CRT #9 (7-2 Tur 1): Unicode digits, invisible separators, and the fallback that kept the surname ──
// All numbers here are synthetic: the digits of `0660 1234567` written in other scripts or split apart.
const ARABIC_PHONE = '٠٦٦٠١٢٣٤٥٦٧';                  // U+0660… Arabic-Indic: NFKC leaves these alone
const ZW_PHONE = [...'06601234567'].join('\u200B');  // ZERO WIDTH SPACE between every digit; not in JS `\s`
/** What a reader of the rendered value SEES: the invisible format characters are not on the screen. */
const seen = (v: string) => v.normalize('NFKC').replace(/\p{Cf}/gu, '');

test('maskName masks a phone written in Arabic-Indic digits — an ASCII-only digit class let it through', () => {
  const out = maskName(`Omar ${ARABIC_PHONE}`);
  assert.equal(out, 'Omar ٠٦…٦٧');
  assert.doesNotMatch(seen(out), /\p{Nd}{5,}/u);
  assert.equal(assertMasked(out, 'name'), out);
});

test('an Arabic-Indic number typed WITH separators is masked — the digits are counted across the spaces', () => {
  // With spaces the longest contiguous run is four, so this case shows the digits are COUNTED across the
  // separators in Arabic-Indic too, not only matched when they sit back to back.
  assert.equal(maskName('Omar ٠٦٦٠ ١٢٣ ٤٥٦٧'), 'Omar ٠٦…٦٧');
  assert.equal(maskFreeText('call ٠٦٦٠ ١٢٣ ٤٥٦٧ please'), 'call ٠٦…٦٧ please');
});

test('maskName masks a phone whose digits are split by zero-width spaces', () => {
  const out = maskName(`Omar ${ZW_PHONE}`);
  assert.equal(out, 'Omar 06…67');
  assert.doesNotMatch(seen(out), /\p{Nd}{5,}/u);
  assert.equal(assertMasked(out, 'name'), out);
});

test('maskName applies NFKC: superscript digits and a fullwidth @ are a phone and an email after all', () => {
  assert.equal(maskName('⁰⁶⁶⁰¹²³⁴⁵⁶⁷'), '06…67');
  assert.equal(maskName('anna.schmidt＠example.com'), 'a…@example.com');
});

test('assertMasked refuses the UNMASKED Unicode forms, not just ASCII runs', () => {
  assert.throws(() => assertMasked(`Omar ${ARABIC_PHONE}`, 'name'), /refusing to render/);
  assert.throws(() => assertMasked(`Omar ${ZW_PHONE}`, 'name'), /refusing to render/);
  assert.throws(() => assertMasked('⁰⁶⁶⁰¹²³⁴⁵⁶⁷', 'name'), /refusing to render/);
  assert.throws(() => assertMasked('anna.schmidt＠example.com', 'name'), /email address/);
  // Control: the masked forms of the same inputs still pass, so the tripwire did not simply get stricter.
  assert.equal(assertMasked('Omar ٠٦…٦٧', 'name'), 'Omar ٠٦…٦٧');
});

test('the digit/email fallback reduces the surname to an initial, as the normal branch does', () => {
  assert.equal(maskName('Vera Quellbrunn 1234567'), 'Vera Q. 12…67');
  assert.equal(maskName('Vera Quellbrunn vera.q@example.com'), 'Vera Q. v…@example.com');
  // A surname glued to the number is a token with digits in it; its letters still go.
  assert.ok(!maskName('Vera Quellbrunn06601234567').includes('Quellbrunn'));
  assert.ok(!maskName('Vera Quellbrunn 0660 123 4567').includes('Quellbrunn'));
  // Control: the normal branch and the single-token email/phone cases are unchanged.
  assert.equal(maskName('Anna Maria Schmidt'), 'Anna M. S.');
  assert.equal(maskName('+436601234567'), '+43…67');
});

test('astral digits are cut as code points — slicing UTF-16 units would leave half a surrogate on screen', () => {
  // Adlam digits (U+1E950…) are `\p{Nd}`, untouched by NFKC, and two UTF-16 units each.
  const adlam = String.fromCodePoint(...[0, 6, 6, 0, 1, 2, 3, 4, 5, 6, 7].map((d) => 0x1E950 + d));
  const out = maskName(`Omar ${adlam}`);
  assert.equal(out, `Omar ${String.fromCodePoint(0x1E950, 0x1E956)}…${String.fromCodePoint(0x1E956, 0x1E957)}`);
  assert.doesNotMatch(out, /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/, 'a lone surrogate reached the output');
});

// ── Lane D review: invisible characters OUTSIDE \p{Cf}, and a surname glued to an email ─────────────────────
// Each digit of the synthetic `06601234567` is followed by a character a screen does not show (or, for the
// keycap, draws as part of the digit). None of them is stripped any more: each is a NON-LETTER, so it simply
// extends the run (ruling 2026-10-26). The leak check counts DIGITS in the output, whatever sits between them.
// The Hangul filler U+3164 used to be in this list and is not: it is a LETTER (`Lo`), so it is outside what
// the mechanism claims — see the BOUND test below, which pins exactly what it does to it.
const digitsIn = (v: string) => [...v.replace(/\P{Nd}/gu, '')].length;
const INVISIBLE_SPLIT: Record<string, string> = {
  'combining grapheme joiner U+034F': [...'06601234567'].join('\u034F'),
  'variation selector-16 U+FE0F': [...'06601234567'].join('\uFE0F'),
  'keycap digits (digit U+FE0F U+20E3)': [...'06601234567'].map((d) => `${d}\uFE0F\u20E3`).join(''),
};

test('maskName and maskFreeText mask a phone split by invisible NON-LETTERS that are not \\p{Cf}', () => {
  for (const [what, phone] of Object.entries(INVISIBLE_SPLIT)) {
    const name = maskName(`Omar ${phone}`);
    assert.equal(name, 'Omar 06…67', what);
    assert.ok(digitsIn(name) <= 4, `${what}: ${name}`);
    assert.equal(maskFreeText(`call ${phone} please`), 'call 06…67 please', what);
    assert.equal(assertMasked(name, 'name'), name);
  }
});

test('assertMasked refuses those unmasked forms', () => {
  for (const [what, phone] of Object.entries(INVISIBLE_SPLIT)) {
    assert.throws(() => assertMasked(`Omar ${phone}`, 'name'), /refusing to render/, what);
  }
});

test('a surname glued to an email inside one token is reduced; only the email match is left to the email rule', () => {
  assert.equal(maskName('Anna Schmidt/anna@example.com'), 'Anna S./a…@example.com');
  assert.equal(maskName('Anna Schmidt:a@b.co'), 'Anna S.:a…@b.co');
  // An `@` that is not part of a valid email gets the plain initial rule.
  assert.equal(maskName('Anna Schmidt@'), 'Anna S.');
  for (const v of ['Anna Schmidt/anna@example.com', 'Anna Schmidt:a@b.co', 'Anna Schmidt@']) {
    assert.ok(!maskName(v).includes('Schmidt'), v);
  }
});

// ── Ruling 2026-10-26, MASK v3 in its FALLBACK form: ONE mechanism (NFKC → strip \p{Cf} → \p{Nd} to ASCII → lines →
// per non-letter run: ≥7 digits masks the run; no date/time exemption — v3's leaked). The golden table
// (`mask.golden.ts`) is the proof; the cases below pin individual properties. Every number is synthetic.
const BASE = '06601234567';
const fromDigits = (zero: number) => String.fromCodePoint(...[...BASE].map((d) => zero + Number(d)));
const splitBy = (sep: string) => [...BASE].join(sep);
/** Each raw form a phone number arrives in, unmasked. The test name of each case is its key. */
const LEAK_FORMS: Record<string, string> = {
  'Arabic-Indic digits (U+0660…)': fromDigits(0x0660),
  'fullwidth digits (U+FF10…)': fromDigits(0xFF10),
  'zero-width space U+200B between the digits': splitBy('​'),
  'zero-width non-joiner U+200C between the digits': splitBy('‌'),
  'zero-width joiner U+200D between the digits': splitBy('‍'),
  'word joiner U+2060 between the digits': splitBy('⁠'),
  'BOM U+FEFF between the digits': splitBy('﻿'),
  'soft hyphen U+00AD between the digits': splitBy('­'),
  'Braille blank U+2800 between the digits': splitBy('⠀'),
  'musical symbol U+1D159 between the digits': splitBy(String.fromCodePoint(0x1D159)),
  'spaces': '0660 123 45 67',
  'dashes': '0660-123-45-67',
  'dots': '0660.123.45.67',
  'mixed separators with a country prefix': '+43 (660) 123-45.67',
};

for (const [form, phone] of Object.entries(LEAK_FORMS)) {
  test(`MASK masks a phone written with ${form}`, () => {
    const text = maskFreeText(`call ${phone} please`);
    assert.match(text, /^call \+?.{2}….{2} please$/u, `${form}: ${JSON.stringify(text)}`);
    assert.ok(digitsIn(text) <= 4, `${form}: digits leaked in ${JSON.stringify(text)}`);
    const name = maskName(`Omar ${phone}`);
    assert.ok(digitsIn(name) <= 4, `${form}: digits leaked in ${JSON.stringify(name)}`);
    // The mask's own output passes the tripwire, and masking it again changes nothing.
    assert.equal(assertMasked(text, 'text'), text);
    assert.equal(assertMasked(name, 'name'), name);
    assert.equal(maskFreeText(text), text);
  });
  test(`assertMasked REJECTS the raw leak form: ${form}`, () => {
    assert.throws(() => assertMasked(`call ${phone} please`, 'text'), /refusing to render/, form);
    assert.throws(() => assertMasked(phone, 'name'), /refusing to render/, form);
  });
}

test('MASK: the Braille blank U+2800 and U+1D159 are NOT \\p{Cf} — they are counted as separators, not stripped', () => {
  // The whole point of the mechanism: these two survive the strip step, and the number is masked anyway.
  assert.doesNotMatch('⠀', /\p{Cf}/u);
  assert.doesNotMatch(String.fromCodePoint(0x1D159), /\p{Cf}/u);
  assert.equal(maskFreeText(`call ${splitBy('⠀')} please`), 'call 06…67 please');
  assert.equal(maskFreeText(`call ${splitBy(String.fromCodePoint(0x1D159))} please`), 'call 06…67 please');
});

test('MASK keeps the digits\' own script in the head and tail, and a + prefix', () => {
  assert.equal(maskFreeText(`call ${fromDigits(0x0660)}`), 'call ٠٦…٦٧');
  assert.equal(maskFreeText(`call ${fromDigits(0xFF10)}`), 'call 06…67');      // NFKC folds fullwidth to ASCII
  assert.equal(maskFreeText('call +43 660 1234567'), 'call +43…67');
});

test('FALLBACK: dates are over-masked — there is no date exemption any more', () => {
  for (const [d, m] of [['2026-10-26', '20…26'], ['26.10.2026', '26…26'], ['01.01.1999', '01…99'], ['31.12.2030', '31…30']]) {
    assert.equal(maskFreeText(`see you on ${d} then`), `see you on ${m} then`, d);
    assert.throws(() => assertMasked(`see you on ${d} then`, 'text'), /refusing to render/, d);
  }
  assert.equal(maskFreeText('from 26.10.2026 to 27.10.2026'), 'from 26…26 to 27…26');
  assert.equal(maskFreeText('2026-10-26 / 2026-10-27'), '20…27');
});

test('MASK: a time alone (four digits) stays readable; a date beside it is over-masked', () => {
  for (const t of ['10:30', '00:00', '23:59']) assert.equal(maskFreeText(`at ${t} ok`), `at ${t} ok`, t);
  assert.equal(maskFreeText('on 26.10.2026 at 10:30'), 'on 26…26 at 10:30');
});

test('FALLBACK: a time range has eight digits and is over-masked', () => {
  assert.equal(maskFreeText('14:00-15:30'), '14…30');
  assert.equal(maskFreeText('free 14:00-15:30 or 16:00 - 17:30?'), 'free 14…30 or 16…30?');
  assert.throws(() => assertMasked('14:00-15:30', 'text'), /refusing to render/);
});

test('MASK: digits in any script count — a date in Arabic-Indic or Devanagari digits is masked like an ASCII one', () => {
  const ar = (s: string) => s.replace(/[0-9]/g, (d) => String.fromCodePoint(0x0660 + Number(d)));
  const deva = (s: string) => s.replace(/[0-9]/g, (d) => String.fromCodePoint(0x0966 + Number(d)));
  assert.equal(maskFreeText(`on ${ar('26.10.2026')}`), `on ${ar('26')}…${ar('26')}`);
  assert.equal(maskFreeText(`at ${deva('14:00-15:30')}`), `at ${deva('14')}…${deva('30')}`);
});

test('MASK: a zero-width character inside a date is stripped first — the date is still eight digits, masked', () => {
  assert.equal(maskFreeText('on 26.\u200B10.2026'), 'on 26…26');
  // …and an email whose local part is split by one is still one address to the email rule.
  assert.equal(maskFreeText('write to anna\u200Bschmidt@example.com'), 'write to a…@example.com');
});

test('MASK: invalid dates and times are masked — like every run of seven or more digits under the fallback', () => {
  assert.equal(maskFreeText('ref 26.13.2026'), 'ref 26…26');
  assert.equal(maskFreeText('ref 32.10.2026'), 'ref 32…26');
  assert.equal(maskFreeText('ref 2026-13-26'), 'ref 20…26');
  assert.equal(maskFreeText('ref 24:00-24:30'), 'ref 24…30');
  assert.equal(maskFreeText('ref 12:60-12:61'), 'ref 12…61');
  assert.equal(maskFreeText('ref 26.10.2126'), 'ref 26…26');
});

test('MASK: a date or time glued to more digits is masked as one longer number', () => {
  assert.equal(maskFreeText('call 0626.10.2026'), 'call 06…26');
  assert.equal(maskFreeText('call 26.10.20261'), 'call 26…61');
  assert.equal(maskFreeText('call 0610:301'), 'call 06…01');
  assert.equal(maskFreeText('call 12026-10-26'), 'call 12…26');
  // A date beside a number in the same run: one run, masked whole. R1b kept the date as a BOUNDARY here — the
  // mechanism that leaked `Tel 2012-12-12-34`; v3's whole-run exemption then leaked `Tel 2012-12-12` (fallback).
  assert.equal(maskFreeText('26.10.2026 0660 1234567'), '26…67');
});

test('FALLBACK: dashed pairs and ISO dates are masked alike — no year rule decides it any more', () => {
  assert.equal(maskFreeText('call 0660-12-12-34'), 'call 06…34');
  assert.throws(() => assertMasked('call 0660-12-12-34', 'text'), /refusing to render/);
  assert.equal(maskFreeText('on 2026-10-26 at 14:00'), 'on 20…26 at 14:00');
  assert.equal(maskFreeText('born 1999-01-31'), 'born 19…31');
});

test('MASK: the threshold is seven digits per run — six stay, seven go', () => {
  assert.equal(maskFreeText('code 123 456'), 'code 123 456');
  assert.equal(maskFreeText('code 123 4567'), 'code 12…67');
  assert.throws(() => assertMasked('code 123 4567', 'text'), /refusing to render/);
  assert.equal(assertMasked('code 123 456', 'text'), 'code 123 456');
});

test('MASK: a run is counted across ONE line break (R1d), and a letter ends it', () => {
  assert.equal(maskFreeText('0660\n123 45'), '06…\n…45');
  assert.equal(maskFreeText('06\n123\n45'), '06\n123\n45');
  assert.throws(() => assertMasked('0660\n123 45', 'text'), /refusing to render/);   // the guard pairs lines too
  // a NAME is one line on the screen: its decision is per line, so the fallback branch is not opened by pairing
  assert.equal(maskName('Anna 0660\n123 b 456789'), 'Anna 0. 1. b. 4.');
  assert.equal(maskName('Omar 0660\n123'), 'Omar 0. 1.');
  assert.equal(maskFreeText('room 0660 and 123 45'), 'room 0660 and 123 45');
});

test('MASK is idempotent — maskFreeText on a masked value returns it unchanged', () => {
  for (const raw of [...Object.values(LEAK_FORMS).map((p) => `call ${p} please`),
                     'on 26.10.2026 at 14:00-15:30', 'write to anna.schmidt@example.com']) {
    const once = maskFreeText(raw);
    assert.equal(maskFreeText(once), once, raw);
    // maskName is NOT idempotent and never was: its fallback output (`Omar 06…67`) has fewer than seven digits,
    // so a second pass takes the initials branch (`Omar 0.`). It loses detail; it must never gain digits.
    const name = maskName(`Omar ${raw}`);
    assert.ok(digitsIn(maskName(name)) <= digitsIn(name), raw);
  }
});

test('maskName decides with the same mechanism: a date in a name is a number now (fallback); a separated number too', () => {
  assert.equal(maskName('Anna Schmidt 26.10.2026'), 'Anna S. 26…26');
  assert.equal(maskName(`Omar ${splitBy('⠀')}`), 'Omar 06…67');
  // Initials can join digits the input kept apart; the reduced form is asked again and masked.
  assert.ok(digitsIn(maskName('Anna12345 6a 7')) <= 4, maskName('Anna12345 6a 7'));
});

test('BOUND: an invisible LETTER between the digits defeats the run count — data minimisation, not a boundary', () => {
  // The Hangul filler U+3164 is `Lo`: to the mechanism it is a letter, exactly like `0a6a6a0…`. Asserted so no
  // comment can quietly claim more. maskName still reduces the token to its first character, so a NAME does
  // not leak it; free text and the tripwire do not see it.
  const hangul = splitBy('ㅤ');
  assert.match('ㅤ', /\p{L}/u);
  assert.equal(maskName(`Omar ${hangul}`), 'Omar 0.');
  assert.equal(digitsIn(maskFreeText(`call ${hangul}`)), 11);
  assert.doesNotThrow(() => assertMasked(hangul, 'text'));
  assert.equal(digitsIn(maskFreeText(`call ${splitBy('a')}`)), 11);
});

test('the \\p{Nd}→ASCII mapping\'s assumption holds in this runtime: every decimal-digit stretch is whole tens', () => {
  // asciiDigit() reads a digit's value as its distance from the start of its contiguous \p{Nd} stretch, mod 10.
  // That is only right if Unicode encodes every decimal set as a full 0..9 range; checked over the whole space.
  const nd = /\p{Nd}/u;
  let start = -1;
  const bad: string[] = [];
  for (let cp = 0; cp <= 0x110000; cp++) {
    const isNd = cp < 0x110000 && !(cp >= 0xD800 && cp <= 0xDFFF) && nd.test(String.fromCodePoint(cp));
    if (isNd && start < 0) start = cp;
    if (!isNd && start >= 0) { if ((cp - start) % 10 !== 0) bad.push(start.toString(16)); start = -1; }
  }
  assert.deepEqual(bad, []);
});

// ── MASK v3 golden table — every row asserted EXACTLY. This, not assertMasked, is the proof. ──────────────────────
for (const row of [...MASKED, ...UNMASKED]) {
  test(`GOLDEN: ${JSON.stringify(row.input)} → ${JSON.stringify(row.output)} (${row.why})`, () => {
    assert.equal(maskFreeText(row.input), row.output);
  });
}

test('GOLDEN table sanity: masked rows lose digits, unmasked rows keep every one, and both are fixed points', () => {
  // A row filed on the wrong side, or an expected output that is itself not stable, would make the table lie.
  for (const { input, output } of MASKED) {
    assert.ok(digitsIn(output) < digitsIn(input.normalize('NFKC')), `${input} → ${output}`);
  }
  for (const { input, output } of UNMASKED) {
    assert.equal(digitsIn(output), digitsIn(input.normalize('NFKC')), `${input} → ${output}`);
  }
  for (const { output } of [...MASKED, ...UNMASKED]) {
    assert.equal(maskFreeText(output), output, output);
    assert.equal(assertMasked(output, 'golden'), output);
  }
  assert.ok(MASKED.length >= 60 && UNMASKED.length >= 8);
});

test('FALLBACK: a phone written exactly as a date or time shape is masked — the v3 exemption leak, closed by removal', () => {
  assert.equal(maskFreeText('Tel 2012-12-12'), 'Tel 20…12');
  assert.equal(maskFreeText('Tel +2012-12-12'), 'Tel +20…12');
  assert.equal(maskFreeText('Tel 12.12-12.12'), 'Tel 12…12');
  assert.equal(maskFreeText('Tel 0 2012-12-12'), 'Tel 02…12');
});

// ── M1: maskFreeText's multi-line output must pass assertMasked, and be a fixed point ───────────────────────────
const MULTI_LINE = [
  'call 0660 12\n345 67 thanks',                   // eleven digits across one break: masked as one number (R1d)
  'room 12345\nmy number is 0660 1234567',          // a short number, then a phone on the next line
  'first 0660 123\r\nsecond 456 7890\r\nthird ok',  // CRLF, three lines
  '0660\n123 45',
  '26.10.2026\n14:00-15:30\n+43 660 1234567',
];

test('assertMasked(maskFreeText(x)) does not throw for multi-line input — the old ` · ` join made it refuse its own output', () => {
  for (const raw of MULTI_LINE) {
    const out = maskFreeText(raw);
    assert.doesNotThrow(() => assertMasked(out, 'text'), `${JSON.stringify(raw)} → ${JSON.stringify(out)}`);
    assert.ok(out.includes('\n'), `${JSON.stringify(raw)} lost its line break: ${JSON.stringify(out)}`);
  }
  assert.equal(maskFreeText('room 12345\nmy number is 0660 1234567'), 'room 12345\nmy number is 06…67');
});

test('maskFreeText is idempotent on multi-line input', () => {
  for (const raw of MULTI_LINE) {
    const once = maskFreeText(raw);
    assert.equal(maskFreeText(once), once, JSON.stringify(raw));
  }
});
