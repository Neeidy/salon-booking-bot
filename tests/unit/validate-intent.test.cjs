#!/usr/bin/env node
/**
 * Unit test for `Validate Intent` + the `Extraction Transient?` route — the PERMANENT-LOCK guard (Codex MED-6).
 *
 * WHY IT EXISTS: Codex sent {"intent":"answer_faq","confidence":0.92,"slots":{"faqTopic":"price"}} — a
 * perfectly ordinary price question whose `dateExpr` key was simply ABSENT. The committed schema requires
 * that key, so validation failed, `Invalid or Handoff Gate` fired and `Mark Handoff` wrote stage='handoff':
 * a PERMANENT lock on a customer who did nothing wrong. That is the same class as the `hi` bug this phase
 * opened with. The previous drill for this path used dateExpr:null — a PRESENT key with a null value, which
 * validates — so it could never have found this. The difference between "null" and "absent" is the whole bug,
 * and every case below removes the key entirely.
 *
 * WHY IT EXECUTES THE COMMITTED NODE AND THE COMMITTED IF EXPRESSION: `.claude/rules/contract-integrity.md`.
 * The node body comes from n8n/workflow.sanitized.json (proved byte-identical to live by
 * scripts/check-content-parity.py) and the routing decision is evaluated from the `Extraction Transient?`
 * node's own `leftValue` expression text — not a paraphrase of it. A rewritten condition therefore fails here.
 *
 * ⚠ Same accepted security note as resolve-date.test.cjs: this runs `jsCode` from the committed export via
 * `new Function`. A PR touching the workflow JSON is a CODE change and must be read as one.
 *
 * Run:  node tests/unit/validate-intent.test.cjs      (exit 0 = all pass)
 */
const fs = require('fs');
const path = require('path');

const WF = path.join(__dirname, '../../n8n/workflow.sanitized.json');
const wf = JSON.parse(fs.readFileSync(WF, 'utf8'));
const nodeOf = (name) => wf.nodes.find(n => n.name === name);

const src = nodeOf('Validate Intent').parameters.jsCode;
const validateIntentNode = new Function('$json', '$', src);

// The routing expressions, taken verbatim from the committed IF nodes: "={{ <expr> }}".
const condOf = (name) => {
  const raw = nodeOf(name).parameters.conditions.conditions[0].leftValue;
  const m = raw.match(/^=\{\{([\s\S]+)\}\}$/);
  if (!m) { console.error(name + ' leftValue is not an ={{ }} expression: ' + raw); process.exit(1); }
  return new Function('$json', '$', 'return (' + m[1] + ');');
};
const transientCond = condOf('Extraction Transient?');
const repeatCond    = condOf('Repeat Extraction Failure?');
// `prev` is what `Merge State` read from Airtable at the START of this turn — the only thing the escalation
// ladder keys on. `null` = a clean previous turn.
let PREV_INTENT = null;
const $merge = (n) => (n === 'Merge State'
  ? { first: () => ({ json: { state: { ...CTX.state, last_intent: PREV_INTENT } } }) }
  : { first: () => ({ json: CTX }) });
// "routes to the retry builder" is now TWO gates, and the test walks both — a single-gate helper would have
// gone on passing after `Repeat Extraction Failure?` was inserted in front of the builder.
const routesToRetry = (out) => transientCond(out, $merge) === true && repeatCond(out, $merge) === false;
const routesToHandoff = (out) => transientCond(out, $merge) === false || repeatCond(out, $merge) === true;

const CTX = { channel: 'widget', sender_key: 'widget:test', text: 'how much is a haircut?',
              state: { stage: 'collecting', last_intent: 'book', slots: { serviceId: null, date: null, time: null } } };
const $ = () => ({ first: () => ({ json: CTX }) });
const withStage = (stage) => { CTX.state = { ...CTX.state, stage }; };
const llm = (obj, stop) => ({ stop_reason: stop || 'end_turn', content: [{ text: JSON.stringify(obj) }] });
const run = (raw) => validateIntentNode(raw, $)[0].json;

