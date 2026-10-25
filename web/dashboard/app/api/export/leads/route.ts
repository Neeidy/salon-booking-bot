/**
 * GET the owner's leads as a masked CSV. Takes NO input: no query string, no body, no path parameter is read.
 * Answers 404 unless DASHBOARD_EXPORT_ENABLED=1: a RELEASE gate until the Phase 7-2 Codex audit, not a security
 * boundary. Who may download is decided by Cloudflare Access in front of the whole dashboard host; this handler
 * does not check it. Everything else, and why, is in lib/exportCsv.ts.
 */
import { readAppointments, readLeads, resetBudget } from '../../../../lib/store.ts';
import { shopConfig } from '../../../../lib/shopConfig.ts';
import { exportResponse } from '../../../../lib/exportCsv.ts';

export const dynamic = 'force-dynamic';

export async function GET(): Promise<Response> {
  return exportResponse('leads', {
    env: process.env,
    readAppointments,
    readLeads,
    resetBudget,
    timezone: () => shopConfig().timezone,
    now: () => Date.now(),
  });
}
