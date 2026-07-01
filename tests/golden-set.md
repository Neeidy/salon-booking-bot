# tests: golden-set (happy-path intents)

> **Role of this file:** the reference set of expected intents. `qa-tester` runs these; `/goal` in Phase 7
> iterates until they all pass. Test data only — **never real customer PII**.

Format: input message → expected `{intent, key slots}` → expected outcome.

| # | Message (customer) | Expected intent | Slots | Outcome |
|---|---|---|---|---|
| G1 | "Yarin saat 3 icin sac kesimi randevusu alabilir miyim?" | `book` | serviceId=haircut, time=15:00 | booking created + confirmation |
| G2 | "Sakal tirasi ne kadar?" | `answer_faq` | — | price from config |
| G3 | "Cumartesi kacta acisiniz?" | `answer_faq` | — | hours from config |
| G4 | "Randevu almak istiyorum" (no details) | `book` | all null | slot-fill: ask service → date → time |
| G5 | "Adim Mehmet, beni arayin" | `capture_lead` | customerName=Mehmet | lead saved to Airtable |
| G6 | "Sac + sakal, bu Cuma 11:00" | `book` | serviceId=haircut_beard, date=Fri, time=11:00 | booking created |
| G7 | (unclear) "olur mu acaba" | `unknown`/low-conf | — | handoff |

<TODO (Phase 2/7): expand to ~15–20 cases; add the exact expected JSON per case as the flow stabilizes>
