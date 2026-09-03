// Corner ribbon — DEMO builds only. honesty-demos.md requires a demo to say it is one; the
// build-config bridge refuses to build an example-config site with demoMode off, so this cannot be
// silently dropped on a demo.
import { isDemo } from '../../lib/config';

export function MockRibbon() {
  if (!isDemo) return null;
  return <div className="mock-ribbon" aria-hidden="true"><span>Mock</span></div>;
}
