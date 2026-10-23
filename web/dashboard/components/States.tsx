/**
 * D19 · D20 — the page could not be built. SERVER component.
 *
 * The distinction this file exists to keep: a FAILED READ is not an EMPTY SHOP. Rendering blank panels
 * when the store is unreachable tells the owner they have no bookings, which is both false and
 * reassuring — the worst combination available on a board someone trusts.
 */
export function Unavailable({ busy, misconfigured, detail }: { busy: boolean; misconfigured?: boolean; detail: string }) {
  return (
    <main className="wrap">
      <section className="panel" aria-labelledby="err-h">
        <h2 id="err-h">This board could not load</h2>
        {misconfigured ? (
          /* Third branch, and it is not cosmetic: `credentials()` throws BEFORE any request, so the
             sentence below would blame a service nobody called and send the operator to check the
             network instead of the one file that is wrong (`code-reviewer` #6). */
          <p className="release">
            This board is not configured yet. Its database credentials are missing, or its database role
            is not read-only, so nothing was read at all — nothing is wrong with the bot or with your data.
          </p>
        ) : busy ? (
          <p className="release">
            The database is busy right now. <strong>The bot has priority</strong> — it shares the same
            database, and answering customers comes before drawing this page. Try again
            in a minute.
          </p>
        ) : (
          <p className="release">
            The data service did not answer. Nothing is shown rather than showing an empty shop, because
            an empty board and a failed read look identical and only one of them is good news.
          </p>
        )}
        <span className="tech">{detail}</span>
      </section>
    </main>
  );
}
