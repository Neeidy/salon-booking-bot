#!/usr/bin/env node
/**
 * Unit test for the `Resolve Date` n8n node — the calendar-arithmetic guard (CRT #12).
 *
 * WHY IT EXECUTES THE COMMITTED NODE INSTEAD OF A COPY: `.claude/rules/contract-integrity.md` — a
 * hand-mirrored copy of the logic would be a second truth that drifts silently. This file extracts the
 * `jsCode` of `Resolve Date` from `n8n/workflow.sanitized.json` (which `scripts/check-live-parity.py` +
 * `check-content-parity.py` prove is byte-identical to live) and runs it with the same globals n8n gives
 * a Code node: `$json`, `$('<node>')` and `DateTime`. So a green run here is a statement about the node
 * that is actually deployed, not about a snippet someone pasted into a test.
 *
 * WHY `now` IS FIXED: a date test that uses the real clock passes or fails depending on the day it is run.
 * With `now` pinned to Monday 2026-09-07 09:00 Europe/Vienna the rule table is asserted, not the calendar.
 *
 * ⚠ SECURITY NOTE (security-auditor, 2026-09-08): this file EXECUTES `jsCode` taken from the committed
 * export via `new Function`, with full Node privileges (`process.env`, `require` via `process.mainModule`
 * are reachable inside that body). On a PUBLIC repo that makes n8n/workflow.sanitized.json — a file reviewers
 * read as DATA — an executable surface for anyone who can open a PR, triggered by running the tests. The
 * alternative (hand-copying the node body) is worse: it is the second source of truth contract-integrity.md
 * forbids. So the risk is accepted here and moved to the REVIEW model: a PR touching the workflow JSON is a
 * code change, not a data change, and must be read as one. Sandboxing this run is open in ROADMAP.
 *
 * Run:  node tests/unit/resolve-date.test.cjs      (exit 0 = all pass)
 */
const fs = require('fs');
const path = require('path');
const { DateTime } = require(path.join(__dirname, '../../scripts/node_modules/luxon'));

const WF = path.join(__dirname, '../../n8n/workflow.sanitized.json');
const src = JSON.parse(fs.readFileSync(WF, 'utf8')).nodes.find(n => n.name === 'Resolve Date').parameters.jsCode;

const TZ = 'Europe/Vienna';
// `now` is handed over in UTC, never pre-zoned. The node does `DateTime.now().setZone(tz)`, and a harness that
// passes an already-Vienna clock cannot tell whether that setZone is there — mutation-tested: deleting it left
// the whole suite green. 07:00Z == 09:00 Vienna, so the shop-clock expectations below read naturally.
const NOW = '2026-09-07T07:00:00Z';                      // Monday, 09:00 shop time
const CFG = { config: { business: { timezone: TZ } } };
const node = new Function('$json', '$', 'DateTime', src);
// The injected DateTime must be the REAL Luxon with ONLY the clock overridden. An earlier version handed
// over `{ now }` alone; the node then gained a `DateTime.fromISO` call and the suite died with
// "fromISO is not a function" — a harness that fakes more than it needs can fail on correct code, or worse,
// pass on broken code because the missing surface was never exercised.
const clock = (nowISO) => new Proxy(DateTime, {
  get: (target, prop) => prop === 'now'
    ? () => DateTime.fromISO(nowISO || NOW, { zone: 'utc' })
    : Reflect.get(target, prop),
});
const run = (json, nowISO, tz) => node(json,
  () => ({ first: () => ({ json: tz ? { config: { business: { timezone: tz } } } : CFG }) }),
  clock(nowISO))[0].json;

