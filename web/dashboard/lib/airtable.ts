/**
 * The ONLY module in this repo that holds the Airtable PAT.
 *
 * CRT #10 is four claims, and this file is where three of them are either true or false:
 *   1. the PAT never reaches a browser        — it is read from process.env here and nowhere else;
 *   2. the PAT is READ-ONLY                   — measured, not configured: 2026-09-12, a read returns
 *                                               200 and both write shapes return 403 (ROADMAP, K-2);
 *   3. this is NOT a general proxy            — see below, it is the whole design of this file;
 *   4. no dashboard/PII code ships to Vercel  — that is `web/`'s two-app split, not this file.
 *
 * WHY IT IS NOT A PROXY, stated as a rule and not as an intention: **no exported function takes a
 * table, a filter, a field list, a sort or a record id from its caller.** There are exactly four
 * reads, each one hard-coded, each returning a narrow shape. A caller cannot ask this module for
 * something the dashboard does not already display. The moment a function grows a parameter that
 * reaches the query, this file becomes an authenticated Airtable proxy sitting behind Cloudflare
 * Access, and CRT #10's third line stops being true.
 *
 * FIELD SELECTION IS A SECURITY CONTROL, NOT AN OPTIMISATION (Yigitcan's addition E2). Masking is the
 * SECOND layer; the first is never fetching the value. Every query below sends an explicit `fields[]`
 * list, and the binding rule is Yigitcan's own wording: **a displayed field is fetched, a field that
 * is not displayed is not fetched.** `conversations.computed_reply`, `cancel_target_id` and
 * `appointments.gcal_event_id` are therefore not in the response, not in this process's memory, and
 * cannot leak from anywhere downstream.
 * ⚠ **This paragraph used to name `recent_messages` as the example of a field that is never fetched,
 * and that was FALSE — it is fetched (see FIELDS below) and rendered by `HandoffQueue`, because the
 * handoff queue's entire job is to show the owner what the customer said.** The sentence survived the
 * narrowing of this claim three sections down and was corrected here on 2026-09-12 (`code-reviewer`
 * #3). Recorded rather than silently swapped, because this file's own rule is that a FALSE statement
 * about a security control is worse than a loose one: the next reader treats the list as proven. What
 * protects `recent_messages` is not non-fetching — it is `maskFreeText` plus the SERVER-component
 * boundary, and those are a different, weaker guarantee than "never left Airtable".
 *
 * THE AIRTABLE BUDGET IS SHARED WITH THE BOT AND IT IS BINDING: 5 requests/sec/base, un-raisable, and
 * an overrun costs a 30-second penalty applied base-wide — the dashboard would knock the production
 * bot over. So: ONE bulk read per table, four per page, no per-row request, no auto-refresh. The
 * counter here is a tripwire, NOT the measurement: it only sees calls that pass through it, which is
 * precisely the blind spot this project keeps finding. The real number is measured at the NETWORK
 * layer and compared with this counter; a disagreement means the counter is blind, and that
 * disagreement is the finding (Yigitcan's addition E1).
 */
import type { Appointment, Lead, HandoffRow, SpendRow } from './types.ts';

const API = 'https://api.airtable.com/v0';

/** Server-only. A RUNTIME guard, the same shape `@salon/shared/config` carries and for the same reason. */
if (typeof globalThis === 'object' && 'window' in globalThis && 'document' in globalThis) {
  throw new Error(
    'web/dashboard/lib/airtable.ts was imported into a browser bundle. It holds the Airtable PAT. '
    + 'The build-time boundary is scripts/check-client-imports.cjs; this throw is the runtime half.',
  );
}

