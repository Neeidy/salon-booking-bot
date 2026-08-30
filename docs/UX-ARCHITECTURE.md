# UX / Fonksiyon Mimarisi — Phase 6 öncesi türetme belgesi

> **Bu belgenin rolü:** Phase 6 (Next.js vitrin + widget + dashboard) tasarımına başlamadan önce,
> sistemin **gerçekte ürettiği** her müşteri durumunu ve her sahip sinyalini repodaki mevcut
> artefaktlardan türetmek. Piksel belgesi değil — **fonksiyon ve durum** belgesi.
> Tarih: 2026-08-27 · Kaynak: `n8n/workflow.sanitized.json` (172 node) ·
> `n8n/workflow.reminders.sanitized.json` (17) · `n8n/workflow.purge.sanitized.json` (4) ·
> `config/client.config.example.json` · `schemas/` · `design/mockups/`

---

## §0 — Amaç ve türetme kuralı

### Neden bu adım var

Geçmişte tasarım ile sistem birbirini tutmadı ve emek çöp oldu: görsel önce yapıldı, sistemin
gerçekte ürettiği durumlar (hata ekranları, ara durumlar, sahibin görmesi gereken sinyaller)
tasarıma hiç girmedi. Bu adımın amacı bunu **yapısal olarak imkânsız kılmak**.

