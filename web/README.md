# web — frontend

> **Role of this folder:** the vitrin frontend. Target = a **single Next.js app deployed on Vercel**.
> **Not built yet** — this is a skeleton. It gets built and wired to live data in **Phase 6**.

## Target shape (finalized in Phase 6)
| Surface | Route | What |
|---|---|---|
| Landing | `/` | marketing/vitrin page (branded from `client.config.json`) |
| Chat widget | embeddable | the widget customers chat with; talks to the n8n webhook |
| Owner dashboard | `/admin` | lead/customer CRM view (reads Airtable) |

One app, three surfaces — not three apps. Branding, services, hours, and tone all come from
[`../config/client.config.example.json`](../config/client.config.example.json) (config-driven, no code change per client).

## Do NOT build this yet
Order discipline (MASTER-BRIEF §10): **works first (Phases 2–5), then shines (Phase 6).** Until Phase 6,
`landing/`, `widget/`, and `dashboard/` are empty skeletons (`.gitkeep`). The Phase 1 mockup that guides this
build lives in [`../design/`](../design/).

<TODO (Phase 6): choose Next.js version + styling approach; wire widget → n8n webhook; wire dashboard → Airtable>
