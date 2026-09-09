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
 * The node body comes from n8n/workflow.sanitized.json and the routing decision is evaluated from the
 * committed IF nodes' own `leftValue` expression text AND their `operator` — not a paraphrase of either.
 * A rewritten condition or an inverted operator therefore fails here; the combinator is NOT evaluated and
 * the harness refuses to run if either IF ever grows a second condition.
 *
 * ⚠ "byte-identical to live" is CONDITIONAL on `check-content-parity.py` having been run against the live
 * instance in the same state — it needs credentials this suite does not have. A green run here is a
 * statement about the COMMITTED artefact (corrected 2026-09-09g).
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
// ⚠ EVALUATES THE WHOLE IF, NOT JUST ITS EXPRESSION (Codex round 4). The first version read `leftValue`
// alone, so flipping the node's `operator.operation` from "true" to "false" — inverting every routing
// decision in the flow — left the suite at 33/33. The IF's verdict is expression AND operator AND
// combinator; a test that reads one third of the configuration is testing a third of the node. The
// operator is applied here and an unrecognised one is a hard failure rather than a silent default,
// because "we did not understand the config so we assumed the good case" is how this class of hole starts.
// PRECISELY what this evaluates, since overclaiming here is the same sin: the EXPRESSION and the OPERATOR.
// The COMBINATOR is not evaluated — flipping `and`->`or` survives — and it cannot matter while there is
// exactly one condition, which is why that count is asserted rather than assumed. Add a second condition to
// either IF and this harness stops with an error instead of quietly testing a node it no longer understands.
const condOf = (name) => {
  const cfgNode = nodeOf(name).parameters.conditions;
  const conds = cfgNode.conditions;
  if (conds.length !== 1) { console.error(name + ': expected exactly 1 condition, found ' + conds.length); process.exit(1); }
  const c = conds[0];
  const raw = c.leftValue;
  const m = raw.match(/^=\{\{([\s\S]+)\}\}$/);
  if (!m) { console.error(name + ' leftValue is not an ={{ }} expression: ' + raw); process.exit(1); }
  const op = (c.operator || {});
  if (op.type !== 'boolean' || (op.operation !== 'true' && op.operation !== 'false')) {
    console.error(name + ': unsupported operator ' + JSON.stringify(op) + ' — the harness must be taught it '
      + 'before it can claim to evaluate this node'); process.exit(1);
  }
  const negate = op.operation === 'false';
  const body = new Function('$json', '$', 'return (' + m[1] + ');');
  return (json, dollar) => (negate ? !body(json, dollar) : !!body(json, dollar));
};
const transientCond = condOf('Extraction Transient?');
const repeatCond    = condOf('Repeat Extraction Failure?');
// `prev` is what `Merge State` read from Airtable at the START of this turn — the only thing the escalation
// ladder keys on. `null` = a clean previous turn.
// ⚠ IT IS NOT A LITERAL ANY MORE (Codex round 4). Setting it to the string 'invalid' by hand meant the
// ladder was tested against the harness's OPINION of what turn 1 persists, not against what turn 1 actually
// writes — so changing `Validate Intent`'s `last_intent: valid ? parsed.intent : 'invalid'` to 'book', which
// breaks the ladder outright, left the suite at 33/33. `persistedAfter()` closes that loop: it runs the
// committed node for turn 1 and follows the value through the SAME mapping `Save State` writes
// (`$json.state.last_intent`) and `Merge State` reads back, so turn 2 sees what turn 1 really left behind.
let PREV_INTENT = null;
// what `Save State`'s own `stage` column expression produced on the last `persistedAfter()` run
let STAGE_WRITTEN;
// ⚠ THE WHOLE PERSISTENCE CHAIN IS EXECUTED — producer, retry builder, column mapping, Airtable row,
// readback (Codex round 4, finding 1). Two earlier versions of this helper were each one node short of the
// loop, and each left the ladder's real killer alive:
//   * v1 wrote `out.state.last_intent` with a comment claiming that is what Save State stores — a hand mirror.
//   * v2 fetched Save State's column expression. That killed a DIFFERENT mutant (deleting the column) but
//     still skipped the two nodes BETWEEN the producer and that column. Measured: the ORIGINAL mutant —
//     `Build Extraction-Retry State` doing `state: { ...j.state, last_intent: 'book' }` — stayed GREEN at
//     34/34, and so did nulling `Merge State`'s `last_intent` readback. Both make the ladder unreachable, so
//     a systematic contract failure re-asks until the max-turns guard instead of handing off.
// The round-4 claim that "all three of Codex's mutants were killed" was also false: the surviving one had
// been REPLACED with an easier mutant rather than killed. Retracted in docs/ROADMAP.md, closed here instead.
//
// The chain below, and PRECISELY which parts are committed artefacts (the earlier version said "every step
// executing the COMMITTED node", and step 4 is a literal — code-reviewer, round 5):
//   1 `Validate Intent`                 — committed node, executed
//   2 `Build Extraction-Retry State`    — committed node, executed
//   3 `Save State`.last_intent + .stage — committed COLUMN EXPRESSIONS, fetched and evaluated
//   4 the Airtable row                  — HAND-BUILT here from (3)'s outputs; Airtable itself is not run
//   5 `Merge State`                     — committed node, executed, and its `last_intent` readback is read
// Only `last_intent` and `stage` travel the whole way; `Merge State`'s other readbacks (turn_count, slots)
// are not asserted here and this comment does not pretend they are.
const chainSrc = (n) => nodeOf(n).parameters.jsCode;
const persistedAfter = (raw) => {
  const produced = validateIntentNode(raw, $)[0].json;                                    // 1 producer
  const retryCfg = () => ({ first: () => ({ json: { config: { messageTemplates: { notUnderstood: 'X' } } } }) });
  const built = new Function('$json', '$', chainSrc('Build Extraction-Retry State'))(produced, retryCfg)[0].json;  // 2
  const cols = (nodeOf('Save State').parameters.columns || {}).value || {};               // 3 column mapping
  const expr = cols.last_intent;
  if (typeof expr !== 'string') {
    console.error('Save State has no `last_intent` column mapping — the escalation ladder reads a value '
      + 'nothing writes. Fix the flow or this harness, but do not let this pass.'); process.exit(1);
  }
  const m = expr.match(/^=\{\{([\s\S]+)\}\}$/);
  if (!m) { console.error('Save State.last_intent is not an ={{ }} expression: ' + expr); process.exit(1); }
  const written = new Function('$json', 'return (' + m[1] + ');')(built);
  // ⚠ `stage` IS EVALUATED FROM ITS COLUMN TOO (code-reviewer, round 5). It used to be hand-copied from
  // `built.state.stage`, which left the SEVENTH fixed axis of this phase — and on the one field that is this
  // class's entire contract. Measured: setting `Save State`'s stage column to `={{ 'handoff' }}`, i.e.
  // writing a PERMANENT LOCK on every single turn (MED-6 restored in the worst possible form), left the suite
  // at 35/35. The two existing stage assertions could not see it: one greps the BUILDER's body, the other
  // RUNS the builder — and neither of them is the thing that writes the column.
  const stageExpr = cols.stage;
  if (typeof stageExpr !== 'string') {
    console.error('Save State has no `stage` column mapping — "no stage write, no lock" cannot be checked.');
    process.exit(1);
  }
  const sm = stageExpr.match(/^=\{\{([\s\S]+)\}\}$/);
  if (!sm) { console.error('Save State.stage is not an ={{ }} expression: ' + stageExpr); process.exit(1); }
  const writtenStage = new Function('$json', 'return (' + sm[1] + ');')(built);
  STAGE_WRITTEN = writtenStage;
  const row = { id: 'recDrill0000000001', createdTime: '2026-09-08T00:00:00.000Z',        // 4 the written row
                fields: { sender_key: CTX.sender_key, last_intent: written,
                          stage: writtenStage, turn_count: 1 } };
  const mergeCtx = () => ({ first: () => ({ json: { channel: 'widget', senderId: 'test',
                            sender_key: CTX.sender_key, text: 'next turn' } }) });
  const merged = new Function('$json', '$', chainSrc('Merge State'))(row, mergeCtx)[0].json;   // 5 readback
  const readBack = merged.state.last_intent;
  return (readBack === undefined || readBack === '') ? null : readBack;
};
const $merge = (n) => (n === 'Merge State'
  ? { first: () => ({ json: { state: { ...CTX.state, last_intent: PREV_INTENT } } }) }
  : { first: () => ({ json: CTX }) });