Bu bir teorik risk değil — **bu belgeyi yazarken canlı örneği bulundu**:
`design/mockups/variants/widget-a-cream-ink.html:217-218` müşteriye bir "Outside working hours"
balonu gösteriyor; motor o mesajı **hiç üretmiyor** (`messageTemplates.outsideHours` ölü, bkz. §8
BULGU #4). Yani Phase 1 mockup'ı, sistemde karşılığı olmayan bir ekranı zaten vaat etmiş durumda.

### Türetme kuralı (bağlayıcı)

1. **Hiçbir ekran/durum hayal edilmez.** Her biri repodaki mevcut bir artefakttan türetilir ve
   kaynağı **dosya + node adı** ile gösterilir.
2. Kaynağı olmayan bir ekran bu belgeye ancak **"YENİ — gerekçesi şu"** etiketiyle, ayrı olarak
   girer. Sessizce eklenmez.
3. Doğrulanamayan hiçbir şey iddia edilmez — **DOĞRULANAMADI** yazılır.
4. Bu belge boşlukları **çözmez, listeler** (§8). Kararlar §9'da Yigitcan'a bırakılır.

### Bu belge NE DEĞİL

Görsel tasarım · renk · tipografi · layout içermez. `/plan-flow` değil, CP planı değil, drill
matrisi değil. Bunlar bu belge **onaylandıktan sonra** gelir.

---

## §1 — Aktörler ve yüzeyler

| Aktör | Yüzey | UI var mı | Giriş noktası |
|---|---|---|---|
| Müşteri | **Widget** (demo sitesi + gömülebilir snippet) | ✅ tarayıcı | `POST /webhook/barber-inbound` — `x-zernio-signature` header'ı **YOK** |
| Müşteri | **WhatsApp** | ❌ UI yok — mesaj balonu | Aynı endpoint — `x-zernio-signature` header'ı **VAR** (Zernio BSP) |
| Sahip | **Dashboard** | ✅ tarayıcı (`/admin`) | Henüz yok — Phase 6'da kurulacak |
| Sahip | **Telegram** | ✅ (mevcut, tek gerçek alert kanalı) | `Send Owner Alert (Telegram)` |

Kanal ayrımı **route-by-header** ile yapılır: `Is Zernio Inbound?` node'u
`!!headers['x-zernio-signature']` bakar (CRT#3 / M2 düzeltmesi). Gövde şekline bakılmaz.

### NOT-surface — her yüzeyin YAPMADIĞI

| Yüzey | YAPMAZ |
|---|---|
| Widget | Müşteri kimliği doğrulamaz (`sessionId` = session-token gücü, doğrulanmış kimlik **değil**) · takvim göstermez · ödeme almaz · geçmiş randevu listesi göstermez |
| WhatsApp | Buton/liste/rich-media göndermez (düz metin) · proaktif mesaj atmaz (tek istisna: hatırlatma, o da onaylı template ile) |
| Dashboard | Müşteriyle sohbet etmez (bugün "Reply" bağlanmamış bir affordance) · GCal/Airtable'a **doğrudan yazmaz** (§5) · çoklu personel / çoklu şube yönetmez (T1 kapsam dışı) |
| Telegram | Aksiyon almaz — tek yönlü bildirim; "çözüldü" işaretlemesi yok |

### Instagram

Mimari olarak hazır, **config-gated, varsayılan KAPALI**
(`config/client.config.example.json` → `channels.instagram.enabled: false`). Canlı bağlantı
müşteri onboarding'ine ertelendi. **Bu belgenin kapsamı dışı.**

### Zernio (WhatsApp BSP) — güncel durum

Abonelik **KAPALI** (sahip 2026-08-26'da `isActive:false` teyit etti, `docs/ROADMAP.md`). Kod
tarafı canlı ve drill'lenmiş: HMAC gate, adapter, outbound send hepsi çalışır durumda. Yani
whatsapp akışları bu belgede **gerçek** kabul edilir; sadece abonelik kapalı.

---

## §2 — Müşteri akışları

Ortak sözleşme: her akış `Normalize Inbound` → front-gate'ler (§3) → `Load State` → `Merge State`
→ `Check Handoff Lock` → `Check Bot Guards` → `Spend Gate` → `Extract Intent` (LLM) →
`Validate Intent` → `Confidence & Intent Gate` → `Route Intent` zincirinden geçer. Cevap metni
**tek kaynaktan** gelir: `computed_reply` (Refactor #5) — her builder onu yazar,
`Build Reply Payload` okur, boşsa `reply_fallback` bayrağı kalkar.

**Stage makinesi (gerçek, doğrulanmış — 9 değer):**

```
new ──▶ collecting ──▶ ready ──▶ confirming ──▶ booked
 │           ▲                                    │
 │           └──── (slot reddedildi: invalid/past/closed/busy)
 │
 ├──▶ cancel_confirming ──▶ cancelled | new (iptal edildi/vazgeçildi)
 ├──▶ reschedule_confirming ──▶ booked | new (taşındı/vazgeçildi)
 └──▶ handoff  (kilit: bu stage'de bot artık cevap üretmez)
```

| Stage | Yazan node(lar) | Okuyan / çıkış |
|---|---|---|
| `new` | `Merge State` (varsayılan) · `Build Cancel-Aborted State` · `Build Reschedule-Aborted State` | intent sınıflandırmasıyla yeniden yönlenir |
| `collecting` | `Slot Gate` (eksik slot) · `Compute Availability` (slot reddedildi) | `Slot Gate` · `Build Reply Payload` |
| `ready` | `Slot Gate` (3 slot tam) | `Availability Gate` → `Build FreeBusy Query` |
| `confirming` | `Compute Availability` (slot müsait) | `Build Event Request` — **fail-closed**: başka stage'de gelen "yes" boş `eventId` üretir → `Mark Handoff` |
| `booked` | `Build Booked State` · `Build Dry-Run Booked State` · `Build Mirror-Failed State` · `Build Reschedule-Done State` | **stage-tabanlı okuyucu YOK** — çıkış yeni intent sınıflandırması ile |
| `cancel_confirming` | `Build Cancel-Confirm State` | `Confirm Router` → `Confirm Fresh?` (confirm-TTL) → `Verify Confirm Live` |
| `cancelled` | `Build Cancelled State` | **stage-tabanlı okuyucu YOK** — terminal |
| `reschedule_confirming` | `Compute Reschedule Availability` | `Reschedule Router` → `Reschedule Fresh?` |
| `handoff` | 15 node (`Mark Handoff` + 14 hata/needs-human builder) | `Check Handoff Lock` → `Handoff Lock Reply` (sessiz kilit, LLM harcanmaz) |

> ⚠ `docs/DATA-MODEL.md` bu enum'u `new\|collecting\|ready\|done\|handoff` diye yazıyor —
> **bayat**. `done` hiçbir node tarafından stage olarak yazılmıyor; 5 gerçek stage belgesiz.
> §8 BULGU #3.

---

### 2.1 — Karşılama (yeni / dönen müşteri)

| | |
|---|---|
| **Giriş** | Herhangi bir ilk mesaj; `Load State` kaydı bulur/bulmaz |
| **Adımlar** | `Merge State` → `found` + `last_updated_prev` okunur; `Build Reply Payload` içinde `now − last_updated_prev > bot.sessionGapMinutes` (30 dk) ise **yeni oturum** |
| **Metin** | Dönen müşteri: `"Welcome back! "` **hard-coded** (`Build Reply Payload`), template değil. Sadece `stage === 'collecting'` iken öne eklenir |
| **Çıkış** | Mesajın intent'ine göre 2.2–2.8'den birine |
| **Stage** | değiştirmez |
| **⚠** | `messageTemplates.greeting` tanımlı ama **hiçbir node üretmiyor** (§8 BULGU #4) — yeni müşteri için ayrı bir karşılama ekranı **yok**; ilk cevap doğrudan intent cevabı |

### 2.2 — FAQ (7 konu, deterministik — LLM cevabı değil)

`Answer FAQ` node'u. LLM yalnızca `faqTopic`'i sınıflandırır; **cevabı config üretir**.

| faqTopic | Cevabın kaynağı | Örnek şekil |
|---|---|---|
| `price` | `cfg.services[].priceEUR` — serviceId varsa tek servis, yoksa tüm liste | "Haircut is €25." / "Our prices: Haircut €25, Beard Trim €15, Haircut + Beard €35." |
| `services` | `cfg.services[].name + durationMin` | "We offer: Haircut (30 min), Beard Trim (20 min), Haircut + Beard (45 min)." |
| `hours` | `cfg.workingHours` 7 gün | "Opening hours — Mon: 10:00-19:00 · … · Sat: 10:00-18:00 · Sun: closed." |
| `address` | `cfg.faq.address` | serbest metin |
| `parking` | `cfg.faq.parking` | serbest metin |
| `walkin` | `cfg.faq.walkin` | serbest metin |
| `other` / `null` | `messageTemplates.faqUnknown` | "Good question — let me check with the team…" |

**Stage:** yazmaz (tek-turluk, Airtable'a gitmez). **Çıkış:** 200 · `Send Reply To Origin`.
**Tasarım notu:** `price`/`services`/`hours` cevapları **çok satırlı ve uzun** — widget balonunun
liste/tablo görünümüne ihtiyacı var, düz balon taşar.

### 2.3 — Randevu alma (servis → tarih/saat → müsaitlik → onay → booked)

| Adım | Node | Müşteri ne görür | Stage |
|---|---|---|---|
| 1. eksik slot | `Slot Gate` | `askService` → "Which service would you like? (Haircut / Beard Trim / Haircut + Beard)" | `collecting` |
| 2. eksik tarih/saat | `Slot Gate` | `askDateTime` → "What day and time works for you?" | `collecting` |
| 3. 3 slot tam | `Slot Gate` | (cevap yok, doğrudan müsaitliğe) | `ready` |
| 4. müsait | `Compute Availability` | "Haircut, Thursday 4 Sep 14:00 — shall I book it? (yes / no)" (**literal, template değil** — tarih/saat örnek) | `confirming` |
| 5. "yes" | `Build Event Request` → GCal insert → write-then-verify | `bookingConfirmed` → "You're booked: {service}, {date} {time}. See you then!" | `booked` |

**Çıkışlar (5 farklı sonuç, hepsi gerçek):**

| Sonuç | Node | Metin | Stage | Sahip sinyali |
|---|---|---|---|---|
| Başarılı | `Build Booked State` | `bookingConfirmed` | `booked` | yok |
| Dry-run | `Build Dry-Run Booked State` | `bookingConfirmed` (**aynı metin**) | `booked` | yok — müşteri farkı göremez |
| Mirror-failed (GCal OK, Airtable patladı) | `Build Mirror-Failed State` | `bookingConfirmed` | `booked` | `mirror_failed` alert |
| Verify belirsiz | `Build Verify-Unavailable State` / `Build Reconcile-Unresolved State` | `bookingNeedsConfirm` / `verifyIncomplete` | `handoff` | `verify_unavailable` / `reconcile_unresolved` |
| Yarış kaybedildi | `Build Race-Lost State` (temiz) / `Build Orphan State` (silme de patladı) | `slotJustTaken` veya `verifyIncomplete` | `handoff` | Orphan → `orphan_event`; **Race-Lost → alert YOK** (KK3, normal sonuç) |

### 2.4 — Slot dolu → alternatifler

`Compute Availability`, `overlaps()` true olduğunda o günün çalışma pencerelerini 30 dk adımla
tarar, **en fazla 3** boş slot toplar:

- Alternatif bulunursa (saatler örnek, gerçek liste GCal'dan gelir): `"{tarih} is taken. Free that day: 10:00, 10:30, 15:00. Which works?"`
- Bulunamazsa: `"{tarih} is taken and that day is full — want another day?"`

**Stage:** `collecting` (ve **reddedilen slot state'ten temizlenir** — sonraki "yes" yanlışlıkla
booking yapamasın; fail-closed). **Metin literal**, `messageTemplates`'te karşılığı yok.
**Tasarım notu:** widget'ta bu 3 alternatif **tıklanabilir çip** olmaya en uygun yer — ama bugün
düz metin; tıklanabilir yapmak frontend işi, motor değişmez.

Diğer red sınıfları (hepsi `collecting`, hepsi literal metin):

| Durum | Metin |
|---|---|
| `invalid` (tarih okunamadı) | "Sorry, I couldn't read that date/time — what day and time would you like?" |
| `past` | "{tarih} has already passed — give me a future day and time." |
| `closed` | "We're closed {gün}. Open {saatler}. What time works?" |

### 2.5 — İptal (bul → onayla → sonuç)

| Adım | Node | Metin | Stage |
|---|---|---|---|
| Randevu yok | `Build No-Booking Reply` | `cancelNoBooking` | değişmez |
| Cutoff içinde | `Build Cancel-Cutoff Reply` | `cancelCutoff` | `handoff` |
| Bozuk kayıt | `Build Cancel-NeedsHuman State` | `cancelNeedsHuman` / `cancelTargetGone` | `handoff` |
| Onay sorusu | `Build Cancel-Confirm State` | **literal**: `Cancel your {service} on {when}? Reply "yes" to cancel, or anything else to keep it.` Birden fazla randevu varsa: `(you have N bookings — this cancels the {when} one)` | `cancel_confirming` |
| "hayır" | `Build Cancel-Aborted State` | `cancelAborted` | `new` |
| Silindi | `Build Cancelled State` | `cancelDone` (204) veya `cancelAlreadyDone` (404/410) | `cancelled` |
| GCal silme patladı | `Cancel Delete Unavailable Reply` | `cancelUnavailable` | — (503) |

**Güvenlik mekanizmaları (tasarımın bozmaması gerekenler):**
- `cancel_target_id` — "yes" **o kayda** bağlanır, IDOR yok
- `confirm_turn` — onay yalnızca **hemen sonraki turda** geçerli (confirm-TTL)
- Hedef `sender_key` ile bulunur, **asla müşterinin verdiği id ile değil**

### 2.6 — Erteleme (bul → yeni slot → onayla → taşındı)

`Reschedule Lookup` sahibin **en yakın gelecekteki** randevusunu bulur, cancel ile aynı doğrulamayı
uygular (`structOk`: geçerli `start_utc` + gid şekli + `calendar_id`), cutoff'u **eski** randevuya
uygular, yeni slotu bu turun intent'inden okur.

| Sonuç | Metin | Stage |
|---|---|---|
| Randevu yok | `rescheduleNoBooking` | değişmez |
| Bozuk kayıt / servis eşleşmedi | `rescheduleNeedsHuman` | `handoff` |
| Cutoff içinde | `rescheduleCutoff` | `handoff` |
| Yeni slot verilmedi | `rescheduleAskSlot` | değişmez |
| Yeni slot müsait | (literal, `Compute Reschedule Availability`) | `reschedule_confirming` |
| "hayır" | `rescheduleAborted` | `new` |
| Taşındı | `rescheduleDone` | `booked` |
| Yeni event insert patladı | `rescheduleInsertFailed` — **eski randevu duruyor** | `handoff` |
| Mirror patladı | `rescheduleMirrorFailed` | `handoff` |
| Yarış kaybedildi | `slotJustTaken` / `verifyIncomplete` | `handoff` |
| Yarış + eski event silinemedi (orphan) | `rescheduleDone` (⚠ müşteriye başarılı der) veya `verifyIncomplete` | `handoff` |

**Yan etki:** erteleme `appointments.reminded = false` yapar → taşınan randevu **yeniden hatırlatılır**.

### 2.7 — Lead yakalama

`Build Lead State` → `leadCaptured` → "Thanks! We've got your details and someone from the team
will reach out soon." Airtable `leads` tablosuna yazar (`name`, `phone`, `source`, `message`,
`status`, `created_at` — 3'ü PII). Yazma patlarsa → `Lead Unavailable Reply` (503) +
`lead_unavailable` alert.

### 2.8 — İnsana devir — **3 sınıf, asla birleştirilmez**

`.claude/rules/handoff.md` sözleşmesi. Müşteri üçünde de benzer nazik metin görebilir; **makine
tarafı ayrışır**:

| Sınıf | Sebep | State yazar mı | HTTP | Node |
|---|---|---|---|---|
| **guard-trip** | kill-switch · max-turns · spend-cap | ❌ geçici | 200 | `Handoff Reply` · `Build Spend-Cap Reply` |
| **infra-unavailable** | dış sistem çöktü | ❌ geçici | **5xx + `error` bayrağı** | `LLM/Lead/Calendar/Cancel Delete Unavailable Reply` · `Send Error Response` |
| **intent-handoff** | düşük güven · bilinmeyen · needs-human | ✅ `stage=handoff`, `last_intent` | 200 | `Mark Handoff` + 14 builder |

**Devir kilidi:** `stage === 'handoff'` iken `Check Handoff Lock` her mesajı `Handoff Lock Reply`'a
yönlendirir → `handoffLocked` → "A team member is already helping you here — they'll reply
shortly." **WhatsApp'a gönderilmez** (`should_send: false` — müşteri zaten biliyor), widget gövdeyi
alır. LLM harcanmaz. **Kilidi açacak bir müşteri yolu yok** — sahip Airtable'da `stage`'i
değiştirmeli. Bu dashboard'ın gerçek bir işi (§4c).

### 2.9 — Hatırlatma (giden mesaj, UI yok)

Ayrı workflow: `Salon Booking Bot — Reminders`, **saatlik** schedule.

| | |
|---|---|
| Seçim | `Find Due Appointments`: `status="booked"` AND `NOT({reminded})` AND `start_utc` şimdi ile `now + reminderHoursBefore` (24 sa) arasında |
| Metin | `messageTemplates.reminder` (**reminders workflow'unun kendi `Load Config (Reminders)`'ında**) → "Reminder: your {service} is booked for {when}. See you soon!" `{when}` shop timezone'da, DST doğru |
| Gönderim | WhatsApp **onaylı template** (`appointment_reminder`, `en_US`) — iş-başlatımlı mesaj 24s penceresi dışında serbest metin olamaz |
| Fren | `bot.whatsappSendDisabled` (varsayılan **true**) → `Reminder Send (dry-run)` payload'ı loglar, yine de `reminded` damgalar |
| Kilit | `bot.killSwitch` → `Reminders Halted` |
| Semantik | **send-first, stamp-after** = at-least-once (kabul edilmiş) |
| Bilinen limit | GCal'dan doğrudan iptal edilen randevu yine hatırlatılabilir; `mirror_failed` satırları hiç hatırlatılmaz |

### 2.10 — Guard-trip'ler (müşterinin gördüğü)

| Guard | Config | Müşteri ne görür | Ayırt edilebilir mi |
|---|---|---|---|
| Kill-switch | `bot.killSwitch` | `handoff` template | ❌ max-turns ile aynı (§8 BULGU #7) |
| Max-turns | `bot.maxTurnsPerConversation` (12) | `handoff` template | ❌ |
| Spend-cap | `bot.llmCostCapUsd` ($10/ay) | `handoff` template | ❌ |
| Dry-run (booking) | `bot.dryRun` | `bookingConfirmed` — **gerçek booking'den ayırt edilemez** | ❌ tasarım kararı |
| Dry-run (WhatsApp send) | `bot.dryRun` | **hiçbir şey** — mesaj sessizce gitmez | ❌ |

---

## §3 — Müşteri hata / kenar durum ekranları

Bu bölüm **eksiksiz** olmak zorunda. Sistemin ürettiği her HTTP çıkışı burada. Ekranı olmayan her
çıkış **🕳 BOŞLUK** olarak işaretli — Phase 6 bunları tasarlamak zorunda.

### 3.1 — Converged çıkışlar (12 dal → `Finalize Outbound` → `Channel Switch`)

Widget `_outbound_body`'yi **birebir** alır (senkron). WhatsApp `_outbound_reply`'i alır ve yalnızca
`_outbound_should_send === true` ise gönderilir.

| # | Node | HTTP | Widget gövdesinde `reply` var mı | WA gönderir mi | Ekran durumu |
|---|---|---|---|---|---|
| 1 | `Send Reply To Origin` | 200 | ✅ | ✅ | normal balon |
| 2 | `Handoff Reply` | 200 | ✅ `handoff` | ✅ | devir balonu |
| 3 | `Handoff Lock Reply` | 200 | ✅ `handoffLocked` | ❌ zaten biliyor | kilit balonu — **girdi alanı kapatılmalı mı? 🕳 tasarım kararı** |
| 4 | `Idempotent Replay` | 200 | ❌ `{status:'duplicate_ignored', sender_key}` | ❌ | 🕳 **BOŞLUK** — widget'ın ne göstereceği tanımsız (muhtemelen: hiçbir şey, sessiz yut) |
| 5 | `Booking State-Unsaved Reply` | 200 | ✅ + `state_unsaved:true` + `gcal_event_id` | ✅ | booking mesajı; state kaydedilemedi |
| 6 | `Send Reject Response` | **400** | ❌ `{ok:false, error:'invalid_payload', handoff:true}` | ✅ `notUnderstood` | 🕳 **BOŞLUK** — widget metinsiz |
| 7 | `Send Error Response` | **503** | ❌ `{ok:false, error:'state_unavailable', handoff:true}` | ✅ `handoff` | 🕳 **BOŞLUK** — widget metinsiz |
| 8 | `LLM Unavailable Reply` | 503 | ✅ `handoff` | ✅ | hata balonu |
| 9 | `Lead Unavailable Reply` | 503 | ✅ `handoff` | ✅ | hata balonu |
| 10 | `Calendar Unavailable Reply` | 503 | ✅ `handoff` | ✅ | hata balonu |
| 11 | `Cancel Delete Unavailable Reply` | 503 | ✅ `cancelUnavailable` + `cancel_delete_failed:true` | ✅ | hata balonu |
| 12 | `Build Spend-Cap Reply` | 200 | ✅ `handoff` | ✅ | devir balonu — ⚠ drift-guard bunu denetlemiyor (§8 BULGU #2) |

**#6 ve #7 kritik:** widget bu iki durumda **hiçbir okunabilir metin almıyor**. Bugün widget'ın ne
göstereceği motorda tanımlı değil — frontend'in kendi kararı. §9 açık karar 4.

### 3.2 — Converged OLMAYAN çıkışlar (front-gate, doğrudan cevap)

| Node | HTTP | Gövde | Koşul | Ekran |
|---|---|---|---|---|
| `Reject Unsigned Request` | **403** | `{ok:false, error:'invalid_signature'}` | `x-zernio-signature` var ama HMAC tutmuyor | 🕳 müşteri ekranı **yok ve olmamalı** — bu bir saldırgan yolu. **Asla mesaj tetiklemez** (D-b3 güvenlik değişmezi: converged olsaydı saldırgana "keyfi numaraya mesaj attırma" primitifi verirdi) |
| `Reject Bot Request` | **403** | `{ok:false, error:'turnstile_failed'}` | widget + `turnstile.enabled` + token doğrulanamadı (fail-closed) | 🕳 **BOŞLUK** — widget "doğrulama başarısız, sayfayı yenileyin" gibi bir durum göstermeli |
| `Respond Normalize Reject` (whatsapp) | **422** | `{ok:false, error:'normalize_failed'}` | imzalı ama şekli bozuk Zernio payload'ı | ekran yok (Zernio'nun kendi loguna sinyal) + `normalize_drift` alert |
| `Respond Normalize Reject` (widget) | **400** | `{ok:false, error:'bad_request'}` | widget payload'ında `sessionId` yok | 🕳 **BOŞLUK** — alert **bilerek yok**: widget endpoint'i kimlik doğrulamasız, alert tetikletmek sahibin Telegram'ına DoS primitifi olurdu |

### 3.3 — n8n dışındaki kenar durumlar

| Durum | Nerede | Müşteri ne görür |
|---|---|---|
| **Rate-limit** | **Cloudflare edge** — `barber-inbound-ratelimit`, `/webhook/` içeren yol, **20 istek/dk/IP, Block**. n8n içinde rate-limit **yok** | Widget'ın `fetch`'i Cloudflare'in blok cevabını alır (n8n'e hiç ulaşmaz). Sayfa yüklenmeye devam eder — **sadece mesaj gönderimi** engellenir. 🕳 **BOŞLUK** — widget'ın "çok hızlı gönderiyorsunuz" durumu tasarlanmamış |
| **n8n tamamen erişilemez** | ağ/host | 🕳 **BOŞLUK** — offline/timeout durumu tasarlanmamış (`docs/PHASE-6-BACKLOG.md` §1 bunu zaten açık bırakıyor) |
| **Duplicate mesaj** | `Dedupe Gate` → `Is Duplicate` | bkz. 3.1 #4 |

### 3.4 — Sistem anahtarlarının müşteri yüzü

| Anahtar | Müşteri görüntüsü |
|---|---|
| `bot.killSwitch = true` | her mesaja `handoff` template'i; hiç LLM, hiç yazma |
| `bot.dryRun = true` | **görünür fark yok** — booking onayı gerçek gibi; WhatsApp mesajı sessizce gitmez |
| spend-cap aşıldı | `handoff` template'i |
| `bot.whatsappSendDisabled` | müşteri **hatırlatma** almaz; sohbet cevapları etkilenmez |

---

## §4 — Sahip (dashboard) bilgi mimarisi

Phase 1'de bir dashboard mockup'ı zaten var
(`design/mockups/variants/dashboard-a-cream-ink.html`): KPI şeridi (4 kutu) · Appointments tablosu
· Leads tablosu · sağ rayda "Handoff alerts" listesi. **Bu belge o mockup'ı doğrular ve eksiğini
söyler.**

### 4.a — Randevular

| | |
|---|---|
| **Kaynak** | Airtable `appointments` |
| **Alanlar (gerçek)** | `sender_key`(PII) · `service` · `start_utc` · `end_utc` · `gcal_event_id` · `calendar_id` · `channel` · `customer_name`(PII) · `status` (`booked\|cancelled`) · `reminded` · `reminder_sent` · `created_at` |
| **Görünümler** | bugün · yaklaşan · geçmiş (`start_utc` UTC saklanır, **shop timezone'da gösterilir**) |
| **Satırda** | saat · servis · müşteri (maskeli) · kanal · durum · hatırlatıldı mı |
| **Aksiyonlar** | iptal · ertele → **§5 sözleşmesine tabi** |
| **Sıfır durumu** | "bugün randevu yok" — `docs/PHASE-6-BACKLOG.md` §1'de zaten açık |
| **⚠ Gerçek** | Müsaitliğin **doğruluk kaynağı Google Calendar**; `appointments` bir aynadır. `mirror_failed` sonrası bu tablo GCal ile **uyuşmaz** ve dashboard bunu bilemez |

### 4.b — Lead'ler

Kaynak: Airtable `leads` — `name`(PII) · `phone`(PII) · `source` · `message`(PII) · `status`
(`new\|contacted\|converted`) · `created_at`. Aksiyon: durum değiştirme (yıkıcı değil, §5 dışı).

### 4.c — DEVİR KUYRUĞU — **en kritik bölüm**

Bugün alert'lerin tek evi **Telegram**. Dashboard'ın asıl işi bu.

**21 alert sınıfı** (FIX-1 ile 19'dan çıktı: `cancel_mirror_failed` + `purge_error`). Ana workflow'un
20'si tek node'da toplanıyor: `Build Owner Alert` (28 kaynak node besliyor); `purge_error` purge
workflow'unun kendi composer'ında, `reminder_error` reminders'ınkinde.
Kapı: `ownerAlert.enabled !== true` → hiç alert yok. Throttle: **(sınıf, sender_key) çifti başına
30 dk** (`ownerAlert.throttleMinutes`), n8n `$getWorkflowStaticData('global')` içinde.

| # | Sınıf | Tetikleyen | Sahip ne yapmalı |
|---|---|---|---|
| 1 | `handoff_lock` | `Handoff Lock Reply` | konuşmayı devral, `stage`'i aç |
| 2 | `max_turns` | `Handoff Reply` (kill-switch KAPALIYKEN) | konuşmayı devral |
| 3 | `state_unavailable` | `Send Error Response` | Airtable'ı kontrol et |
| 4 | `llm_unavailable` | `LLM Unavailable Reply` | Anthropic durumu |
| 5 | `lead_unavailable` | `Lead Unavailable Reply` | lead'i elle kaydet |
| 6 | `calendar_unavailable` | `Calendar Unavailable Reply` | GCal durumu |
| 7 | `state_unsaved` | `Booking State-Unsaved Reply` | booking gerçek, state yok — elle doğrula |
| 8 | `cancel_delete_failed` | `Cancel Delete Unavailable Reply` | GCal'dan elle sil |
| 9 | `spend_cap` | `Build Spend-Cap Reply` | bütçe kararı |
| 10 | `spend_meter_unavailable` | `Build Spend-Meter Alert` | `bot_metrics` erişimi (**fail-OPEN** — LLM çalışmaya devam eder) |
| 11 | `normalize_drift` | `Build Normalize Reject` (**yalnız whatsapp**) | Zernio payload şekli değişti |
| 12 | `dedupe_marker_failed` | `Build Dedupe-Marker Alert` | çift işleme riski |
| 13 | `zernio_send_failed` | `Outbound Send Failed` | müşteriye cevap **gitmedi** — elle yaz |
| 14 | `orphan_event` | `Build Orphan State` · `Build Reschedule Race-Orphan State` | **GCal'da çift kayıt var — elle sil** |
| 15 | `mirror_failed` | `Build Mirror-Failed State` · `Build Reschedule Mirror-Failed State` | Airtable ile GCal uyuşmuyor |
| 16 | `verify_unavailable` | `Build Verify-Unavailable State` (+reschedule) | booking'i elle doğrula |
| 17 | `reconcile_unresolved` | `Build Reconcile-Unresolved State` | booking'i elle doğrula |
| 18 | `reconcile_conflict` | `Build Reconcile-Handoff State` | gerçek çakışma |
| 19 | `cancel_needs_human` | `Build Cancel-NeedsHuman State` | elle iptal |
| + | `handoff` (genel) | `stage='handoff'` yazan ama üstteki bayrağı olmayan her node | konuşmayı devral |
| + | `reply_fallback` | `Build Reply Payload` (`computed_reply` boş) | öngörülmemiş yol — incele |
| 20 | **`cancel_mirror_failed`** | `Build Cancelled State` (**FIX-1**) | GCal'dan silindi ama Airtable `booked` kaldı — randevuyu elle iptal et; hatırlatma gidebilir |
| + | `reminder_error` | reminders wf, **kendi composer'ı**, global throttle (sender başına değil) | hatırlatma turu patladı |
| + | **`purge_error`** | purge wf, **kendi composer'ı** (**FIX-1**), throttle `purge_error:<branch>` | temizlik durdu — `branch` hangisini söyler: `processed_messages` (dedupe) veya `conversations_pii` (PII scrub) |

**Alert VERİLMEYENLER (bilinçli):** `race_lost` (normal sonuç, KK3) · kill-switch trip'i (sahip
kendi açtı, KK2) · duplicate · 403 unsigned · 403 turnstile · widget-lane normalize reject.
~~**Alert verilmeyenler (kaza):** `cancel_mirror_failed`~~ → **KAPANDI (FIX-1, 2026-08-30).**
Artık kendi sınıfıyla alert veriyor (§4c tablosu, sıra 20). Kaza kategorisi **boş**.

> ### Devir kuyruğunun temel problemi — ✅ ÇÖZÜLDÜ (FIX-1, 2026-08-30)
> **Önceden:** 18 residue bayrağının 17'si EPHEMERAL'di — hiçbiri Airtable'a yazılmıyordu. Bir alert
> Telegram'da kaydırılıp gittiğinde geriye yalnız `stage='handoff'` (sebebi söylemez) ve 18 sınıfın
> 6'sında `gcal_event_id` kalıyordu. Yalnız Airtable okuyan bir dashboard **sebebi göremezdi**.
>
> **Şimdi:** `Send Owner Alert (Telegram)` **başarı** çıkışı → `Alert Context` → `Find Conversation Row`
> → **`Record Alert Class`** her **teslim edilmiş** alert'i `conversations.last_alert_class` +
> `last_alert_at` alanlarına yazıyor. Dashboard artık takılı bir konuşmanın **neden** takıldığını
> Airtable'dan okuyabiliyor.
>
> **Dürüst sınırlar (tasarımın bilmesi gerekenler):**
> 1. **Yalnız TESLİM EDİLMİŞ alert yazılır** (Codex #5). Telegram gönderimi patlarsa alan **boş kalır** —
>    ve boş olan **doğru** bilgidir. Dashboard asla "sahip haberdar edildi" demez, edilmemişken.
> 2. **Throttle'da yazılmaz** — composer `[]` döndüğü için alan güncellenmez (F4).
> 3. **Son değer, geçmiş değil** — sonraki bir sınıf öncekini ezer. Tam transkript ertelendi (§9 K1).
> 4. **Satır ZATEN VAR olmalı** (Codex #4). Upsert kullanılmıyor: widget'ta `sender_key` istemci
>    kontrolündeki `sessionId`'den türüyor, ve **şekil varlık kanıtı değildir** — upsert, yalnız-metadata
>    çöp satır yaratılmasına izin veriyordu. Arama 0 sonuç dönerse **hiçbir şey yazılmaz** (alert yine
>    Telegram'a gider). Bedeli: konuşma satırı olmayan alert'ler (`normalize_drift`, ilk-temas spend-cap)
>    Airtable'da **iz bırakmaz**.
> 5. **Kimlik sınırı değişmedi:** widget `sessionId`'sini bilen biri o oturumu taklit edebilir — bu
>    CP4a'dan beri kayıtlı, kabul edilmiş bir T1 limiti (README "session-token gücü, doğrulanmış kimlik
>    değil"), A2'nin getirdiği bir açık değil. A2'nin kapattığı şey, **başka** bir anahtara yazabilme
>    ve satır uydurabilme idi.
> 4. **"Çözüldü" işaretleme mekanizması hâlâ YOK** — alan son durumu tutar, sahip "hallettim" diyemez.

### 4.d — Sistem sağlığı

**12 anahtar** (bugün hepsi n8n içindeki `Load Config` Code node'unda **hard-coded literal** —
değiştirmek n8n editöründe kod düzenlemek demek; `client.config.example.json` henüz **bağlı değil**):

| Anahtar | Varsayılan | Okuyan node | Etkisi |
|---|---|---|---|
| `bot.killSwitch` | `false` | `Check Bot Guards` · `Kill-Switch Gate` (reminders) | acil durdurma → hepsi devir |
| `bot.dryRun` | `false` | `Live Booking?` · `Live Send?` | gerçek yazma yok |
| `bot.whatsappSendDisabled` | `true` | `Send Disabled?` (**yalnız reminders**) | hatırlatma göndermez |
| `ownerAlert.enabled` | `true` | `Build Owner Alert` (×2) | **false → tüm alert'ler sessizce durur** |
| `ownerAlert.throttleMinutes` | `30` | aynı | alert penceresi |
| `channels.widget.turnstile.enabled` | `true` | `Turnstile Gate` | bot koruması |
| `bot.llmCostCapUsd` | `10.00` | `Eval Spend` · `Spend Gate` | aylık sert tavan |
| `bot.confidenceThreshold` | `0.7` | `Confidence & Intent Gate` | altı → devir |
| `bot.maxTurnsPerConversation` | `12` | `Check Bot Guards` | tur tavanı |
| `bot.reminderHoursBefore` | `24` | `Compute Reminder Window` | hatırlatma penceresi |
| `bot.sessionGapMinutes` | `30` | `Build Reply Payload` | "Welcome back!" eşiği |
| `bot.cancellationCutoffHours` | `2` | `Cancel Lookup` · `Reschedule Lookup` (+validate) | iptal/erteleme kesim saati |

**Spend metresi:** `bot_metrics` (`period_key` aylık · `cost_usd` · `updated_at`). LLM'den **önce**
okunur, **sonra** artırılır. Okuma/yazma patlarsa **fail-OPEN** (LLM çalışır) +
`spend_meter_unavailable` alert. Eşzamanlı turlarda TOCTOU kabul edilmiş — yumuşak fren, atomik
defter değil.

**Ekranda olması gerekenler:** kill-switch/dry-run durumu (ve **kim ne zaman açtı** — bugün kayıtlı
değil, 🕳) · spend metresi (`cost_usd` / `llmCostCapUsd`, bu ay) · son hatalar (🕳 **kaynak yok** —
n8n execution log'u dışında sorgulanabilir bir yer yok) · açık flag'ler (🕳 4.c'deki aynı problem).

### 4.e — Config anahtarlarının şema durumu (Phase 6'nın "config-wired" hedefi için)

| Anahtar | `Load Config` (canlı) | `client.config.example.json` | `client.config.schema.json` |
|---|---|---|---|
| `ownerAlert.*` | ✅ | ❌ | ❌ |
| `channels.widget.turnstile.enabled` | ✅ | ❌ | ❌ (`additionalProperties:false` → **eklenirse şema patlar**) |
| `bot.whatsappSendDisabled` | ❌ (main'de yok) | ✅ | ✅ |
| `messageTemplates.reminder` | ❌ (main'de yok — reminders wf'de ✅) | ✅ | — |

Phase 6 "config-driven"ı gerçekten bağlayacaksa bu tablo önce kapatılmalı.

---

## §5 — Aksiyon sözleşmesi (mimari şart — pazarlıksız)

> **Kural:** Dashboard'daki her **yıkıcı** aksiyon (iptal · erteleme · devri devralma) **doğrudan
> Google Calendar'a veya Airtable'a DOKUNMAZ.** n8n'deki mevcut korumalı yoldan geçer.

**Gerekçe:** üç denetim turunda (CRT #8 · Codex CRT #3 · CP5e) kurulan korumaların **tamamı** o
yolun içinde yaşıyor: hedef doğrulama (`Validate Cancel Target` — gid şekli, `calendar_id`,
`sender_key` sahipliği) · cutoff kontrolü · confirm-TTL (`confirm_turn`) · yapısal 404/410
sınıflandırması (metne bakmadan) · orphan yönetimi · write-then-verify · owner-alert. Dashboard'dan
doğrudan Airtable'a yazan bir "İptal" butonu bunların **hepsini tek tıkla baypas eder** ve
`gcal_event_id` GCal'da yaşamaya devam eder — yani müşteri iptal ettiğini sanır, berber randevuyu
takviminde görmeye devam eder.

### Aksiyon → mevcut yol eşlemesi

| # | Dashboard aksiyonu | Yıkıcı mı | Mevcut n8n yolu | Durum |
|---|---|---|---|---|
| 1 | Randevu iptal | ✅ | `Cancel Lookup` → `Validate Cancel Target` → `Build Cancel-Confirm State` → `Verify Confirm Live` → GCal delete → `Update Appointment Cancelled` | ⚠ **var ama erişilemez** — yalnızca `/webhook/barber-inbound` üzerinden, **müşteri kimliğiyle**, iki turlu "yes" onayıyla. Sahip için giriş noktası **YOK** → **yeni yol gerekiyor** |
| 2 | Randevu ertele | ✅ | `Reschedule Lookup` → … → insert + eski event delete | ⚠ aynı — **yeni yol gerekiyor** |
| 3 | Devri devralma (`stage=handoff` kilidini açma) | ✅ (müşteriye bot cevabı geri açar) | **hiçbir yol yok** — hiçbir node `handoff` stage'ini temizlemiyor | ⛔ **CANLI KUSUR** → §9 K6: **Phase 6'da yapılacak**, tek yazma istisnası (yalnız `stage`'i `new`'e döndürür; takvime/randevuya dokunmaz, geri alınabilir) |
| 4 | Alert'i "çözüldü" işaretleme | ❌ | **hiçbir yol yok**, saklanacak alan da yok | ❌ **yeni yol gerekiyor** (§9 karar 1) |
| 5 | Müşteriye elle mesaj ("Reply" butonu) | ❌ ama **dışa dönük** | `Send WhatsApp (Zernio)` var ama yalnızca outbound zincirinin içinde | ❌ **yeni yol gerekiyor** — ⚠ **güvenlik**: keyfi numaraya mesaj attırabilen bir endpoint, `Reject Unsigned Request`'in converged edilmeme sebebinin (D-b3 "message-trigger primitive") ta kendisidir. Tasarımı bu riski bilerek yapılmalı |
| 6 | Kill-switch / dry-run çevirme | ✅ (sistem geneli) | config n8n Code node'unda hard-coded | ❌ **yeni yol gerekiyor** |
| 7 | Lead durumu değiştirme | ❌ | — | ✅ doğrudan Airtable yazımı kabul edilebilir (yıkıcı değil, dış sistem yok) |
| 8 | Randevu / lead **okuma** | ❌ | — | ✅ doğrudan Airtable okuma |

**Sonuç: 6 aksiyonun 6'sı için yeni bir korumalı yol gerekiyor.** Bu belge o yolu **tasarlamaz** —
sadece "sessizce doğrudan yazma" seçeneğinin kapalı olduğunu tespit eder.

**Karara bağlandı (§9 K6):** Phase 6'da yalnızca **#3 (devir kilidini açma)** yapılır — canlı kusur
olduğu ve en düşük riskli yazma olduğu için. **#1/#2 (iptal/erteleme) Phase 7'ye**, kendi
Critical-Review Target'ları ile. #5 (elle mesaj) ve #6 (kill-switch çevirme) kapsam dışı kalır.

---

## §6 — Deploy topolojisi (karar verildi)

| Yüzey | Nerede | Neden |
|---|---|---|
| Public berber demo sitesi (landing) | **Vercel** | vitrin; herkese açık olmalı |
| Gömülebilir widget snippet | **Vercel** | müşteri sitesine gömülecek; CDN gerekir |
| **Dashboard** | **Yigitcan'ın sunucusu, Cloudflare Access arkasında** | **CRT #9'u (dashboard auth) bedavaya çözer** — auth katmanı yazmaya gerek yok; müşteri PII'si üçüncü tarafa gitmez |

Bu, n8n control-plane'inde zaten kanıtlanmış desenin aynısı (CRT #7, 2026-08-26 kapandı): editör +
`/rest` → Access login; `/api` → Access **Service Auth** token; **`/webhook/*` public ve muaf**
(probe ile doğrulandı). Yani **widget'ın n8n'i çağırması için hiçbir Cloudflare kimlik bilgisi
gerekmez** — widget'ın çevre savunması Turnstile + edge rate-limit'tir, Access değil.

> ⚠ Access politikası tuzağı (kayıtlı ders): catch-all `/` Allow app'i `/api`'yi de yutar. Bir
> host'u catch-all Access'e alırken **her otomasyon yolunun daha spesifik bir app'i önceden
> kurulmuş olmalı**, yoksa otomasyon anında ölür. Dashboard'ı Access arkasına alırken aynı hata
> tekrarlanmamalı.

### TAŞINABİLİRLİK KISITI (bağlayıcı)

**Vercel'e özgü hiçbir şey kullanılmayacak.** Yasak: edge functions/middleware'e bağımlı mimari ·
Vercel KV / Postgres / Blob · Vercel-only image pipeline · Vercel Cron.

**Tüm n8n/Airtable erişimi kendi API katmanımızın arkasında olacak** — hiçbir tarayıcı kodu
doğrudan Airtable'a veya n8n `/api`'sine gitmez. Bu hem güvenlik (Airtable PAT tarayıcıya
inmemeli) hem taşınabilirlik gereği.

**Sonuç:** iki yön (Vercel ↔ kendi sunucu) arasında geçiş bir **redeploy meselesi** olur, bir
yeniden yazım değil. Dashboard bugün kendi sunucuda; yarın müşteriye satılırken Vercel'e taşınmak
istenirse kod aynı kalır.

---

## §7 — Veri katmanı gerçeği

### Ne yok

**DB yok, Airtable var.** Eksik olanlar — ve bunlar **zaten iki kez kayıtlı**:

| Eksik | Sonuç | Kayıt |
|---|---|---|
| Unique constraint | booking'de atomik çift-kayıt engeli yok → write-then-verify ile **daraltılmış**, kapatılmamış TOCTOU | CRT #8 / CP2b — "best-effort, NOT an atomic lock" |
| Transaction | GCal + Airtable arası bütünlük yok → `mirror_failed`, `orphan_event` sınıfları bu yüzden var | `.claude/rules/booking-integrity.md` |
| Atomik compare-and-swap | dedupe `search → create` atomik değil; **eşzamanlı** çift teslimat çift işlenebilir | Codex CRT#3 **M1b** — "kabul edilmiş T1 limiti, gerçek çözüm T1→T2 tier sıçraması, Phase 8" |

Bunların hiçbiri bu belgede çözülmez. **Dashboard'ın görevi bunları gizlemek değil, görünür
kılmaktır** (§4c).

### Phase 6 için SOMUT risk: Airtable API rate limit

**Naif bir dashboard sayfa açılışında kaç okuma yapar? (türetilmiş tahmin — kısıt bunu YASAKLAR, bkz. altta)**

| Panel | Tablo | İstek | Not |
|---|---|---|---|
| Bugünün randevuları | `appointments` | 1 | `start_utc` aralık filtresi |
| Yaklaşan randevular | `appointments` | 1 | ayrı filtre → ayrı istek |
| Lead'ler | `leads` | 1 | |
| Devir kuyruğu | `conversations` | 1 | `stage='handoff'` filtresi |
| Spend metresi | `bot_metrics` | 1 | dönem satırı |
| **Toplam** | | **~5 istek / sayfa açılışı** | = saniyelik bütçenin **tamamı** |

Bot aynı anda çalışırken **tek bir müşteri turu** şu Airtable çağrılarını yapar: `Check Processed`
(1) · `Load State` (1) · `Read Spend` (1) · `Save State` (1) · `Record LLM Spend` (1) ·
`Record Processed` (1) — **booking turunda ek olarak** `Write Appointment` (1) ve iptal/erteleme
turunda `Find Booking` + `Update…` (2). Yani **tur başına 6-9 istek**.

**Sıkışma senaryosu:** dashboard'ı açık tutan sahip + aynı anda 1-2 aktif sohbet turu → aynı base
üzerinde **11-14 istek/saniye**, limitin 2-3 katı.

### Airtable'ın sert limiti (DOĞRULANDI — Airtable resmi dokümanı, sahip teyidi 2026-08-27)

| Gerçek | Değer |
|---|---|
| İstek limiti | **5 istek / saniye / base** |
| Plana göre değişir mi | **HAYIR — tüm planlarda sabit** |
| Yükseltilebilir mi | **HAYIR** |
| Aşımda ne olur | **429** + **30 saniye** bekleme cezası |

> ### ⛔ Bu bir performans konusu değil, bir KESİNTİ riski
> Ceza **base geneline** uygulanır ve **30 saniye** sürer. Yani dashboard'ın taşırdığı bir saniye,
> **botu 30 saniye boyunca yere serer**: `Load State` patlar → `Load State Errored?` →
> `Send Error Response` (503) → müşteri "bir ekip üyesi dönecek" mesajı alır ve `state_unavailable`
> alert'i düşer. **Sahibin dashboard'ı açması, müşterinin randevu alamamasına sebep olur.**
>
> Bütçe matematiği acımasız: saniyede **5** hakkımız var. Naif dashboard sayfası **~5 istek**
> (üstteki tablo) — tek başına saniyenin tamamını yer. Aynı anda tek bir bot turu **6-9 istek**
> istiyor. Yani **naif tasarım + tek aktif sohbet = garanti 429.**

### TASARIM KISITI (bağlayıcı — Phase 6 bunu ihlal edemez)

1. **Sayfa başına TEK TOPLU okuma.** Dashboard'ın bir sayfa açılışı **tek bir** Airtable okuma
   turu yapar; panel başına ayrı istek yok.
2. **Satır başına ayrı istek KESİNLİKLE YOK.** 20 randevu için 20 istek = anında 429 + 30 sn bot
   kesintisi. Her satırın verisi toplu okumadan gelir; "detay için tıkla" ayrı çağrı yapmaz,
   zaten çekilmiş veriyi açar.
3. **Otomatik yenileme YOK.** Sahip elle yeniler. Polling yapan bir dashboard, botu kalıcı olarak
   429 sınırında tutar.
4. **Bot'a öncelik.** Kendi API katmanımız (§6) dashboard okumalarını bot turlarının **arkasına**
   alır. Yavaş dashboard kabul edilebilir; düşen bir booking değil.
5. **Kısa TTL cache** kendi katmanımızda (30-60 sn) — sahibin arka arkaya yenilemesi Airtable'a
   yansımaz.
6. **Sayfalama** — tablolar ilk N satırı gösterir; "daha fazla" ayrı ve **isteğe bağlı** bir tur.

> Kısıt 1 ve 2, §6'daki "kendi API katmanı" kararının teknik gerekçesidir: tarayıcı doğrudan
> Airtable'a gitseydi istek sayısını kimse denetleyemezdi.

### DB'ye geçiş TETİKLEYİCİLERİ (karar sürüklenmesin)

Aşağıdakilerden **biri** gerçekleşirse T1→T2 tier sıçraması (Postgres + unique constraint) gündeme
alınır. Bu üçü olmadan **Airtable'da kalınır** — erken karmaşıklık yasak:

| | Tetikleyici | Neden bu eşik |
|---|---|---|
| **a** | Canlıda **gerçek bir çift-booking** gözlenmesi | write-then-verify'ın yetmediğinin kanıtı; CRT #8'in kabul edilmiş kalıntısının gerçekleşmesi |
| **b** | Airtable rate limit'e **çarpılması** (bot turu veya dashboard 429 alması) | 5 rps sabit ve **yükseltilemez** — okuma azaltmaları tükendiğinde geriye tek seçenek veri katmanını değiştirmek kalır |
| **c** | **Çok-personel / çok-şube** isteyen müşteri | takvim başına kaynak, çakışma matrisi — Airtable'ın ifade edemeyeceği model |

---

## §8 — Boşluklar ve çelişkiler

> Bu bölüm **çözüm önermez, listeler.** Kararlar §9 ve sonraki fazlarda.

### 8.1 — ⚠ BULGU: sistem çelişkileri (envanterden çıktı, hepsi doğrulandı)

**#1 — `cancel_mirror_failed` sessizce yutuluyor. (kural ihlali)** ✅ **KAPANDI (FIX-1, 2026-08-27)**
— `Build Cancelled State` → `Build Owner Alert` kenarı eklendi + sınıf zincirine ayrı
`cancel_mirror_failed` sınıfı eklendi. **Canlı drill ile kanıtlandı** (F1: `_alert_class=cancel_mirror_failed`,
Telegram node'u çalıştı, müşteri cevabı değişmedi; F2 kontrol: normal iptalde alert yok).
`Build Cancelled State` bu bayrağı set ediyor, ama: (a) node'un tek çıkışı `Save State (Post-Write)`
— `Build Owner Alert`'e kenarı yok; (b) `Build Owner Alert`'in sınıf zincirinde
`cancel_mirror_failed` kontrolü yok; (c) branch `stage:'cancelled'` yazdığı için `stage==='handoff'`
catch-all'una da düşmüyor. **Sonuç:** GCal'dan silme başarılı ama Airtable güncellemesi patlarsa
ne alert var ne kalıcı kayıt — Airtable randevuyu `booked` göstermeye devam eder, hatırlatma bile
gidebilir. Kardeş vakalar (`mirror_failed`, `reschedule_mirror_failed`) alert veriyor; bu üçlüde
tek boşluk. `.claude/rules/n8n-conventions.md` "failures must be VISIBLE" ihlali.

**#2 — `Build Spend-Cap Reply` denetlenmeyen 12. converged çıkış.** ✅ **KAPANDI (FIX-1)** —
`scripts/check-outbound-inventory.py` `CONVERGE` listesine eklendi (guard artık **12** dal sayıyor);
**3 sabotaj vakasıyla FAIL-edebilirliği kanıtlandı** (should_send · kenar · status).
12 dal `Finalize Outbound`'a giriyor; `scripts/check-outbound-inventory.py`'nin `CONVERGE` listesi
11 tanesini sayıyor. Node doğru çalışıyor (200 · `should_send:true` · `handoff`) ama drift-guard
onu korumuyor — biri `_outbound_should_send`'i bozarsa guard yakalamaz.

**#3 — `docs/DATA-MODEL.md` bayat (iki yerde).** ✅ **KAPANDI (FIX-1)** — stage enum'u 9 gerçek
değere güncellendi (`done` kaldırıldı), 4 belgesiz alan + K1'in 2 yeni alanı belgelendi.
(a) stage enum'u `new\|collecting\|ready\|done\|handoff` diyor; gerçek 9 değer —
`confirming · booked · cancel_confirming · cancelled · reschedule_confirming` belgesiz, `done`
hiçbir zaman yazılmıyor. (b) `conversations` tablosunda workflow'un yazdığı ama belgede olmayan
4 alan: `gcal_event_id · cancel_target_id · confirm_turn · computed_reply`.

**#4 — TASARIM ZATEN SİSTEMİ AŞMIŞ — bu belgenin varlık sebebi.** ✅ **KAPANDI (FIX-1)** —
mockup'tan "Outside working hours" kartı (ve sahipsiz kalan `.msg.hours` CSS kuralı) silindi;
`outsideHours` + `greeting` **ölü config anahtarları** hem `client.config.example.json`'dan hem canlı
`Load Config`'ten kaldırıldı (K5). Tam regresyon **26/26** — hiçbir node onları kullanmıyormuş.
`design/mockups/variants/widget-a-cream-ink.html:217-218` "Outside working hours" balonunu
`messageTemplates.outsideHours` metniyle gösteriyor. O template **ölü**: tüm workflow'da tek geçişi
`Load Config` tanımı; hiçbir node üretmiyor. Aynısı `greeting` için de geçerli (tanım + bir sticky
note; dönen-müşteri selamı `Build Reply Payload` içinde hard-coded `"Welcome back! "`). Yani Phase 1
mockup'ı, sistemin **hiç göndermediği** bir ekranı müşteriye vaat ediyor.

**#5 — `conversations` için TTL yok.** ✅ **KAPANDI (FIX-1) — SINIRLI OLARAK.**
Purge workflow'una ikinci dal eklendi (`Compute PII Cutoff` → `Find Stale Conversations` →
`Scrub Recent Messages`): 30 günden eski satırlarda `recent_messages` **boşaltılır**, satır **korunur**.
**OVERCLAIM YASAK — bu "PII TTL çözüldü" DEĞİLDİR:** temizlenen şey **mesaj içeriğidir**;
`sender_key` whatsapp'ta **telefon numarası içerir** ve satır durdukça **süresiz kalır**. Satır silme,
`stage='handoff'` kilidini sessizce açacağı ve `cancel_target_id`/`confirm_turn` state'ini düşüreceği
için **AYRI bir karardır**.
`docs/DATA-MODEL.md` `last_updated`'ı "for TTL/expiry" diye tarif ediyor; purge workflow'u
**yalnızca** `processed_messages` siliyor (30 gün). `recent_messages` (PII — son 5 müşteri mesajı)
süresiz duruyor. Belge var olmayan bir mekanizmayı ima ediyor.

**#6 — `customers` tablosu belgeli ama ölü.** ✅ **KAPANDI (FIX-1)** — `docs/DATA-MODEL.md`'den
gerekçesiyle çıkarıldı. Airtable'daki boş tablo **silinmedi** (geri alınamaz, hiçbir şeyi bozmuyor).
3 workflow JSON'unda tek referans yok. CP6 kararı zaten düşürmüş ("returning-customer greeting uses
`conversations.found` + session-gap"). `docs/DATA-MODEL.md` hâlâ tarif ediyor.

**#7 — kill-switch ↔ max-turns müşteriye ayırt edilemez.** ⏸ **AÇIK — bilinçli.** Bugün bir hata
değil (sahip tarafında KK2 ile ayrışıyor); tasarımın bunu bilmesi yeterli.
İkisi de `Check Bot Guards` false dalından aynı `Handoff Reply`'a, aynı template'e gidiyor. Sahip
tarafında ayrışıyor (KK2: kill-switch susturulur, max-turns `max_turns` alert'i verir) — yani ayrım
**yalnızca alert katmanında** var, cevapta yok. Şu an bir hata değil, ama tasarımın bilmesi gerek.

**#8 — widget 400/503'te metinsiz kalıyor.** ⏸ **Phase 6'ya bağlandı** — §9 K4'teki somut kural
(400→`notUnderstood`, 503→`handoff`) frontend'de uygulanacak; motor değişmiyor.
`Send Reject Response` (400) ve `Send Error Response` (503) gövdesinde `reply` anahtarı yok;
WhatsApp tarafı `_outbound_reply` ile metin alıyor, widget almıyor. Motor bu iki durumda widget'a
ne göstereceğini söylemiyor.

**#9 — `docs/FLOW-DIAGRAM.md` CRT#7'yi hâlâ "OPEN" yazıyor.** ✅ **KAPANDI (FIX-1)** — pasaj probe
kanıtlarıyla CLOSED'a çevrildi ve neden bayat kaldığı not edildi (`governance-sync.md` kural 6).
`docs/ROADMAP.md` ve `docs/ARCHITECTURE-DECISIONS.md` aynı gün (2026-08-26) probe kanıtıyla
"CLOSED" demiş. Doküman-senkron boşluğu (`governance-sync.md` kural #6).

### 8.2 — Yüzeysiz kalanlar (envanterde var, hiçbir ekranda yok)

| Ne | Bugün nerede | Boşluk |
|---|---|---|
| **17 residue bayrağı** (`orphan_event`, `mirror_failed`, `verify_unavailable`, `reconcile_unresolved`, `reconcile_conflict`, `cancel_delete_failed`, `cancel_needs_human`, `zernio_send_failed`, `reply_fallback`, `normalize_drift`, `dedupe_marker_failed`, `spend_cap_tripped`, `spend_meter_unavailable`, `state_unsaved`, `reschedule_orphan`, `reschedule_mirror_failed`, `race_lost`) | yalnız Telegram + n8n execution log | **sorgulanabilir ev yok** → dashboard 4.c'nin temel problemi |
| **21 alert sınıfının hiçbiri** için "çözüldü" işareti | — | mekanizma da alan da yok (sınıf+zaman artık kayıtlı, ama "hallettim" işareti değil) |
| **`Idempotent Replay` (200)** widget ekranı | — | tanımsız |
| **`Send Reject Response` (400)** widget ekranı | — | tanımsız (BULGU #8) |
| **`Send Error Response` (503)** widget ekranı | — | tanımsız (BULGU #8) |
| **`Reject Bot Request` (403 turnstile)** widget ekranı | — | tanımsız |
| **Normalize reject (400 widget)** ekranı | — | tanımsız |
| **Edge rate-limit (429/blok)** widget ekranı | — | tanımsız |
| **Offline / n8n erişilemez** durumu | — | tanımsız (`PHASE-6-BACKLOG.md` §1) |
| **Sıfır durumları** (0 randevu / 0 lead / 0 devir) | — | tanımsız (`PHASE-6-BACKLOG.md` §1) |
| **`stage='handoff'` kilidini açma** | hiçbir yol yok | ⛔ **CANLI KUSUR** (eksik özellik değil) — devredilen müşteri sonsuza dek susturulmuş. → §9 K6: Phase 6'da tek yazma istisnası |
| **"Son hatalar" ekranı** için veri kaynağı | n8n execution log | dışarıdan sorgulanabilir değil |
| **Kill-switch/dry-run'ı kimin ne zaman açtığı** | kayıtlı değil | denetim izi yok |
| **`ownerAlert.enabled=false`** durumu | sessizce tüm alert'leri keser | sahibin bunu görebileceği bir yer yok |

### 8.3 — Şema / config boşlukları

`ownerAlert.*` ve `channels.widget.turnstile.enabled` canlı config'de var ama
`client.config.example.json` ve `client.config.schema.json`'da **yok**; şema
`additionalProperties:false` olduğu için bugün eklenirse **doğrulama patlar**. Phase 6'nın
"config-wired" hedefi (`PHASE-6-BACKLOG.md` §6) bu kapatılmadan gerçekleşemez.

---

## §9 — Kararlar (KAPANDI — Yigitcan, 2026-08-27)

Bu bölüm artık açık soru içermiyor. Her karar bağlayıcıdır; uygulaması "Phase 6 öncesi düzeltme
turu" ve Phase 6 planına dağıtılmıştır.

### K1 — Devir kuyruğu kaynağı → **conversations satırına iki alan**

**Karar:** yeni tablo YOK, tam transkript YOK. Mevcut `conversations` satırına **iki alan**:

| Alan | İçerik |
|---|---|
| `last_alert_class` | son alert'in sınıfı (21 sınıftan biri) |
| `last_alert_at` | ne zaman düştüğü (UTC) |

Yazım **alert dalından, best-effort** — yani `Build Owner Alert` tarafından, **cevap yolundan
ayrı**. D-c değişmezi korunur: alert yolundaki bir hata müşteri cevabını asla etkilemez.

**Neden C değil (belgenin önerisi reddedildi, gerekçesi kayıt altında):** sebebi göremeyen bir
devir kuyruğu yarım kalır. Sahip "bu konuşma neden takıldı?" sorusunu Telegram'da aramak zorunda
kalırsa dashboard'ın varlık sebebi ortadan kalkar. İki alan 18 residue sınıfının **hepsini**
kapsar ve şema riski minimumdur.

**Kalan sınır (dürüstlük):** bu "son alert"tir, alert **geçmişi** değil. Aynı konuşmada arka arkaya
iki farklı sınıf düşerse ikincisi birincinin üstüne yazar. Kabul edilmiş — tam transkript/geçmiş
ertelendi.

### K2 — Landing kapsamı → **odaklı bot vitrini**
Tam salon sitesi (harita · arama butonu · yorumlar · galeri) **kapsam dışı**.
`docs/PHASE-6-BACKLOG.md` §4 böylece kapanır.

### K3 — Dashboard veri erişimi → **kendi API katmanı**
Tarayıcı **asla** doğrudan Airtable'a gitmez; Airtable PAT'ı tarayıcıya inmez. §6 taşınabilirlik
kısıtı + §7 kısıt 1/2/4 yalnızca bu katmanda uygulanabilir.

### K4 — Widget 400/503 metni → **config template (mevcut anahtarlar, YENİ anahtar YOK)**

Motor değişmez (`reply` anahtarı eklenmez).

**Somut kural (Phase 6'da uygulanacak):**

| Durum | Widget'ın göstereceği metin |
|---|---|
| `Send Reject Response` → **400** `invalid_payload` | `messageTemplates.notUnderstood` |
| `Send Error Response` → **503** `state_unavailable` | `messageTemplates.handoff` |

**Neden yeni anahtar eklenmiyor:** WhatsApp tarafı bu iki durumda **zaten** tam olarak bu iki
anahtarı gönderiyor (`_outbound_reply`, CP4b-1 ruling'i). Widget aynı anahtarları okuyunca iki kanal
tek metin kaynağında birleşir. Dahası: tüketicisi (frontend) henüz yokken yeni bir anahtar eklemek,
K5'te az önce sildiğimiz tuzağın aynısını yaratırdı — hiçbir şey yapmayan bir config anahtarı.
Bu yüzden K4 **düzeltme turunda repo değişikliği yapmaz**; Phase 6'da tüketicisiyle birlikte gelir.

### K5 — `outsideHours` + `greeting` → **tasarımdan çıkar + ölü config anahtarlarını TEMİZLE**
Mockup'taki "Outside working hours" durum kartı silinir. Motor değişmez — bot 7/24 cevap verir ve
bu doğru davranıştır (kapalıyken de randevu alınabilmeli).

**Ek karar (belgenin önerisini genişletir):** ölü config anahtarları da **silinir**.
Gerekçe: hiçbir şey yapmayan bir config anahtarı, tekrar satılabilir bir template'te **sonraki
müşteri için tuzaktır** — birisi `outsideHours` metnini değiştirir, hiçbir şey olmaz, ve neden
olmadığını anlamak için motoru okumak zorunda kalır.

### K6 — Phase 6 kapsamı → **salt-okunur + devir kuyruğu, TEK yazma istisnası ile**

**İstisna: "devir kilidini serbest bırak" yazma aksiyonu Phase 6'DA olacak.**

**Gerekçe (belgenin önerisini düzeltir):** §5'te tespit edilen "`stage='handoff'` kilidini açacak
hiçbir yol yok" bulgusu **eksik özellik değil, CANLI KUSURDUR**. Devredilen müşteri bugün
**sonsuza dek susturulmuş** durumda: her mesajına `handoffLocked` cevabı gider, bot bir daha asla
devreye girmez ve kilidi açacak hiçbir arayüz yoktur.

Bu aynı zamanda **en düşük riskli yazma**: `conversations.stage`'i `new`'e döndürür. Takvime
dokunmaz, randevuya dokunmaz, dış sisteme dokunmaz, geri alınabilir.

**İptal / erteleme yazmaları Phase 7'ye kalır** — kendi Critical-Review Target'ları ile.

### K7 — BULGU #1 zamanlaması → **Phase 6'dan ÖNCE, ayrı küçük fix turu**
Onaylandı. §8'deki doküman/guard düzeltmeleri ve K1/K4/K5'in repo tarafı aynı tura alınır.
Detaylar: "Phase 6 öncesi düzeltme turu" planı.

---

## §10 — Kararların uygulama dağılımı

| Karar | Nerede uygulanır |
|---|---|
| K1 iki alan (`last_alert_class`/`last_alert_at`) | düzeltme turu (Airtable alan + `Build Owner Alert` yazımı) |
| K4 400/503 config template'leri | düzeltme turu (config + şema) |
| K5 ölü anahtar temizliği | düzeltme turu (config + `Load Config`) |
| K7 = BULGU #1 · #2 · #3 · #5 · #6 · #9 | düzeltme turu |
| K2 landing kapsamı · K3 API katmanı · K6 salt-okunur + kilit açma | **Phase 6** `/plan-flow` |
| İptal/erteleme yazma yolları | **Phase 7** + kendi CRT |
| §7 Airtable kısıtları (1-6) | **Phase 6** — bağlayıcı kabul kriteri |

### §10.1 — Kabul edilen ama ADLANDIRILMIŞ kalıntı: hatırlatma penceresi

FIX-1, BULGU #1'i **görünür** yaptı — **engellemedi**. Tam pencere:

> Bir randevu, başlangıcından **24 saat ile 2 saat (`cancellationCutoffHours`) ARASINDA** iptal edilir,
> **Airtable mirror yazımı patlar**, ve **hatırlatma henüz gönderilmemiştir** → müşteri, **iptal ettiği**
> randevu için hatırlatma alır.

"Sahip önce görür" argümanı **bu pencerede zayıftır**: sahibin ≤1 saati vardır ve müsait olmayabilir.

Olasılık düşük (hem bir Airtable arızası hem de o dar zaman aralığı gerekir), bu yüzden **şimdi
düzeltilmedi**. Ama belirsiz bir "kabul edilmiş limit" olarak geçiştirilmedi — `docs/ROADMAP.md`
Phase 7 satırına **adlandırılmış madde** olarak girdi: *"reminders: gönderim öncesi GCal event
varlığı doğrulaması (cancel-mirror-failed penceresi)"*.

**Canlı kanıt:** FIX-1'in F1 drill'i tam bu durumu üretti — GCal event'i silindi, Airtable satırı
`booked` kaldı, `start_utc` 24 saatin içindeydi (yani hatırlatma adayıydı). Drill sonrası elle
temizlendi.

---

## Kapanış — bu belge neyi garanti eder

Phase 6 tasarımı bundan sonra **§2'deki 10 akışı, §3'teki 18 çıkışı ve §4'teki 21 alert sınıfını**
kaynak olarak alır. Bir ekran bu belgede yoksa, sistemde de yoktur — ve tasarıma girmesi için önce
**"YENİ — gerekçesi şu"** olarak buraya girmesi gerekir.

§8'deki 9 bulgu ve 14 yüzeysiz kalem, tasarımın **bilerek** boş bırakacağı yerlerdir; sessizce
atlanan yerler değil. §9'daki 7 karar 2026-08-27'de kapandı; §10 hangisinin nerede uygulanacağını
söyler. §7'deki 6 Airtable kısıtı Phase 6 için **bağlayıcı kabul kriteridir**.