/**
 * FIELD LISTS — the security control.
 *
 * The rule, stated precisely after `code-reviewer` found the loose version: **a PII field is fetched
 * only if it is rendered.** Non-PII context fields may be in a list without being drawn — `end_utc`,
 * `reminder_sent`, `created_at`, `leads.created_at` and `conversations.stage` are fetched and not
 * currently rendered (`stage` drives the server-side filter). The earlier wording, "exactly what its
 * panel RENDERS", was false about those five, and a false statement about a security control is worse
 * than a loose one: the next reader treats the list as proven and adds a PII field to it.
 *
 * THE RULE (Yigitcan, 2026-09-12): **a field that is DISPLAYED is fetched; a field that is not
 * displayed is not fetched; and no PII crosses a client-component boundary.** E2 was never "do not
 * fetch PII" — it was "do not fetch PII you do not show". `recent_messages` IS shown (D9 is the
 * handoff queue, and those lines are what let the owner take the conversation over), so it is
 * fetched, and the protection moves to the boundary: the panel that renders it stays a SERVER
 * component, so the text reaches the page behind Cloudflare Access and never the RSC payload.
 *
 * ⚠ One deliberate omission, named so nobody "restores" it as a convenience:
 *   - `appointments.gcal_event_id` — `security-secrets.md` measured it to be a hex ENCODING of
 *     `sender_key|date|time|serviceId`, not a hash, so a full one reverses to a bearer credential
 *     with one command. D4 lists it; it is not fetched.
 *
 * `sender_key` is NO LONGER FETCHED. The Airtable formula field `sender_masked` holds the masked form,
 * so for most rows the full value — a BEARER credential on the widget lane, not merely PII — never
 * leaves Airtable at all. Not fetching beats masking: E2's own logic, applied one level up.
 *
 * ⚠ THE FORMULA WAS WRONG WHEN THIS FILE WAS FIRST WRITTEN, AND IS NOW FIXED. Recorded rather than
 * deleted, because the defect is the reusable part: `LEFT({sender_key}, 16) & "…"` returned the WHOLE
 * key whenever the key was 16 characters or shorter — 91 of the 592 rows then in the table, 15% —
 * while appending an ellipsis that claimed truncation; and for a `whatsapp:` key it truncated from
 * the identifying END, the opposite of what `maskPhone()` does on purpose. The suggestion had come
 * from a brief and had never been run against the data.
 * The corrected formula branches on the channel and uses `MIN(16, LEN - 4)`, so at least four
 * characters are always removed. VERIFIED 2026-09-12 over a 100-row sample, comparing lengths only
 * and printing no values: **zero rows carry the full key, minimum four characters removed.**
 */
const FIELDS = {
  appointments: ['start_utc', 'end_utc', 'service', 'channel', 'status', 'reminded', 'reminder_sent',
                 'created_at', 'customer_name'],
  leads: ['name', 'phone', 'source', 'status', 'created_at'],
  conversations: ['sender_masked', 'stage', 'last_alert_class', 'last_alert_at', 'last_intent',
                  'turn_count', 'last_updated', 'recent_messages'],
  bot_metrics: ['period_key', 'cost_usd', 'updated_at'],
} as const;

export class AirtableError extends Error {
  // Written out rather than as TypeScript parameter properties: Node's strip-only type removal does
  // NOT support them (`ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`), so the shorthand makes this module
  // unrunnable by `node --test` and by any drill — which is how this was found, by running it. Next's
  // SWC would have compiled it happily, and the file would have been untestable outside Next.
  readonly table: string;
  readonly status: number;
  readonly retryable: boolean;
  constructor(table: string, status: number, retryable: boolean) {
    super(`Airtable ${table}: HTTP ${status}`);
    this.name = 'AirtableError';
    this.table = table;
    this.status = status;
    this.retryable = retryable;
  }
}

/**
 * A tripwire, and its scope is narrower than it looks — stated because `code-reviewer` measured it.
 *
 * The counter is MODULE-level, so it is per-PROCESS, not per-render. Two browsers loading the page at
 * the same instant each reset it and each count to 4, while EIGHT requests leave the process: measured,
 * the counter stayed silent. It protects against one render fanning out, which is the mistake it was
 * written for; it cannot see concurrency, and the real limit (5 req/s shared with the bot) is a
 * concurrency limit. A per-render counter needs AsyncLocalStorage and a real brake needs a sliding
 * window — both are named, neither is here.
 *
 * It is also only safe because `page.tsx` issues all four reads inside ONE synchronous block before
 * awaiting: there is no `await` between `resetBudget()` and the last `readX()` call. Insert one — a
 * Suspense boundary, a "fetch the queue first" refactor — and two concurrent renders will each throw
 * "5 requests in one render", which would be a FALSE statement about what happened.
 */
let requestsThisRender = 0;
export function resetBudget(): void { requestsThisRender = 0; }
export function budgetUsed(): number { return requestsThisRender; }
export const BUDGET_PER_PAGE = 4;

