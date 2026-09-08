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
  ['agree — code and LLM both say Friday', 'friday at 11', {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['MISMATCH — LLM returns a Saturday for "friday"', 'friday at 11', {dateExpr:'friday',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:'date_mismatch',outcome:'mismatch'}],
  ['MISMATCH — code wins on "tomorrow" too', 'tomorrow', {dateExpr:'tomorrow',date:'2026-09-16',time:null},
    {date:'2026-09-08',dropped:false,cls:'date_mismatch',outcome:'mismatch'}],
  // Consequence of the generic weekday rule, pinned deliberately: even for "tomorrow", a disagreement that
  // is an exact multiple of 7 days reads as the clipping signature and abstains. A false abstain here costs
  // one re-ask; guessing costs an irreversible wrong booking. Rare in practice — a model's date error slips
  // by ONE day far more often than by exactly seven (measured: the only live mismatch was Wed -> Thu).
  ['exact +7 disagreement abstains even for "tomorrow"', 'tomorrow', {dateExpr:'tomorrow',date:'2026-09-15',time:null},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['"next <weekday>" is REFUSED, not guessed', 'next tuesday', {dateExpr:'next tuesday',date:'2026-09-15',time:null},
    {date:null,dropped:true,cls:'date_ambiguous',outcome:'ambiguous_next'}],
  ['backstop — dateExpr missing while a day is named', 'see you friday', {dateExpr:null,date:'2026-09-12',time:null},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'expr_missing_but_day_named'}],
  ['backstop — full word "saturday"', 'see you saturday', {dateExpr:null,date:'2026-09-13',time:null},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'expr_missing_but_day_named'}],
  ['backstop — "weds", which the node\'s own DAYS map accepts', 'weds please', {dateExpr:null,date:'2026-09-16',time:null},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'expr_missing_but_day_named'}],
  ['backstop must NOT trip on "wedding"', "haircut on 2026-10-03 at 14:00, it's for a wedding", {dateExpr:null,date:'2026-10-03',time:'14:00'},
    {date:'2026-10-03',dropped:false,cls:null,outcome:'unresolved_llm_date_kept'}],
  ['backstop must NOT trip on "friend"', 'my friend sent me, book 2026-10-03 14:00', {dateExpr:null,date:'2026-10-03',time:'14:00'},
    {date:'2026-10-03',dropped:false,cls:null,outcome:'unresolved_llm_date_kept'}],
  ['backstop must NOT trip on "monthly"', 'monthly package on 2026-10-03', {dateExpr:null,date:'2026-10-03',time:null},
    {date:'2026-10-03',dropped:false,cls:null,outcome:'unresolved_llm_date_kept'}],
  // CLIPPING — the one way this design can produce a wrong booking. A multi-word expression must stay
  // unparsed so the LLM's date survives; if the model ever CLIPS it to "friday", the code would win with
  // a date a week early. See ARCH-DEC 2026-09-08 and drills E16a/b.
  ['clipping guard — "friday next week" stays unparsed', 'friday next week', {dateExpr:'friday next week',date:'2026-09-18',time:'11:00'},
    {date:'2026-09-18',dropped:false,cls:null,outcome:'date_unverified'}],
  ['clipping guard — "the friday after next" stays unparsed', 'the friday after next', {dateExpr:'the friday after next',date:'2026-09-25',time:null},
    {date:'2026-09-25',dropped:false,cls:null,outcome:'date_unverified'}],
  ['documented gap — "in two weeks" keeps the LLM date', 'in two weeks', {dateExpr:'in two weeks',date:'2026-09-21',time:null},
    {date:'2026-09-21',dropped:false,cls:null,outcome:'date_unverified'}],
  ['ISO passthrough', 'on 2026-09-11', {dateExpr:'2026-09-11',date:'2026-09-11',time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // Monday-today vs Monday-next-week are the same weekday, so this now ABSTAINS rather than overriding —
  // and that is the better answer: "monday at 08:00" on a Monday at 09:00 is genuinely ambiguous.
  ['weekday IS today, asked time passed -> abstain (same weekday)', 'monday 08:00', {dateExpr:'monday',date:'2026-09-07',time:'08:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['weekday IS today, asked time still ahead -> today', 'monday 11:00', {dateExpr:'monday',date:'2026-09-07',time:'11:00'},
    {date:'2026-09-07',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['weekday was YESTERDAY -> next week', 'sunday 11:00', {dateExpr:'sunday',date:'2026-09-13',time:'11:00'},
    {date:'2026-09-13',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // A customer-supplied string must never reach Object.prototype: DAYS['constructor'] passes a truthy
  // check and then crashes now.set({weekday: Object}). Own-property lookup only.
  ['prototype key "constructor" is not a weekday', 'constructor', {dateExpr:'constructor',date:'2026-09-11',time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'date_unverified'}],
  // ---- CLIPPING GUARD (ruling 2026-09-08b). Same weekday a different week = the clipping signature:
  // the code must ABSTAIN, because it cannot know whether the wording carried a week offset dateExpr lost.
  ['clipping signature — same weekday, +1 week -> ABSTAIN', 'friday in two weeks at 11',
    {dateExpr:'friday',date:'2026-09-18',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['clipping signature — same weekday, +2 weeks -> ABSTAIN', 'friday after next at 11',
    {dateExpr:'friday',date:'2026-09-25',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  // ---- and the guard must NOT swallow a plain arithmetic error: a DIFFERENT weekday still lets code win.
  ['arithmetic error — different weekday -> CODE STILL WINS', 'friday at 11',
    {dateExpr:'friday',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:'date_mismatch',outcome:'mismatch'}],
  ['arithmetic error — off by one the other way -> CODE STILL WINS', 'friday at 11',
    {dateExpr:'friday',date:'2026-09-10',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:'date_mismatch',outcome:'mismatch'}],
  ['unusable LLM date is not a clipping signal', 'friday at 11',
    {dateExpr:'friday',date:'not-a-date',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:'date_mismatch',outcome:'mismatch'}],
  // ---- MEASUREMENT ONLY: dateExpr present but unparseable. Behaviour unchanged (LLM date kept, no drop,
  // no alert) — the label exists so the size of this hole can be counted from executions.
  ['date_unverified — "fri morning"', 'fri morning at 11',
    {dateExpr:'fri morning',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'date_unverified'}],
  ['date_unverified — "friday next week" (kept, NOT dropped)', 'friday next week at 11',
    {dateExpr:'friday next week',date:'2026-09-18',time:'11:00'},
    {date:'2026-09-18',dropped:false,cls:null,outcome:'date_unverified'}],
  ['no dateExpr at all stays unresolved_llm_date_kept', 'book 2026-09-11 at 11',
    {dateExpr:null,date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'unresolved_llm_date_kept'}],

  ['no date given at all', 'a haircut', {dateExpr:null,date:null,time:null},
    {date:null,dropped:false,cls:null,outcome:'unresolved_llm_date_kept'}],

  // ---- ABBREVIATIONS. The prompt tells the model to copy the customer's OWN wording verbatim, so
  // dateExpr:"fri" is a real input. Deleting every abbreviation from the node's DAYS map used to leave this
  // suite 20/20 green while an unchecked LLM date sailed through — i.e. CRT #12 itself, undetected.
  ['abbrev "fri"',   'fri at 11',   {dateExpr:'fri',  date:'2026-09-11',time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['abbrev "tues"',  'tues at 11',  {dateExpr:'tues', date:'2026-09-08',time:'11:00'}, {date:'2026-09-08',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['abbrev "weds"',  'weds at 11',  {dateExpr:'weds', date:'2026-09-09',time:'11:00'}, {date:'2026-09-09',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['abbrev "thurs"', 'thurs at 11', {dateExpr:'thurs',date:'2026-09-10',time:'11:00'}, {date:'2026-09-10',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['abbrev "sat"',   'sat at 11',   {dateExpr:'sat',  date:'2026-09-12',time:'11:00'}, {date:'2026-09-12',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['abbrev "sun"',   'sun at 11',   {dateExpr:'sun',  date:'2026-09-13',time:'11:00'}, {date:'2026-09-13',dropped:false,cls:null,outcome:'resolved_by_code'}],

  // ---- prefix + punctuation forms named in the rule table but never asserted
  ['"this friday" prefix', 'this friday at 11', {dateExpr:'this friday',date:'2026-09-11',time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['"on friday" prefix',   'on friday at 11',   {dateExpr:'on friday',  date:'2026-09-11',time:'11:00'}, {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['trailing punctuation', 'friday.',           {dateExpr:'friday.',    date:'2026-09-11',time:null},    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['"today"',              'today at 17:00',    {dateExpr:'today',      date:'2026-09-07',time:'17:00'}, {date:'2026-09-07',dropped:false,cls:null,outcome:'resolved_by_code'}],
];

let pass = 0, fail = 0;
for (const [label, text, slots, exp] of CASES) {
  let out;
  try { out = run({ text, slots }); }
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
          && out.date_resolution.outcome === 'mismatch';   // the code overrode a wrong LLM date
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
    && dr.reason === 'next_occurrence' && dr.outcome === 'mismatch') {
  pass++; console.log('  ok     date_resolution carries expr/llm/code/reason, not just the outcome');
} else { fail++; console.log('  FAIL   date_resolution incomplete: ' + JSON.stringify(dr)); }

// the no-slots path must still define the flags every downstream node reads
const bare = run({ text: 'hi', slots: null });
if (bare.date_dropped === false && bare.date_alert === false && bare.date_resolution === undefined) {
  pass++; console.log('  ok     no slots this turn -> flags defined, nothing resolved');
} else { fail++; console.log('  FAIL   no-slots path: ' + JSON.stringify(bare)); }

console.log(`\nresolve-date: ${pass}/${pass + fail} pass (node code read from n8n/workflow.sanitized.json, now=${NOW} ${TZ})`);
process.exit(fail ? 1 : 0);
