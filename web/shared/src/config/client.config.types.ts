// >>> GENERATED from schemas/client.config.schema.json — DO NOT EDIT BY HAND.
// Regenerate: node scripts/generate-config-types.cjs   ·   Drift-guard: same script with --check
// Hand-editing this file re-creates the second-truth problem the generator exists to remove
// (.claude/rules/contract-integrity.md).
/**
 * Per-client, NON-SECRET config for one salon-booking-bot deployment.
 */
export interface ClientConfig {
  /**
   * FRONTEND-ONLY — no n8n node reads it (same class as branding.*). true → every surface shows the mock/demo ribbon + footer notice (.claude/rules/honesty-demos.md); false → a real client install shows neither. OPTIONAL, omitted = false, so the live engine Load Config does not need to carry it. Added in Phase 6 (SCREEN-INVENTORY §8 K5, option A) — deliberately NOT added earlier, because a config key with no consumer is a trap for the next client; the consumer (web/) exists as of this phase.
   */
  demoMode?: boolean;
  business: {
    name: string;
    /**
     * IANA tz, e.g. Europe/Vienna
     */
    timezone: string;
    locale?: string;
  };
  /**
   * Calendar the bot books into (freeBusy + events); a calendar shared with the service account. Real value in n8n Load Config; placeholder here.
   */
  googleCalendarId?: string;
  branding?: {
    primaryColor?: string;
    accentColor?: string;
    /**
     * Rendered on the PUBLIC site, so this is an ENFORCED pattern, not a decorative "format": ajv runs without ajv-formats, which silently ignores unknown formats — the old "format":"uri" looked like a constraint and enforced nothing. CONTRACT for a client: either an absolute https:// URL or a root-relative path (/logo.svg) for a self-hosted logo. http://, javascript:, and PROTOCOL-RELATIVE //host/logo.png are all rejected — the last one matters because it silently loads from a third-party host over the page scheme, which is exactly the dependency a public demo must not have. No regex lookahead is used, so the pattern stays portable across validators.
     */
    logoUrl?: string;
  };
  /**
   * Config-gated channels; a channel omitted here is OFF. Several may be enabled at once — the brain is channel-agnostic: every inbound message is normalized to {channel, sender_key, text} with sender_key = '{channel}:{id}', and the reply always returns to the origin channel. instagram ships default OFF: live connection is per-client (Meta app review, business account, 24h messaging window).
   */
  channels?: {
    whatsapp?: WhatsappChannel;
    widget?: WidgetChannel;
    instagram?: Channel;
  };
  /**
   * @minItems 1
   */
  services: [
    {
      id: string;
      name: string;
      durationMin: number;
      priceEUR?: number;
    },
    ...{
      id: string;
      name: string;
      durationMin: number;
      priceEUR?: number;
    }[]
  ];
  /**
   * Per weekday (mon..sun): array of HH:MM-HH:MM ranges; [] means closed.
   */
  workingHours: {
    [k: string]: string[];
  };
  bot: {
    tone?: string;
    confidenceThreshold: number;
    maxTurnsPerConversation?: number;
    /**
     * Idle minutes after which a returning sender's next message is treated as a new session → 'Welcome back' greeting (CP6).
     */
    sessionGapMinutes?: number;
    /**
     * Hours before start_utc within which a booking can no longer be cancelled/rescheduled by the bot (→ call the shop) (CP3/CP4).
     */
    cancellationCutoffHours?: number;
    /**
     * Hours before start_utc to send the single appointment reminder (CP5). The reminders workflow selects booked, not-yet-reminded appointments starting within this window.
     */
    reminderHoursBefore?: number;
    /**
     * Emergency stop — when true the bot is handoff-only (no LLM, no writes).
     */
    killSwitch?: boolean;
    /**
     * Global dry-run brake (CP5b-3, subset B). true = block the two real-world writes: the new-booking Google Calendar event insert (a dry booked-state is persisted instead, no real event) and the whatsapp Zernio send. Fail-safe OR with the other brakes. Default false (live). Reminder sends have their own whatsappSendDisabled brake.
     */
    dryRun?: boolean;
    /**
     * Reminder/outbound WhatsApp send brake (killSwitch-level). true (default) = NO live template send; the dry-run branch logs the exact payload (CP4c). Coexists with the global dry-run — any brake stops the send.
     */
    whatsappSendDisabled?: boolean;
    /**
     * USD per 1,000 INPUT tokens for the intent LLM. PRICING LIVES IN CONFIG, NOT CODE — if the provider price changes, update this one line (and llmPricePer1kTokensOut); no node/code edit. Haiku 4.5 ≈ $1/1M = 0.001 (CP5b spend-cap).
     */
    llmPricePer1kTokensIn?: number;
    /**
     * USD per 1,000 OUTPUT tokens for the intent LLM. Config-driven pricing — one-line update on any price change. Haiku 4.5 ≈ $5/1M = 0.005 (CP5b spend-cap).
     */
    llmPricePer1kTokensOut?: number;
    /**
     * Hard MONTHLY LLM spend cap in USD (spend-safety brake). Over cap → stop calling the LLM → deterministic reply + handoff. Default 10.00 ≈ 2,000–5,000 turns/mo, far above one salon's real traffic → never limits legitimate use, only trips on abuse/runaway (CP5b spend-cap).
     */
    llmCostCapUsd?: number;
    /**
     * This interface was referenced by `undefined`'s JSON-Schema definition
     * via the `patternProperty` "^\$comment".
     */
    [k: string]: string | number | boolean | undefined;
  };
  /**
   * Owner-alert channel (Telegram). Every failure/handoff class reaches a human through this — WHILE THE CHANNEL IS UP; if it is down the failure is visible only in the n8n execution log (Codex INVARIANT #1). These two keys MUST be identical across all three Load Configs (main · reminders · purge) — asserted by scripts/check-cancel-validation-parity.py. A kill that silences only some alerts is not a kill.
   */
  ownerAlert?: {
    /**
     * false → every alert composer returns [] and NO alert of any class is sent, silently. There is no second channel.
     */
    enabled?: boolean;
    /**
     * Suppression window. main: per (class, sender_key). reminders/purge: per (class, branch). Throttle is applied BEFORE delivery, so a suppressed alert is never retried.
     */
    throttleMinutes?: number;
  };
  /**
   * Named reply templates; may contain {service},{date},{time} placeholders.
   */
  messageTemplates: {
    [k: string]: string;
  };
  /**
   * Free-text answers for FAQ topics NOT derivable from structured config (price/hours/services are computed from services[]/workingHours). A topic without an entry here → deterministic deflect via messageTemplates.faqUnknown (never an LLM guess).
   */
  faq?: {
    address?: string;
    parking?: string;
    walkin?: string;
  };
  /**
   * Documentation-only key; ignored by the loader.
   *
   * This interface was referenced by `ClientConfig`'s JSON-Schema definition
   * via the `patternProperty` "^\$comment".
   */
  [k: string]:
    | string
    | boolean
    | {
        name: string;
        /**
         * IANA tz, e.g. Europe/Vienna
         */
        timezone: string;
        locale?: string;
      }
    | {
        primaryColor?: string;
        accentColor?: string;
        /**
         * Rendered on the PUBLIC site, so this is an ENFORCED pattern, not a decorative "format": ajv runs without ajv-formats, which silently ignores unknown formats — the old "format":"uri" looked like a constraint and enforced nothing. CONTRACT for a client: either an absolute https:// URL or a root-relative path (/logo.svg) for a self-hosted logo. http://, javascript:, and PROTOCOL-RELATIVE //host/logo.png are all rejected — the last one matters because it silently loads from a third-party host over the page scheme, which is exactly the dependency a public demo must not have. No regex lookahead is used, so the pattern stays portable across validators.
         */
        logoUrl?: string;
      }
    | {
        whatsapp?: WhatsappChannel;
        widget?: WidgetChannel;
        instagram?: Channel;
      }
    | [
        {
          id: string;
          name: string;
          durationMin: number;
          priceEUR?: number;
        },
        ...{
          id: string;
          name: string;
          durationMin: number;
          priceEUR?: number;
        }[]
      ]
    | {
        [k: string]: string[];
      }
    | {
        tone?: string;
        confidenceThreshold: number;
        maxTurnsPerConversation?: number;
        /**
         * Idle minutes after which a returning sender's next message is treated as a new session → 'Welcome back' greeting (CP6).
         */
        sessionGapMinutes?: number;
        /**
         * Hours before start_utc within which a booking can no longer be cancelled/rescheduled by the bot (→ call the shop) (CP3/CP4).
         */
        cancellationCutoffHours?: number;
        /**
         * Hours before start_utc to send the single appointment reminder (CP5). The reminders workflow selects booked, not-yet-reminded appointments starting within this window.
         */
        reminderHoursBefore?: number;
        /**
         * Emergency stop — when true the bot is handoff-only (no LLM, no writes).
         */
        killSwitch?: boolean;
        /**
         * Global dry-run brake (CP5b-3, subset B). true = block the two real-world writes: the new-booking Google Calendar event insert (a dry booked-state is persisted instead, no real event) and the whatsapp Zernio send. Fail-safe OR with the other brakes. Default false (live). Reminder sends have their own whatsappSendDisabled brake.
         */
        dryRun?: boolean;
        /**
         * Reminder/outbound WhatsApp send brake (killSwitch-level). true (default) = NO live template send; the dry-run branch logs the exact payload (CP4c). Coexists with the global dry-run — any brake stops the send.
         */
        whatsappSendDisabled?: boolean;
        /**
         * USD per 1,000 INPUT tokens for the intent LLM. PRICING LIVES IN CONFIG, NOT CODE — if the provider price changes, update this one line (and llmPricePer1kTokensOut); no node/code edit. Haiku 4.5 ≈ $1/1M = 0.001 (CP5b spend-cap).
         */
        llmPricePer1kTokensIn?: number;
        /**
         * USD per 1,000 OUTPUT tokens for the intent LLM. Config-driven pricing — one-line update on any price change. Haiku 4.5 ≈ $5/1M = 0.005 (CP5b spend-cap).
         */
        llmPricePer1kTokensOut?: number;
        /**
         * Hard MONTHLY LLM spend cap in USD (spend-safety brake). Over cap → stop calling the LLM → deterministic reply + handoff. Default 10.00 ≈ 2,000–5,000 turns/mo, far above one salon's real traffic → never limits legitimate use, only trips on abuse/runaway (CP5b spend-cap).
         */
        llmCostCapUsd?: number;
        /**
         * This interface was referenced by `undefined`'s JSON-Schema definition
         * via the `patternProperty` "^\$comment".
         */
        [k: string]: string | number | boolean | undefined;
      }
    | {
        /**
         * false → every alert composer returns [] and NO alert of any class is sent, silently. There is no second channel.
         */
        enabled?: boolean;
        /**
         * Suppression window. main: per (class, sender_key). reminders/purge: per (class, branch). Throttle is applied BEFORE delivery, so a suppressed alert is never retried.
         */
        throttleMinutes?: number;
      }
    | {
        [k: string]: string;
      }
    | {
        address?: string;
        parking?: string;
        walkin?: string;
      }
    | undefined;
}
/**
 * whatsapp channel — the base channel fields plus the outbound-send identity a business-initiated send (the reminder) needs. NON-SECRET: accountId is an account handle, not a token; the API key lives in n8n Credentials.
 */
