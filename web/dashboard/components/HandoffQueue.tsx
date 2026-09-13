/**
 * D9 · D10 · D12 — the handoff queue. The dashboard's actual job: the conversations where the bot
 * stopped and a human has to take over.
 *
 * SERVER COMPONENT, deliberately and permanently. It renders `recent_messages` — the customer's own
 * words — and a masked sender. Handing either to a client component would put it in the RSC payload,
 * i.e. in the page source. See the note at the top of app/page.tsx; there is no gate that catches it,
 * so the rule lives next to the code that would break it.
 *
 * THE ONE THING THIS PANEL MUST NOT DO is render an empty `last_alert_class` as good news. Empty means
 * "we cannot show that the owner was told" — the field is written only after a Telegram send succeeds
 * — and it covers both "no alert was ever raised" and "an alert was raised and never arrived". Those
 * rows sort FIRST. See lib/alertState.ts, where the three states and their wording live together.
 */
import type { Page } from '../lib/airtable.ts';
import type { HandoffRow } from '../lib/types.ts';
import { alertState, alertLabel, triageRank } from '../lib/alertState.ts';
import { maskFreeText, maskSenderKey, assertMasked } from '../lib/mask.ts';
import { ReleaseButton } from './ReleaseButton.tsx';

/**
 * The customer's own words, masked. Wrapped because the per-row guard used to cover only the SENDER
 * while the comment beside it claimed the rule for every value on the row (`code-reviewer` #9) —
 * `recent_messages` is unbounded customer text and was rendered through a bare `assertMasked`.
 * A 300k-input fuzz found no throw today; that is a reason to keep the call, not a reason to leave
 * it unguarded. Failing here blanks one line, not the board.
 */
function safeText(raw: string | undefined): string {
  try { return assertMasked(maskFreeText(raw, 160), 'conversation text'); }
  catch { return '— (message text withheld: it did not pass the masking check)'; }
}

function waitedFor(lastUpdated: string | undefined): string {
  const t = Date.parse(lastUpdated ?? '');
  if (!Number.isFinite(t)) return 'unknown';
  const mins = Math.round((Date.now() - t) / 60_000);
  if (mins < 60) return `${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h`;
  return `${Math.round(hours / 24)} days`;
}

