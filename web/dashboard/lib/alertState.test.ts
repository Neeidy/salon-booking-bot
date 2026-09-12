/**
 * The three D9 states, asserted — including the one that matters most: an empty class must NEVER
 * render as good news. The row SHAPES come from the live base as it stood on 2026-09-12; the rows
 * themselves were drill residue and have since been deleted, so nothing here should be read as a
 * measurement of customer behaviour.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { alertState, alertLabel, triageRank } from './alertState.ts';

const T = (min: number) => new Date(Date.UTC(2026, 8, 12, 12, 0, 0) + min * 60_000).toISOString();

test('delivered and current → notified, and the label states WHEN rather than "you are up to date"', () => {
  const s = alertState('handoff', T(0), T(5));
  assert.equal(s.kind, 'notified');
  assert.match(alertLabel(s), /last notified .* — handoff/);
  // The wording must not promise currency: inside the 30-minute throttle window a LATER event can be
  // suppressed, so the only honest statement is the time of the last delivery (code-reviewer A2).
  assert.doesNotMatch(alertLabel(s), /^notified — /);
});

test('EMPTY class → unconfirmed, and the words never say "no alert"', () => {
  for (const empty of ['', '   ', undefined, null]) {
    const s = alertState(empty, T(0), T(0));
    assert.equal(s.kind, 'unconfirmed');
    const label = alertLabel(s);
    assert.match(label, /NOT confirmed/);
    // The failure this module exists to prevent: "no alert" reads as "nothing was wrong".
    assert.doesNotMatch(label, /no alert/i);
    assert.doesNotMatch(label, /none/i);
  }
});

test('a class with NO delivery timestamp is also unconfirmed — a class alone is not a delivery', () => {
  assert.equal(alertState('handoff', '', T(0)).kind, 'unconfirmed');
  assert.equal(alertState('handoff', undefined, T(0)).kind, 'unconfirmed');
  assert.equal(alertState('handoff', 'not-a-date', T(0)).kind, 'unconfirmed');
});

test('throttled: the alert predates the conversation by more than the throttle window → stale', () => {
  const s = alertState('handoff', T(0), T(45));
  assert.equal(s.kind, 'stale');
  assert.match(alertLabel(s), /last notified 45 min before/);
  // It must NOT claim the owner is up to date.
  assert.doesNotMatch(alertLabel(s), /^notified —/);
});

test('the 30-minute boundary is compared before rounding, and 30 itself is stale', () => {
  assert.equal(alertState('handoff', T(0), T(29)).kind, 'notified');
  assert.equal(alertState('handoff', T(0), T(30)).kind, 'stale');       // the boundary itself
  assert.equal(alertState('handoff', T(0), T(29.6)).kind, 'notified');  // rounds to 30, is NOT stale
  assert.equal(alertState('handoff', T(0), T(31)).kind, 'stale');
});

test('an alert NEWER than the conversation is current, not negatively stale', () => {
  const s = alertState('handoff', T(10), T(0));
  assert.equal(s.kind, 'notified');
});

test('an unparseable conversation timestamp degrades to notified, never to a false staleness claim', () => {
  // We know the alert was delivered; we do not know the conversation's clock. Inventing "stale" from
  // a missing value would be the same class of lie in the opposite direction.
  assert.equal(alertState('handoff', T(0), 'nonsense').kind, 'notified');
});

test('triage puts the rows nobody can prove were delivered at the TOP', () => {
  const rows = [
    alertState('handoff', T(0), T(5)),      // notified
    alertState('', T(0), T(0)),             // unconfirmed
    alertState('handoff', T(0), T(90)),     // stale
  ].sort((a, b) => triageRank(a) - triageRank(b));
  assert.deepEqual(rows.map((r) => r.kind), ['unconfirmed', 'stale', 'notified']);
});

test('a delivered-but-throttled event still renders as notified — the known limit, pinned', () => {
  // Inside the window a second event is suppressed and nothing in Airtable records it. The label must
  // therefore not claim the owner knows about the LATEST event — only when the last delivery was.
  // This is the module's honest boundary, asserted so nobody "improves" the wording back.
  const s = alertState('handoff_lock', T(0), T(20));
  assert.equal(s.kind, 'notified');
  assert.doesNotMatch(alertLabel(s), /up to date|current|all clear/i);
});
