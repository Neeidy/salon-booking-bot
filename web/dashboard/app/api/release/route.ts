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
  let payload: { recordId?: unknown; messageId?: unknown };
  try {
    payload = await request.json();
  } catch {
    return Response.json({ ok: false, reason: 'bad_request' }, { status: 400 });
  }

  const recordId = typeof payload.recordId === 'string' ? payload.recordId.trim() : '';
  const messageId = typeof payload.messageId === 'string' ? payload.messageId.trim() : '';
  // Shape-check here as well as in the engine. Two independent checks of one precondition is not
  // duplication when they sit on opposite sides of a network boundary: this one keeps a malformed click
  // from spending an Airtable call, the engine's keeps a forged request from writing.
  if (!recordId || !messageId) {
    return Response.json({ ok: false, reason: 'bad_request' }, { status: 400 });
  }

  const outcome = await releaseHandoff(recordId, messageId);
  // The engine's status is REPORTED, not proxied: the body is ours, so nothing the engine says can reach
  // the browser unexamined.
  return Response.json(
    { ok: outcome.ok, reason: outcome.reason },
    { status: outcome.ok ? 200 : 200 },
  );
}
