/**
 * The owner's ONE write, as a route handler.
 *
 * WHY A ROUTE HANDLER RATHER THAN A SERVER ACTION: a server action is imported by the client component
 * that calls it, which puts a client→server import edge in the graph. `check-client-imports.cjs` walks
 * exactly that graph and cannot tell a server action from ordinary server code, so the choice was between
 * teaching the gate an exception and not creating the edge. Not creating it is cheaper and leaves the gate
 * able to mean what it says. The browser reaches this over `fetch`; no module crosses.
 *
 * The secret is never here either — `lib/ownerAction.ts` owns it, this file owns the HTTP shape.
 */
import { releaseHandoff } from '../../../lib/ownerAction.ts';

export const dynamic = 'force-dynamic';

export async function POST(request: Request): Promise<Response> {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ ok: false, reason: 'bad_request' }, { status: 400 });
  }
  // ⚠ `request.json()` on a body of literal `null` SUCCEEDS and yields null, so the destructuring below
  // threw a TypeError and the client saw an unhandled 500 instead of the structured refusal this handler
  // exists to give (Codex CRT #11). Valid JSON is not the same thing as a usable object.
  if (typeof payload !== 'object' || payload === null) {
    return Response.json({ ok: false, reason: 'bad_request' }, { status: 400 });
  }
  const p = payload as { recordId?: unknown; messageId?: unknown };

  const recordId = typeof p.recordId === 'string' ? p.recordId.trim() : '';
  const messageId = typeof p.messageId === 'string' ? p.messageId.trim() : '';
  // Shape-check here as well as in the engine. Two independent checks of one precondition is not
  // duplication when they sit on opposite sides of a network boundary: this one keeps a malformed click
  // from spending an Airtable call, the engine's keeps a forged request from writing.
  if (!recordId || !messageId) {
    return Response.json({ ok: false, reason: 'bad_request' }, { status: 400 });
  }

  const outcome = await releaseHandoff(recordId, messageId);
  // The engine's status is REPORTED, not proxied: the body is ours, so nothing the engine says reaches the
  // browser unexamined. ⚠ But it used to collapse every outcome onto HTTP 200 — `outcome.ok ? 200 : 200`,
  // which is the same number twice and was written as if it were a choice. A failure that arrives as 200
  // is invisible to anything that reads status codes: a proxy, a log, a future caller that is not this
  // component (Codex CRT #11). The reason still carries the detail; the status now carries the outcome.
  const status = outcome.ok ? 200
    : outcome.reason === 'misconfigured' ? 500
    : outcome.reason === 'unreachable' ? 502
    : outcome.status >= 400 ? outcome.status
    : 400;
  return Response.json(
    { ok: outcome.ok, reason: outcome.reason, ...(outcome.degraded ? { degraded: outcome.degraded } : {}) },
    { status },
  );
}