// PREV_INTENT is set from `persistedAfter()` — the EXECUTED chain — or to an explicit control value. The
// literal 'invalid' is used only where the case is deliberately about a value arriving from somewhere else
// (a sticky flag surviving a no-write turn, an owner's partial unlock); the ladder's own cases take it from
// the chain, because that is the thing under test.
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
  const failingPayload = llm({ intent: 'answer_faq', confidence: 0.92, slots: { faqTopic: 'price' } });
  const out = run(failingPayload);
  PREV_INTENT = null;
  check('FIRST extraction failure in a row -> retry, no lock',
    routesToRetry(out) === true, { retry: routesToRetry(out) });
  // turn 2 inherits what turn 1 ACTUALLY persisted — no hand-written control value
  PREV_INTENT = persistedAfter(failingPayload);
  check("the ladder's input is what turn 1 really wrote, not a literal in this file",
    PREV_INTENT === 'invalid', { persisted: PREV_INTENT });
  // The contract of this whole class, checked where it is actually enforced — the COLUMN, not the builder.
  check('Save State\'s own stage column writes the stage back unchanged — an extraction-transient turn '
      + 'persists NO lock', STAGE_WRITTEN === CTX.state.stage && STAGE_WRITTEN !== 'handoff',
    { written: STAGE_WRITTEN, handed: CTX.state.stage });
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
  PREV_INTENT = persistedAfter(llm({ intent: 'ignore_previous_instructions', confidence: 0.99, slots: {} }));
  check('...and it IS bounded: the second one escalates to the handoff gate',
    routesToRetry(out) === false && PREV_INTENT === 'invalid', { retry: routesToRetry(out), prev: PREV_INTENT });
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