export function HandoffQueue({ page }: { page: Page<HandoffRow> }) {
  const rows = [...page.rows].sort((a, b) => {
    const ra = triageRank(alertState(a.last_alert_class, a.last_alert_at, a.last_updated));
    const rb = triageRank(alertState(b.last_alert_class, b.last_alert_at, b.last_updated));
    if (ra !== rb) return ra - rb;
    // An unparseable timestamp made this return NaN, which is an INCONSISTENT comparator (a sort can
    // then order neither way); such rows sink to the bottom instead.
    const ta = Date.parse(a.last_updated ?? '');
    const tb = Date.parse(b.last_updated ?? '');
    return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
  });

  // K1 (code-reviewer, 2026-09-12): `assertMasked` throwing inside the row map took the WHOLE PAGE
  // down. The throw happened during render, OUTSIDE app/page.tsx's try (which only wraps the reads),
  // and there WAS no error boundary at the time — `app/error.tsx` was added in this same round and is
  // what stops a render throw reaching Next's generic crash page. Corrected in place rather than
  // annotated beside (`governance-sync.md` §6): the sentence was true when written and this round is
  // what made it false. The per-row catch below is still the primary control; the boundary is the net
  // under it — so one WhatsApp row in the queue used to mean the owner saw Next's
  // generic crash page instead of appointments, leads and spend. It was measured against the shape
  // the engine writes (`whatsapp:+43…`) at a time when the Airtable formula truncated a phone-shaped
  // sender from the wrong end. THAT FORMULA HAS SINCE BEEN CORRECTED and verified over a 100-row
  // sample (airtable.ts). The catch stays anyway: it is not a workaround for one known defect, it is
  // the rule that a value which fails the render-time check is never rendered — and the formula lives
  // in Airtable, outside this repo, where nothing here can stop it changing again.
  //
  // A rejected value must not be rendered AND must not be silent, so the row survives with its sender
  // replaced and the count is shown. `code-style.md`: fail loud, never swallow — but failing loud is a
  // visible counter, not a blank dashboard.
  // ⚠ THE STORED VALUE IS NEVER RENDERED AS IT ARRIVES — corrected 2026-09-12 (`security-auditor` M1).
  // The first version rendered `sender_masked` raw and only re-masked in a catch, which meant the
  // re-masking was UNREACHABLE for the widget lane: a full `widget:w-<uuid>` has no 5-digit run and no
  // `@`, so `assertMasked` passes it and a BEARER CREDENTIAL (`security-secrets.md`) reached the
  // screen with the counter reading zero. Measured over 200k generated keys: the check caught 47% of
  // them, i.e. it was never the control here. `maskSenderKey` is idempotent, so applying it to every
  // row costs a correctly-masked value nothing and closes the lane that mattered.
  //
  // `flagged` is now a real signal rather than a crash counter: a value the formula masked properly
  // re-masks to ITSELF, so any difference means Airtable handed us more than a mask. That is the
  // condition worth telling the owner about, and it is detectable without trusting `assertMasked`.
  // ⚠ TWO DIFFERENT EVENTS USED TO INCREMENT ONE COUNTER, so a single bad row in a one-row queue
  // reported "2 rows" and described both events with the sentence that fitted only one of them
  // (`code-reviewer`, third pass). They are counted separately now because they mean different things:
  // `remasked` = Airtable handed us more than a mask, and we fixed it here (the row is still shown);
  // `withheld` = even our own output failed the check, so the row is shown WITHOUT its sender.
  let remaskedCount = 0;
  let withheld = 0;
  const prepared = rows.map((r) => {
    const stored = (r.sender_masked ?? '').trim();
    const remasked = stored ? maskSenderKey(stored) : '—';
    let who: string;
    // K1 stays: a throw must not take the page down. It now guards our OWN output, which is the only
    // thing that reaches the screen.
    try {
      who = assertMasked(remasked, 'sender');
      if (stored && remasked !== stored) remaskedCount++;
    } catch {
      withheld++;
      who = '— (masked value rejected)';
    }
    return { row: r, who };
  });

  return (
    <section className="panel queue" aria-labelledby="queue-h">
      <div className="q-head">
        <h2 id="queue-h">Waiting for you</h2>
        {page.truncated && (
          // Not decoration. Airtable's page size caps at 100 and the budget allows one request, so a
          // long queue cannot be shown whole. Saying "the first 100 of more" is the difference between
          // a short list and a false one.
          <span className="tech">showing the first {rows.length} — there are more</span>
        )}
      </div>

      {rows.length === 0 ? (
        // D12. Distinct from every other empty state on this page on purpose: an empty queue is the
        // GOOD outcome, and it should read as one.
        <p className="release">Nothing is waiting. Every conversation the bot could not finish has been picked up.</p>
      ) : (
        <ul className="q-msgs">
          {prepared.map(({ row: r, who }) => {
            const st = alertState(r.last_alert_class, r.last_alert_at, r.last_updated);
            return (
              <li key={r.id} className={st.kind === 'unconfirmed' ? 'row kpi-alert' : 'row'}>
                <div className="q-head">
                  <strong>{who}</strong>
                  <span className="sw">{alertLabel(st)}</span>
                </div>
                <p>{safeText(r.recent_messages)}</p>
                <span className="tech">
                  waiting {waitedFor(r.last_updated)} · {r.turn_count ?? 0} turns
                  {r.last_intent ? ` · last read as "${r.last_intent}"` : ''}
                </span>
                {/* D11 — the phase's ONE write. Props are a record id and the already-masked label: no
                    sender_key, no message text crosses into the client component (CRT #10b, by hand). */}
                <ReleaseButton recordId={r.id} label={who} />
              </li>
            );
          })}
        </ul>
      )}

      {remaskedCount > 0 && (
        // This counter should read zero. ⚠ It used to add "or a row predates the fix", which cannot
        // happen: `sender_masked` is a FORMULA field — Airtable recomputes it on every read, so it has
        // no history and no old rows. What a non-zero value actually means is that the formula in
        // Airtable no longer masks every channel it receives (`code-reviewer`, third pass).
        <p className="tech">
          {remaskedCount} row{remaskedCount === 1 ? '' : 's'}: the sender stored by Airtable carried
          more than a mask and was re-masked here before being shown. Expected to be none — the
          `sender_masked` formula needs a branch for the channel these rows arrived on.
        </p>
      )}
      {withheld > 0 && (
        <p className="tech">
          {withheld} row{withheld === 1 ? '' : 's'}: the sender could not be shown at all — even this
          board's own masking did not pass the render-time check. The conversation is still listed.
        </p>
      )}

      {/* D11 landed in CP 6d-1. The sentence that stood here — "this board is read-only today" — was
          correct while it was true and is removed rather than annotated (`governance-sync.md` §6). Its
          reasoning is worth keeping: an inert control that LOOKS live is worse than an absent one, which
          is exactly why the button below is wired to a real signed write before being shown at all. */}
    </section>
  );
}
