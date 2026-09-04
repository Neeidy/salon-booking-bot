/**
 * Site config access + the derivations the design needs.
 *
 * The config object itself comes from config.generated.json, which scripts/build-config.mjs already
 * validated against the COMMITTED schema. Nothing here re-validates; nothing here reads the filesystem.
 */
import raw from '../config.generated.json';
import type { ClientConfig } from '@salon/shared/config';

export const config = raw as unknown as ClientConfig;
export const isDemo = config.demoMode === true;

const DAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
const DAY_LABEL: Record<string, string> = {
  mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Saturday', sun: 'Sunday',
};

export interface HoursRow {
  label: string;
  value: string;
  closed: boolean;
}

/**
 * Group consecutive days that share identical hours — the design shows "Mon – Fri / Saturday /
 * Sunday", but that grouping is a PROPERTY OF THE DATA, not a hardcoded layout: a client who opens
 * Sunday and closes Wednesday must get correct rows without touching this code. Ranges are printed
 * with an en dash to match the mockup ("10:00 – 19:00").
 */
export function hoursRows(): HoursRow[] {
  const wh = config.workingHours as Record<string, string[] | undefined>;
  const rows: HoursRow[] = [];
  let i = 0;
  while (i < DAY_ORDER.length) {
    const key = DAY_ORDER[i];
    const spec = JSON.stringify(wh[key] ?? []);
    let j = i;
    while (j + 1 < DAY_ORDER.length && JSON.stringify(wh[DAY_ORDER[j + 1]] ?? []) === spec) j++;
    const ranges = wh[key] ?? [];
    const label = i === j ? DAY_LABEL[key] : `${DAY_LABEL[DAY_ORDER[i]].slice(0, 3)} – ${DAY_LABEL[DAY_ORDER[j]].slice(0, 3)}`;
    rows.push(
      ranges.length === 0
        ? { label, value: 'Closed', closed: true }
        : { label, value: ranges.map((r) => r.replace('-', ' – ')).join(', '), closed: false },
    );
    i = j + 1;
  }
  return rows;
}

/**
 * Footer place line, DERIVED from faq.address (SCREEN-INVENTORY §1 L7 — no separate address key is
 * allowed). faq.address is a free-text SENTENCE ("We're at Musterstrasse 12, 1010 Vienna — 2 minutes
 * from …"), so this pulls the part between "at " and the first dash.
 *
 * HONEST LIMIT: that is a heuristic over prose written by a human, and another client will phrase it
 * differently. When it does not match, this returns null and the footer shows the brand ALONE —
 * never a mangled fragment. A wrong address on a public page is worse than no address.
 */
export function shortAddress(): string | null {
  const a = config.faq?.address;
  if (!a) return null;
  const m = a.match(/\bat\s+(.+?)\s*[—–-]\s/);
  const candidate = (m?.[1] ?? '').trim().replace(/[.,;]$/, '');
  return candidate.length >= 4 && candidate.length <= 80 ? candidate : null;
}

/**
 * "Get directions" target. A PLAIN outbound link, not an embed: no API key, no cookie, no script, and
 * nothing is requested until the visitor clicks. A live map embed would put a third party's tracking
 * inside the CLIENT'S site and hand them the cookie-consent obligation; a rendered static map image is
 * not an option either, because every free provider forbids caching/redistributing it in a product we
 * resell (ARCH-DEC 2026-09-03). Address text + parking + this link do the same job with none of that.
 */
export function directionsUrl(): string | null {
  const a = config.faq?.address;
  const target = shortAddress() ?? a;
  if (!target) return null;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(target)}`;
}
