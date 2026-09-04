/**
 * Hero demo conversations — FOUR scenarios, rotated.
 *
 * THE RULE: every BOT line is engine-verbatim. Customer lines are mock and may be written freely.
 * Inventing bot copy is a logged defect class in this repo, so each bot line below is either
 *   (a) a config messageTemplates.* string with its placeholders filled the way the engine fills them, or
 *   (b) a reproduction of a LITERAL inside a named n8n Code node.
 * Case (b) is a derived copy of engine text, so it is guarded: scripts/check-hero-engine-text.cjs
 * asserts every shape below still exists in the committed workflow, and fails the build gate if the
 * engine's wording changes (.claude/rules/contract-integrity.md).
 *
 * Building the strings FROM CONFIG (rather than hardcoding "Haircut is €25.") is what makes the second
 * client's hero correct automatically: a shop with different services and hours gets its own numbers.
 */
import type { ClientConfig } from '@salon/shared/config';

export interface Bubble {
  from: 'bot' | 'user';
  text: string;
  stamp: string;
  /** Where a bot line comes from — rendered as an HTML comment for reviewers, never shown. */
  source?: string;
  confirm?: boolean;
  chips?: string[];
}
export interface Scenario { id: string; label: string; bubbles: Bubble[] }

const money = (s: { priceEUR?: number }) => (s.priceEUR != null ? `€${s.priceEUR}` : 'price on request');

/** `Answer FAQ` case 'hours' — reproduced literally, including the ' · ' joiner and final period. */
function hoursAnswer(cfg: ClientConfig): string {
  const days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
  const label: Record<string, string> = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' };
  const wh = (cfg.workingHours ?? {}) as Record<string, string[] | undefined>;
  return 'Opening hours — ' + days
    .map((d) => `${label[d]}: ${wh[d] && wh[d]!.length ? wh[d]!.join(', ') : 'closed'}`)
    .join(' · ') + '.';
}

const fill = (tpl: string, vars: Record<string, string>) =>
  tpl.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);

export function heroScenarios(cfg: ClientConfig): Scenario[] {
  const svc = cfg.services[0];                       // the demo books the first configured service
  const t = cfg.messageTemplates as Record<string, string>;
  // Sample slot. The ENGINE formats with Luxon 'cccc d LLL HH:mm' in the shop timezone; these are the
  // approved mockup's sample values, kept so the demo reads like a real Friday afternoon booking.
  const when = 'Friday 4 Sep 15:30';
  const date = 'Friday 4 Sep';
  const time = '15:30';

  return [
    {
      id: 'booking',
      label: 'Booking',
      bubbles: [
        { from: 'user', text: `Can I get a ${svc.name.toLowerCase()} Friday at 15:30?`, stamp: '14:02' },
        // W12 — literal in `Compute Availability`: `${svcName}, ${fmt} — shall I book it? (yes / no)`
        { from: 'bot', text: `${svc.name}, ${when} — shall I book it? (yes / no)`, stamp: '14:02',
          source: 'W12 · literal in Compute Availability', chips: ['yes', 'no'] },
        { from: 'user', text: 'yes', stamp: '14:03' },
        // W13 — messageTemplates.bookingConfirmed, filled in `Build Booked State`
        { from: 'bot', text: fill(t.bookingConfirmed, { service: svc.name, date, time }), stamp: '14:03',
          source: 'W13 · messageTemplates.bookingConfirmed', confirm: true },
      ],
    },
    {
      id: 'cancel',
      label: 'Cancelling',
      bubbles: [
        { from: 'user', text: `I need to cancel my ${svc.name.toLowerCase()}`, stamp: '09:11' },
        // W19 — literal in `Build Cancel-Confirm State` (single-booking variant: `multi` is '')
        { from: 'bot', text: `Cancel your ${svc.name} on ${when}? Reply "yes" to cancel, or anything else to keep it.`,
          stamp: '09:11', source: 'W19 · literal in Build Cancel-Confirm State', chips: ['yes', 'keep it'] },
        { from: 'user', text: 'yes', stamp: '09:12' },
        // W20 — messageTemplates.cancelDone, filled in `Build Cancelled State`
        { from: 'bot', text: fill(t.cancelDone, { service: svc.name, when }), stamp: '09:12',
          source: 'W20 · messageTemplates.cancelDone', confirm: true },
      ],
    },
    {
      id: 'faq',
      label: 'Questions',
      bubbles: [
        { from: 'user', text: `how much is a ${svc.name.toLowerCase()}?`, stamp: '18:40' },
        // W3 — `Answer FAQ` case 'price', single-service branch: `${one.name} is ${money(one)}.`
        { from: 'bot', text: `${svc.name} is ${money(svc)}.`, stamp: '18:40', source: "W3 · Answer FAQ case 'price'" },
        { from: 'user', text: 'and when are you open?', stamp: '18:40' },
        // W5 — `Answer FAQ` case 'hours'. One engine line; the design breaks it at the engine's own
        // ' · ' separators for readability — formatting only, every character preserved.
        { from: 'bot', text: hoursAnswer(cfg), stamp: '18:41', source: "W5 · Answer FAQ case 'hours'" },
      ],
    },
    {
      id: 'handoff',
      label: 'Over to a person',
      bubbles: [
        { from: 'user', text: "it's complicated — I'd rather explain to a person", stamp: '11:24' },
        // W44 — messageTemplates.handoff via `Mark Handoff` (200, writes stage='handoff').
        // This is the INTENT handoff. The infra-failure class reuses the same string but returns 5xx —
        // never present this bubble as "what you see when something breaks".
        { from: 'bot', text: t.handoff, stamp: '11:24', source: 'W44 · messageTemplates.handoff' },
        { from: 'user', text: 'hello? is anyone there?', stamp: '11:26' },
        // W47 — messageTemplates.handoffLocked via `Handoff Lock Reply` (no LLM, no state write)
        { from: 'bot', text: t.handoffLocked, stamp: '11:26', source: 'W47 · messageTemplates.handoffLocked' },
      ],
    },
  ];
}