export interface WhatsappChannel {
  enabled: boolean;
  /**
   * Adapter id — zernio.
   */
  provider?: string;
  /**
   * Zernio sending account id for outbound business-initiated sends (reminders). Real value in n8n Load Config; placeholder here.
   */
  accountId?: string;
  /**
   * Meta-approved WhatsApp template for the appointment reminder. A template is REQUIRED because the reminder is business-initiated, outside the 24h customer-service window (freeform is only allowed inside it). name/language are per-client (the approved template's variable order must match Build Reminder Payload's templateParams — CP4d/prod concern).
   */
  reminderTemplate?: {
    name?: string;
    /**
     * Template language code, e.g. en_US.
     */
    language?: string;
  };
}
/**
 * widget channel — the base channel fields plus the Cloudflare Turnstile gate. The widget endpoint is PUBLIC and unauthenticated, so bot-protection is a per-client toggle. NON-SECRET: only the on/off flag lives here; the Turnstile secret is an n8n credential.
 */
export interface WidgetChannel {
  enabled: boolean;
  /**
   * Adapter id — webchat.
   */
  provider?: string;
  /**
   * Cloudflare Turnstile bot-protection for the widget lane. When enabled, the widget must POST a turnstileToken; Turnstile Gate → Verify Turnstile → Turnstile Valid? fails CLOSED (403 turnstile_failed) if verification fails or the call errors.
   */
  turnstile?: {
    enabled?: boolean;
  };
}
export interface Channel {
  enabled: boolean;
  /**
   * Adapter id — e.g. whatsapp: zernio · widget: webchat · instagram: meta-graph
   */
  provider?: string;
}
