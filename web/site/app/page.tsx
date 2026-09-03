// The app reads the BUILD-TIME artifact, never the filesystem: scripts/build-config.mjs validated it
// against the committed schema before writing it. Measured reason (2026-09-03): a dynamic readFileSync
// here made Next trace the whole project into the server output, and config/ + schemas/ were not traced
// at all — so any non-static read would have failed on a real deployment.
import config from '../config.generated.json';

export default function Page() {
  return (
    <main>
      <h1>{config.business.name}</h1>
      <p>demoMode: {String(config.demoMode === true)}</p>
      <ul>{config.services.map((s) => (<li key={s.id}>{s.name} — {s.durationMin}min — €{s.priceEUR}</li>))}</ul>
    </main>
  );
}
