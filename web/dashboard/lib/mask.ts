/**
 * PII masking — applied on the SERVER, before any value crosses a boundary.
 *
 * WHERE THE BOUNDARY ACTUALLY IS, and why this file exists at all. It is tempting to mask in the
 * component that renders the value. That is too late, and the reason is the one CRT #10b names:
 * Next serialises a client component's PROPS into the RSC payload, which is plain text inside the
 * HTML. A full phone number handed to a client component is in the page source even though no pixel
 * ever shows it. Measured on `web/site` — the whole client config is sitting in the built
 * `index.html` for exactly this reason. So the rule here is: **mask at the data layer, and let the
 * unmasked value stop there.**
 *
 * A screenshot is the other threat, and it is the likelier one. The owner will photograph this
 * dashboard to send a colleague a booking. Every masked form below is designed to survive that:
 * enough to recognise a row, never enough to reconstruct the value.
 */

/**
 * A phone number: keep the country prefix and the last two digits.
 * `+43 660 1234567` → `+43…67`. The prefix tells the owner which country/channel; the last two let
 * them match it against a message on their own phone. Nothing in between is recoverable.
 */
export function maskPhone(raw: string | undefined | null): string {
  const s = (raw ?? '').trim();
  if (!s) return '—';
  const digits = s.replace(/[^\d+]/g, '');
  // Threshold 8, not 4: at 6 digits the old rule showed four of them and the collision property the
  // tests assert stopped holding (code-reviewer A10). Anything this short is masked entirely.
  // ⚠ The count must EXCLUDE the leading `+`, or the threshold is silently 7: `+12345678` has eight
  // characters but seven digits, and passed — showing four of the seven, which is the very ratio A10
  // rejected. Counted on digits alone now.
  const digitCount = s.replace(/\D/g, '').length;
  if (digitCount <= 8) return '•'.repeat(Math.max(Math.min(digitCount, 8), 1));
  const head = digits.startsWith('+') ? digits.slice(0, 3) : digits.slice(0, 2);
  return `${head}…${digits.slice(-2)}`;
}

/**
 * Steps 1–2 of the single mechanism below: NFKC, then remove every `\p{Cf}` format character. NFKC folds
 * compatibility forms onto their plain ones (superscript `⁶` → `6`, fullwidth `＠` → `@`, fullwidth `６` → `6`);
 * `\p{Cf}` (zero-width space, word joiner, BOM, soft hyphen …) renders as nothing, so a digit run split by one
 * is a run on the screen. Both are applied to the text that is MASKED and RETURNED, so what is checked is what
 * a reader sees. The cost, accepted: a joiner inside an emoji sequence or a ZWNJ inside a name is removed.
 * ⚠ `…` IS KEPT OUT OF NFKC, because NFKC turns it into `...` and `…` is this module's own mask marker:
 * `a…@example.com` became `a...@example.com`, which the email tripwire reads as a full address, so
 * `assertMasked` rejected the module's own output (measured: two tests went red when it was folded).
 */
function normalise(raw: string): string {
  return raw.split('…').map((part) => part.normalize('NFKC')).join('…').replace(/\p{Cf}/gu, '');
}

const ND = /^\p{Nd}$/u;
/**
 * Step 3: a `\p{Nd}` code point → its ASCII digit, by numeric value, for EVERY Unicode decimal-digit block.
 * Unicode encodes each decimal digit set as a contiguous 0..9 range (adjacent sets, like the mathematical digits,
 * are back to back), so the value is the distance from the start of the contiguous `\p{Nd}` stretch, mod 10.
 * That property is asserted over the whole code space by a test, so a runtime with a different Unicode table
 * cannot make this quietly wrong.
 */
function asciiDigit(ch: string): string {
  if (!ND.test(ch)) return ch;
  let start = ch.codePointAt(0)!;
  while (ND.test(String.fromCodePoint(start - 1))) start--;
  return String((ch.codePointAt(0)! - start) % 10);
}

const LETTER = /^\p{L}$/u;

/** Step 7's threshold: seven digits is the shortest national subscriber number worth protecting. */
const RUN_DIGITS = 7;

