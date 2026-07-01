# design: data-flow diagram

> **Role of this file:** the Phase 1 flow diagram (a design artifact). It mirrors MASTER-BRIEF §8 and guides
> the Phase 2 n8n build. The visual mockups live in [`mockups/`](mockups/).

```
[Customer]
  ├ WhatsApp ──(Zernio webhook)──┐
  └ Website widget ──(webhook)───┤
                                  ▼
                         [n8n · RS]  ← engine/brain
   0) Load conversation state (Airtable `conversations`, keyed by sender) → merge prior slots
   1) LLM intent extract → JSON → schema-validate (fail → error + handoff)
   2) Route: deterministic (menu/price/hours/slots = IF/Switch) · free text → LLM
   3) Slot-fill: missing slot (service/date/time) → ask + save state → loop until complete
   4) Act: ├ Book (only when complete) → availability → write → re-verify (no atomic lock → cancel+handoff)
           ├ Capture lead → Airtable
           └ Answer FAQ (from config)
   5) confidence < 0.7 → Human handoff (notify owner)
   6) any failure → Error branch (VISIBLE notify)
                                  ▼
                    reply → (Zernio / widget) → Customer

[Owner] sees: Google Calendar (appointments) · Dashboard (CRM) · handoff/error alerts
```

<TODO (Phase 1): add the visual mockups (landing / widget / dashboard) to mockups/ and link them here>
