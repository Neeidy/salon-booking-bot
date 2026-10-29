/**
 * The engine's fixed message-text retention, in a module with NO imports: the client chat panel reads it for its
 * notice, and a client component must not reach lib/config (scripts/check-client-imports.cjs — the whole baked config
 * belongs to the server render). Purge erases `conversations.recent_messages` 30 days after a conversation's last
 * update (`Compute PII Cutoff`) and deletes `processed_messages` after 30 days (`Compute Purge Cutoff`); the engine
 * hard-codes both, and tests/unit/privacy-facts.test.cjs holds this number to them.
 */
export const MESSAGE_TEXT_DAYS = 30;