let pass = 0, fail = 0;
const check = (label, cond, got) => {
  if (cond) { pass++; console.log('  ok     ' + label); }
  else { fail++; console.log('  FAIL   ' + label + '\n         got ' + JSON.stringify(got)); }
};

// ---- 1) THE CODEX PAYLOAD, VERBATIM. `slots` has ONLY faqTopic — the dateExpr key does not exist.
{
  const out = run(llm({ intent: 'answer_faq', confidence: 0.92, slots: { faqTopic: 'price' } }));
  check('CODEX-M6 the exact payload: schema-invalid, but flagged TRANSIENT',
    out.valid === false && out.extraction_transient === true, out);
  check('CODEX-M6 it does NOT route to the handoff gate — no permanent lock',
    routesToRetry(out) === true, { routes: routesToRetry(out) });
  check('CODEX-M6 the failure is still VISIBLE (invalid_reason names the missing key)',
    typeof out.invalid_reason === 'string' && out.invalid_reason.indexOf('dateExpr') !== -1, out.invalid_reason);
}

// ---- 2) THE DRILL Yigitcan asked for: the key ABSENT across four ordinary intents. None may lock.
const ABSENT = [
  ['FAQ / price',  { intent: 'answer_faq',   confidence: 0.95, slots: { faqTopic: 'price', serviceId: 'haircut' } }],
  ['lead',         { intent: 'capture_lead', confidence: 0.8,  slots: { notes: 'asked about hair coloring' } }],
  ['cancel',       { intent: 'cancel',       confidence: 0.9,  slots: {} }],
  ['greeting',     { intent: 'unknown',      confidence: 0.3,  slots: {} }],
];
for (const [label, payload] of ABSENT) {
  const out = run(llm(payload));
  check('no dateExpr key at all — ' + label + ' does NOT lock',
    out.valid === false && out.extraction_transient === true && routesToRetry(out) === true,
    { valid: out.valid, transient: out.extraction_transient, routes: routesToRetry(out) });
}

// ---- 3) THE BOUNDARY. A jailbreak/explicit handoff must STILL lock even when its payload is schema-invalid,
// or the fix would have opened a hole in the control that actually matters.
{
  const out = run(llm({ intent: 'handoff', confidence: 0.97, slots: {} }));
  check('intent=handoff with an invalid payload STILL locks (never routed to retry)',
    out.extraction_transient === true && routesToRetry(out) === false,
    { transient: out.extraction_transient, routes: routesToRetry(out) });
}

// ---- 4) THE THREE NON-SCHEMA FAILURES keep the lock: they are not a contract slip, they are the model not
// answering at all. Each must be transient=false so `Extraction Transient?` sends it to the handoff gate.
const HARD = [
  ['bad stop_reason', { stop_reason: 'max_tokens', content: [{ text: '{}' }] }],
  ['unparseable JSON', { stop_reason: 'end_turn', content: [{ text: 'not json' }] }],
  ['a JSON array, not an object', { stop_reason: 'end_turn', content: [{ text: '[1,2]' }] }],
];
for (const [label, raw] of HARD) {
  const out = run(raw);
  check('hard failure keeps the lock — ' + label,
    out.intent === 'handoff' && out.extraction_transient !== true && routesToRetry(out) === false,
    { intent: out.intent, transient: out.extraction_transient, routes: routesToRetry(out) });
}