/**
 * THE ONE MASKING MECHANISM (MASK v3 in its pre-committed FALLBACK form, ruling 2026-10-26; the line rule of R1d) —
 * `maskName` takes its decision from it, `maskFreeText` takes its output from it, and `assertMasked` re-runs it as an
 * idempotence check. Input is `normalise`d text (steps 1–2):
 *   3. every `\p{Nd}` is read as its ASCII digit (analysis only — the output keeps the digit's own script);
 *   4. the text is split at newlines and each line is cut into maximal runs of NON-LETTER characters (`\P{L}`:
 *      spaces, punctuation, symbols, marks, anything);
 *   5. NO EXEMPTION. v3 exempted a run whose whole edge-stripped form was exactly one date/time shape; its own
 *      adversarial search then found phones written exactly as such a shape passing unmasked (`Tel 2012-12-12`,
 *      `Tel 12.12-12.12`, `Tel +2012-12-12` — the `+` is a symbol, so the edge strip removed it). That is the class
 *      the R1b boundary leaked, found again, and the ruling pre-committed the answer: no exemption at all, over-mask,
 *      no further design. v3's exemption is kept out of the code, not commented out;
 *   6. ACROSS ONE LINE BREAK (ruling D, R1d): the run that ends a line (it reaches the line's end) and the run that
 *      starts the next line (it starts at column 0) are counted TOGETHER when both hold a digit — a newline is a
 *      non-letter too, so for the decision they are one run. A number typed over two lines (`0660\n123 4567`) was
 *      shown in full by the line-by-line rule of M1. Each pair of adjacent lines is judged on its own;
 *   7. a run with seven or more digits — alone, or together with its partner across a line break — is masked: every
 *      digit of the ORIGINAL run goes, from its first digit (or a `+` directly before it) to its last. A run that is
 *      masked alone keeps the first two digits and the last two in their own script, `…` between (`+43…67`,
 *      `06…67`). A run masked WITH a partner keeps the head only where the number starts and the tail only where it
 *      ends, so the lines stay lines on the screen and the pair shows no more than one number would: `0660\n123 4567`
 *      → `06…\n…67`; a line whose only run continues the number above AND the one below shows `…` alone
 *      (`0660\n123\n4567` → `06…\n…\n…67`). The run's characters before that span and after it hold no digit
 *      and are kept, so the words round a number stay apart.
 * It does NOT enumerate separators. A blank Braille cell (U+2800, `So`), a musical symbol (U+1D159), a combining
 * mark or a keycap between the digits is a non-letter like a space, so it extends the run instead of splitting it.
 *
 * RECORDED BOUNDS — what this does not do, by design, so no comment or test can claim more:
 *   - a 5- or 6-digit number is NOT masked (the threshold is seven digits per run, or per pair across one break);
 *   - each adjacent pair of lines is judged on its own; digits are never summed over more than two lines, so a
 *     number spread over three or more lines whose every adjacent pair holds fewer than seven digits (`06\n123\n45`)
 *     is not masked, nor is a pair with a letter between a digit and the break;
 *   - a vanity number (letters, `0800-FRISEUR`) is not caught; letters end a run, an invisible LETTER included
 *     (the Hangul filler U+3164 is `Lo`), so digits interleaved with letters on purpose defeat it;
 *   - dates, times, ranges, lists and prices with seven or more digits in one non-letter run — or in two runs
 *     that meet at a line break — are OVER-masked: `26.10.2026` → `26…26`, `14:00–15:30` → `14…30`,
 *     `12:00\n13:00` → `12…\n…00`, `0660 1234567, 0660 7654321`, `1.250.000,00`. A date the owner needs is in the
 *     booking's own columns, which are not free text;
 *   - built for NON-ADVERSARIAL input: this is data minimisation for an owner's screen and a screenshot, NOT a
 *     security boundary.
 */
interface Run { i: number; j: number; digitAt: number[]; prev: boolean; next: boolean }

