/**
 * Which sentence the release button shows for the route's answer — a pure function, so a test can drive it.
 * `ReleaseButton.tsx` is a client component and Node cannot load `.tsx`; the mapping lived inside it and was
 * therefore only ever checked by reading its source text. This module imports nothing and holds no secret, so
 * a client component may import it (`check-client-imports.cjs` walks it like any other).
 */
export interface RouteAnswer { ok?: boolean; reason?: string; degraded?: unknown }

export function screenReason(data: RouteAnswer): string {
  if (data.degraded === 'alert_undelivered') return 'released_no_alert';
  // ANY other degraded value is still a degraded release, and must not read as a plain one. The committed
  // engines still send `degraded:'marker_unwritten'` (the parked original, the live copy until the staged edit
  // is deployed, and the rollback path); a value this board has never heard of gets the same hedged line.
  if (data.degraded !== undefined && data.degraded !== null && data.degraded !== '') return 'released_degraded';
  return data.reason ?? 'unreachable';
}
