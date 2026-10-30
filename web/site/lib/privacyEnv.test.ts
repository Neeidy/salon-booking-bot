/**
 * The /privacy page's controller and contact come from build-time env (rulings R2h-1/2): unset or blank must give
 * null, which the page renders as its visible placeholder; a value is used as given, trimmed. Fake values only.
 *
 * Run: node --test lib/privacyEnv.test.ts   (Node strips the types; nothing is compiled)
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { envValue } from './privacyEnv.ts';

test('unset or blank → null (the page shows the placeholder)', () => {
  for (const v of [undefined, '', '   ', '\n\t']) assert.equal(envValue(v), null, JSON.stringify(v));
});

test('a value → that value, trimmed', () => {
  assert.equal(envValue('privacy@example.test'), 'privacy@example.test');
  assert.equal(envValue('  Test Controller \n'), 'Test Controller');
});