function maskDigitRuns(text: string): { out: string; masked: number } {
  const lines = text.split('\n').map((line) => {
    const cps = [...line];
    // One analysis character per code point: a `\p{Nd}` as its ASCII digit, everything else as itself.
    const ana = cps.map(asciiDigit);
    const runs: Run[] = [];
    let i = 0;
    while (i < cps.length) {
      if (LETTER.test(cps[i])) { i++; continue; }
      let j = i;
      while (j < cps.length && !LETTER.test(cps[j])) j++;
      const digitAt: number[] = [];
      for (let k = i; k < j; k++) if (/^[0-9]$/.test(ana[k])) digitAt.push(k);
      runs.push({ i, j, digitAt, prev: false, next: false });
      i = j;
    }
    return { cps, runs };
  });

  // Step 6: a line's last run, when it reaches the line's end, meets the next line's first run, when it starts at 0.
  for (let k = 0; k + 1 < lines.length; k++) {
    const up = lines[k].runs[lines[k].runs.length - 1];
    const down = lines[k + 1].runs[0];
    if (!up || !down || up.j !== lines[k].cps.length || down.i !== 0) continue;
    if (!up.digitAt.length || !down.digitAt.length || up.digitAt.length + down.digitAt.length < RUN_DIGITS) continue;
    up.next = true;
    down.prev = true;
  }

  let masked = 0;
  const out = lines.map(({ cps, runs }) => {
    let res = '';
    let at = 0;
    for (const r of runs) {
      res += cps.slice(at, r.i).join('');
      at = r.j;
      const d = r.digitAt;
      if (d.length < RUN_DIGITS && !r.prev && !r.next) { res += cps.slice(r.i, r.j).join(''); continue; }
      masked++;
      const first = d[0];
      const last = d[d.length - 1];
      const from = first > r.i && cps[first - 1] === '+' ? first - 1 : first;
      const head = r.prev ? '' : `${from < first ? '+' : ''}${d.slice(0, 2).map((k) => cps[k]).join('')}`;
      const tail = r.next ? '' : d.slice(-2).map((k) => cps[k]).join('');
      // Marks right after the last digit are drawn ON it (a keycap six is `6` U+FE0F U+20E3), so they go with it.
      let after = last + 1;
      while (after < r.j && /^\p{M}$/u.test(cps[after])) after++;
      res += `${cps.slice(r.i, from).join('')}${head}…${tail}${cps.slice(after, r.j).join('')}`;
    }
    return res + cps.slice(at).join('');
  }).join('\n');
  return { out, masked };
}

/**
 * A person's name: first name, then initials. `Anna Maria Schmidt` → `Anna M. S.`
 * The owner runs a barbershop and knows their customers by first name; a surname on a screen that
 * might be photographed buys nothing.
 */
export function maskName(raw: string | undefined | null): string {
  const s = normalise(raw ?? '').trim();
  const parts = s.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '—';

  // ⚠ THE FIRST FIX OF S3 WAS NARROWER THAN THE DEFECT, and the test pinned only the shape it did
  // catch. The trigger was `/\d{5,}/` — five CONSECUTIVE digits — but people type a number with
  // separators, and then the longest run is four. Measured (`code-reviewer`, 2026-09-12):
  // `0660-123-4567`, `0660.123.4567`, `+43-660-123-4567` and `0660/123/4567` all came through
  // UNTOUCHED and `assertMasked` passed every one of them — no 5-run, no `@`. The decision is now the
  // one `maskFreeText` and `assertMasked` use: does `maskDigitRuns` find a non-letter run with seven or
  // more digits, in any script, whatever separates them. A year or a house number stays a name.
  // ⚠ ONE LINE AT A TIME (R1d): a name is printed on one line (its tokens re-joined with spaces), so the line-break
  // pairing of `maskDigitRuns` buys a name nothing — and it sent `Anna 0660\n123 b 456789` down the fallback branch
  // below, which keeps short runs whole: ten digits shown where the initials branch showed three (lane D review,
  // R1d). Asked per line, the decision is the R1c one; the initials branch and its re-check catch what joins up.
  const hasNumber = s.split('\n').some((line) => maskDigitRuns(line).masked > 0);
  const [first, ...rest] = parts;
  // ⚠ THIS FALLBACK USED TO BE `maskFreeText(s, 40)` ON THE WHOLE STRING, which masks digits and emails and
  // nothing else — so `First Surname 1234567` came out with the surname in full, past `assertMasked`, into
  // both panels and both CSV files (Codex CRT #9, 7-2 Tur 1). The surname rule is not optional on this
  // branch: every token after the first loses its letters to an initial, and only then does the free-text
  // masker deal with the digits and the email. Inside a token, only a VALID email match is left whole for the
  // email rule (which keeps one character of its local part); the letters around it go to initials too. The
  // first version left any `@`-token whole, so `Schmidt/anna@example.com` kept the surname (Lane D review).
  if (/@/.test(s) || hasNumber) {
    return maskFreeText([first, ...rest.map(reduceToken)].join(' '), 40);
  }

  // ⚠ S3 (security-auditor, 2026-09-12): a SINGLE token was returned untouched, so a "name" that is
  // really a phone number or an email came straight through — and this is not hypothetical. The name
  // comes from `slots.customerName`, which `schemas/intent.schema.json` declares as a free string with
  // no pattern and no maxLength: it is whatever the model pulled out of the customer's own sentence.
  // Both call sites rendered it unguarded while masking the phone in the very next column.
  // Initials can JOIN digits the input kept apart (`Anna12345 6a 7` → `Anna12345 6. 7.`: the `a` that split the
  // run is gone), so the reduced form is asked the same question again.
  const masked = [first, ...rest.map((p) => `${[...p][0]}.`)].join(' ');
  if (/@/.test(masked) || maskDigitRuns(masked).masked > 0) return maskFreeText(masked, 40);
  return masked;
}