/**
 * A configuration fault, distinct from a transport fault ON PURPOSE (`code-reviewer` #6, 2026-09-12).
 * `credentials()` throws before any request is made, so reporting it as "the data service did not
 * answer" blames a service that was never contacted and sends the operator to the wrong place. The
 * page only ever sees `e.name`, so the NAME is the whole signal — which is why this class exists
 * rather than a flag on the message.
 */
export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

function credentials(): { pat: string; baseId: string } {
  const pat = process.env.AIRTABLE_PAT_READONLY;
  const baseId = process.env.AIRTABLE_BASE_ID;
  // Fail loudly and EARLY. A dashboard that renders empty panels because a variable is missing looks
  // exactly like a dashboard whose shop has no bookings, and that is the worst failure available here.
  if (!pat || !baseId) {
    throw new ConfigError(
      'AIRTABLE_PAT_READONLY and AIRTABLE_BASE_ID must both be set (web/dashboard/.env.local). '
      + 'Refusing to render: an unconfigured dashboard and an empty one look identical.',
    );
  }
  if (!baseId.startsWith('app') || baseId.length !== 17) {
    // Measured 2026-09-12: a base id pasted without its `app` prefix returns 404 on every read, which
    // reads as a code defect rather than as a typo. Shape-check it once, here, with a useful message.
    throw new ConfigError(
      `AIRTABLE_BASE_ID does not look like a base id (expected "app" + 14 characters, got ${baseId.length}). `
      + 'Every read would return 404 and look like a bug in this code.',
    );
  }
  return { pat, baseId };
}

/**
 * The one place a request is made. Private on purpose: `table` and `fields` come from the constants
 * above, never from a caller — that is what keeps this module from being a proxy.
 */
export interface Page<T> {
  rows: T[];
  /**
   * TRUE when Airtable said there is another page and we did not fetch it.
   *
   * ⚠ This flag is not a nicety, it is the difference between a short list and a LIE. Measured
   * 2026-09-12: `appointments` held more than 100 rows, and so did `conversations` filtered to
   * `stage='handoff'` — the dashboard's own main panel. (The handoff backlog has since been deleted;
   * the appointments ceiling is structural and stays.) Airtable's page size maxes at 100, and the
   * binding budget is ONE request per table (5 req/s shared with the bot, a 30-second base-wide
   * penalty on overrun), so "one read" and "all rows" cannot both hold. The resolution is not to
   * paginate quietly; it is to render "the first 100 of more" and say so. A dashboard that shows 100
   * of 340 appointments with no mark is worse than one that shows none.
   */
  truncated: boolean;
}

