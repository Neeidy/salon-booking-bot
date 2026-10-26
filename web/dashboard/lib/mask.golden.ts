/**
 * MASK v3 golden table, FALLBACK form (ruling 2026-10-26: v3's date/time exemption leaked phones written exactly as
 * a date or time shape, so the pre-committed fallback applies — no exemption, over-mask). `maskFreeText(input)` must
 * equal `output` EXACTLY, row by row
 * (asserted in `lib/mask.test.ts`). This table, not `assertMasked`, is the proof of the masking mechanism:
 * `assertMasked` calls the same function and cannot see its errors; a literal expected output can.
 *
 * Every number is SYNTHETIC — mostly the digits of `0660 1234567` re-written, or dates used as digit groups.
 * Invisible and look-alike characters are written as `\u` escapes so a reviewer can see them.
 * Each expected output follows from the rule alone: ≥7 digits in one non-letter run → first two, `…`, last two; a run
 * paired across a line break (R1d) keeps only the head above the break and only the tail below it.
 */
export interface GoldenRow { input: string; output: string; why: string }

/** Each must come out with its digits reduced to the mask token (or, for an over-mask, said so in `why`). */
export const MASKED: GoldenRow[] = [
  // ── the R1b leak class (one group formed a date or time and R1b's boundary hid it): each is one run of ≥7 digits ──
  { input: 'Tel 2012-12-12-34', output: 'Tel 20…34', why: 'ten digits in one run' },
  { input: '20.12.2012-34-56', output: '20…56', why: 'dotted date plus two groups' },
  { input: '+43 1 2012-12-12', output: '+43…12', why: 'country and area code before a date-shaped group' },
  { input: '0664 2012-12-12', output: '06…12', why: 'mobile prefix before a date-shaped group' },
  { input: '+43 664 20.12.2012', output: '+43…12', why: 'country and mobile prefix before a dotted date' },
  { input: '0171.12.12.2012', output: '01…12', why: 'dotted groups ending in a dotted date' },
  { input: '12:30-45-67-89', output: '12…89', why: 'a time followed by dashed pairs' },
  { input: 'call 0660-12-12-34', output: 'call 06…34', why: 'dashed pairs, ten digits in one run' },
  { input: 'call 0660-12-12', output: 'call 06…12', why: 'eight digits in one run (4-2-2)' },
  // ── the 14 leak forms of R1b, each in a sentence ──
  { input: 'call \u0660\u0666\u0666\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667 please', output: 'call \u0660\u0666…\u0666\u0667 please', why: 'Arabic-Indic digits keep their script' },
  { input: 'call \uFF10\uFF16\uFF16\uFF10\uFF11\uFF12\uFF13\uFF14\uFF15\uFF16\uFF17 please', output: 'call 06…67 please', why: 'fullwidth digits: NFKC folds them to ASCII' },
  { input: 'call 0\u200B6\u200B6\u200B0\u200B1\u200B2\u200B3\u200B4\u200B5\u200B6\u200B7 please', output: 'call 06…67 please', why: 'zero-width space U+200B' },
  { input: 'call 0\u200C6\u200C6\u200C0\u200C1\u200C2\u200C3\u200C4\u200C5\u200C6\u200C7 please', output: 'call 06…67 please', why: 'zero-width non-joiner U+200C' },
  { input: 'call 0\u200D6\u200D6\u200D0\u200D1\u200D2\u200D3\u200D4\u200D5\u200D6\u200D7 please', output: 'call 06…67 please', why: 'zero-width joiner U+200D' },
  { input: 'call 0\u20606\u20606\u20600\u20601\u20602\u20603\u20604\u20605\u20606\u20607 please', output: 'call 06…67 please', why: 'word joiner U+2060' },
  { input: 'call 0\uFEFF6\uFEFF6\uFEFF0\uFEFF1\uFEFF2\uFEFF3\uFEFF4\uFEFF5\uFEFF6\uFEFF7 please', output: 'call 06…67 please', why: 'BOM U+FEFF' },
  { input: 'call 0\u00AD6\u00AD6\u00AD0\u00AD1\u00AD2\u00AD3\u00AD4\u00AD5\u00AD6\u00AD7 please', output: 'call 06…67 please', why: 'soft hyphen U+00AD' },
  { input: 'call 0\u28006\u28006\u28000\u28001\u28002\u28003\u28004\u28005\u28006\u28007 please', output: 'call 06…67 please', why: 'Braille blank U+2800 (So, not Cf)' },
  { input: 'call 0\u{1D159}6\u{1D159}6\u{1D159}0\u{1D159}1\u{1D159}2\u{1D159}3\u{1D159}4\u{1D159}5\u{1D159}6\u{1D159}7 please', output: 'call 06…67 please', why: 'musical symbol U+1D159 (So, not Cf)' },
  { input: 'call 0660 123 45 67 please', output: 'call 06…67 please', why: 'spaces' },
  { input: 'call 0660-123-45-67 please', output: 'call 06…67 please', why: 'dashes' },
  { input: 'call 0660.123.45.67 please', output: 'call 06…67 please', why: 'dots' },
  { input: 'call +43 (660) 123-45.67 please', output: 'call +43…67 please', why: 'mixed separators with a country prefix' },
  // ── more forms ──
  { input: 'call \u2070\u2076\u2076\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077 please', output: 'call 06…67 please', why: 'superscript digits are No, not Nd: only NFKC makes them digits' },
  { input: 'call 0\uFE0F\u20E36\uFE0F\u20E36\uFE0F\u20E30\uFE0F\u20E31\uFE0F\u20E32\uFE0F\u20E33\uFE0F\u20E34\uFE0F\u20E35\uFE0F\u20E36\uFE0F\u20E37\uFE0F\u20E3 please', output: 'call 06…67 please', why: 'keycap digits: the marks on the last digit go with it' },
  { input: 'call +43 660 1234567', output: 'call +43…67', why: 'a + directly before the first digit is kept' },
  { input: 'ref \u0662\u0669.\u0661\u0669.\u0662\u0660\u0662\u0666', output: 'ref \u0662\u0669…\u0662\u0666', why: 'eight Arabic-Indic digits in one run keep their script' },
  { input: 'code 123 4567', output: 'code 12…67', why: 'seven digits: the threshold' },
  // ── masked under v3 too (near misses of its former exemption shapes) ──
  { input: 'ref 26.13.2026', output: 'ref 26…26', why: 'month 13' },
  { input: 'ref 32.10.2026', output: 'ref 32…26', why: 'day 32' },
  { input: 'ref 26.10.2126', output: 'ref 26…26', why: 'year 21xx' },
  { input: 'ref 2126-10-26 14:30', output: 'ref 21…30', why: 'ISO date and time' },
  { input: 'ref 24:00-24:30', output: 'ref 24…30', why: 'hour 24' },
  { input: 'ref 12:60-12:61', output: 'ref 12…61', why: 'minute 60' },
  { input: 'call 0626.10.2026', output: 'call 06…26', why: 'a date glued to more digits' },
  { input: 'call 12026-10-26', output: 'call 12…26', why: 'a five-digit "year"' },
  { input: 'call 0610:301', output: 'call 06…01', why: 'a time glued to more digits' },
  { input: '2026-10-26 14:30 15:30', output: '20…30', why: 'over-mask: a date and two times in one run' },
  // ── recorded over-masks: one run of seven or more digits ──
  { input: '26.10.2026 0660 1234567', output: '26…67', why: 'OVER-MASK: a date beside a phone is one run' },
  { input: '2026-10-26 / 2026-10-27', output: '20…27', why: 'OVER-MASK: a date range' },
  { input: 'am 26.10.2026, 14:30', output: 'am 26…30', why: 'OVER-MASK: a date and a time in one run' },
  { input: '0660 123 4567, 0660 765 4321', output: '06…21', why: 'OVER-MASK: a list is one run' },
  { input: 'Preis 1.250.000,00 €', output: 'Preis 12…00 €', why: 'OVER-MASK: a price' },
  // ── lines ──
  { input: 'first 0660 1234567\nsecond 26.10.2026', output: 'first 06…67\nsecond 26…26', why: 'each line is its own text; the date is over-masked' },
  { input: 'hi\r\n+43 660 1234567\r\nbye', output: 'hi\n+43…67\nbye', why: 'CRLF becomes LF; the phone on its line is masked' },
  // ── across ONE line break (ruling D, R1d): the run ending a line and the run starting the next count together ──
  { input: '0660 12\n34 567', output: '06…\n…67', why: 'six digits and five across one break: the head stays above, the tail below' },
  { input: '0660\n123 4567', output: '06…\n…67', why: 'a phone typed over two lines' },
  { input: 'Tel 0660\n1234567 bitte', output: 'Tel 06…\n…67 bitte', why: 'the words round the number stay on their lines' },
  { input: '+43 660\n123 45', output: '+43…\n…45', why: 'the country prefix stays with the head' },
  { input: '0660\n123\n4567', output: '06…\n…\n…67', why: 'three lines, each adjacent pair seven digits: the middle line shows no digit' },
  { input: 'Anruf 0660\n\n123 4567', output: 'Anruf 06…\n…67', why: 'a blank line is dropped BEFORE the decision, so the lines that touch on screen are paired' },
  { input: '0660 1234567\n89 bitte', output: '06…\n…89 bitte', why: 'a masked phone continued by digits on the next line: the head above, the tail below' },
  { input: '0660\nab 1234567', output: '0660\nab 12…67', why: 'a letter between the break and the digits: not paired, the lower line is masked alone and 0660 stays' },
  { input: 'ab 12 cd 0660\n123', output: 'ab 12 cd 06…\n…23', why: 'the LAST run of the upper line is paired, not its first (12 stays)' },
  { input: '0660\n123 ab 45', output: '06…\n…23 ab 45', why: 'the FIRST run of the lower line is paired, not its last (45 stays)' },
  { input: '0660 1234567\n- ok', output: '06…67\n- ok', why: 'the next line starts with a run that holds no digit: no partner, the phone is masked alone' },
  { input: '12:00\n13:00', output: '12…\n…00', why: 'OVER-MASK: two times on adjacent lines are eight digits across one break' },
  { input: '\u0660\u0666\u0666\u0660\n\u0661\u0662\u0663', output: '\u0660\u0666…\n…\u0662\u0663', why: 'Arabic-Indic digits across a break keep their script' },
  // ── FALLBACK: dates and times with seven or more digits in one run are over-masked (no exemption any more) ──
  { input: 'am 26.10.2026.', output: 'am 26…26.', why: 'over-mask: a date is eight digits' },
  { input: '14:00–15:30', output: '14…30', why: 'over-mask: a time range is eight digits' },
  { input: '9:30-10:30', output: '93…30', why: 'over-mask: seven digits' },
  { input: '26.10.2026 14.30', output: '26…30', why: 'over-mask: date and time' },
  { input: '2026-10-26 14:30', output: '20…30', why: 'over-mask: ISO date and time' },
  { input: '26.10.2026 14:00-15:30', output: '26…30', why: 'over-mask: date and time range' },
  { input: 'am 2026-10-26 14:30 – 15:00?', output: 'am 20…00?', why: 'over-mask: the trailing ? stays outside the span' },
  { input: 'free 14:00 — 15:30 ok', output: 'free 14…30 ok', why: 'over-mask: em-dash range' },
  { input: 'um 9.30-10.30', output: 'um 93…30', why: 'over-mask: dotted range, seven digits' },
  { input: '(26.10.2026)', output: '(26…26)', why: 'over-mask: the brackets hold no digit and stay' },
  { input: 'born 1999-01-31', output: 'born 19…31', why: 'over-mask: a birth date' },
  { input: 'see you on 31.12.2030 then', output: 'see you on 31…30 then', why: 'over-mask' },
  { input: 'on \u0662\u0666.\u0661\u0660.\u0662\u0660\u0662\u0666', output: 'on \u0662\u0666…\u0662\u0666', why: 'over-mask: an Arabic-Indic date keeps its script' },
  { input: 'at \u0967\u096A:\u0966\u0966-\u0967\u096B:\u0969\u0966', output: 'at \u0967\u096A…\u0969\u0966', why: 'over-mask: a Devanagari time range' },
  { input: 'on 26.\u200B10.2026', output: 'on 26…26', why: 'over-mask: the zero-width space is stripped first' },
  // ── the exemption leaks v3's own search found — the reason the fallback applies ──
  { input: 'Tel 2012-12-12', output: 'Tel 20…12', why: 'eight digits grouped exactly as an ISO date' },
  { input: 'Tel 12.12.2012', output: 'Tel 12…12', why: 'eight digits grouped exactly as a dotted date' },
  { input: 'Tel 12.12-12.12', output: 'Tel 12…12', why: 'eight digits grouped exactly as a dotted time range' },
  { input: 'Tel 9.12-12.12', output: 'Tel 91…12', why: 'seven digits grouped as a one-digit-hour range' },
  { input: 'Tel 2012-12-12 12.12', output: 'Tel 20…12', why: 'twelve digits grouped as a date and a time' },
  { input: 'Tel +2012-12-12', output: 'Tel +20…12', why: 'a leading + — v3 stripped it before the exemption test' },
];

/** Each must come out exactly as written in `output` — readable, its digits all there. */
export const UNMASKED: GoldenRow[] = [
  { input: 'code 123 456', output: 'code 123 456', why: 'BOUND: six digits are not masked' },
  { input: 'room 0660 and 123 45', output: 'room 0660 and 123 45', why: 'a letter ends a run' },
  { input: '06\n123\n45', output: '06\n123\n45', why: 'BOUND: each adjacent pair holds five digits, and digits are never summed over three lines' },
  { input: 'call 0660 at\n1234 please', output: 'call 0660 at\n1234 please', why: 'a letter after the digits on the upper line: not paired, eight digits stay' },
  { input: 'can I come at 10:30 on the 5th, is it 25 euro?', output: 'can I come at 10:30 on the 5th, is it 25 euro?', why: 'ordinary small numbers' },
  { input: 'see you at 14:30', output: 'see you at 14:30', why: 'a time alone has four digits' },
  { input: 'um 9.30 bitte', output: 'um 9.30 bitte', why: 'a one-digit-hour time' },
  { input: 'am 26.10. passt', output: 'am 26.10. passt', why: 'a day and month without a year' },
  { input: 'zip 1010 Wien', output: 'zip 1010 Wien', why: 'a postcode' },
];