/** Letter runs to initials: `Schmidt` → `S.`; digits and punctuation are left for `maskFreeText`. */
function initials(t: string): string {
  return t.replace(/\p{L}[\p{L}\p{M}]*/gu, (w) => `${[...w][0]}.`);
}

/**
 * One name token after the first, on the digit/email fallback. A plain word is an initial. A token with a
 * digit or a valid email keeps those for `maskFreeText` and loses every letter run around them. A token with
 * an `@` that is not a valid email is a plain initial: there is nothing in it the email rule would recognise.
 */
function reduceToken(p: string): string {
  if (!/[@\p{Nd}]/u.test(p)) return `${[...p][0]}.`;
  const emails = [...p.matchAll(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g)];
  if (/@/.test(p) && emails.length === 0) return `${[...p][0]}.`;
  let out = '';
  let at = 0;
  for (const m of emails) {
    out += initials(p.slice(at, m.index)) + m[0];
    at = m.index + m[0].length;
  }
  return out + initials(p.slice(at));
}

/**
 * A `sender_key` — `"{channel}:{id}"`.
 *
 * ⚠ This one is NOT ordinary PII: `security-secrets.md` measured it to be **session-token strength**
 * on the widget lane, because `Find Booking` looks appointments up by it and on the widget it derives
 * from the client-supplied `sessionId`. Anyone holding the full value can post it as their own and
 * reach that conversation's cancel/reschedule. So it is masked harder than a phone number, and the
 * CHANNEL is kept in clear on purpose — it is a fixed literal (`whatsapp:`, `widget:`), it carries no
 * entropy, and it is the single most useful thing on the row: it tells the owner WHERE to reply.
 *
 * `widget:w-4f3a91c2…` → `widget:w-4f3a…`   ·   `whatsapp:+436601234567` → `whatsapp:+43…67`
 */
export function maskSenderKey(raw: string | undefined | null): string {
  const s = (raw ?? '').trim();
  // `—` is this module's own "nothing here" output, so it must survive a second pass unchanged —
  // without this it became `—…`, which reads as a truncated value rather than an absent one.
  if (!s || s === '—') return '—';
  const at = s.indexOf(':');
  if (at < 0) return `${s.slice(0, 4)}…`;
  const channel = s.slice(0, at);
  const id = s.slice(at + 1);

  // ⚠ IDEMPOTENT BY CONSTRUCTION, AND THE FIRST ATTEMPT AT IT WAS A HOLE. That version short-circuited
  // on `s.includes('…')` — "it has an ellipsis, so it is already masked". It is not: the Airtable
  // formula's ORIGINAL defect produced exactly `<the whole key>…`, appending an ellipsis that claimed a
  // truncation it had not performed, on 91 of 592 rows. So the one shape most likely to arrive here
  // unmasked was the one shape that was waved through, and the counter stayed silent because the value
  // equalled its own "re-masking" (`code-reviewer`, 2026-09-12, third pass).
  //
  // Detecting "already masked" by a CHARACTER cannot work. Producing a canonical form can: every branch
  // below is a function of the id's leading characters only, so masking a masked value returns it
  // unchanged while a full value is always cut. The one exception that genuinely cannot be re-derived
  // is a masked PHONE (`+43…67` has already lost its middle), so that single shape — the exact output
  // `maskPhone` emits, not "anything with an ellipsis" — is matched precisely and returned as is.
  if (/^\+?\d{1,3}…\d{2}$/.test(id)) return `${channel}:${id}`;

  // A phone-shaped id is masked as a phone whether or not it carries a `+`: the WhatsApp lane builds
  // `whatsapp:${senderId}` from the provider's MSISDN and nothing guarantees the plus, so keying on it
  // sent a bare national number down the prefix branch and printed its first six digits.
  const stripped = id.replace(/…+$/, '');
  if (stripped && /^\+?[\d\s().-]+$/.test(stripped)) return `${channel}:${maskPhone(stripped)}`;

  // Everything else keeps a short prefix and nothing more. `w-` is a fixed literal in chatClient.ts,
  // so `widget:w-` on its own leaks zero entropy — and slicing is idempotent, which is the point.
  return `${channel}:${stripped.slice(0, 6)}…`;
}

