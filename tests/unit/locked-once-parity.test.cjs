/**
 * THE DRIFT GUARD FOR A DELIBERATE SECOND COPY.
 *
 * `web/snippet/src/lockedOnce.ts` and `web/site/lib/lockedOnce.ts` implement the same rule twice, on
 * purpose: the two surfaces draw the same conversation with different machinery and `@salon/shared`
 * holds no UI state. `contract-integrity.md` permits a hand-mirrored copy ONLY with a drift guard
 * committed in the same change — this is that guard, and it is the only thing standing between "two
 * implementations" and "two behaviours", which is what the repo had before CP 6c-3: the snippet showed
 * the handoff line once and the site repeated it on every message.
 *
 * ⚠ IT MUST FAIL IN BOTH DIRECTIONS, or the mirror is just a copy with a comment. Changing the snippet
 * alone is red; changing the site alone is red. Proven by mutation, both ways, in the same round it was
 * written (`reporting.md`: the claim is written AFTER the mutant dies).
 *
 * The suite is NOT "do they agree today" — two identical constant functions would also agree. It drives
 * both over a SEQUENCE of replies and compares the transcripts, so a difference in WHEN the flag is set
 * shows up, not only a difference in the branch.
 *
 * Run: node tests/unit/locked-once-parity.test.cjs
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const ROOT = join(__dirname, '..', '..');

/**
 * Both copies are TypeScript with a single exported FUNCTION plus one types-only `export interface`, which
 * the loader strips, and no imports — so they are loaded by
 * stripping the types textually rather than by adding a compiler to this suite. The extraction is
 * asserted below: if a copy ever grows an import or a second export, the load fails loudly instead of
 * silently testing something else.
 */
function load(relPath) {
  const src = readFileSync(join(ROOT, relPath), 'utf8');
  assert.ok(!/^\s*import\s/m.test(src), `${relPath} gained an import — this loader only handles a pure module`);
  const exports = src.match(/^export function (\w+)/gm) || [];
  assert.equal(exports.length, 1, `${relPath} must export exactly one function, found ${exports.length}`);
  assert.ok(/^export function lockLineDecision/m.test(src), `${relPath} no longer exports lockLineDecision`);
  const js = src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
    .replace(/export interface [\s\S]*?\n\}/g, '')          // the LockDecision shape is types only
    .replace(/export function/g, 'function')
    .replace(/\n\s*reply: \{[^}]*\},\n\s*alreadyShown: boolean,\n\): LockDecision/g, 'reply, alreadyShown)');
  assert.ok(!/:\s*(boolean|string|LockDecision)/.test(js),
    `${relPath} has a type annotation this loader does not strip — update the loader, do not weaken the test`);
  // eslint-disable-next-line no-new-func
  return new Function(`${js}; return lockLineDecision;`)();
}

const snippet = load('web/snippet/src/lockedOnce.ts');
const site = load('web/site/lib/lockedOnce.ts');

/** Drives one implementation over a sequence and returns what the visitor would SEE. */
function transcript(fn, replies) {
  let shown = false;
  const drawn = [];
  for (const r of replies) {
    // BOTH decisions come from the function under test. The caller no longer re-derives the flag, so a
    // copy that draws correctly but burns the one-shot at the wrong moment is visible here too.
    const d = fn(r, shown);
    shown = d.nowShown;
    if (d.draw) drawn.push(r.id);
  }
  return drawn.join(',');
}

const SEQUENCES = {
  'three locks in a row — the defect that started this': [
    { id: 'L1', locked: true }, { id: 'L2', locked: true }, { id: 'L3', locked: true },
  ],
  'a normal reply AFTER a lock must still be drawn': [
    { id: 'L1', locked: true }, { id: 'N1' }, { id: 'L2', locked: true }, { id: 'N2' },
  ],
  'no lock at all': [{ id: 'N1' }, { id: 'N2' }, { id: 'N3' }],
  'lock flag absent vs false vs true': [
    { id: 'A' }, { id: 'B', locked: false }, { id: 'C', locked: true }, { id: 'D', locked: true },
  ],
  'a lock as the very first reply': [{ id: 'L1', locked: true }, { id: 'L2', locked: true }],
  // security-auditor M2: chatClient's unmapped-response branch returns kind:'system' AND carries
  // `locked` through. Suppressing it left the visitor in silence on every message after the first.
  'a SYSTEM line carrying locked is never suppressed': [
    { id: 'S1', kind: 'system', locked: true }, { id: 'S2', kind: 'system', locked: true },
  ],
  // …and it must not burn the one-shot either, or the first REAL lock line is the one that vanishes.
  'a system+locked line does not consume the one-shot': [
    { id: 'S1', kind: 'system', locked: true }, { id: 'L1', locked: true }, { id: 'L2', locked: true },
  ],
};

for (const [name, replies] of Object.entries(SEQUENCES)) {
  test(`parity: ${name}`, () => {
    assert.equal(transcript(snippet, replies), transcript(site, replies),
      'the two copies of the handoff-lock rule have DRIFTED');
  });
}

test('the expected transcripts, pinned — parity alone would pass for two identically WRONG copies', () => {
  // Agreement is necessary and not sufficient: two copies that both showed the line three times would
  // agree perfectly. The behaviour itself is asserted here, once, against the snippet copy.
  assert.equal(transcript(snippet, SEQUENCES['three locks in a row — the defect that started this']), 'L1');
  assert.equal(transcript(snippet, SEQUENCES['a normal reply AFTER a lock must still be drawn']), 'L1,N1,N2');
  assert.equal(transcript(snippet, SEQUENCES['no lock at all']), 'N1,N2,N3');
  assert.equal(transcript(snippet, SEQUENCES['lock flag absent vs false vs true']), 'A,B,C');
  assert.equal(transcript(snippet, SEQUENCES['a SYSTEM line carrying locked is never suppressed']), 'S1,S2');
  assert.equal(transcript(snippet, SEQUENCES['a system+locked line does not consume the one-shot']), 'S1,L1');
});
