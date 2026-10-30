/**
 * A build-time env value for the /privacy page, or null when it is unset or blank (rulings R2h-1/2). It lives apart
 * from privacy.ts, which reads the client config, so lib/privacyEnv.test.ts can run it with plain Node.
 */
export function envValue(v: string | undefined): string | null {
  const t = (v ?? '').trim();
  return t === '' ? null : t;
}