/**
 * Free text a customer wrote — `recent_messages`, a lead's first line, a note.
 *
 * ⚠ THIS USED TO BE CALLED `maskText` AND IT ONLY TRUNCATED. That was the single worst defect in this
 * file, because the name asserted a control the code did not perform: `LeadsPanel` reduced a phone to
 * `+43…67` while the handoff queue printed the SAME number in full, three rows away, inside the
 * customer's own sentence. A lead-capture bot's whole job is to make people type their phone number
 * into the chat (`code-reviewer`, 2026-09-12).
 *
 * So it now MASKS FIRST and truncates second, and the order matters: truncating first would leave a
 * half-written phone number that the masker no longer recognises.
 *
 * What it catches, and what it cannot: emails, and any number of seven or more digits as `maskDigitRuns`
 * defines it — in any script, whatever non-letter characters sit between the digits. A date or a time range is
 * eight digits and is OVER-masked too (`26.10.2026` → `26…26`, `14:00–15:30` → `14…30`): the fallback has no
 * exemption (ruling 2026-10-26). It does NOT catch a
 * name, an address or a handle, and it never will by pattern; the bounds are listed on `maskDigitRuns`.
 * ⚠ `assertMasked` on the result is NOT a second check on this function: it runs the same mechanism, so a run
 * this misses, it misses too. The proof is the golden table, `lib/mask.golden.ts`.
 *
 * Message boundaries are kept as `\n` (ruling 2026-10-26, M1). The engine stores the last messages newline-joined;
 * the old ` · ` join put two lines into one, so the run counter read digits ACROSS messages and `assertMasked`
 * refused this function's own output. Since R1d the DECISION reads across one line break again (step 6 of
 * `maskDigitRuns`) while the OUTPUT keeps the lines: a number split over two lines is masked as one. The one
 * component that renders it, `HandoffQueue`, does so with `white-space: pre-line` (`.q-text` in app/globals.css).
 * `maskName`'s call into this function cannot carry a newline: it re-joins its tokens with spaces first (its own
 * decision asks `maskDigitRuns` one line at a time).
 */
export function maskFreeText(raw: string | undefined | null, max = 160): string {
  let s = normalise(raw ?? '').replace(/\r/g, '').trim();
  if (!s) return '—';

  // Email first: its local part can contain digits that the number rule would otherwise chew up.
  s = s.replace(/\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g,
                (_m, first, domain) => `${first}…@${domain}`);

  // One message per line, as the engine stored them: spaces collapsed inside a line, blank lines dropped. BEFORE the
  // number rule, so the lines it pairs across a break (step 6 of `maskDigitRuns`) are the lines the screen shows:
  // dropped afterwards, a blank line would have kept `0660` and `123 4567` apart for the decision and adjacent on
  // the screen.
  s = s.split('\n').map((line) => line.replace(/[ \t]+/g, ' ').trim()).filter(Boolean).join('\n');

  // Then every number: the same shape maskPhone produces (`+43…67`, `06…67`), so the two surfaces agree.
  s = maskDigitRuns(s).out;

  if (s.length > max) {
    const cut = s.slice(0, max);
    const lastSpace = cut.lastIndexOf(' ');
    s = `${(lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
  }
  return s;
}

/**
 * A last-chance check on a value about to be rendered.
 *
 * ⚠ ITS DOCSTRING USED TO CLAIM "nothing may reach a client component without passing through here",
 * and that was false twice over: nothing enforces it, and the panels do not all call it. Corrected to
 * what it actually does (`code-reviewer`, 2026-09-12).
 *
 * WHAT IT IS: an IDEMPOTENCE GUARD. It refuses a value that `maskDigitRuns` would still change — a non-letter
 * run holding seven or more digits, alone or with its partner across one line break — and a full email address.
 * Because it calls the SAME function the maskers use, it cannot detect that function's errors: an input the
 * mechanism wrongly leaves unmasked, it wrongly passes.
 * What it does catch is a value that never went through a masker, or a masker whose output is not a fixed point.
 * WHAT IT DOES NOT SEE, in addition: a person's name, a street address, a social handle, a widget `sender_key`
 * (its digits are split by letters), and everything listed under RECORDED BOUNDS on `maskDigitRuns`.
 * It is not proof of masking; that is `lib/mask.golden.ts`, an input → exact-output table asserted row by row.
 */
export function assertMasked(value: string, what: string): string {
  // It asks the masking mechanism itself, never a regex of its own: a second definition of "a number" is the
  // copy that drifts (`contract-integrity.md`), and it is how the old tripwire shared the maskers' blind spots.
  const seen = normalise(value);
  if (maskDigitRuns(seen).masked > 0) {
    throw new Error(`${what} still contains a run of ${RUN_DIGITS}+ digits after masking: refusing to render it.`);
  }
  if (/\b[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/.test(seen)) {
    throw new Error(`${what} still contains a full email address after masking: refusing to render it.`);
  }
  return value;
}