// [label, customer text, LLM slots, expected {date, dropped, cls, outcome}]
const CASES = [
  // ============ CODEX COUNTEREXAMPLES (CRT #12 round 1) — permanent cases, per Yigitcan's acceptance
  // criterion: "the auditor's counterexamples become the regression suite itself".
  ['CODEX-1a "friday morning" resolves to the RIGHT Friday, never the Saturday the model returned',
    'haircut friday morning at 11', {dateExpr:'friday morning',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  ['CODEX-1b dateExpr of a single space -> abstain, never the LLM date',
    'haircut at 11', {dateExpr:' ',date:'2026-09-12',time:'11:00'},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],
  ['CODEX-1c dateExpr MISSING + "in two weeks" -> abstain',
    'haircut in two weeks at 11', {date:'2026-09-21',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'}],
  ['CODEX-3 a COMPUTED iso in dateExpr is refused (not in the customer text)',
    'can I come friday at 11', {dateExpr:'2026-09-12',date:'2026-09-12',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  // ============ RESIDUAL RISK — RECORDED, NOT CLOSED (2026-09-09d).
  // The week-context rule was REMOVED on Yigitcan's threshold ("a fourth adjustment removes the rule").
  // These inputs therefore now PROPOSE this week's Friday even though the sentence shifts the week. The
  // ONLY thing that catches it is the confirmation step, which shows the customer the full weekday + date.
  // They are kept as cases — asserting the accepted behaviour — so the gap stays visible and cannot be
  // reintroduced or "fixed" silently by someone who does not know it was a deliberate decision.
  ['RESIDUAL CODEX-4a "on friday" is bare after stripping -> BOOKS (accepted gap)',
    'I am away all this week, haircut on friday at 11', {dateExpr:'on friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['STILL CAUGHT CODEX-4b "in five weeks" — by the weekday-signature check, not raw text',
    'in five weeks, haircut friday at 11', {dateExpr:'friday',date:'2026-10-16',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['CODEX-6a "sun-kissed" + a date the customer typed -> KEPT, no alarm',
    'sun-kissed balayage on 2026-09-11 at 11', {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['CODEX-6b "my sister weds soon" + a typed date -> KEPT, no alarm',
    'my sister weds soon, haircut on 2026-09-11 at 11', {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],

  // ============ THE ARCHITECTURE: the LLM's date is a signal, never a value
  ['LLM date on a different weekday is IGNORED, not obeyed', 'haircut friday at 11',
    {dateExpr:'friday',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  ['agreement resolves normally', 'haircut friday at 11',
    {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['same weekday a different week -> abstain (clipping signature)', 'haircut friday at 11',
    {dateExpr:'friday',date:'2026-09-18',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['an unusable LLM date is not a signal', 'haircut friday at 11',
    {dateExpr:'friday',date:'not-a-date',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  ['"next <weekday>" is refused, never guessed', 'next tuesday',
    {dateExpr:'next tuesday',date:'2026-09-15',time:null},
    {date:null,dropped:true,cls:'date_ambiguous',outcome:'ambiguous_next'}],

  // ============ AMENDMENT 2026-09-09b — the echo vs a genuinely new date
  ['confirm echo of the validated slot is NOT a new claim', 'yes',
    {dateExpr:null,date:'2026-09-11',time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'echo_of_validated_slot'},
    {slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'confirming'}],
  ['a DIFFERENT date with no expression is STILL refused', 'yes',
    {dateExpr:null,date:'2026-09-18',time:'11:00'}, {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'},
    {slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'confirming'}],
  ['no stored slot at all -> a bare date is still refused', 'book me',
    {dateExpr:null,date:'2026-09-11',time:'11:00'}, {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'}],

  // ============ FAIL-CLOSED: an unresolvable expression ASKS, it does not fall back to the model
  ['unresolvable wording asks', 'haircut in two weeks at 11',
    {dateExpr:'in two weeks',date:'2026-09-21',time:'11:00'},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],
  ['"11 september" asks (date PARSING is still out of scope)', 'haircut 11 september at 11',
    {dateExpr:'11 september',date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],
  ['a prototype key is not a weekday', 'constructor',
    {dateExpr:'constructor',date:'2026-09-11',time:null},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],
  ['no day named at all -> nothing to resolve, nothing dropped', 'a haircut please',
    {dateExpr:null,date:null,time:null},
    {date:null,dropped:false,cls:null,outcome:'no_date'}],

  // ============ GRAMMAR EXPANSION (scope item 2) — qualifiers that cannot move the day are stripped,
  // so ordinary wording resolves instead of re-asking. Anything that CAN move the day is not stripped.
  ['strip: "friday afternoon"', 'x', {dateExpr:'friday afternoon',date:'2026-09-11',time:'15:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "fri morning"', 'x', {dateExpr:'fri morning',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "friday evening"', 'x', {dateExpr:'friday evening',date:'2026-09-11',time:'18:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "on friday"', 'x', {dateExpr:'on friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "this friday"', 'x', {dateExpr:'this friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "friday this week"', 'x', {dateExpr:'friday this week',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "friday please"', 'x', {dateExpr:'friday please',date:'2026-09-11',time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: punctuation', 'x', {dateExpr:'friday.',date:'2026-09-11',time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['NOT stripped: "next friday" still refused', 'x', {dateExpr:'next friday',date:'2026-09-18',time:null},
    {date:null,dropped:true,cls:'date_ambiguous',outcome:'ambiguous_next'}],
  ['NOT stripped: "friday next week" still asks', 'x', {dateExpr:'friday next week',date:'2026-09-18',time:null},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],

  // ============ ISO PROVENANCE — the customer typed it, or it does not count
  ['iso the customer typed is accepted', 'book me 2026-09-11 at 11',
    {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['iso NOT in the text is refused even if it matches the LLM date', 'book me on friday at 11',
    {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],

  // ============ WEEK-CONTEXT: fires on a bare weekday, silent on ordinary bookings
  ['RESIDUAL: "away all this week" -> BOOKS this week (accepted gap, ARCH-DEC 2026-09-09d)', "I'm away all this week, so haircut friday at 11:00",
    {dateExpr:'friday',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  ['RESIDUAL: "busy until next week" -> BOOKS this week (accepted gap)', "I'm busy until next week - haircut friday at 11:00",
    {dateExpr:'friday',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  ['STILL CAUGHT: a month offset — the LLM date lands a whole week out, same weekday', 'haircut friday, in a month',
    {dateExpr:'friday',date:'2026-10-09',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['NO week context: ordinary booking', 'haircut friday at 11:00',
    {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['NO week context: "weekly"', 'weekly trim, haircut friday at 11:00',
    {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['NO week context: unqualified "weekend"', 'do you have weekend hours? haircut friday at 11:00',
    {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['NO week context: "midweek"/"biweekly"/"weeknights"', 'biweekly midweek weeknights, haircut friday at 11:00',
    {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['NO week context: unnegated "this week"', 'haircut friday this week at 11:00',
    {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['week context does NOT fire when the expression is not bare', 'in two weeks, haircut friday next week',
    {dateExpr:'friday next week',date:'2026-09-25',time:null},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],

  // ============ FLOW-REVIEWER COUNTEREXAMPLES (round-2 review) — permanent cases. Generalising the week
  // rule by REPLACING the enumerated phrases regressed both directions; these lock both.
  ['RESIDUAL FR-1a "the friday after next" -> BOOKS (accepted gap)', 'the friday after next at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL FR-1b "the one after next" -> BOOKS (accepted gap)', 'not this friday, the one after next, 11am',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['FR-1c a PAST reference must NOT abstain', 'I had a cut a few weeks ago - friday at 11?',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['FR-1d "3 months since my last cut" must NOT abstain', '3 months since my last cut, friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['FR-1e conversational "how is your week going" must NOT abstain', 'how is your week going? friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // KNOWINGLY GIVEN UP 2026-09-09c: 'in' is direction-blind ("I last came in june" is past), so month
  // references only count behind a forward preposition. Losing "in october" is accepted BECAUSE a veto now
  // asks instead of locking — the rule need not be perfect, the mistake needs to be cheap.
  ['GIVEN UP: "in october" no longer abstains', 'friday at 11 in october',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL forward month DOES abstain: "starting october" -> BOOKS (accepted gap)', 'starting october, friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL forward month DOES abstain: "from june onwards" -> BOOKS (accepted gap)', 'from june onwards, friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL FR-2b a day offset -> BOOKS (accepted gap)', 'back in 10 days - friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL FR-2c an ordinal anchor -> BOOKS (accepted gap)', 'after the 20th, friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL FR-2d an abbreviated offset -> BOOKS (accepted gap)', 'friday at 11 in 2 wks',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL FR-2e "till the 20th" -> BOOKS (accepted gap)', 'I am on holiday till the 20th, friday at 11 works',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['FR-2f "may I book" must NOT trip the month list', 'may I book friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // FR-4: shape-valid but non-existent. On the reschedule path this became a GCal 400 surfaced to the owner
  // as `calendar_unavailable` — a customer typo dressed as an infra outage.
  ['GIVEN UP: a BARE ordinal no longer abstains', 'the friday of the 21st at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['RESIDUAL an ordinal behind a forward preposition still abstains -> BOOKS (accepted gap)', 'from the 21st, friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['GIVEN UP: "in may" no longer abstains', 'friday at 11 in may',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['FR-2i "may I book" is not — the preposition is what makes it a month', 'may I book friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['FR-2j "march me in" is not a month either', 'march me in on friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // ============ N1 (flow-reviewer, round-2 verification) — direction-blind markers fired on ordinary
  // salon sentences, and on a CONFIRM turn that became a PERMANENT LOCK. All seven must stay silent.
  ['N1-a "I last came in june"', 'I last came in june, can I book friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['N1-b "you coloured it in march"', 'you coloured it in march, can I come friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['N1-c "the 1st time I came"', 'the 1st time I came you did a great job, friday at 11 please',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['N1-d "may 2 of us come"', 'may 2 of us come friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['N1-e "from the 2 options"', 'from the 2 options I want the balayage friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['N1-f "by the 3 of us"', 'by the 3 of us we need friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['N1-g the confirm sentence that used to LOCK', 'yes, friday at 11 - the 1st time was great',
    {dateExpr:'friday',date:null,time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],

  ['FR-4 a non-existent date is refused, not resolved', 'book 2026-02-30 at 11',
    {dateExpr:'2026-02-30',date:'2026-02-30',time:'11:00'},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],
  ['FR-9 "friday, please" resolves (trailing comma stripped)', 'haircut friday, please',
    {dateExpr:'friday, please',date:null,time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],

  // ============ weekday-is-today boundary
  ['weekday IS today, time already passed -> abstain (same weekday)', 'monday 08:00',
    {dateExpr:'monday',date:'2026-09-07',time:'08:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['weekday IS today, time still ahead -> today', 'monday 11:00',
    {dateExpr:'monday',date:'2026-09-07',time:'11:00'},
    {date:'2026-09-07',dropped:false,cls:null,outcome:'resolved_by_code'}],

];

let pass = 0, fail = 0;
for (const [label, text, slots, exp, state] of CASES) {
  let out;
  try { out = run(state ? { text, slots, state } : { text, slots }); }
  catch (e) { console.log('  CRASH  ' + label + ' -> ' + e.message); fail++; continue; }
  const got = { date: out.slots.date, dropped: out.date_dropped,
                cls: out.date_alert_class, outcome: out.date_resolution.outcome };
  const ok = got.date === exp.date && got.dropped === exp.dropped && got.cls === exp.cls
          && got.outcome === exp.outcome && out.date_alert === (exp.cls !== null);
  if (ok) { pass++; console.log('  ok     ' + label); }
  else { fail++; console.log('  FAIL   ' + label + '\n         got  ' + JSON.stringify(got)
                             + '\n         want ' + JSON.stringify(exp)); }
}
// ---- DST + month-end, each with its own pinned clock. A single fixed `now` cannot reach them: from
// 2026-09-07 every weekday resolves inside 09-07..09-13, so claiming DST/month-end coverage off that clock
// would be a claim the suite structurally cannot make.
// Each fixture hands the LLM a DELIBERATELY WRONG date, so the expected value can ONLY come from the
// resolver: with matching dates these cases stayed green even when resolveDate was stubbed to return null.
// The DST clock sits just past midnight Vienna, where `plus({days:1})` and `plus({hours:24})` diverge —
// the classic DST bug is invisible at 08:00.
const off1 = (iso) => DateTime.fromISO(iso).plus({ days: 1 }).toISODate();   // wrong, and a DIFFERENT weekday
const DATED = [
  ['DST — "tomorrow" across the 2026-10-25 changeover', '2026-10-24T22:30:00Z', 'tomorrow', 'tomorrow', '2026-10-26'],
  ['DST — weekday landing ON the switch day',           '2026-10-20T07:00:00Z', 'sunday',   'sunday',   '2026-10-25'],
  ['month-end — Tue 29 Sep -> Thu 1 Oct',               '2026-09-29T07:00:00Z', 'thursday', 'thursday', '2026-10-01'],
  ['month-end — "tomorrow" across 30 Sep',              '2026-09-30T07:00:00Z', 'tomorrow', 'tomorrow', '2026-10-01'],
  // BACK-FILL branch: `if (d < now.startOf('day')) d = d.plus({weeks:1})`. From a Monday every weekday is
  // already ahead, so this line was never entered — deleting it, or flipping it to .minus(), left the suite
  // green while the second form books into the PAST. Needs a clock late in the week.
  ['back-fill — Monday asked on a Friday goes to NEXT week',  '2026-09-11T07:00:00Z', 'monday',  'monday',  '2026-09-14'],
  ['back-fill — Tuesday asked on a Friday goes to NEXT week', '2026-09-11T07:00:00Z', 'tuesday', 'tuesday', '2026-09-15'],
];
for (const [label, nowISO, text, expr, wantDate] of DATED) {
  const slots = { dateExpr: expr, date: off1(wantDate), time: '11:00' };
  const out = run({ text, slots }, nowISO);
  const ok = out.slots.date === wantDate && out.date_resolution.code === wantDate
          && out.date_resolution.outcome === 'llm_date_ignored';   // the code produced it; the LLM's answer was ignored
  if (ok) { pass++; console.log('  ok     ' + label); }
  else { fail++; console.log('  FAIL   ' + label + ' -> got ' + out.slots.date
                             + ' (' + out.date_resolution.outcome + '), want ' + wantDate); }
}

// FAIL-1 from the 4th review: the node comment claims this suite "asserts every DAYS key resolves".
// Eight keys had no case at all (mon, tue, wednesday, wed, thursday, thu, thur, saturday), so the claim
// was false in the committed AND deployed comment. Every key is asserted here now.
const DAY_KEYS = [['monday','2026-09-14'],['mon','2026-09-14'],['tuesday','2026-09-08'],['tue','2026-09-08'],
  ['tues','2026-09-08'],['wednesday','2026-09-09'],['wed','2026-09-09'],['weds','2026-09-09'],
  ['thursday','2026-09-10'],['thu','2026-09-10'],['thur','2026-09-10'],['thurs','2026-09-10'],
  ['friday','2026-09-11'],['fri','2026-09-11'],['saturday','2026-09-12'],['sat','2026-09-12'],
  ['sunday','2026-09-13'],['sun','2026-09-13']];
let keyFails = 0;
for (const [key, want] of DAY_KEYS) {
  // 08:00 already passed at the 09:00 shop clock, so 'monday'/'mon' must roll a week forward, not sit on today
  const out = run({ text: key + ' at 08:00', slots: { dateExpr: key, date: off1(want), time: '08:00' } });
  if (!(out.slots.date === want && out.date_resolution.reason === 'next_occurrence')) {
    keyFails++; console.log('  FAIL   DAYS key ' + JSON.stringify(key) + ' -> ' + out.slots.date + ', want ' + want);
  }
}
if (keyFails) { fail++; } else { pass++; console.log('  ok     all ' + DAY_KEYS.length + ' DAYS keys resolve (every abbreviation and full name)'); }

// ---- CONFIG-DRIVEN TIMEZONE. This is a resold template: the shop timezone comes from
// `business.timezone`, and hardcoding 'Europe/Vienna' in the node must fail here. At 13:00Z it is still
// 7 Sep in Vienna but already 8 Sep in Auckland, so the same clock yields two different "today"s.
{
  // wrong dates one day off the truth in each zone, so neither reads as the clipping signature
  const vie = run({ text: 'today', slots: { dateExpr: 'today', date: '2026-09-08', time: null } },
                   '2026-09-07T13:00:00Z');
  const akl = run({ text: 'today', slots: { dateExpr: 'today', date: '2026-09-09', time: null } },
                   '2026-09-07T13:00:00Z', 'Pacific/Auckland');
  if (vie.slots.date === '2026-09-07' && akl.slots.date === '2026-09-08') {
    pass++; console.log('  ok     the shop timezone comes from config, not a hardcoded zone (Vienna vs Auckland)');
  } else {
    fail++; console.log('  FAIL   config timezone ignored: Vienna=' + vie.slots.date + ' Auckland=' + akl.slots.date);
  }
}

// ---- PROVENANCE STAMP: REMOVED 2026-09-09e with the veto it existed for (no gate read it, it could not be
// persisted). Asserted ABSENT so it cannot quietly return: a stamp nothing enforces is a guarantee the repo
// does not keep, and this project has already paid for one of those.
{
  const r1 = run({ text: 'haircut friday at 11', slots: { dateExpr: 'friday', date: '2026-09-11', time: '11:00' } });
  if (r1.slots.dateSrc === undefined && r1.slots.date === '2026-09-11') {
    pass++; console.log('  ok     no provenance stamp is emitted (removed with the veto)');
  } else {
    fail++; console.log('  FAIL   dateSrc reappeared: ' + JSON.stringify(r1.slots));
  }
}

// ---- STRUCTURAL: the node returns `slots: {...s, date}`. Narrowing that to `{date}` silently destroys
// serviceId/time and breaks booking, and a suite that only reads slots.date never notices.
const keep = run({ text: 'haircut friday at 11',
  slots: { serviceId: 'haircut', dateExpr: 'friday', date: '2026-09-11', time: '11:00', customerName: 'Alex' } });
if (keep.slots.serviceId === 'haircut' && keep.slots.time === '11:00'
    && keep.slots.customerName === 'Alex' && keep.slots.dateExpr === 'friday') {
  pass++; console.log('  ok     every other slot survives the rewrite (serviceId/time/customerName/dateExpr)');
} else { fail++; console.log('  FAIL   slots were narrowed: ' + JSON.stringify(keep.slots)); }

// ---- STRUCTURAL: date_resolution is the owner's whole view of what happened. Reducing it to {outcome}
// leaves the Telegram alert unable to say what the customer said vs what each side computed.
const dr = run({ text: 'friday at 11', slots: { dateExpr: 'friday', date: '2026-09-12', time: '11:00' } }).date_resolution;
if (dr.expr === 'friday' && dr.llm === '2026-09-12' && dr.code === '2026-09-11'
    && dr.reason === 'next_occurrence' && dr.outcome === 'llm_date_ignored') {
  pass++; console.log('  ok     date_resolution carries expr/llm/code/reason, not just the outcome');
} else { fail++; console.log('  FAIL   date_resolution incomplete: ' + JSON.stringify(dr)); }

// the no-slots path must still define the flags every downstream node reads
const bare = run({ text: 'hi', slots: null });
if (bare.date_dropped === false && bare.date_alert === false && bare.date_resolution === undefined) {
  pass++; console.log('  ok     no slots this turn -> flags defined, nothing resolved');
} else { fail++; console.log('  FAIL   no-slots path: ' + JSON.stringify(bare)); }

console.log(`\nresolve-date: ${pass}/${pass + fail} pass (node code read from n8n/workflow.sanitized.json, now=${NOW} ${TZ})`);
process.exit(fail ? 1 : 0);
