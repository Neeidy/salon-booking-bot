// The barber demo site — L1-L9 (docs/SCREEN-INVENTORY.md §1), ported from the approved
// design/mockups/site/index.html. Section order and markup are the locked visual contract; the
// values behind them now come from client config instead of being hand-written.
import { SiteHeader } from '../components/site/SiteHeader';
import { Hero } from '../components/site/Hero';
import { Menu } from '../components/site/Menu';
import { Craft } from '../components/site/Craft';
import { HoursPlace } from '../components/site/HoursPlace';
import { Closer } from '../components/site/Closer';
import { SiteFooter } from '../components/site/SiteFooter';
import { MockRibbon } from '../components/site/MockRibbon';
import { SitePanel } from '../components/site/SitePanel';
import { LiveChatPanel } from '../components/site/LiveChatPanel';
import { readEndpointConfig } from '../lib/chatClient';
import { SiteChrome } from '../components/site/SiteChrome';
import { SiteMotion } from '../components/site/SiteMotion';
import { config } from '../lib/config';

export default function Page() {
  // LIVE panel when the endpoint is configured; the static transcription otherwise, so a checkout
  // without .env.local still builds and renders honestly rather than shipping a dead input box.
  const endpoint = readEndpointConfig();
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <Menu />
        <Craft />
        <HoursPlace />
        <Closer />
      </main>
      <SiteFooter />
      <MockRibbon />
      {endpoint ? <LiveChatPanel config={config} endpoint={endpoint} /> : <SitePanel />}
      <SiteChrome />
      <SiteMotion />
    </>
  );
}
