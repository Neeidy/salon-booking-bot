/**
 * Where THIS front end gets its engine endpoint and Turnstile site key.
 *
 * Split out of `chatClient` when that module moved to `@salon/shared/chat` (Phase 6b): the transport
 * and the reply-mapping contract are shared with the embeddable snippet, but HOW an endpoint is
 * resolved is not. This file is the site's answer — Next's `NEXT_PUBLIC_*` build-time inlining. The
 * snippet has its own, because `process.env` means nothing inside an esbuild IIFE.
 *
 * Returns null rather than throwing so the caller can degrade VISIBLY (the panel says it is not
 * configured) instead of rendering a chat box that silently cannot send.
 */
import type { EndpointConfig } from '@salon/shared/chat';

export function readEndpointConfig(): EndpointConfig | null {
  const webhookUrl = process.env.NEXT_PUBLIC_WEBHOOK_URL;
  const turnstileSiteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  if (!webhookUrl || !turnstileSiteKey) return null;   // caller degrades visibly, never silently
  return { webhookUrl, turnstileSiteKey };
}
