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
 * A person's name: first name, then initials. `Anna Maria Schmidt` → `Anna M. S.`
 * The owner runs a barbershop and knows their customers by first name; a surname on a screen that
 * might be photographed buys nothing.
 */
export function maskName(raw: string | undefined | null): string {
  const s = (raw ?? '').trim();
  const parts = s.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '—';

  // ⚠ THE FIRST FIX OF S3 WAS NARROWER THAN THE DEFECT, and the test pinned only the shape it did
  // catch. The trigger was `/\d{5,}/` — five CONSECUTIVE digits — but people type a number with
  // separators, and then the longest run is four. Measured (`code-reviewer`, 2026-09-12):
  // `0660-123-4567`, `0660.123.4567`, `+43-660-123-4567` and `0660/123/4567` all came through
  // UNTOUCHED and `assertMasked` passed every one of them — no 5-run, no `@`. So the decision is
  // taken on the RAW input's digit COUNT, which separators cannot dilute. Seven is the shortest
  // national subscriber number worth protecting; a year or a house number stays a name.
  // `\p{Nd}` rather than `\d`: the sentence above says "the RAW input's digit COUNT", and `\d` is
  // ASCII-only, so an Eastern-Arabic-numeral phone number counted as zero digits (`code-reviewer`).
  const digitCount = s.replace(/\p{Nd}/gu, '#').replace(/[^#]/g, '').length;
  if (/@/.test(s) || digitCount >= 7) return maskFreeText(s, 40);

  const [first, ...rest] = parts;

  // ⚠ S3 (security-auditor, 2026-09-12): a SINGLE token was returned untouched, so a "name" that is
  // really a phone number or an email came straight through — and this is not hypothetical. The name
  // comes from `slots.customerName`, which `schemas/intent.schema.json` declares as a free string with
  // no pattern and no maxLength: it is whatever the model pulled out of the customer's own sentence.
  // Both call sites rendered it unguarded while masking the phone in the very next column.
  const masked = [first, ...rest.map((p) => `${[...p][0]}.`)].join(' ');
  if (/@/.test(masked) || /\d{5,}/.test(masked)) return maskFreeText(masked, 40);
  return masked;
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
 * What it catches, and what it cannot: emails and digit runs — including numbers written with spaces,
 * dots or dashes, which is how people actually type them. It does NOT catch a name, an address or a
 * handle, and it never will by regex. `assertMasked` is applied to the result, so a run this misses
 * still cannot reach a screen — it raises instead, which is the honest failure direction.
 */
export function maskFreeText(raw: string | undefined | null, max = 160): string {
  let s = (raw ?? '').replace(/\r/g, '').trim();
  if (!s) return '—';

  // Email first: its local part can contain digits that the phone rule would otherwise chew up.
  s = s.replace(/\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g,
                (_m, first, domain) => `${first}…@${domain}`);

  // A phone number as humans type it: an optional +, then 7 or more digits with spaces, dots, dashes,
  // slashes or brackets anywhere between them. Keep the leading country/area hint and the last two —
  // the same shape maskPhone produces, so the two surfaces agree.
  s = s.replace(/\+?\d[\d\s.\-()/]{5,}\d/g, (m) => {
    const digits = m.replace(/\D/g, '');
    if (digits.length < 7) return m;                  // a date or a price, not a number to hide
    const head = m.trim().startsWith('+') ? `+${digits.slice(0, 2)}` : digits.slice(0, 2);
    return `${head}…${digits.slice(-2)}`;
  });

  // Any remaining long run of digits — an order id, an IBAN fragment, something we did not model.
  s = s.replace(/\d{5,}/g, (m) => `${m.slice(0, 2)}…${m.slice(-2)}`);

  // Newlines become a visible separator rather than vanishing: the engine stores the last five
  // messages newline-joined, and collapsing them into one paragraph hid where one message ended.
  s = s.replace(/\n+/g, ' · ').replace(/[ \t]+/g, ' ').trim();

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
 * WHAT IT CATCHES: a run of five or more digits, and an email address. WHAT IT DOES NOT: a person's
 * name, a street address, a social handle, or a widget `sender_key` (which has no digit run at all).
 * It is a tripwire on the shapes that are mechanically recognisable — not a proof of masking.
 */
export function assertMasked(value: string, what: string): string {
  if (/[0-9]{5,}/.test(value)) {
    throw new Error(`${what} still contains a run of 5+ digits after masking: refusing to render it.`);
  }
  if (/\b[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/.test(value)) {
    throw new Error(`${what} still contains a full email address after masking: refusing to render it.`);
  }
  return value;
}
