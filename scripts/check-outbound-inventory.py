#!/usr/bin/env python3
"""
Outbound convergence drift-guard (CP4b).

WHY: CP4b converged every reply branch into ONE channel-aware outbound
(Finalize Outbound -> Channel Switch -> widget respond / whatsapp send). Each branch
carries its EXACT response in `_outbound_status` + `_outbound_body` (so the widget
response stays byte-identical to the pre-convergence respondToWebhook it replaced),
plus `_outbound_should_send` for the whatsapp side.

The `_outbound_should_send` RULE (the source of truth — DERIVE, do not enumerate):
    Send a WhatsApp message only if the customer must LEARN SOMETHING THEY DO NOT
    ALREADY KNOW.
  - SEND      : conversational reply, handoff (guard-trip), any infra-unavailable
                (llm/lead/calendar/cancel-delete/state), booking-state-unsaved.
                They tell the customer a NEW outcome/state.
      · Send Error Response (503 infra): the widget body has no reply, so the whatsapp
        side sends config.messageTemplates.handoff + sets _outbound_owner_flag (ruling
        2026-08-23). HONESTY DEBT: that message promises a human but owner-alert is
        Phase 5 — tracked with the terminal-fallback in ONE Phase-5 ROADMAP line.
      · Send Reject Response (400 invalid payload): a real signed WhatsApp that fails
        validation is usually normal customer behaviour (media-only / >1000 chars), not
        an attack (only SIGNED requests reach here). Silence is a dead end, so the
        whatsapp side sends config.messageTemplates.notUnderstood (ruling 2026-08-23) —
        NO new template. A media-specific message is a Phase-5 refinement.
  - NO-SEND   : duplicate (already got the reply on the 1st delivery), handoff-lock
                (already told a human is helping). Widget still gets its body.

SECURITY (D-b3): `Reject Unsigned Request` (403) is NEVER converged. Routing it through
the shared outbound would hand an attacker a MESSAGE-TRIGGER primitive — an unsigned
request with a forged conversationId could make the bot send a WhatsApp message to an
arbitrary number. Separation is a security requirement, not a cleanliness choice.

This guard is a close-gate + security-auditor check. Non-zero exit = the convergence
contract drifted. Runs on the committed sanitized workflow (no n8n API needed).
"""
import json, re, sys, os

PATH = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('SANITIZED_PATH', 'n8n/workflow.sanitized.json')

CONVERGE = ['Send Reply To Origin','Handoff Reply','Handoff Lock Reply','Idempotent Replay',
 'Booking State-Unsaved Reply','Send Reject Response','Send Error Response','LLM Unavailable Reply',
 'Lead Unavailable Reply','Calendar Unavailable Reply','Cancel Delete Unavailable Reply']
NO_SEND = {'Handoff Lock Reply','Idempotent Replay'}   # customer already knows

def fail(msg):
    print('OUTBOUND DRIFT — ' + msg); sys.exit(1)

wf = json.load(open(PATH))
byname = {n['name']: n for n in wf['nodes']}
conns = wf['connections']

# 1. Reject Unsigned Request stays a SEPARATE respondToWebhook (security invariant)
rej = byname.get('Reject Unsigned Request')
if not rej or rej['type'] != 'n8n-nodes-base.respondToWebhook':
    fail('Reject Unsigned Request must stay a separate respondToWebhook (never converged) — D-b3 security invariant')
if 'Finalize Outbound' in [t['node'] for b in conns.get('Reject Unsigned Request', {}).get('main', [[]])[0] for t in [b]]:
    fail('Reject Unsigned Request must NOT route into the shared outbound (message-trigger risk)')

# 2. every converged branch is a Code tag carrying _outbound_status + _outbound_body, routed to Finalize
for nm in CONVERGE:
    n = byname.get(nm)
    if not n: fail(f'{nm} missing')
    if n['type'] != 'n8n-nodes-base.code':
        fail(f'{nm} must be a Code tag (converged), not {n["type"]}')
    js = n['parameters'].get('jsCode', '')
    if '_outbound_status:' not in js or '_outbound_body:' not in js:
        fail(f'{nm} must set _outbound_status and _outbound_body')
    if '_outbound_should_send:' not in js:
        fail(f'{nm} must set _outbound_should_send')
    tgt = [t['node'] for b in conns.get(nm, {}).get('main', [[]]) for t in b]
    if 'Finalize Outbound' not in tgt:
        fail(f'{nm} must route to Finalize Outbound (got {tgt})')
    # should_send rule
    m = re.search(r'_outbound_should_send:\s*(true|false)', js)
    want = 'false' if nm in NO_SEND else 'true'
    if not m or m.group(1) != want:
        fail(f'{nm} _outbound_should_send must be {want} (should_send rule: send only if the customer learns something new)')

# 3. Finalize -> Channel Switch -> widget respond reads _outbound_body + _outbound_status
if 'Channel Switch' not in [t['node'] for b in conns.get('Finalize Outbound', {}).get('main', [[]]) for t in b]:
    fail('Finalize Outbound must route to Channel Switch')
wr = byname.get('Send Reply (widget)')
if not wr or wr['type'] != 'n8n-nodes-base.respondToWebhook':
    fail('Send Reply (widget) respondToWebhook missing')
p = wr['parameters']
if '_outbound_body' not in p.get('responseBody', ''):
    fail('Send Reply (widget) must emit $json._outbound_body (widget body comes from the branch tag)')
if '_outbound_status' not in str((p.get('options') or {}).get('responseCode', '')):
    fail('Send Reply (widget) responseCode must be $json._outbound_status (widget status comes from the branch tag)')

print(f'outbound inventory OK — {len(CONVERGE)} branches converged (Code tags -> Finalize Outbound -> Channel '
      f'Switch), widget respond reads _outbound_body/_status; should_send rule enforced (NO-SEND: {sorted(NO_SEND)}); '
      f'Reject Unsigned Request stays a separate 403 (message-trigger safe)')
