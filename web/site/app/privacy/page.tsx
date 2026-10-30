/**
 * /privacy — what this DEMO does with what a visitor types (public demo gate #14 and its honesty additions).
 *
 * Every statement here is a fact about the running engine, kept true by tests/unit/privacy-facts.test.cjs against
 * the committed workflows and the config; the numbers come from lib/privacy.ts. It describes the demo only, so a
 * non-demo build has no such page: a real client publishes their own.
 *
 * Styles are local to this page on purpose: `app/globals.css` is a verbatim transcription of an approved mockup and
 * is a locked visual contract (the same reason as /install).
 */
import { notFound } from 'next/navigation';
import { config, isDemo } from '../../lib/config';
import {
  BACKUP_DAYS, LEAD_DAYS, MESSAGE_TEXT_DAYS, PRIVACY_CONTACT, PRIVACY_CONTROLLER, PROCESSORS, RUN_RECORD_DAYS,
  TURNSTILE_PRIVACY_URL,
} from '../../lib/privacy';

export const metadata = {
  title: `Privacy — ${config.business.name} (demo)`,
  robots: { index: false, follow: false },
};

const STYLES = `
.pv{--cream:#F1EEE6;--ink:#16150F;--oxide:#B4472E;--muted:#5C594E;--rule:rgba(22,21,15,.18);
background:var(--cream);color:var(--ink);min-height:100vh;
font-family:var(--font-instrument,system-ui),system-ui,sans-serif;font-size:16px;line-height:1.6}
.pv .wrap{max-width:760px;margin:0 auto;padding:clamp(36px,6vw,72px) clamp(20px,4vw,48px) 96px}
.pv .eyebrow{font-size:12px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--oxide)}
.pv h1{font-family:var(--font-fraunces,Georgia),Georgia,serif;font-weight:600;
font-size:clamp(32px,5vw,48px);line-height:1.06;letter-spacing:-.015em;margin:10px 0 0}
.pv .lede{color:var(--muted);max-width:60ch;margin-top:14px}
.pv h2{font-family:var(--font-fraunces,Georgia),Georgia,serif;font-weight:600;font-size:22px;
margin:40px 0 10px;padding-top:16px;border-top:1px solid var(--rule)}
.pv p{margin:0 0 12px;max-width:64ch}
.pv ul{margin:0 0 12px 20px;max-width:64ch}
.pv li{margin:6px 0}
.pv a{color:var(--oxide)}
`;

