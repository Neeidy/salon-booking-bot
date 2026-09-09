#!/usr/bin/env node
/**
 * Unit test for the `Resolve Date` n8n node — the calendar-arithmetic guard (CRT #12).
 *
 * WHY IT EXECUTES THE COMMITTED NODE INSTEAD OF A COPY: `.claude/rules/contract-integrity.md` — a
 * hand-mirrored copy of the logic would be a second truth that drifts silently. This file extracts the
 * `jsCode` of `Resolve Date` from `n8n/workflow.sanitized.json` and runs it with the same globals n8n gives
 * a Code node: `$json`, `$('<node>')` and `DateTime`. So a green run here is a statement about the COMMITTED
 * node, not about a snippet someone pasted into a test.
 *
 * ⚠ CONDITIONAL, and the condition is not this file's to satisfy (corrected 2026-09-09g): "the node that is
 * actually deployed" holds only while `check-live-parity.py` + `check-content-parity.py` were run against
 * the live instance IN THE SAME STATE. Those guards need credentials this suite does not have, so a green
 * run here proves nothing about production on its own — and for most of this project's history they were
 * comparing the DRAFT, not the published graph, so even their green did not mean what the sentence said.
 * Read this file as: the committed artefact behaves like this.
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
  // ⚠ KNOWN-FAILING — RESTORED VERBATIM 2026-09-09f. The committed version of this row had Codex's model
  // date silently moved from 2026-09-11 to 2026-10-16 and was then labelled "STILL CAUGHT": the input was
  // edited until it passed. Codex's actual counterexample is below, unchanged, and it is NOT caught — with
  // the model agreeing on this week's Friday there is no disagreement for the clipping check to see. It is
  // recorded as a known failure (E20), not rewritten again. The row asserts the WRONG behaviour on purpose,
  // so that the day someone closes E20 this row goes red and has to be re-read.
  ['KNOWN-FAILING CODEX-4b "in five weeks" is NOT caught (E20) — the sentence shifts the week, dateExpr does not',
    'in five weeks, haircut friday at 11', {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
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
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'confirming'},intent:'confirm'}],
  ['a DIFFERENT date with no expression is STILL refused', 'yes',
    {dateExpr:null,date:'2026-09-18',time:'11:00'}, {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'confirming'},intent:'confirm'}],
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
  // ⚠ 2026-09-09f: every row in this block used to pass a placeholder customer text of 'x'. That was only
  // ever valid because the relative side had NO provenance check — the very asymmetry Codex HIGH-2a found.
  // With the check in place a placeholder text is not a weaker fixture, it is an INVALID one, so each row
  // now carries the sentence the expression was supposedly copied from. This is a fixture correction, not a
  // relaxation: the assertions (date / dropped / class / outcome) are unchanged.
  ['strip: "friday afternoon"', 'haircut friday afternoon', {dateExpr:'friday afternoon',date:'2026-09-11',time:'15:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "fri morning"', 'haircut fri morning', {dateExpr:'fri morning',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "friday evening"', 'haircut friday evening', {dateExpr:'friday evening',date:'2026-09-11',time:'18:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "on friday"', 'haircut on friday at 11', {dateExpr:'on friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "this friday"', 'haircut this friday at 11', {dateExpr:'this friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['ANCHOR: "friday this week" resolves when that day is still ahead', 'haircut friday this week at 11', {dateExpr:'friday this week',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: "friday please"', 'haircut friday please', {dateExpr:'friday please',date:'2026-09-11',time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['strip: punctuation', 'haircut friday.', {dateExpr:'friday.',date:'2026-09-11',time:null},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['NOT stripped: "next friday" still refused', 'haircut next friday', {dateExpr:'next friday',date:'2026-09-18',time:null},
    {date:null,dropped:true,cls:'date_ambiguous',outcome:'ambiguous_next'}],
  ['NOT stripped: "friday next week" still asks', 'haircut friday next week', {dateExpr:'friday next week',date:'2026-09-18',time:null},
    {date:null,dropped:true,cls:'date_unresolved',outcome:'unresolved_expr'}],

  // ============ ISO PROVENANCE — the customer typed it, or it does not count
  ['iso the customer typed is accepted', 'book me 2026-09-11 at 11',
    {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['iso NOT in the text is refused even if it matches the LLM date', 'book me on friday at 11',
    {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],

  // ============ WEEK CONTEXT CARRIED BY THE SENTENCE — CORRECTED HEADER 2026-09-09f (Codex HIGH-3).
  // This header used to read "fires on a bare weekday, silent on ordinary bookings", describing a rule that
  // had already been DELETED (2026-09-09d). Nothing below fires it. These rows assert the ACCEPTED GAP E20:
  // a week shift the sentence carries but `dateExpr` does not is NOT detected here; the confirmation step
  // (weekday + full date) is the only thing that catches it.
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
  ['the ANCHOR comes from dateExpr, never from the sentence: "this week" in the text alone changes nothing', 'haircut friday this week at 11:00',
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
  // ⚠ CORRECTED 2026-09-09f (Codex HIGH-3). This block used to justify itself with "a veto now asks instead
  // of locking". THERE IS NO VETO — it was removed in 2026-09-09e, in the same commit that shipped this
  // comment, so the sentence was false the moment it was written. The month/ordinal rules it describes were
  // removed too (2026-09-09d). What the rows below actually assert is the accepted gap: every one of these
  // sentences resolves to this week's Friday and books.
  ['GIVEN UP: "in october" no longer abstains', 'friday at 11 in october',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['ACCEPTED GAP "starting october" -> BOOKS this week\'s friday', 'starting october, friday at 11',
    {dateExpr:'friday',date:null,time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['ACCEPTED GAP "from june onwards" -> BOOKS this week\'s friday', 'from june onwards, friday at 11',
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
  ['ACCEPTED GAP "from the 21st" -> BOOKS this week\'s friday', 'from the 21st, friday at 11',
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

  // ============ CODEX ROUND-3 COUNTEREXAMPLES — verbatim, permanent. Same standing criterion as round 1:
  // the auditor's inputs become the regression suite. None of these were edited to make them pass.

  // --- HIGH-2a: PROVENANCE ASYMMETRY. The ISO side demanded the customer's own text; the relative side
  // demanded nothing, so the model could answer a DIFFERENT day than the one the customer named.
  ['CODEX-H2a customer said friday, dateExpr says saturday -> refused (relative provenance)',
    'can I come friday at 11', {dateExpr:'saturday',date:'2026-09-12',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['CODEX-H2a the same check is SILENT when the customer really typed that day',
    'can I come saturday at 11', {dateExpr:'saturday',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-12',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['CODEX-H2a a "tomorrow" the customer never typed is refused too',
    'can I come friday at 11', {dateExpr:'tomorrow',date:'2026-09-08',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  // The hole a PLAIN substring check would leave, closed by the word boundary. Found in self-review, not by
  // an auditor — recorded because "the auditor did not catch it" is not evidence that it was not there.
  ['boundary: "sat" hiding inside "satisfied" is NOT the customer typing Saturday',
    'I was satisfied last time, can I come friday at 11', {dateExpr:'sat',date:'2026-09-12',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['boundary: a standalone "sat" IS the customer typing it',
    'sat at 11 please', {dateExpr:'sat',date:'2026-09-12',time:'11:00'},
    {date:'2026-09-12',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['boundary: punctuation still counts as a boundary ("friday." / "friday,")',
    'haircut friday, at 11', {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // ⚠ REPLACED 2026-09-09f. The row here used to read `boundary: a hyphen counts too ("mon-fri")` with the
  // text 'are you open mon-fri? book me fri at 11' — which contains a STANDALONE `fri`, so it passed on that
  // word and said nothing about the hyphen. `code-reviewer` killed it with a mutant that flipped the boundary
  // class: the suite stayed 115/115. A row that cannot fail is not a row. These three DO fail without the fix,
  // and every one of them is a real accept measured on the previous version — the same Codex HIGH-2a shape
  // (the model naming a day the customer never chose), hiding inside ordinary salon vocabulary.
  ['boundary: "sun" inside "sun-kissed" is vocabulary, not a chosen Sunday',
    'sun-kissed balayage at 11', {dateExpr:'sun',date:'2026-09-13',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['boundary: "sat" inside "sat/sun opening hours" is a question, not a booking',
    'what are your sat/sun opening hours?', {dateExpr:'sat',date:'2026-09-12',time:null},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['boundary: "mon" inside "mon-fri" is an hours RANGE, not a chosen Monday',
    'are you open mon-fri?', {dateExpr:'mon',date:'2026-09-07',time:null},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['boundary: the same word standing alone in the same sentence IS the customer choosing it',
    'are you open mon-fri? book me on fri at 11', {dateExpr:'fri',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // The STATED COST of the boundary, asserted so it is a known behaviour and not a surprise: an abbreviation
  // the customer did not type is refused. dateExpr is VERBATIM by contract, and this fails cheaply (a re-ask).
  ['the leading "coming" strip is NOT redundant — it carries a model-added prefix through provenance',
    'can i come friday at 11', {dateExpr:'coming friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['boundary COST: the model abbreviates "friday" to "fri" -> refused, turn re-asks',
    'can I come friday at 11', {dateExpr:'fri',date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['boundary: an ISO date glued to a longer number is not the customer typing it',
    'my ref is 2026-09-110, book me', {dateExpr:'2026-09-11',date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],
  ['CODEX-H2a capitalisation is not forgery — the check is case-insensitive on both sides',
    'Can I come Friday at 11?', {dateExpr:'friday',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['CODEX-H2a the qualifier may be stripped and the DAY still has to be in the text',
    'haircut friday morning', {dateExpr:'saturday morning',date:'2026-09-12',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_forged',outcome:'expr_not_from_customer'}],

  // --- HIGH-2b: the echo exception looked at NEITHER intent NOR stage. Codex walked in through `collecting`.
  // Flipping the two fixtures above from 'confirming' to 'collecting' left the old suite at 82/82 — i.e. the
  // boundary was never tested at all. All four corners are pinned now.
  ['CODEX-H2b collecting + "in two weeks" + dateExpr:null + the stored date echoed back -> REFUSED',
    'in two weeks', {dateExpr:null,date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'collecting'},intent:'book'}],
  ['CODEX-H2b right stage, wrong intent -> REFUSED',
    'tomorrow please', {dateExpr:null,date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'confirming'},intent:'book'}],
  ['CODEX-H2b right intent, no confirmation pending -> REFUSED',
    'yes', {dateExpr:null,date:'2026-09-11',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'collecting'},intent:'confirm'}],
  ['CODEX-H2b cancel_confirming is a confirm lifecycle -> the echo is allowed',
    'yes', {dateExpr:null,date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'echo_of_validated_slot'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'cancel_confirming'},intent:'confirm'}],
  ['CODEX-H2b reschedule_confirming likewise',
    'yes', {dateExpr:null,date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'echo_of_validated_slot'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'reschedule_confirming'},intent:'confirm'}],
  // The OTHER side of the same boundary, and the reason the prompt changed in this round: a slot-filling turn
  // that names no day at all must NOT be refused — it must resolve to nothing, so `Merge Slots` carries the
  // already-validated stored date forward deterministically (`fresh.date ?? stored.date`). `no_date` sets
  // date_dropped=false, which is exactly what keeps that carry-forward alive. If this row ever flips to
  // `date_without_expr`, mid-booking customers are being asked for the day twice.
  ['collecting + a message with no day at all -> nothing to resolve, nothing dropped (stored date survives)',
    '11am please', {dateExpr:null,date:null,time:'11:00'},
    {date:null,dropped:false,cls:null,outcome:'no_date'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:null},stage:'collecting'},intent:'book'}],
  ['CODEX-H2b a confirm turn whose date is NOT the stored one is still refused',
    'yes', {dateExpr:null,date:'2026-09-18',time:'11:00'},
    {date:null,dropped:true,cls:'date_expr_missing',outcome:'date_without_expr'},
    {state:{slots:{serviceId:'haircut',date:'2026-09-11',time:'11:00'},stage:'confirming'},intent:'confirm'}],

  // --- MED-5: the clipping check fired where no clipping is possible. It now runs ONLY on a bare-weekday
  // resolution (`next_occurrence`) and compares NORMALISED dates.
  ['CODEX-M5a an ISO date the customer typed is not clipping-checked', 'book 2026-09-11 at 11',
    {dateExpr:'2026-09-11',date:'2026-09-18',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  ['CODEX-M5a "tomorrow" is not clipping-checked either (same weekday, a week out)', 'haircut tomorrow at 11',
    {dateExpr:'tomorrow',date:'2026-09-15',time:'11:00'},
    {date:'2026-09-08',dropped:false,cls:null,outcome:'llm_date_ignored'}],
  // ⚠ FLIPPED 2026-09-09f, and this row is OURS, not Codex's — Codex MED-5a's own input is the ISO row above
  // and it is untouched. This one was an extrapolation ("an anchor carries no qualifier to lose") and
  // `code-reviewer` refuted the reasoning: the anchor can be INVENTED by the model, and excluding it let one
  // token switch `week_ambiguous` off. Measured on Wed 2026-09-09, text "i am away, can i book friday the week
  // after" with model date 2026-09-18: `friday` REFUSED, `this friday` BOOKED 2026-09-11 with no alert. An
  // anchor narrows which week we may answer; it does not buy immunity from the disagreement signal.
  ['an anchor the customer DID type is clipping-checked like any other weekday resolution', 'haircut friday this week at 11',
    {dateExpr:'friday this week',date:'2026-09-18',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['...and the INVENTED anchor (no "this" anywhere in the text) cannot disable week_ambiguous either',
    'i am away, can i book friday the week after', {dateExpr:'this friday',date:'2026-09-18',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['...while an anchor the model did NOT contradict still resolves', 'haircut friday this week at 11',
    {dateExpr:'friday this week',date:'2026-09-11',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['CODEX-M5b the same calendar day in another format is AGREEMENT, not a week apart', 'haircut friday at 11',
    {dateExpr:'friday',date:'2026-09-11T00:00:00',time:'11:00'},
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['CODEX-M5b a real week-apart disagreement in that same format IS still caught', 'haircut friday at 11',
    {dateExpr:'friday',date:'2026-09-18T00:00:00',time:'11:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],

  // ============ weekday-is-today boundary
  ['weekday IS today, time already passed -> abstain (same weekday)', 'monday 08:00',
    {dateExpr:'monday',date:'2026-09-07',time:'08:00'},
    {date:null,dropped:true,cls:'date_week_ambiguous',outcome:'week_ambiguous'}],
  ['weekday IS today, time still ahead -> today', 'monday 11:00',
    {dateExpr:'monday',date:'2026-09-07',time:'11:00'},
    {date:'2026-09-07',dropped:false,cls:null,outcome:'resolved_by_code'}],

];

let pass = 0, fail = 0;
for (const [label, text, slots, exp, extra] of CASES) {
  let out;
  // `extra` is merged into the item verbatim: since 2026-09-09f the echo exception reads BOTH `intent` and
  // `state.stage`, so a fixture that only carried `state` could not express "the stage is right, the intent
  // is not" — and that pair is exactly the boundary Codex HIGH-2b walked through.
  try { out = run(extra ? { text, slots, ...extra } : { text, slots }); }
  catch (e) { console.log('  CRASH  ' + label + ' -> ' + e.message); fail++; continue; }
  const got = { date: out.slots.date, dropped: out.date_dropped,
                cls: out.date_alert_class, outcome: out.date_resolution.outcome };
  const ok = got.date === exp.date && got.dropped === exp.dropped && got.cls === exp.cls
          && got.outcome === exp.outcome && out.date_alert === (exp.cls !== null);
  if (ok) { pass++; console.log('  ok     ' + label); }
  else { fail++; console.log('  FAIL   ' + label + '\n         got  ' + JSON.stringify(got)
                             + '\n         want ' + JSON.stringify(exp)); }
}
// ---- "THIS WEEK" IS AN ANCHOR (Codex HIGH-1 — our own regression, measured by Codex on a Saturday clock).
// Each row carries its OWN clock: a single Monday `now` structurally cannot express "the anchored day is
// already behind us", so claiming this coverage off the shared clock would be a claim the suite cannot make.
// The LLM date is null in every row, exactly as Codex reported it, so the expected value can come from
// nothing but the resolver.
const ANCHORED = [
  ['ANCHOR CODEX-H1 Saturday clock — "friday this week" must NOT roll to next Friday',
    '2026-09-12T07:00:00Z', 'haircut friday this week at 11', 'friday this week', '11:00',
    {date:null,dropped:true,cls:'date_anchor_past',outcome:'anchor_past'}],
  ['ANCHOR CODEX-H1 same day, asked time already gone -> refuse (never roll a week)',
    '2026-09-11T07:00:00Z', 'haircut friday this week at 08:00', 'friday this week', '08:00',
    {date:null,dropped:true,cls:'date_anchor_past',outcome:'anchor_past'}],
  ['ANCHOR CODEX-H1 same day, asked time still ahead -> today resolves',
    '2026-09-11T07:00:00Z', 'haircut friday this week at 11', 'friday this week', '11:00',
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['ANCHOR the UNanchored twin still rolls forward — the anchor is what changes the answer',
    '2026-09-12T07:00:00Z', 'haircut friday at 11', 'friday', '11:00',
    {date:'2026-09-18',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['ANCHOR a mid-week clock with the day still ahead resolves inside THIS week',
    '2026-09-09T07:00:00Z', 'haircut friday this week at 11', 'friday this week', '11:00',
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // ⚠ code-reviewer, 2026-09-09f: `friday this week` anchored but `this friday` did not — `stripQualifiers`
  // deleted the leading `this` before `splitAnchor` ever saw it, so on a Saturday the commoner phrasing still
  // answered 2026-09-18 in silence. The Monday-clock row in CASES could not see it (both readings give the
  // same date there). These two rows are the same sentence in two word orders and must agree.
  ['ANCHOR both word orders agree: "this friday" on a Saturday refuses, exactly like "friday this week"',
    '2026-09-12T07:00:00Z', 'haircut this friday at 11', 'this friday', '11:00',
    {date:null,dropped:true,cls:'date_anchor_past',outcome:'anchor_past'}],
  ['ANCHOR "this friday" mid-week still resolves inside THIS week',
    '2026-09-09T07:00:00Z', 'haircut this friday at 11', 'this friday', '11:00',
    {date:'2026-09-11',dropped:false,cls:null,outcome:'resolved_by_code'}],
  // Mutation note, recorded because a survivor was explained rather than waved away: adding `coming` to
  // splitAnchor's prefix regex SURVIVES, because `stripQualifiers` removes a leading `coming` before
  // `splitAnchor` ever sees it — equivalent by ORDERING, not by behaviour. The combined mutant (drop `coming`
  // from the strip list AND anchor it) DOES kill this row, so the row is not vacuous.
  // ⚠ RETRACTED CLAIM, 2026-09-09f. This block briefly said mutant M33 (dropping `coming` from
  // `stripQualifiers`) was "proven EQUIVALENT by a 32928-input differential sweep with ZERO behavioural
  // differences". THE SWEEP WAS RIGGED THE SAME WAY THE ANCHOR SWEEP WAS: it built the customer text FROM the
  // dateExpr, so `occursIn` was true in every single input — and the provenance branch is the ONE place the
  // strip changes behaviour. `code-reviewer` produced the counterexample in one attempt; it is the row below.
  // The strip is NOT redundant: it is what lets a `coming` the MODEL added still pass provenance.
  // A dimension held constant is not a dimension swept. Third time this round.
  // ⚠ ORDERING, RECORDED (code-reviewer, 2026-09-09f): `stripQualifiers` removes a leading `coming` BEFORE
  // `splitAnchor` runs, so `coming friday` is unanchored but **`this coming friday` IS anchored** (the `this`
  // prefix survives and `coming` is gone by then). On a Saturday that phrase therefore RE-ASKS, even though a
  // person saying it almost certainly means next Friday. Direction is safe (an extra question, never a wrong
  // day) and the alternative — teaching `splitAnchor` about `coming` — reopens the natural-language race this
  // repo abandoned on 2026-09-09d. Asserted so the behaviour is a decision on the record, not a surprise.
  ['ANCHOR "this coming friday" IS anchored (ordering), so a Saturday clock re-asks — accepted',
    '2026-09-12T07:00:00Z', 'haircut this coming friday at 11', 'this coming friday', '11:00',
    {date:null,dropped:true,cls:'date_anchor_past',outcome:'anchor_past'}],
  ['ANCHOR "coming friday" is NOT an anchor — it points forward, so it still rolls (accepted, unchanged)',
    '2026-09-12T07:00:00Z', 'haircut coming friday at 11', 'coming friday', '11:00',
    {date:'2026-09-18',dropped:false,cls:null,outcome:'resolved_by_code'}],
  ['ANCHOR "monday this week" on a Friday is in the past -> refuse, never next Monday',
    '2026-09-11T07:00:00Z', 'haircut monday this week at 11', 'monday this week', '11:00',
    {date:null,dropped:true,cls:'date_anchor_past',outcome:'anchor_past'}],
];
for (const [label, nowISO, text, expr, time, exp] of ANCHORED) {
  const out = run({ text, slots: { dateExpr: expr, date: null, time } }, nowISO);
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

// ---- CODEX ROUND-4 REPRODUCTIONS, VERBATIM. Two of them are two-NODE defects: `Resolve Date` alone looks
// innocent and the damage appears in `Merge Slots`. So this block runs BOTH committed bodies in sequence,
// exactly as the flow does. Asserting only the resolver would have been the same fixed-axis mistake this
// round has already made four times — the axis here is "which node you look at".
{
  const wfj = JSON.parse(fs.readFileSync(WF, 'utf8'));
  const msSrc = wfj.nodes.find(n => n.name === 'Merge Slots').parameters.jsCode;
  const CFG2 = { services: [{ id: 'haircut', name: 'Haircut' }, { id: 'beard', name: 'Beard Trim' }] };
  const mergeSlots = (rd) => new Function('$json', '$', msSrc)(rd, () => ({ first: () => ({ json: { config: CFG2 } }) }))[0].json;
  const stored = { slots: { serviceId: 'haircut', date: '2026-09-11', time: null }, stage: 'collecting' };

  // [label, text, expected merged date after BOTH nodes]
  const PAIR = [
    // Codex finding 2, his input and his clock. The model extracted NOTHING (dateExpr null AND date null);
    // the stored Friday then survived and the bot proposed Friday to a customer who said Saturday.
    ['CODEX-R4-2 "Saturday at 11" with an empty extraction must NOT inherit the stored Friday',
      'Saturday at 11', null, 'day_named_not_extracted'],
    // Codex's OWN legitimate control, kept verbatim: no day literal in the text, so the stored date is the
    // right answer and must survive. This row is what stops the fix from becoming "never inherit".
    ['CODEX-R4-2 control: "11am please" names no day -> the stored date SURVIVES',
      '11am please', '2026-09-11', 'no_date'],
    ['a second day literal form is caught too ("tomorrow")', 'tomorrow at 11', null, 'day_named_not_extracted'],
    ['and an abbreviation is caught ("sat")', 'sat at 11', null, 'day_named_not_extracted'],
    // the accepted false positive, asserted so it is a known cost and not a surprise
    ['ACCEPTED COST: a PAST mention of a day also re-asks',
      'I got a haircut last saturday, can I book 11am please', null, 'day_named_not_extracted'],
    // "satisfied" must not read as "sat" — the boundary check still governs
    ['a day literal hiding inside a word does NOT trigger the re-ask',
      'I was satisfied last time, 11am please', '2026-09-11', 'no_date'],
  ];
  // The OUTCOME is asserted alongside the merged date. Asserting only the date left the whole signalling half
  // of this fix without a dying mutant: deleting `day_named_not_extracted` from the ALERT map, or renaming the
  // outcome to 'no_date' while keeping `dropped`, both kept the suite green — and both silently restore the
  // second half of the defect this row exists for ("no drop, NO ALERT"). code-reviewer, round 4.
  for (const [label, text, wantDate, wantOutcome] of PAIR) {
    const rd = run({ text, slots: { dateExpr: null, date: null, time: '11:00' }, state: stored, intent: 'book' });
    const got = mergeSlots(rd).state.slots.date;
    // `date_alert === false` is asserted for BOTH shapes on purpose: this class drops without pinging, and
    // that is a DECISION (the measured false-positive set is wide and the rate is unmeasured). Restoring the
    // ping means this row goes red first and the person doing it has to argue for it.
    const ok = got === wantDate && rd.date_resolution.outcome === wantOutcome && rd.date_alert === false;
    if (ok) { pass++; console.log('  ok     ' + label); }
    else { fail++; console.log('  FAIL   ' + label + '\n         merged date got ' + JSON.stringify(got)
                               + ', want ' + JSON.stringify(wantDate)
                               + '  · outcome got ' + rd.date_resolution.outcome + ', want ' + wantOutcome); }
  }
  // The `storedDate` half of the condition had no case either: without a stored date there is nothing to
  // inherit, so a day literal must NOT manufacture a refusal on a fresh conversation.
  {
    const fresh = run({ text: 'Saturday at 11', slots: { dateExpr: null, date: null, time: '11:00' },
                        state: { slots: { serviceId: null, date: null, time: null }, stage: 'new' }, intent: 'book' });
    const ok = fresh.date_dropped === false && fresh.date_resolution.outcome === 'no_date';
    if (ok) { pass++; console.log('  ok     no stored date -> a day literal does not manufacture a refusal'); }
    else { fail++; console.log('  FAIL   fresh conversation refused: ' + fresh.date_resolution.outcome); }
  }
}

// ---- CODEX ROUND-4: the word boundary was ASCII-only, so a Unicode separator walked straight through it.
// Every row is a real salon string with the ASCII separator swapped for its typographic twin — the kind a
// phone keyboard or a paste from a website produces without anyone noticing.
{
  const SEP = [
    ['U+2011 non-breaking hyphen', 'sun\u2011kissed balayage at 11', 'sun'],
    ['U+2013 en dash',             'what are your sat\u2013sun opening hours?', 'sat'],
    ['U+2014 em dash',             'are you open mon\u2014fri?', 'mon'],
    ['U+2212 minus sign',          'are you open mon\u2212fri?', 'mon'],
    ['U+2215 division slash',      'your sat\u2215sun hours?', 'sat'],
    ['U+FF0D fullwidth hyphen',    'sun\uFF0Dkissed balayage at 11', 'sun'],
    ['U+00AD soft hyphen',         'sun\u00ADkissed balayage at 11', 'sun'],
    ['U+200B zero-width space',    'sun\u200Bkissed balayage at 11', 'sun'],
    ['U+200C zero-width non-joiner','sun\u200Ckissed balayage at 11', 'sun'],
    ['U+200D zero-width joiner',   'sun\u200Dkissed balayage at 11', 'sun'],
    ['U+2060 word joiner',         'sun\u2060kissed balayage at 11', 'sun'],
    ['U+FEFF BOM',                 'sun\uFEFFkissed balayage at 11', 'sun'],
  ];
  for (const [label, text, expr] of SEP) {
    const out = run({ text, slots: { dateExpr: expr, date: null, time: '11:00' } });
    const ok = out.slots.date === null && out.date_alert_class === 'date_expr_forged';
    if (ok) { pass++; console.log('  ok     separator: ' + label + ' does not smuggle a day past provenance'); }
    else { fail++; console.log('  FAIL   separator: ' + label + ' -> booked ' + out.slots.date
                               + ' (' + out.date_resolution.outcome + ')'); }
  }
  // The fold is applied to the EXPRESSION too, and that is not cosmetic: it decides which ALERT the owner
  // gets. A customer really typing "sat<en dash>sun" whose wording the model copies verbatim is an
  // UNPARSEABLE expression, not a forged one — telling the owner "forged" would be a false accusation about
  // their own customer. Without the expression fold this row reports date_expr_forged.
  {
    const both = run({ text: 'what are your sat\u2013sun opening hours?',
                       slots: { dateExpr: 'sat\u2013sun', date: null, time: null } });
    const ok = both.slots.date === null && both.date_alert_class === 'date_unresolved';
    if (ok) { pass++; console.log('  ok     separator: a verbatim-copied unicode range is UNRESOLVED, not forged'); }
    else { fail++; console.log('  FAIL   separator: verbatim unicode range -> ' + both.date_alert_class
                               + ' (' + both.date_resolution.outcome + '), want date_unresolved'); }
  }
  // and the ASCII twins must still behave — the fold must not become a hole of its own
  const ascii = run({ text: 'sun-kissed balayage at 11', slots: { dateExpr: 'sun', date: null, time: '11:00' } });
  if (ascii.slots.date === null) { pass++; console.log('  ok     separator: the ASCII twin still refuses'); }
  else { fail++; console.log('  FAIL   separator: ASCII twin regressed'); }
}

// ---- THE ANCHOR SAFETY PROPERTY, PROVEN BY EXHAUSTION rather than argued in a comment.
// The node deliberately does NOT demand that a `this` came from the customer. The reason is a PROPERTY: an
// anchored resolution is always the unanchored resolution or a REFUSAL — so an anchor the model invented can
// only cost a re-ask, never book a different day. If that property stops holding, the exemption goes with it.
//
// ⚠ THIS SWEEP WAS ITSELF VACUOUS ON ITS FIRST COMMIT (code-reviewer, 2026-09-09f). It pinned `date: null` in
// BOTH arms — and `slots.date` is the single variable the property depends on, because the clipping check
// keys on a disagreement between the model's date and ours. With a real `slots.date` the anchored branch
// returned `anchored_week`, which the clipping check did not cover, so ONE invented token silently disabled
// `week_ambiguous`: on Wed 2026-09-09, text "i am away, can i book friday the week after" with model date
// 2026-09-18 gave `friday` -> REFUSE, `this friday` -> BOOKS 2026-09-11 with no alert. 4956 violations in
// 9408 inputs. A sweep that excludes the variable under test proves nothing; the `date` dimension is part of
// the sweep now, and the fix was written only after this went red.
{
  const DAYS_L = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
  const TIMES  = [null, '08:00', '11:00', '23:30', '00:01'];
  // null · agreeing · same weekday one and two weeks out (the clipping signature) · a different weekday
  const DATE_OF = (base) => [null, base,
    DateTime.fromISO(base).plus({ weeks: 1 }).toISODate(),
    DateTime.fromISO(base).minus({ weeks: 1 }).toISODate(),
    DateTime.fromISO(base).plus({ days: 1 }).toISODate()];
  let violations = 0, refusals = 0, checked = 0, firstViolation = null;
  for (let d = 0; d < 21; d++) for (const h of [0, 7, 12, 20]) {
    const iso = DateTime.fromISO('2026-09-01T00:00:00Z').plus({ days: d, hours: h }).toISO();
    for (const day of DAYS_L) for (const t of TIMES) {
      const at = t ? ' at ' + t : '';
      // the unanchored answer is the yardstick, so the date candidates are built around IT
      const probe = run({ text: 'haircut ' + day + at, slots: { dateExpr: day, date: null, time: t } }, iso);
      for (const dt of DATE_OF(probe.slots.date || '2026-09-11')) {
        const a = run({ text: 'haircut this ' + day + at, slots: { dateExpr: 'this ' + day, date: dt, time: t } }, iso);
        const u = run({ text: 'haircut ' + day + at,       slots: { dateExpr: day,          date: dt, time: t } }, iso);
        checked++;
        // ⚠ ATTRIBUTED refusals only. The first version counted every anchored refusal, and most of them come
        // from the UNANCHORED side (a `dt` one week out trips `week_ambiguous` in both arms) — so a mutant
        // that made `splitAnchor` a no-op still showed 5880 "refusals" and the sweep stayed GREEN while the
        // anchor did nothing at all (code-reviewer, third pass). Counting only refusals the anchor CAUSED is
        // what makes this non-vacuous: with the no-op mutant that count is 0 and the row goes red.
        if (a.slots.date === null) { if (u.slots.date !== null) refusals++; }
        else if (a.slots.date !== u.slots.date) {
          violations++;
          if (!firstViolation) firstViolation = { iso, day, t, dt, anchored: a.slots.date, unanchored: u.slots.date };
        }
      }
    }
  }
  if (firstViolation) console.log('         first violation: ' + JSON.stringify(firstViolation));
  // `refusals > 0` matters as much as `violations === 0`: without it the property would also hold for an
  // anchor that does nothing at all, and the assertion would be vacuous.
  if (violations === 0 && refusals > 0) {
    pass++; console.log('  ok     anchor safety: ' + checked + ' inputs, 0 dates the unanchored path would not give, '
                        + refusals + ' refusals (so the anchor is not a no-op)');
  } else {
    fail++; console.log('  FAIL   anchor safety: violations=' + violations + ' refusals=' + refusals);
  }
}

// ---- TWO LANES, CHECKED SEPARATELY — never by generalisation (three times in this phase a drill on the
// booking lane was read as proof for the reschedule lane, and three times it was wrong; the worst was
// `Reschedule Lookup` reading `$('Validate Intent')`, UPSTREAM of the guard, so the whole reschedule branch
// bypassed it). The DOMINATOR check below deletes `Resolve Date` from the graph and requires that neither
// date-writer stays reachable from `Validate Intent`.
// ⚠ It would NOT have caught that bypass, and the claim that it would has been removed (Codex round 4).
// `Reschedule Lookup` was and is topologically downstream of the guard; the defect was WHICH FIELD it read
// once it got there. Topology and field-reading are different questions — the executed lane assertions
// further down are the ones that answer the second.
{
  const conns = JSON.parse(fs.readFileSync(WF, 'utf8')).connections;
  const reach = (from, skip) => {
    const seen = new Set(), q = [from];
    while (q.length) {
      const n = q.shift();
      for (const b of ((conns[n] || {}).main || [])) for (const c of (b || [])) {
        if (c.node === skip || seen.has(c.node)) continue;
        seen.add(c.node); q.push(c.node);
      }
    }
    return seen;
  };
  const WRITERS = ['Merge Slots', 'Reschedule Lookup'];   // the only two nodes that put a NEW date into state
  const fromResolve = reach('Resolve Date');
  const bypass = reach('Validate Intent', 'Resolve Date');
  for (const w of WRITERS) {
    const ok = fromResolve.has(w) && !bypass.has(w);
    if (ok) { pass++; console.log('  ok     lane: ' + w + ' is downstream of Resolve Date and unreachable without it'); }
    else { fail++; console.log('  FAIL   lane: ' + w + ' downstream=' + fromResolve.has(w) + ' bypassable=' + bypass.has(w)); }
  }
  // ⚠ AND EACH LANE IS EXECUTED, NOT GREPPED (Codex round 4). This block used to assert that the two node
  // bodies CONTAIN the strings `date_dropped === true` and `$('Resolve Date')`. Both strings survive the one
  // mutation that matters — swapping `rd.slots.date` for `vi.slots.date`, i.e. reading the LLM's raw date
  // instead of the resolved one, which is EXACTLY the reschedule bypass this project shipped once before.
  // The suite stayed 126/126. So the two writers are now RUN, with the raw and the resolved date set to
  // DIFFERENT values so that only one of them can produce the asserted answer.
  //
  // The old comment here claimed this check "would have caught the round-2 reschedule bypass". It would not
  // have: a grep for a node reference cannot tell which field of that reference is read. That sentence is
  // deleted rather than softened.
  const wf2 = JSON.parse(fs.readFileSync(WF, 'utf8'));
  const bodyOf = (n) => wf2.nodes.find(x => x.name === n).parameters.jsCode;
  const RAW = '2026-09-12';        // what the LLM said  (a Saturday)
  const RES = '2026-09-11';        // what Resolve Date decided (the Friday the customer named)
  const LCFG = { config: { business: { timezone: TZ }, bot: { cancellationCutoffHours: 2 },
    services: [{ id: 'haircut', name: 'Haircut' }], messageTemplates: {} } };
  const vi = { intent: 'reschedule', slots: { serviceId: 'haircut', dateExpr: 'friday', date: RAW, time: '11:00' },
               state: { stage: 'booked', slots: { serviceId: 'haircut', date: null, time: null } } };

  // --- reschedule lane: run the real node with rd != vi
  {
    const rd = { ...vi, slots: { ...vi.slots, date: RES }, date_dropped: false };
    const rows = [{ json: { id: 'recX', fields: { status: 'booked', service: 'Haircut',
      start_utc: DateTime.now().plus({ days: 20 }).toISO(), gcal_event_id: 'abcde12345', calendar_id: 'cal-1' } } }];
    const ctx = (n) => ({ first: () => ({ json: n === 'Load Config' ? LCFG : (n === 'Resolve Date' ? rd : vi) }) });
    const out = new Function('$json', '$', '$input', bodyOf('Reschedule Lookup'))(
      rd, ctx, { all: () => rows })[0].json;
    const got = out.state.slots.date;
    if (got === RES) { pass++; console.log('  ok     lane reschedule: the RESOLVED date is what reaches the move target (ran the node)'); }
    else { fail++; console.log('  FAIL   lane reschedule: move target used ' + got + ', want ' + RES
                               + ' — the lane is reading the LLM date again'); }
    // and the refusal must still be honoured, executed rather than grepped
    const rdDrop = { ...rd, date_dropped: true };
    const ctx2 = (n) => ({ first: () => ({ json: n === 'Load Config' ? LCFG : (n === 'Resolve Date' ? rdDrop : vi) }) });
    const out2 = new Function('$json', '$', '$input', bodyOf('Reschedule Lookup'))(rdDrop, ctx2, { all: () => rows })[0].json;
    if (out2._resched_check === false && out2.state.slots.date !== RAW) {
      pass++; console.log('  ok     lane reschedule: a refused date does not move anything (ran the node)');
    } else { fail++; console.log('  FAIL   lane reschedule: refusal ignored -> ' + JSON.stringify(out2.state.slots)); }
  }

  // --- booking lane: same shape, same discipline
  {
    const CFG3 = { services: [{ id: 'haircut', name: 'Haircut' }] };
    const merge = (rd) => new Function('$json', '$', bodyOf('Merge Slots'))(
      rd, () => ({ first: () => ({ json: { config: CFG3 } }) }))[0].json;
    const kept = merge({ ...vi, slots: { ...vi.slots, date: RES }, date_dropped: false });
    if (kept.state.slots.date === RES) { pass++; console.log('  ok     lane booking: the RESOLVED date is what is merged (ran the node)'); }
    else { fail++; console.log('  FAIL   lane booking: merged ' + kept.state.slots.date + ', want ' + RES); }
    const dropped = merge({ ...vi, slots: { ...vi.slots, date: RES }, date_dropped: true });
    if (dropped.state.slots.date === null) { pass++; console.log('  ok     lane booking: a refused date is nulled, never resurrected (ran the node)'); }
    else { fail++; console.log('  FAIL   lane booking: refusal ignored -> ' + dropped.state.slots.date); }
    // BOTH dates present and DIFFERENT — the only shape that can tell `fresh ?? stored` from `stored ?? fresh`.
    // Without it, reversing that precedence survives: the customer moves from Friday to Saturday, the engine
    // resolves Saturday correctly, and the merge quietly hands the stored Friday to the booking.
    const NEWD = '2026-09-12';
    const replaced = merge({ ...vi, slots: { ...vi.slots, date: NEWD }, date_dropped: false,
      state: { stage: 'collecting', slots: { serviceId: 'haircut', date: RES, time: '11:00' } } });
    if (replaced.state.slots.date === NEWD) { pass++; console.log('  ok     lane booking: a newly resolved date REPLACES the stored one, it does not lose to it'); }
    else { fail++; console.log('  FAIL   lane booking: stored date won over the new one -> ' + replaced.state.slots.date); }
  }
}

console.log(`\nresolve-date: ${pass}/${pass + fail} pass (node code read from n8n/workflow.sanitized.json, now=${NOW} ${TZ})`);
process.exit(fail ? 1 : 0);