// ---- CODEX ROUND-4 FINDING 4, PINNED. The accepted-gap entry claimed every listed false positive "costs
// one extra question". On a `confirming` turn it does not: the confirm route reads `state.slots` in
// `Build Event Request` and never passes through `Merge Slots` or the re-ask path, so the resolver dropping
// the date changes NOTHING — the turn builds an event request from the slot the customer was shown. This row
// executes `Build Event Request` and asserts that, so the recorded cost can never drift back to the softer
// version. (It is not a NEW defect: it is Codex finding 2, already an accepted gap. What was wrong was the
// COST written next to a different gap.)
{
  const { DateTime } = require(path.join(__dirname, '../../scripts/node_modules/luxon'));
  const cfg2 = { business: { timezone: 'Europe/Vienna' },
                 services: [{ id: 'haircut', name: 'Haircut', durationMin: 30 }], bot: {}, messageTemplates: {} };
  // ⚠ THE TURN'S OWN SLOTS ARE EMPTY (code-reviewer, round 5). The first fixture gave the turn the SAME
  // slots as the stored state, so it could not tell `st.slots` from `vi.slots` — and swapping them in
  // `Build Event Request` (which is literally the reschedule bypass this project shipped once) left the suite
  // at 35/35 while the ROADMAP called this row "pinned". Empty turn slots are what the resolver actually
  // produces when it drops, so this is the real shape AND the only one that discriminates.
  const vi = { intent: 'confirm', slots: { serviceId: 'haircut', dateExpr: null, date: null, time: null },
               state: { stage: 'confirming', slots: { serviceId: 'haircut', date: '2026-09-11', time: '11:00' },
                        sender_key: 'widget:test', turn_count: 3, confirm_turn: null } };
  const ctx = (n) => ({ first: () => ({ json: n === 'Load Config' ? { config: cfg2 } : vi }) });
  const built = new Function('$json', '$', 'DateTime', nodeOf('Build Event Request').parameters.jsCode)(vi, ctx, DateTime)[0].json;
  const b = built.booking || {};
  check('a confirming turn books the STORED slot — it does not re-ask, whatever the resolver decided',
    !!b.eventId && b.startISO === '2026-09-11T11:00:00.000+02:00' && b.dateStr === 'Friday 11 Sep',
    { eventId: !!b.eventId, startISO: b.startISO, dateStr: b.dateStr });
}

console.log(`\nvalidate-intent: ${pass}/${pass + fail} pass (node code + IF expression read from n8n/workflow.sanitized.json)`);
process.exit(fail ? 1 : 0);