async function readTable(table: keyof typeof FIELDS, extra?: URLSearchParams): Promise<Page<Record<string, unknown>>> {
  const { pat, baseId } = credentials();
  if (requestsThisRender >= BUDGET_PER_PAGE) {
    throw new Error(
      `Airtable budget exceeded: ${requestsThisRender + 1} requests in one render, cap is ${BUDGET_PER_PAGE}. `
      + 'The base allows 5 req/s SHARED WITH THE BOT, and an overrun penalises the whole base for 30 '
      + 'seconds — a dashboard render must never be able to knock the bot over.',
    );
  }
  requestsThisRender++;

  const q = new URLSearchParams(extra);
  for (const f of FIELDS[table]) q.append('fields[]', f);
  q.set('pageSize', '100');

  const res = await fetch(`${API}/${baseId}/${table}?${q}`, {
    headers: { Authorization: `Bearer ${pat}` },
    cache: 'no-store',
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) {
    // 429 is the one the owner must be told about in the shop's own terms — D19 says "the bot has
    // priority", not "something went wrong".
    throw new AirtableError(table, res.status, res.status === 429 || res.status >= 500);
  }
  const body = (await res.json()) as {
    records?: Array<{ id: string; fields: Record<string, unknown> }>;
    offset?: string;
  };
  return {
    rows: (body.records ?? []).map((r) => ({ id: r.id, ...r.fields })),
    truncated: typeof body.offset === 'string',
  };
}

/**
 * WHY EVERY READ CARRIES A SERVER-SIDE FILTER (Yigitcan's correction A, 2026-09-12).
 *
 * What was measured on 2026-09-12, and what is true NOW, are two different sentences — so both are
 * here. THEN: `appointments` already held more than 100 rows and `conversations` at `stage='handoff'`
 * held 215. NOW: those 215 were all drill residue and were deleted, so the handoff queue is empty.
 * The filters are NOT justified by either number. Fetching everything and showing the first hundred is
 * the WRONG fix at any table size — same request count, wrong data, and the owner cannot tell which
 * hundred they got. The filter belongs on Airtable's side: the request count is identical and the rows
 * are the ones the screen is actually for. A guard that is only correct while a table is large is a
 * guard that quietly stops being correct.
 *
 * The `truncated` flag stays, because a filter can still overflow — it is the second line, not the
 * first. Each filter below is a CONSTANT expression (it reads the clock, never a caller), so this
 * module still cannot be asked for something the dashboard does not display.
 */

/**
 * D1 today · D2 upcoming. ⚠ This was 30 days with an ASCENDING sort, and `code-reviewer` measured what
 * that does to a busy shop: the page size caps at 100, so ascending order returns the OLDEST hundred —
 * all of them in the past — and today and tomorrow sit on a second page that is never fetched. A shop
 * with 150 bookings was shown "No bookings today" and "Nothing booked ahead". The window is now what
 * the screen actually draws: yesterday onwards, ascending, so the first hundred ARE the next hundred.
 * Yesterday rather than today so a late-evening appointment is still visible the next morning.
 */
// Named as a LOOK-BACK, not a "window": it is the DATEADD offset below, and the range it opens is
// unbounded forward. Calling it a window invited the 30-day reading that this filter no longer has.
const APPOINTMENT_LOOKBACK_DAYS = 1;
/** D7 is a working list, not an archive. */
const LEAD_WINDOW_DAYS = 90;

export async function readAppointments(): Promise<Page<Appointment>> {
  const q = new URLSearchParams({
    filterByFormula: `IS_AFTER({start_utc}, DATEADD(TODAY(), -${APPOINTMENT_LOOKBACK_DAYS}, 'days'))`,
    'sort[0][field]': 'start_utc',
    'sort[0][direction]': 'asc',
  });
  return (await readTable('appointments', q)) as unknown as Page<Appointment>;
}
export async function readLeads(): Promise<Page<Lead>> {
  const q = new URLSearchParams({
    filterByFormula: `IS_AFTER({created_at}, DATEADD(TODAY(), -${LEAD_WINDOW_DAYS}, 'days'))`,
    'sort[0][field]': 'created_at',
    'sort[0][direction]': 'desc',
  });
  return (await readTable('leads', q)) as unknown as Page<Lead>;
}
export async function readHandoffQueue(): Promise<Page<HandoffRow>> {
  // The ONLY filter in this file, and it is a constant: the queue is conversations stuck at `handoff`.
  // It is here rather than in a parameter for the reason at the top — a caller-supplied formula is an
  // authenticated query interface, which is the thing CRT #10 says this is not.
  // NOT date-filtered, and that is deliberate: a conversation locked in July is still locked, and
  // hiding it because it is old would be the dashboard telling the owner a queue is shorter than it
  // is. Sorted newest-first so the hundred that DO fit are the actionable ones, and `truncated` says
  // there are more. ⚠ The queue held 215 rows when this was written and holds ZERO now — every one of
  // them was drill residue and they were deleted on 2026-09-12 (docs/ROADMAP.md). The sort and the
  // truncation flag are not there because the queue is long today; they are there because nothing in
  // the engine clears a handoff lock, so it only ever grows until someone acts on it.
  const q = new URLSearchParams({
    filterByFormula: "{stage}='handoff'",
    'sort[0][field]': 'last_updated',
    'sort[0][direction]': 'desc',
  });
  return (await readTable('conversations', q)) as unknown as Page<HandoffRow>;
}
export async function readSpend(): Promise<Page<SpendRow>> {
  // D14 shows THIS period's spend against the cap. The engine buckets by UTC month (`Spend Gate`),
  // so the filter is that bucket — one row, not the whole history.
  const period = new Date().toISOString().slice(0, 7);
  const q = new URLSearchParams({ filterByFormula: `{period_key}='${period}'` });
  return (await readTable('bot_metrics', q)) as unknown as Page<SpendRow>;
}