// ---- 4b) EQUIVALENT MUTANT, PINNED. In the 2026-09-09f mutation round, replacing
// `$json.extraction_transient === true` with `$json.valid !== true` in the route SURVIVED. It is genuinely
// equivalent TODAY — every hard-failure return hard-codes intent:'handoff', and the route's second clause
// excludes that intent — so no input can tell the two apart. But that equivalence is a COINCIDENCE of the
// handoff() helper, not a property of the design: if handoff() ever stopped forcing intent='handoff', the
// flag version would keep locking and the `valid !== true` version would route a dead model answer to a
// polite "could you rephrase". The coupling is therefore pinned here instead of left as a claim in a report.
{
  const forces = /const handoff = \(reason\) => \[\{ json: \{[\s\S]{0,400}?intent: 'handoff'/.test(src);
  check("the hard-failure helper still forces intent='handoff' (the reason mutant M16 is equivalent)",
    forces, { forces });
}

// ---- 4c) MED-1 (flow-reviewer, 2026-09-09f). The transient route was inserted in FRONT of
// `Invalid or Handoff Gate`, and `Confirm Pending & Uncertain?` sits BEHIND that gate — so a schema-invalid
// turn arriving while a cancel/reschedule confirmation was pending stopped reaching the guard that exists for
// exactly that moment. `handoff.md`: "Never act on a classification we distrust while a booking hangs on it",
// and a payload that broke the contract is the strongest form of distrust there is. The stage list in the
// condition is COPIED from `Confirm Pending & Uncertain?`; the assertion below compares the two so they
// cannot drift apart.
{
  const pendingStages = ['cancel_confirming', 'reschedule_confirming'];
  for (const stage of pendingStages) {
    withStage(stage);
    const out = run(llm({ intent: 'cancel', confidence: 0.9, slots: {} }));
    check('a pending confirmation (' + stage + ') still goes to the handoff gate, never to retry',
      out.extraction_transient === true && routesToRetry(out) === false && routesToHandoff(out) === true,
      { transient: out.extraction_transient, retry: routesToRetry(out) });
  }
  withStage('collecting');
  const guard = nodeOf('Confirm Pending & Uncertain?').parameters.conditions.conditions[0].leftValue;
  const mine  = nodeOf('Extraction Transient?').parameters.conditions.conditions[0].leftValue;
  const list  = "['cancel_confirming','reschedule_confirming']";
  check('the two nodes name the SAME pending-confirmation stages (no second truth)',
    guard.indexOf(list) !== -1 && mine.indexOf(list) !== -1, { guard, mine });
}

// ---- 4d) MED-2. Without a ladder a systematic contract failure gives the customer up to
// `bot.maxTurnsPerConversation` (12) identical "could you rephrase" turns while the owner sees ONE alert
// (throttle is 30 min on `class:sender`). The clarify path escalates after TWO; this now matches it.
// `last_intent` is the signal because it survives the turn boundary: the only OTHER writer of 'invalid' is
// the hard-failure handoff, and that one also writes `stage='handoff'`, so the next turn stops at
// `Check Handoff Lock` and never reaches here. Shown, not assumed — see the assertion below.
{
  const out = run(llm({ intent: 'answer_faq', confidence: 0.92, slots: { faqTopic: 'price' } }));
  PREV_INTENT = null;
  check('FIRST extraction failure in a row -> retry, no lock',
    routesToRetry(out) === true, { retry: routesToRetry(out) });
  PREV_INTENT = 'invalid';
  check('SECOND consecutive extraction failure -> escalates to the handoff gate',
    routesToRetry(out) === false && repeatCond(out, $merge) === true, { retry: routesToRetry(out) });
  PREV_INTENT = 'clarify';
  check("an unrelated previous turn does NOT escalate ('clarify' is the other ladder, not this one)",
    routesToRetry(out) === true, { retry: routesToRetry(out) });
  // "consecutive" is shorthand — the same caveat the clarify ladder carries. `last_intent` is a STICKY FLAG,
  // cleared only by a turn that WRITES state; a guard-trip / LLM-outage / spend-cap / idempotent-replay turn
  // in between leaves it standing. So a transient turn, then an outage, then another transient turn escalates.
  // That is the safe direction, and it is asserted rather than left to be discovered.
  PREV_INTENT = 'invalid';
  check('the flag is STICKY, not a consecutive counter — an intervening no-state-write turn does not reset it',
    routesToRetry(out) === false, { retry: routesToRetry(out) });
  PREV_INTENT = null;
  // the structural half of the claim above
  const hard = src.slice(0, src.indexOf('// 4) validate against'));
  check("the ladder's signal is unambiguous: the hard-failure path writes last_intent='invalid' too, but it "
        + "also locks, so a NEXT turn can only see 'invalid' from a transient one",
    /last_intent: 'invalid'/.test(hard) && nodeOf('Mark Handoff').parameters.jsCode.indexOf("stage: 'handoff'") !== -1,
    null);
}

// ---- 4e) code-reviewer #9. The lock boundary keys on the literal string 'handoff', so a schema-invalid
// payload carrying an OUT-OF-ENUM intent (a shape a jailbreak could produce) routes to retry rather than the
// lock. Recorded as a bounded, deliberate trade rather than tightened further: the turn reaches no write path
// (`prompt-injection.md`'s allow-list is what makes an injection harmless, and it is untouched), and since
// MED-2 a SECOND one escalates to `Mark Handoff`. Both halves are asserted, so the bound is a fact here and
// not a sentence in a report.
{
  const out = run(llm({ intent: 'ignore_previous_instructions', confidence: 0.99, slots: {} }));
  PREV_INTENT = null;
  check('an out-of-enum intent on an invalid payload does NOT lock on turn one (known, bounded)',
    out.extraction_transient === true && routesToRetry(out) === true, { retry: routesToRetry(out) });
  PREV_INTENT = 'invalid';
  check('...and it IS bounded: the second one escalates to the handoff gate',
    routesToRetry(out) === false, { retry: routesToRetry(out) });
  PREV_INTENT = null;
  const retry = nodeOf('Build Extraction-Retry State').parameters.jsCode;
  check('...and it can reach no write path: the retry builder only goes to Save State + the owner alert',
    JSON.stringify(wf.connections['Build Extraction-Retry State'].main[0].map(c => c.node).sort())
      === JSON.stringify(['Build Owner Alert', 'Save State']), null);
  const wellFormedJailbreak = run(llm({ intent: 'handoff', confidence: 0.97,
    slots: { serviceId: null, date: null, dateExpr: null, time: null, customerName: null, notes: null, faqTopic: null } }));
  check('the ORDINARY jailbreak shape (valid payload, intent=handoff) still locks on turn one',
    wellFormedJailbreak.valid === true && wellFormedJailbreak.intent === 'handoff'
      && routesToRetry(wellFormedJailbreak) === false, wellFormedJailbreak.intent);
}

// ---- 5) A VALID payload is untouched by any of this.
{
  const out = run(llm({ intent: 'book', confidence: 0.9,
    slots: { serviceId: 'haircut', date: '2026-09-11', dateExpr: 'friday', time: '11:00',
             customerName: null, notes: null, faqTopic: null }, reply: null }));
  check('a valid payload: not transient, not routed to retry, slots intact',
    out.valid === true && out.extraction_transient === false && routesToRetry(out) === false
    && out.slots.dateExpr === 'friday', out);
}

// ---- 6) dateExpr PRESENT and null validates — this is the case the OLD drill used, and the reason it
// found nothing. Kept so the distinction that hid the bug stays on the record.
{
  const out = run(llm({ intent: 'answer_faq', confidence: 0.92,
    slots: { serviceId: null, date: null, dateExpr: null, time: null, customerName: null, notes: null, faqTopic: 'price' } }));
  check('dateExpr PRESENT and null is VALID — "null" and "absent" are not the same test',
    out.valid === true && out.extraction_transient === false, out);
}

// ---- 7) STRUCTURAL: the retry builder must not write `stage`, or the lock comes back by another door.
{
  // ⚠ the canary used to be `/stage\s*:/` alone, which `code-reviewer` showed would miss an ASSIGNMENT
  // (`state.stage = 'handoff'`) and a quoted key (`'stage':`). All three forms are checked now — and the
  // BEHAVIOURAL half below (running the node and asserting the stage comes back unchanged) is what actually
  // proves it; the text scan only catches a stage written in a form the run does not reach.
  const retry = nodeOf('Build Extraction-Retry State').parameters.jsCode;
  const code = retry.replace(/\/\/[^\n]*/g, '');
  const writesStage = /(^|[^.\w])stage\s*:/.test(code) || /['"]stage['"]\s*:/.test(code)
                   || /\.stage\s*=/.test(code) || /\[\s*['"]stage['"]\s*\]\s*=/.test(code);
  check('Build Extraction-Retry State writes no `stage` in ANY form (key, quoted key, or assignment)',
    writesStage === false, { writesStage });
  {
    // behavioural: run the committed node and assert the stage it emits is the one it was handed
    const builder = new Function('$json', '$', retry);
    const inp = { state: { ...CTX.state, stage: 'cancel_confirming', last_intent: 'invalid' }, slots: null };
    const outp = builder(inp, () => ({ first: () => ({ json: { config: { messageTemplates: { notUnderstood: 'X' } } } }) }))[0].json;
    check('...and running it proves it: the stage it was handed comes back unchanged',
      outp.state.stage === 'cancel_confirming' && outp.computed_reply === 'X'
        && outp.extraction_invalid === true, outp.state);
  }
  const conn = wf.connections['Build Extraction-Retry State'].main[0].map(c => c.node).sort();
  check('Build Extraction-Retry State goes to Save State AND the owner alert, and nowhere else',
    JSON.stringify(conn) === JSON.stringify(['Build Owner Alert', 'Save State']), conn);
  const gate = wf.connections['Extraction Transient?'].main.map(b => b.map(c => c.node));
  check('Extraction Transient? true -> the repeat ladder, false -> the unchanged handoff gate',
    JSON.stringify(gate) === JSON.stringify([['Repeat Extraction Failure?'], ['Invalid or Handoff Gate']]), gate);
  const ladder = wf.connections['Repeat Extraction Failure?'].main.map(b => b.map(c => c.node));
  check('Repeat Extraction Failure? true -> Mark Handoff (the lock is CORRECT on the second one), false -> retry',
    JSON.stringify(ladder) === JSON.stringify([['Mark Handoff'], ['Build Extraction-Retry State']]), ladder);
  const alert = nodeOf('Build Owner Alert').parameters.jsCode;
  check('the owner still gets an alert for it (a schema violation is OUR defect and stays visible)',
    alert.indexOf("j.extraction_invalid === true") !== -1 && retry.indexOf('extraction_invalid: true') !== -1, null);
}

// ---- 8) NO DOUBLE OWNER ALERT. `Date Alert?` fans into `Build Owner Alert` on its true branch and into
// `Extraction Transient?` on BOTH branches, and `Build Extraction-Retry State` fans into the alert too — so a
// turn that were both date-alerting AND extraction-transient would ping the owner twice. It cannot happen, and
// this pins WHY rather than leaving it as an assumption: an invalid payload carries `slots: null`, and
// `Resolve Date` returns early on null slots with `date_alert: false`. Break either half and this goes red.
{
  const resolve = new Function('$json', '$', 'DateTime', nodeOf('Resolve Date').parameters.jsCode);
  const cfg = () => ({ first: () => ({ json: { config: { business: { timezone: 'Europe/Vienna' } } } }) });
  const out = run(llm({ intent: 'answer_faq', confidence: 0.92, slots: { faqTopic: 'price' } }));
  const rd = resolve(out, cfg, require(path.join(__dirname, '../../scripts/node_modules/luxon')).DateTime)[0].json;
  check('an extraction-transient turn cannot also raise a date alert (slots:null -> Resolve Date returns early)',
    out.slots === null && rd.date_alert === false && rd.date_dropped === false,
    { slots: out.slots, date_alert: rd.date_alert });
}

console.log(`\nvalidate-intent: ${pass}/${pass + fail} pass (node code + IF expression read from n8n/workflow.sanitized.json)`);
process.exit(fail ? 1 : 0);
