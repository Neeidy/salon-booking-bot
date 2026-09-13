/**
 * The ONLY module that touches `OWNER_HMAC_SECRET` — the same discipline `airtable.ts` applies to the PAT,
 * for a sharper reason: the PAT can read, this secret can WRITE.
 *
 * WHY A SECRET AT ALL, WHEN THE PATH IS ALREADY BEHIND CLOUDFLARE ACCESS. Two layers answer two different
 * questions. Access answers *which machine* (measured in CP 6d-0: unauthenticated 403, service-token
 * through). The HMAC answers *which request*. If the service token ever leaks — it lives in a file on a
 * server, like every credential that has ever leaked — the signature is the only thing standing between a
 * stranger and `conversations.stage`. `ARCH-DEC:147` requires both and names the alternative it rejects:
 * the dashboard writing Airtable directly, which bypasses every guard built in CRT #8, CRT #3 and CP5e.
 *
 * ⚠ NO `NEXT_PUBLIC_` PREFIX, EVER. That prefix inlines the value into the browser bundle. An HMAC secret
 * a visitor can read makes the signature decorative — anyone could forge a release for any conversation.
 * This module is reached only from `app/api/release/route.ts`, a route handler, which is server-only by
 * construction. It is deliberately NOT a server action: a server action is imported BY a client component,
 * and `check-client-imports.cjs` walks imports without being able to tell a server action apart from
 * ordinary code. Choosing the route handler keeps that gate meaningful instead of teaching it to lie.
 *
 * ⚠ THE TARGET IS AN AIRTABLE RECORD ID, NOT A `sender_key`, and that was a correction made before any
 * of this ran. The first draft addressed the conversation by `sender_key` — which the dashboard DOES NOT
 * HAVE and must not have: E2 says a field that is not displayed is not fetched, and a full widget
 * `sender_key` is a BEARER CREDENTIAL (`security-secrets.md`), so `airtable.ts` deliberately fetches only
 * the masked form. Addressing by record id costs nothing, is already on every row, and cannot be replayed
 * into the widget lane the way a stolen `sender_key` can. The rule caught the design, not the other way
 * round.
 *
 * ⚠ AND THE GATE'S KNOWN LIMIT APPLIES HERE TOO: it sees IMPORTS, never PROPS. Passing anything from this
 * module into a client component as a prop would put it in the RSC payload and no gate would fire. Nothing
 * here is ever handed downward — the route returns a shape, never a secret.
 */
import { createHmac, timingSafeEqual } from 'node:crypto';

if (typeof globalThis === 'object' && 'window' in globalThis && 'document' in globalThis) {
  throw new Error(
    'web/dashboard/lib/ownerAction.ts was imported into a browser bundle. It holds OWNER_HMAC_SECRET, '
    + 'which authorises a WRITE to the live conversation store. Refusing to run.',
  );
}

/** A configuration fault, distinct from a transport fault — the same split `airtable.ts` draws. */
export class OwnerConfigError extends Error {
  constructor(message: string) { super(message); this.name = 'OwnerConfigError'; }
}

/** What the owner is allowed to ask for. ONE verb, and the engine enforces the same list independently. */
export const OWNER_ACTIONS = ['release_handoff'] as const;
export type OwnerAction = (typeof OWNER_ACTIONS)[number];

export interface ReleaseOutcome {
  ok: boolean;
  /** HTTP status from the engine, or 0 when the request never left. */
  status: number;
  /** A SHAPE for the screen — never an engine payload, never a credential. */
  reason: 'released' | 'not_locked' | 'not_found' | 'refused' | 'stale' | 'unreachable' | 'misconfigured';
}

function credentials() {
  const url = process.env.OWNER_ACTION_URL;
  const secret = process.env.OWNER_HMAC_SECRET;
  const cfId = process.env.CF_OWNER_ACCESS_CLIENT_ID;
  const cfSecret = process.env.CF_OWNER_ACCESS_CLIENT_SECRET;
  if (!url || !secret || !cfId || !cfSecret) {
    throw new OwnerConfigError(
      'OWNER_ACTION_URL, OWNER_HMAC_SECRET, CF_OWNER_ACCESS_CLIENT_ID and CF_OWNER_ACCESS_CLIENT_SECRET '
      + 'must all be set (web/dashboard/.env.local). Refusing to send an unsigned or unauthenticated '
      + 'write — a half-configured write path fails in the one direction that matters.',
    );
  }
  // Measured in CP 6d-0: these two names are NOT CF_ACCESS_CLIENT_ID/SECRET, which hold the /api token.
  return { url, secret, cfId, cfSecret };
}

/**
 * Sign and send. The body is serialised ONCE and both the signature and the request use that exact string —
 * signing a re-serialised object is how a signature silently stops matching (the engine reads the raw body).
 */
export async function releaseHandoff(recordId: string, messageId: string): Promise<ReleaseOutcome> {
  let creds;
  try { creds = credentials(); } catch { return { ok: false, status: 0, reason: 'misconfigured' }; }

  const body = JSON.stringify({
    action: 'release_handoff' satisfies OwnerAction,
    record_id: recordId,
    messageId,
    ts: Math.floor(Date.now() / 1000),
  });
  const signature = createHmac('sha256', creds.secret).update(body).digest('hex');

  let res: Response;
  try {
    res = await fetch(creds.url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Owner-Signature': signature,
        'CF-Access-Client-Id': creds.cfId,
        'CF-Access-Client-Secret': creds.cfSecret,
      },
      body,
      cache: 'no-store',
    });
  } catch (e) {
    // The full error goes to the server log; the screen gets a shape. A fetch TypeError can carry the URL,
    // and the URL carries the production host (`remote-operator.md`).
    console.error('[dashboard] owner action failed to send:', e);
    return { ok: false, status: 0, reason: 'unreachable' };
  }

  // ⚠ EVERY STATUS IS READ SEPARATELY AND SAYS A DIFFERENT TRUE THING. A single "something went wrong"
  // would be the silence `handoff.md` forbids — here the person left in the dark is the OWNER, staring at
  // a lock they cannot open and unable to tell a refusal from an outage.
  if (res.status === 200) return { ok: true, status: 200, reason: 'released' };
  if (res.status === 409) return { ok: false, status: 409, reason: 'not_locked' };
  if (res.status === 404) return { ok: false, status: 404, reason: 'not_found' };
  if (res.status === 401) return { ok: false, status: 401, reason: 'stale' };
  if (res.status === 403 || res.status === 400) return { ok: false, status: res.status, reason: 'refused' };
  console.error('[dashboard] owner action: unmapped engine status', res.status);
  return { ok: false, status: res.status, reason: 'unreachable' };
}

/** Exported for the unit test: the signature must be verifiable and the comparison constant-time. */
export function verifyForTest(body: string, signature: string, secret: string): boolean {
  const expected = createHmac('sha256', secret).update(body).digest('hex');
  const a = Buffer.from(expected, 'utf8');
  const b = Buffer.from(signature, 'utf8');
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}
