'use client';

/**
 * The error boundary — and the FIRST client component in this app, which is why several other things
 * change in the same commit (the tsconfig gains `dom`, and `web/dashboard` leaves
 * NO_CLIENT_ROOTS_OK in scripts/check-client-imports.cjs; that was the declared removal condition).
 *
 * WHY IT EXISTS: `code-reviewer` measured that a single throw during render — a masked value the
 * render-time check rejected — took the whole board down, because app/page.tsx's try wraps only the
 * READS and Next had no boundary to fall back to. The owner saw a generic crash page instead of their
 * appointments. The panel-level fix keeps that from happening; this is the floor under it.
 *
 * ⚠ IT RECEIVES NO PII AND MUST NOT. Next hands an error boundary the error's `message` and `digest`,
 * and this component is CLIENT code — anything given to it is serialised into the page payload. So it
 * renders `error.digest` (an opaque id Next generates) and a fixed sentence, never the message: a
 * thrown masking error can quote the value that failed the check, and that value is the PII.
 */
export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="wrap">
      <section className="panel">
        <h2>Something on this board failed to draw</h2>
        <p className="release">
          The rest of the page was not shown rather than showing you part of it and letting you think
          it was all of it.
        </p>
        {/* The digest is an opaque identifier; the message is deliberately not rendered, because a
            masking failure carries the unmasked value inside its message. */}
        {error.digest && <span className="tech">reference {error.digest}</span>}
        <p>
          <button type="button" onClick={() => reset()}>Try again</button>
        </p>
      </section>
    </main>
  );
}