export default function PrivacyPage() {
  if (!isDemo) notFound();
  return (
    <main className="pv">
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />
      <div className="wrap">
        <p className="eyebrow">Demo — privacy</p>
        <h1>What happens to what you type</h1>
        <p className="lede">
          {config.business.name} is a demonstration of a booking assistant. The salon, its services, prices and hours
          are mock data. Please do not enter real personal details.
        </p>

        <h2>Your messages</h2>
        <ul>
          <li>Your messages are sent to an AI model (Anthropic&apos;s Claude API) to work out what you want. Prices,
            opening hours and free slots come from fixed rules, not from the AI.</li>
          <li>The last few messages of a conversation are stored in the demo&apos;s database and erased by a nightly job
            {' '}{MESSAGE_TEXT_DAYS} days after the conversation&apos;s last activity. The conversation record itself — its
            booking step, the chosen slot, the assistant&apos;s last reply and a random session id from your browser — is
            not deleted automatically; it is deleted on request.</li>
          <li>Message ids, kept only to ignore a message delivered twice, are deleted after {MESSAGE_TEXT_DAYS} days.</li>
          <li>{LEAD_DAYS === null
            ? 'A callback request — your contact details and your message — is not deleted automatically.'
            : `A callback request — your contact details and your message — is deleted by the nightly job once it is
              older than ${LEAD_DAYS} days. A safety limit stops that job, deleting nothing that night and alerting the
              owner, when it would delete more than a fifth of all callback requests, or more than 200, at once. The limit
              is checked again every night, so it can keep stopping the job, night after night, until enough new requests
              arrive or the owner deletes the old ones by hand — and with fewer than five requests stored, none is deleted automatically.`}</li>
        </ul>

        <h2>Copies outside the database</h2>
        <ul>
          <li>Nightly backups of the database are removed once they are more than {BACKUP_DAYS} full days old, and only
            on a night whose backup succeeds — so a deleted message or request can remain in a backup for at least
            {' '}{BACKUP_DAYS} days more, typically about {BACKUP_DAYS + 1}.</li>
          <li>The booking engine (n8n) keeps a record of each run, which includes your message and the request sent to
            the AI model, for about {RUN_RECORD_DAYS} days — a setting on the server, separate from the deletion above.
            The engine&apos;s own database, which holds those records, is backed up nightly and its backups are removed
            the same way as the ones above, so a run record can remain in a backup for at least {BACKUP_DAYS} days
            more, typically about {BACKUP_DAYS + 1}.</li>
          <li>A record deleted on request is removed from the database and the calendar; its copies in the backups and
            run records above remain until they expire as described.</li>
          <li>The services listed below keep what they receive under their own policies.</li>
        </ul>

        <h2>Bookings are real</h2>
        <p>
          A booking is written to a real Google Calendar — the demo&apos;s own — and to the demo&apos;s database, with
          the service, the time, the name you give and the random session id. It is not deleted automatically; it is
          deleted on request, from the calendar and the database. Cancelling in the chat removes the calendar event; the
          booking record stays in the database, marked cancelled.
        </p>

        <h2>Alerts to the owner</h2>
        <p>
          When the assistant hands a conversation to a person, or something fails, the demo&apos;s owner gets a Telegram
          message. It can include the text of your message, and it is outside the automatic deletion above.
        </p>

        <h2>Services involved</h2>
        <ul>
          {PROCESSORS.map((p) => <li key={p.name}><strong>{p.name}</strong> — {p.use}</li>)}
        </ul>
        <p>
          The bot check is Cloudflare Turnstile; Cloudflare describes what it collects in its{' '}
          <a href={TURNSTILE_PRIVACY_URL} rel="noreferrer">Turnstile privacy addendum</a>. Nothing is sent over
          WhatsApp: replies come back in this chat, and the demo&apos;s WhatsApp reminders are switched off.
        </p>

        <h2>In your browser</h2>
        <p>
          A random session id is kept in this tab&apos;s session storage so a conversation can continue; it is gone when
          the tab closes. The site sets no tracking or advertising cookies of its own.
        </p>

        <h2>Why, and your rights</h2>
        <p>
          The demo processes what you type on the basis of legitimate interest (GDPR Art. 6(1)(f)): demonstrating the
          booking assistant.
        </p>
        <p>
          You can ask for access to what the demo holds about you, for its rectification or erasure, and object to its
          processing — write to the contact below. You also have the right to lodge a complaint with a data-protection
          supervisory authority.
        </p>

        <h2>Questions about your data</h2>
        <p>
          {PRIVACY_CONTROLLER === null
            ? 'PLACEHOLDER — who is responsible for this demo’s data (the controller) has not been published yet; it is added before this demo goes live.'
            : `${PRIVACY_CONTROLLER} is responsible for this demo’s data (the controller).`}
        </p>
        <p>
          {PRIVACY_CONTACT === null
            ? 'PLACEHOLDER — the contact for privacy requests has not been published yet; it is added before this demo goes live.'
            : `Write to ${PRIVACY_CONTACT} to ask what the demo holds about you or to have it deleted. The session id is gone
              once your tab closes, so say what you booked and when, or roughly when you chatted and what you wrote —
              that is how your records are found.`}
        </p>

        <p><a href="/">← Back to the demo</a></p>
      </div>
    </main>
  );
}
