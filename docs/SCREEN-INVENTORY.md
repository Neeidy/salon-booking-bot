# EKRAN ENVANTERİ — Phase 6 tasarım brief'i

> **Rolü:** Claude Design'ın **TEK girdisi**. Phase 6'nın başlangıcı değil, **girdisi**.
> Tarih: 2026-08-31 · Türetildiği kaynak: `docs/UX-ARCHITECTURE.md` (birincil) ·
> `n8n/workflow.sanitized.json` (177 node) · `workflow.reminders.sanitized.json` (19) ·
> `workflow.purge.sanitized.json` (15) · `config/client.config.example.json` ·
> `docs/DATA-MODEL.md` · `design/mockups/variants/*-a-cream-ink.html`

---

## §0 — Amaç, kural, görsel dil

### Neden bu belge var

Tasarımı Claude Design üretecek. Design sistemin gerçekte ne ürettiğini **bilmez**. "Salon booking
sistemi tasarla" dersek 12 reply exit'i, 24 alert sınıfını, 9 stage'i bilmeden çizer — ve bu projede
bir kez yaşanmış olan tasarım-sistem uyuşmazlığı tekrarlanır. (Kanıt: Phase 1 widget mockup'ı,
motorda **hiç üretilmeyen** bir "Outside working hours" ekranı gösteriyordu; FIX-1'de silindi.)

### KURAL (bağlayıcı)

1. **Bu belgede olmayan ekran tasarlanmaz. Bu belgede olan her ekran tasarlanır.**
2. Her ekran ya `docs/UX-ARCHITECTURE.md`'deki bir maddeye ya da canlı sisteme dayanır; kaynağı
   (dosya + node + template) gösterilir.
3. Kaynağı olmayan ekran §7'ye **"YENİ — gerekçesi şu"** etiketiyle girer; sessizce eklenmez.
4. Doğrulanamayan hiçbir şey iddia edilmez — **DOĞRULANAMADI** yazılır.

### Tur A yöntem kararı (Yigitcan, 2026-08-31 — grup 1 kabulünde)
İçerik iskeletini (envanter eşleşmesi + birebir metinler + kaynak yorumları + token disiplini)
**dört grup için de CC üretir**; **Design cilası EN SONA, tek seferde** yapılır — bütün bir dil
verilir, parça parça değil. (Sebep: Design canvas formatı repo'daki "tek başına açılır statik
HTML" sözleşmesiyle uyumsuz çıktı; görsel yükseltme ayrı ve bütüncül bir tur olacak.)

### Görsel dil — SIFIRDAN BAŞLAMA, MEVCUDU GENİŞLET

Onaylı yön: **Direction A "Cream & Ink"**. Üç mockup'ın `<style>` bloğundaki `:root` bu dilin
kaynağıdır (`landing-a-cream-ink.html:23-37` ve widget/dashboard'da birebir aynısı):

| Token | Değer | Not |
|---|---|---|
| `--cream` | `#F1EEE6` | kâğıt zemin |
| `--ink` | `#16150F` | = `branding.primaryColor` |
| `--oxide` | `#B4472E` | = `branding.accentColor` |
| `--oxide-soft` · `--muted` · `--stamp` | `#D98B66` · `#5C594E` · `#C9C4B4` | |
| `--hairline`/`--rule`/`--frame`/`--edge` | `rgba(22,21,15,.14/.18/.35/.25)` | ink'ten türetilmiş |
| `--font-display` | `'Fraunces', serif` | başlıklar, fiyatlar, KPI sayıları |
| `--font-ui` | `'Instrument Sans', system-ui` | gövde, tablo, buton |

**Taşınacak imza teknikleri** (Design bunları korumalı):
- **Kâğıt grain** — tam ekran sabit katman, data-URI SVG `feTurbulence` (`baseFrequency:.85`),
  `opacity:.045`, `pointer-events:none`. Görsel dosya yok.
- **Offset "sticker" gölge** — bulanık değil **keskin** kaydırılmış gölge
  (`8px 8px 0 rgba(22,21,15,.12)`); dashboard KPI'da `5px 5px 0`, alert panelinde oxide tonlu.
- **Gazete fiyat listesi** — `border-top:2px solid ink` + noktalı "leader" bağlantı +
  `font-variant-numeric: tabular-nums`.
- **Ink full-bleed blok** — cream→ink→cream ritmi.
- **Jilet çizgisi motifi** — inline SVG, `stroke-dasharray` ile çizilme animasyonu.
- **Gazete kupürü sohbet çerçevesi** — `1.5px solid ink`, `border-radius:4-6px`; yumuşak "app card"
  DEĞİL.
- **Layout kaydırmayan yazıyor göstergesi** — `.typing` `position:absolute`, thread yüksekliği sabit.

> ⚠ **`design/mockups/tokens.css` KULLANILMAYACAK.** Paleti `#111827`/`#d4a017` — onaylı varyantla
> ve `client.config.example.json` ile **çelişiyor**. Yalnız eski `design/mockups/landing.html`
> import ediyor; üç onaylı varyantın hiçbiri etmiyor. Bkz. §7 BULGU-4.

**Mevcut kırılma noktaları:** landing `840px` · widget `480px` · dashboard `960px` + `480px`.
`prefers-reduced-motion: reduce` üçünde de var.

---

## §1 — YÜZEY 1: BERBER DEMO SİTESİ (public, Vercel)

> **Karar değişikliği — Design'ın bilmesi ŞART.** Mevcut mockup'ta host sayfa bilerek
> "muted placeholder" tutulmuştu. **ARTIK ÖYLE DEĞİL.** Bu sayfa aday müşteriye gösterilecek
> **gerçekçi bir berber dükkânı sitesi**; kahramanı randevu deneyimi olacak.
> (Yigitcan kararı, 2026-08-31. `docs/UX-ARCHITECTURE.md` §9 K2: "odaklı bot vitrini" —
> yani tam kurumsal site değil, ama inandırıcı bir dükkân sitesi.)

### Bölümler

| # | Bölüm | İçerik | Veri kaynağı |
|---|---|---|---|
| L1 | **Sticky header** | marka adı · nav (`#menu`, `#hours`) · CTA "Book by text" | `business.name` **config** · nav sabit |
| L2 | **Hero** | eyebrow · 3 satırlık kinetik başlık · alt metin · 2 CTA · sağda **canlı görünümlü sohbet penceresi** | başlık/metin **sabit** · sohbet içeriği widget ile aynı |
| L3 | **Menü (fiyatlar)** | gazete tarzı fiyat listesi: ad · süre · fiyat | **config** `services[].{name,durationMin,priceEUR}` |
| L4 | **Ink blok — zanaat** | başlık + gövde + outline CTA | **sabit** metin |
| L5 | **Saatler & yer** | 7 günün saatleri + **adres** | saatler **config** `workingHours` · adres **config** `faq.address` (K7 kararı) |
| L6 | **Ink blok — kapanış** | başlık + jilet SVG + dolu CTA | **sabit** |
| L7 | **Footer** | demo uyarısı + marka + yer | `business.name` **config** · yer `faq.address`'ten türetilir · uyarı **sabit** |
| L8 | **Yüzen CTA pill** | bölüm CTA'sı ekrandayken otomatik gizlenir | davranış **sabit** |
| L9 | **Intro perdesi** | tek seferlik (`sessionStorage`), tıklanınca atlanır, reduced-motion'da yok | **sabit** |

### Config-driven olan / olmayan (§6'nın özeti)

**Config'ten gelmesi GEREKEN** (yeni müşteri = config değişikliği): marka adı · 3 servisin adı,
süresi, fiyatı · 7 günün çalışma saatleri · marka renkleri · **adres** (`faq.address`) · otopark
(`faq.parking`) · walk-in (`faq.walkin`) · timezone.

> **K7 uygulandı (BULGU-5 kapandı).** Mockup 3 yerde `"City Center"` yazıyordu ve yapılandırılmış
> adres hiçbir yüzeyde görünmüyordu. Artık L5 **`faq.address`'i okur**; L7 footer'daki yer adı da
> aynı kaynaktan türetilir.
> **Design'a not:** `faq.address` sohbet cümlesi olarak yazılmış
> (*"We're at Musterstrasse 12, 1010 Vienna — 2 minutes from Stephansplatz U-Bahn."*). Site
> bloğunda tam cümle olarak kullanılabilir; ayrı bir "sokak / şehir" alanına **bölmeyin** —
> ayrı `business.address` alanı eklemek yeni config anahtarı demektir ve bu turda yasak.
> `faq.parking` da aynı bölümde kullanılabilir (bugün hiçbir yüzeyde yok).
**Sabit kalması normal**: hero başlığı, zanaat/kapanış metinleri, nav etiketleri, demo uyarısı.

> ⚠ Bugün **hiçbiri gerçekten bağlı değil** — mockup'ta elle yazılı. Değerler config ile
> *tutarlı* ama *bağlı* değil (`PHASE-6-BACKLOG.md` §6 buna "config-consistent, not config-wired"
> diyor). Phase 6'nın template iddiası bunu kapatmaya bağlı.

### NOT-surface (bu sayfanın YAPMADIĞI)
Takvim göstermez · ödeme almaz · hesap/giriş yoktur · gerçek yorum/rating yoktur ·
harita gömmez (adres metin) · blog/galeri yoktur.

---

## §2 — YÜZEY 2: WIDGET (sohbet balonu)

**Kaynak sözleşme:** 12 converged reply exit + 4 doğrudan yanıtlayıcı · 30 `computed_reply`
builder · 27 `messageTemplates` anahtarı (main) · 9 stage.
`scripts/check-outbound-inventory.py` ve `check-computed-reply-coverage.py` bu sayıları guard'lıyor.

### 2.0 — Bileşen anatomisi (mevcut, korunacak)
Launcher (kapalı pill) · Panel (`role="dialog"`) → başlık (avatar · ad · online noktası · kapat) ·
thread (`role="log" aria-live="polite"`, `max-height:min(60vh,440px)`) · girdi çubuğu.
480px altında tam genişlik alt-sayfa.

### 2.1 — Açılış

| ID | Ekran | Tetikleyici | Metin | Kaynak |
|---|---|---|---|---|
| W1 | **Yeni ziyaretçi** | ilk mesaj | **Motorda ayrı karşılama YOK** — motorun ilk cevabı doğrudan intent cevabıdır. Frontend karşılaması: W61 | `messageTemplates.greeting` FIX-1'de silindi (ölü config). §7 BOŞLUK-1 → K4 ile çözüldü |
| W61 | **Frontend karşılaması** ⭐ YENİ (K4 kararı, 2026-08-31) | panel ilk açıldığında, bir kez | **frontend sabit metni** (motor karşılığı yok, motora gönderilmez, state yazılmaz): *"Hi! I'm the {business.name} assistant — I can book, change or cancel an appointment, or answer questions. How can I help?"* (metin düzeltmesi 2026-08-31: ilk sürüm iptali dışarıda bırakıyordu) (`{business.name}` config'ten) | §8 K4 = B: motor değişmez; bu belge metnin TEK kaynağı |
| W2 | **Dönen müşteri** | `state.found` ve `now − last_updated > sessionGapMinutes` (30dk) | `"Welcome back! "` **öneki** + normal cevap | `Build Reply Payload` · **literal**, template değil · yalnız `stage='collecting'` iken |

### 2.2 — FAQ (7 konu, deterministik; LLM yalnız konuyu sınıflandırır)

Hepsi `Answer FAQ` node'u, tek turluk, state yazmaz, çıkış `Send Reply To Origin` (200).

| ID | Konu | Cevabın şekli | Kaynak |
|---|---|---|---|
| W3 | `price` | tek servis: `"{ad} is €{n}."` · hepsi: `"Our prices: Haircut €25, Beard Trim €15, Haircut + Beard €35."` | **config** `services[].priceEUR` |
| W4 | `services` | `"We offer: Haircut (30 min), Beard Trim (20 min), Haircut + Beard (45 min)."` | **config** `services[]` |
| W5 | `hours` | `"Opening hours — Mon: 10:00-19:00 · … · Sun: closed."` (7 gün tek satır) | **config** `workingHours` |
| W6 | `address` | serbest metin | **config** `faq.address` |
| W7 | `parking` | serbest metin | **config** `faq.parking` |
| W8 | `walkin` | serbest metin | **config** `faq.walkin` |
| W9 | `other` / boş | `faqUnknown` → "Good question — let me check with the team…" | template |

> **Tasarım notu:** W3/W4/W5 **çok satırlı ve uzun**. Düz balonda taşar. Liste/tablo görünümü
> gerekiyor. Bu, mevcut mockup'ta karşılığı olmayan bir ihtiyaç.

### 2.3 — Randevu alma

| ID | Ekran | Metin | Stage | Kaynak |
|---|---|---|---|---|
| W10 | Servis sor | `askService` → "Which service would you like? (Haircut / Beard Trim / Haircut + Beard)" | `collecting` | `Slot Gate` |
| W11 | Tarih/saat sor | `askDateTime` → "What day and time works for you?" | `collecting` | `Slot Gate` |
| W12 | Müsait → onay iste | **literal**: `"{servis}, {gün} {tarih} {saat} — shall I book it? (yes / no)"` | `confirming` | `Compute Availability` |
| W13 | **Booked** | `bookingConfirmed` → "You're booked: {service}, {date} {time}. See you then!" | `booked` | `Build Booked State` |

**Chip fırsatı:** W10'un 3 servisi ve W12'nin yes/no'su mockup'ta zaten chip olarak var — korunmalı.

### 2.4 — Müsaitlik reddi (hepsi **literal**, `messageTemplates`'te karşılığı YOK)

| ID | Durum | Metin | Stage |
|---|---|---|---|
| W14 | dolu + alternatif var | `"{tarih} is taken. Free that day: 10:00, 10:30, 15:00. Which works?"` (**en fazla 3**, 30dk adım) | `collecting` |
| W15 | dolu + gün tamamen dolu | `"{tarih} is taken and that day is full — want another day?"` | `collecting` |
| W16 | geçmiş saat | `"{tarih} has already passed — give me a future day and time."` | `collecting` |
| W17 | kapalı saat | `"We're closed then — on {gün} we're open {saatler}. What time works?"` | `collecting` |
| W18 | okunamayan tarih | `"Sorry, I couldn't read that date/time — what day and time would you like?"` | `collecting` |

> **Tasarım notu:** W14'ün 3 alternatifi **tıklanabilir chip** olmaya en uygun yer. Motor düz metin
> üretiyor; chip'e çevirmek frontend işi, motor değişmez.
> **Fail-closed:** reddedilen slot state'ten temizlenir — sonraki "yes" yanlışlıkla booking yapamaz.

### 2.5 — İptal

| ID | Ekran | Metin | Stage |
|---|---|---|---|
| W19 | Onay iste | **literal**: `Cancel your {servis} on {ne zaman}? Reply "yes" to cancel, or anything else to keep it.` (+ birden fazla randevu varsa `(you have N bookings — this cancels the {when} one)`) | `cancel_confirming` |
| W20 | İptal edildi | `cancelDone` → "Done — your {service} on {when} is cancelled." | `cancelled` |
| W21 | Zaten iptalmiş | `cancelAlreadyDone` (GCal 404/410) | `cancelled` |
| W22 | Vazgeçildi | `cancelAborted` → "No problem — your booking stands." | `new` |
| W23 | Cutoff reddi | `cancelCutoff` (randevuya < 2 saat) | `handoff` |
| W24 | Randevu yok | `cancelNoBooking` | değişmez |
| W25 | Otomatik iptal edilemiyor | `cancelNeedsHuman` | `handoff` |
| W26 | Hedef kaybolmuş | `cancelTargetGone` | `handoff` |
| W27 | Takvime ulaşılamadı | `cancelUnavailable` (**503**) | değişmez |

**Görünmez ama tasarımı etkileyen:** W19→W20 arasında `cancel_target_id` + `confirm_turn` var —
"yes" **o kayda** bağlı ve **yalnız hemen sonraki turda** geçerli. Araya başka mesaj girerse
W22'ye düşer. Design bunu "onay penceresi kapandı" olarak anlatabilmeli.

### 2.6 — Erteleme

| ID | Ekran | Metin | Stage |
|---|---|---|---|
| W28 | Yeni slot sor | `rescheduleAskSlot` | değişmez |
| W29 | Yeni slot onayı | **literal**: `Move your {servis} from {eski} to {yeni}? Reply "yes" to move it, or anything else to keep it.` | `reschedule_confirming` |
| W62 | ⭐ YENİ (BULGU-9) — yeni slot okunamadı | **literal**: `I couldn't read that new time — a team member will help you pick one.` | `handoff` |
| W63 | ⭐ YENİ (BULGU-9) — yeni slot geçmişte | **literal**: `{yeni} has already passed — a team member will help you pick a new time.` | `handoff` |
| W64 | ⭐ YENİ (BULGU-9) — yeni slot kapalı saatte | **literal**: `We're closed then — a team member will help you pick a time that works.` | `handoff` |
| W65 | ⭐ YENİ (BULGU-9) — yeni slot dolu | **literal**: `{yeni} is taken — a team member will help you find another time.` | `handoff` |
| W30 | Taşındı | `rescheduleDone` → "Moved — your {service} is now {when}." | `booked` |
| W31 | Vazgeçildi | `rescheduleAborted` | `new` |
| W32 | Randevu yok | `rescheduleNoBooking` | değişmez |
| W33 | Cutoff | `rescheduleCutoff` | `handoff` |
| W34 | Otomatik taşınamıyor | `rescheduleNeedsHuman` | `handoff` |
| W35 | Yeni kayıt açılamadı | `rescheduleInsertFailed` → **eski randevu duruyor** | `handoff` |
| W36 | Slot kapıldı | `slotJustTaken` veya `verifyIncomplete` | `handoff` |
| W37 | Doğrulanamadı | `verifyIncomplete` | `handoff` |
| W38 | Ayna yazımı patladı | `rescheduleMirrorFailed` → "…being finalized" | `handoff` |
| W39 | **Orphan** ⚠ | `rescheduleDone` — **müşteriye BAŞARILI der** ama eski event silinemedi | `handoff` |

> ⚠ **W39 bir çelişki**: müşteri "taşındı" görür, takvimde **iki kayıt** kalmış olabilir. Sahibe
> `orphan_event` alert'i gider. Design bunu "başarılı" ekranı olarak çizecek — sistem öyle diyor.
> Bkz. §7 BULGU-7.

> ⭐ **W62-W65 (BULGU-9, 2026-08-31):** booking tarafının 5 reddi (W14-W18) `collecting`'e dönüp
> yeniden sorarken, erteleme tarafının 4 reddi **doğrudan `handoff`'a düşer** ("a team member will
> help…") — bilinçli tasarım (`Compute Reschedule Availability` başlık yorumu: *"busy/past/closed/
> invalid → handoff with context"*). Bu dört literal motorda baştan beri vardı; envanterin ilk
> sürümü onları kaçırmıştı. Tur A grup 2 taramasında bulundu ve buraya ayrı satır olarak eklendi.

### 2.7 — Booking sonrası belirsizlik (yarış / doğrulama)

| ID | Ekran | Metin | Stage |
|---|---|---|---|
| W40 | Doğruluyoruz | `bookingNeedsConfirm` → "Thanks! We're confirming your booking now…" | `handoff` |
| W41 | Slot kapıldı | `slotJustTaken` → "Sorry — that time was just taken…" | `handoff` |
| W42 | Doğrulama tamamlanamadı | `verifyIncomplete` | `handoff` |

### 2.8 — Lead yakalama

| ID | Ekran | Metin |
|---|---|---|
| W43 | Kaydedildi | `leadCaptured` → "Thanks! We've got your details…" |

### 2.9 — İnsana devir — **ÜÇ SINIF, AYRI EKRAN**

`.claude/rules/handoff.md` sözleşmesi. Müşteri metni benzer olabilir; **makine tarafı ayrışır** ve
Design bunları ayrı durum olarak ele almalı (özellikle 503 grubunun "tekrar dene" davranışı farklı).

| ID | Sınıf | Tetikleyici | HTTP | State yazar mı | Metin |
|---|---|---|---|---|---|
| W44 | **intent-handoff** | düşük güven · `unknown`/`handoff` intent · needs-human | 200 | ✅ `stage=handoff` | `handoff` |
| W45 | **guard-trip** | kill-switch · max-turns · spend-cap | 200 | ❌ geçici | `handoff` |
| W46 | **infra-unavailable** | LLM/takvim/lead/state dış sistem çöktü | **5xx** + `error` bayrağı | ❌ | `handoff` (biri hariç, aşağıda) |
| W47 | **Devir kilidi** | `stage === 'handoff'` iken **her** mesaj | 200 | ❌ | `handoffLocked` → "A team member is already helping you here…" |

> **W47 kritik:** LLM çağrılmaz, state yazılmaz, WhatsApp'a gönderilmez. **Kilidi açacak hiçbir
> müşteri yolu YOK** — yalnız sahip açabilir (Phase 6'daki tek yazma aksiyonu, §4c).
> Design: girdi çubuğu bu durumda ne yapmalı? → §8 açık karar 2.

### 2.10 — Hata ve kenar durumları

| ID | Durum | HTTP | Widget'a metin GELİYOR mu | Kaynak |
|---|---|---|---|---|
| W48 | LLM erişilemez | 503 | ✅ `handoff` | `LLM Unavailable Reply` |
| W49 | Takvim erişilemez | 503 | ✅ `handoff` | `Calendar Unavailable Reply` |
| W50 | Lead yazılamadı | 503 | ✅ `handoff` | `Lead Unavailable Reply` |
| W51 | İptal silme patladı | 503 | ✅ `cancelUnavailable` | `Cancel Delete Unavailable Reply` |
| W52 | Booking state kaydedilemedi | 200 | ✅ booking metni + `state_unsaved` | `Booking State-Unsaved Reply` |
| W53 | **Spend-cap** | 200 | ✅ `handoff` | `Build Spend-Cap Reply` |
| W54 | **State erişilemez** | **503** | ❌ **METİN YOK** — gövde `{ok:false,error:'state_unavailable',handoff:true}` | `Send Error Response` |
| W55 | **Geçersiz girdi** | **400** | ❌ **METİN YOK** — gövde `{ok:false,error:'invalid_payload',handoff:true}` | `Send Reject Response` |
| W56 | **Duplicate mesaj** | 200 | ❌ **EKRAN YOK — sessizce yutulur** (bkz. 2.10.1) | `Idempotent Replay` |
| W57 | **Turnstile reddi** | **403** | ❌ **METİN YOK** — `{ok:false,error:'turnstile_failed'}` | `Reject Bot Request` |
| W58 | **Normalize reddi** (`sessionId` yok) | **400** | ❌ **METİN YOK** — `{ok:false,error:'bad_request'}` | `Respond Normalize Reject` |
| W59 | **Rate-limit** | Cloudflare | ❌ istek n8n'e **hiç ulaşmaz** | edge kuralı `barber-inbound-ratelimit`, 20/dk/IP |
| W60 | **Offline / n8n erişilemez** | — | ❌ | ağ hatası, sistemde karşılığı yok |

### 2.10.1 — Metni olmayan çıkışların KARARI (BULGU-6 kapandı, K1 uygulandı)

Motorda metni olmayan yedi durumun her biri karara bağlandı. **Design bu metinleri icat etmeyecek.**

| ID | Karar | Gösterilecek metin | Gerekçe |
|---|---|---|---|
| **W54** 503 `state_unavailable` | **motor değişmez — frontend config'ten okur** | `messageTemplates.handoff` | Bu bir *konuşma* anıdır ve WhatsApp tarafı **zaten** bu anahtarı gönderiyor; iki kanal tek metin kaynağında birleşir. Motora `reply` eklemek CP4b-1'in "widget gövdesi bit-identical kalır" sözleşmesini bozar ve `check-outbound-inventory.py` guard'ına takılır. Yeni anahtar gerekmiyor. |
| **W55** 400 `invalid_payload` | **motor değişmez — frontend config'ten okur** | `messageTemplates.notUnderstood` | Aynı gerekçe; WhatsApp tarafı bu anahtarı gönderiyor. Müşterinin mesajı işlenemedi — bu marka sesiyle söylenmeli. |
| **W56** duplicate | **EKRAN YOK — sessizce yut** | *(hiçbir şey)* | Müşteri ilk teslimatta cevabını **zaten aldı**. İkinci bir balon "bir şey ters gitti" izlenimi verir. Motor da aynı şeyi söylüyor: `_outbound_should_send:false`. |
| **W57** 403 Turnstile | **frontend sabit metni** | *"We couldn't verify your browser. Please refresh the page and try again."* | Motor **hiç çalışmadı** — bu bir güvenlik katmanı reddi, konuşma değil. Marka sesi taşımasına gerek yok, config anahtarı hak etmiyor. |
| **W58** 400 normalize reddi | **frontend sabit metni** | *"Something went wrong on our side. Please refresh the page and try again."* | `sessionId` eksik = istemci hatası; müşterinin yapabileceği tek şey yenilemek. Motor çalışmadı. |
| **W59** rate-limit (edge) | **frontend sabit metni** | *"Too many messages just now — please wait a moment and try again."* | İstek n8n'e **hiç ulaşmıyor** (Cloudflare); motorun bundan haberi yok. |
| **W60** offline / erişilemez | **frontend sabit metni** | *"We can't reach the salon right now. Please try again in a moment."* | Ağ hatası; sistemde karşılığı yok. |

**Neden W57-W60 için config anahtarı eklenmedi:** tüketicisi (frontend) henüz yokken config anahtarı
eklemek, K5'te sildiğimiz ölü-anahtar tuzağının aynısıdır. Bunlar taşıyıcı/güvenlik katmanı
mesajları — marka sesi taşımıyorlar. Çok dilli hâle gelirlerse config'e Phase 7'de, tüketicileriyle
birlikte girerler.

> **Yukarıdaki dört İngilizce metin bu belgenin ürünüdür, motorun değil** — §7'ye
> "YENİ — frontend metni, motor karşılığı yok" olarak kayıtlı.

### 2.11 — Guard durumlarının görünmeyen yüzü

| Guard | Müşteri farkı görür mü |
|---|---|
| kill-switch vs max-turns | ❌ **ayırt edilemez** — ikisi de aynı `Handoff Reply` |
| spend-cap | ❌ o da aynı `handoff` metni |
| dry-run (booking) | ❌ **gerçek booking'den ayırt edilemez** — aynı `bookingConfirmed` |
| dry-run (WhatsApp gönderim) | ❌ mesaj sessizce gitmez |

### 2.12 — Stage makinesi (9 değer — Design'ın durum grafiği)

```
new ──▶ collecting ──▶ ready ──▶ confirming ──▶ booked
 │           ▲(slot reddedildi)                   │
 ├──▶ cancel_confirming ──▶ cancelled | new
 ├──▶ reschedule_confirming ──▶ booked | new
 └──▶ handoff  ⛔ KİLİT — çıkış yolu YOK (yalnız sahip açar)
```
`stage='handoff'` yazan **17 node** var (`Mark Handoff` + 16 hata/needs-human builder). *(Düzeltme 2026-08-31, Tur A grup 3: önceki "18" sayımına metninde `stage:'handoff'` geçen bir sticky note karışmıştı — yazıcı değil. Sayım yöntemi: node parametrelerinde `stage` ataması taraması, sticky note'lar hariç.)*
DATA-MODEL'de `done` diye bir değer geçmiyor — hiçbir node yazmıyor.

---

## §3 — YÜZEY 3: GÖMÜLEBİLİR SNIPPET

Müşterinin **kendi sitesine** koyacağı hâli. Motor tarafı aynı endpoint, aynı 65 ekran.

| Konu | Demo sitesindeki widget | Gömülebilir snippet |
|---|---|---|
| Host sayfa | Bizim berber sitemiz | **Müşterinin sitesi — hiçbir varsayım yapılamaz** |
| Yerleşim | Sayfa tasarımıyla uyumlu, sağ alt | Yabancı bir sayfaya oturacak → **çakışma riski** (z-index, font miras, CSS sızıntısı) |
| Marka | Bizim cream/ink | Müşterinin markası — `branding.*` config'ten |
| Turnstile | Aynı: widget kanalında `turnstile.enabled` ise token zorunlu | **Aynı** — snippet Cloudflare Turnstile widget'ını kendi render edip `turnstileToken` göndermeli |
| Origin | Aynı origin | **Cross-origin** → n8n webhook CORS'a izin vermeli |
| Kimlik | `sessionId` (istemci üretir) | **Aynı** — "session-token gücü, doğrulanmış kimlik değil" (README, kabul edilmiş T1 limiti) |
| Mock şeridi | Var (demo) | **Gerçek müşteride OLMAMALI** → §8 açık karar 5 |

**Aynı kalan ekranlar:** §2'deki W1-W65'in tamamı — motor kanal ayrımı yapmıyor
(`channel: 'widget'` zorlanıyor, `Normalize Inbound`).

**Değişen/eklenen:**
| ID | Ekran | Neden |
|---|---|---|
| S1 | **Kapalı launcher** (host sayfaya oturmuş) | Tek görünür öğe; müşterinin sayfasına saygılı olmalı |
| S2 | **CSS izolasyon** | Host sayfa fontu/rengi sızmamalı — Shadow DOM veya kapsamlı reset gerekir |
| S3 | **Turnstile challenge görünümü** | Cloudflare kendi widget'ını çizer; snippet ona yer ayırmalı |
| S4 | **Cross-origin hata** | CORS reddi → W60'ın snippet'e özgü hâli |

> **DOĞRULANAMADI:** n8n webhook'unun bugün CORS başlıklarını nasıl döndürdüğü repoda kayıtlı
> değil. Snippet inşa edilmeden önce ölçülmeli.

---

## §4 — YÜZEY 4: DASHBOARD (özel, Cloudflare Access arkasında)

**Phase 6 kapsamı (UX-ARCHITECTURE §9 K6):** SALT OKUNUR + devir kuyruğu + **TEK yazma aksiyonu**
(devir kilidini serbest bırakma). İptal/erteleme yazmaları **Phase 7**.

### 4.0 — Airtable bütçesi (BAĞLAYICI)

Airtable **5 istek/sn/base**, tüm planlarda sabit, yükseltilemez; aşımda **429 + 30 sn** ceza ve
ceza **base geneline** uygulanır → dashboard'ın taşırdığı bir saniye **botu 30 sn yere serer**.

| Panel | Tablo | İstek |
|---|---|---|
| Randevular (bugün + yaklaşan + geçmiş) | `appointments` | **1** — tek toplu okuma, ayrım sunucuda |
| Lead'ler | `leads` | 1 |
| Devir kuyruğu | `conversations` (`stage='handoff'`) | 1 |
| Spend metre | `bot_metrics` | 1 |
| **Sayfa toplamı** | | **4** |

**Kısıt:** satır başına ayrı istek **YOK** · otomatik yenileme **YOK** · "detay" ayrı çağrı yapmaz,
zaten çekilmiş veriyi açar · bota öncelik.

### 4.a — Randevular

| ID | Ekran | İçerik |
|---|---|---|
| D1 | **Bugün** | saat · müşteri (maskeli) · servis (+fiyat) · kanal · durum · hatırlatıldı mı |
| D2 | **Yaklaşan** | aynı alanlar, tarih grubu ile |
| D3 | **Geçmiş** | aynı alanlar, salt okunur |
| D4 | **Randevu detayı** | + `gcal_event_id` · `calendar_id` · `end_utc` · `created_at` · `reminder_sent` |
| D5 | **Boş: bugün randevu yok** | |
| D6 | **Boş: hiç randevu yok** (yeni müşteri) | D5'ten farklı — "henüz başlamadınız" tonu |

Alanlar (`docs/DATA-MODEL.md` §appointments): `sender_key`(PII) · `service` · `start_utc`/`end_utc`
(UTC saklanır, **shop timezone'da gösterilir**) · `gcal_event_id` · `calendar_id` · `channel` ·
`customer_name`(PII) · `status` (`booked|cancelled`) · `reminded` · `reminder_sent` · `created_at`.

**Aksiyon:** yok (Phase 6 salt okunur). İptal/erteleme Phase 7.

> ⚠ **Doğruluk kaynağı Google Calendar**, `appointments` bir aynadır. `mirror_failed` veya
> `cancel_mirror_failed` sonrası bu tablo GCal ile **uyuşmaz** ve dashboard bunu **bilemez**.
> Design bu belirsizliği gizlememeli — bkz. D14.

### 4.b — Lead'ler

| ID | Ekran | İçerik |
|---|---|---|
| D7 | **Lead listesi** | ad(PII) · telefon(**maskeli**) · kanal · durum · ilk mesaj(PII) · tarih |
| D8 | **Boş: lead yok** | |

Durum: `new | contacted | converted`. Durum değiştirme **yıkıcı değil** — tek kabul edilebilir
doğrudan Airtable yazımı (§5 sözleşmesi satır 7). Phase 6'da yapılacak mı → §8 açık karar 3.

### 4.c — DEVİR KUYRUĞU (dashboard'ın asıl işi)

Kaynak: `conversations` where `stage='handoff'`, + `last_alert_class` + `last_alert_at`.

| ID | Ekran | İçerik |
|---|---|---|
| D9 | **Kuyruk listesi** | sender(maskeli) · alert sınıfı · ne zaman · son mesajlar (`recent_messages`, PII) · `last_intent` · bekleme süresi |
| D10 | **Devir detayı** | + slot alanları · `turn_count` · `computed_reply` |
| D11 | **"Devir kilidini serbest bırak"** — **Phase 6'nın TEK yazma aksiyonu** | `conversations.stage` → `new`. Takvime/randevuya dokunmaz, geri alınabilir |
| D12 | **Boş: kuyruk temiz** | |

#### ⚠ D9'un en kritik tasarım şartı — üç durum KARIŞTIRILMAMALI

`last_alert_class` **yalnız teslim edilmiş** alert'te yazılır (Codex #5 düzeltmesi). Yani:

| Airtable'da | Gerçek anlamı | Ekranda |
|---|---|---|
| `stage=handoff` + `last_alert_class` **dolu** | Sahip **haberdar edildi** (Telegram'a ulaştı) | "bildirildi — {sınıf}, {zaman}" |
| `stage=handoff` + `last_alert_class` **boş** | ⚠ **Alert ya hiç üretilmedi ya da TESLİM EDİLEMEDİ** | **"bildirim doğrulanamadı"** — "hiç alert yok" DEĞİL |
| `stage=handoff` + throttle penceresinde | Alert bastırıldı, alan **eski** değeri tutuyor | zaman damgası eski → "son bildirim {zaman}" |

**"Alert yok" ile "alert gitti ama teslim edilemedi" aynı görünürse dashboard yalan söyler.**
Boş alan **belirsizlik** demektir, **iyi haber değil**.

#### Alert sınıfları — **24 tane** (Design her birini bir rozet/etiket olarak ele almalı)

Kaynak: `Build Owner Alert` (main, 21 statik sınıf, **28 kaynak node**) + dinamik
`zernio_send_failed` + `Build Owner Alert (Reminders)` + `Build Owner Alert (Purge)`.

| Grup | Sınıflar | Sahip ne yapar |
|---|---|---|
| **Konuşma devri** | `handoff` · `handoff_lock` · `max_turns` | konuşmayı devral, kilidi aç (D11) |
| **Takvim/Airtable uyuşmazlığı** ⚠ | `orphan_event` · `mirror_failed` · `cancel_mirror_failed` · `reconcile_conflict` · `reconcile_unresolved` · `verify_unavailable` · `state_unsaved` | **elle takvim/Airtable düzelt** — en acil grup |
| **Dış sistem** | `llm_unavailable` · `calendar_unavailable` · `lead_unavailable` · `state_unavailable` · `cancel_delete_failed` | sistem durumu kontrol |
| **Müşteriye ulaşamadı** | `zernio_send_failed` | **cevap gitmedi — elle yaz** |
| **Bütçe** | `spend_cap` · `spend_meter_unavailable` | bütçe kararı |
| **İşleyiş** | `normalize_drift` · `dedupe_marker_failed` · `reply_fallback` · `cancel_needs_human` | incele |
| **Arka plan işleri** | `reminder_error` · `purge_error` (+`branch`: `processed_messages`/`conversations_pii`) | temizlik/hatırlatma durdu |

**Alert VERİLMEYENLER** (dashboard bunları beklememeli): `race_lost` (normal sonuç) ·
kill-switch tripi (sahip kendi açtı) · duplicate · 403 unsigned · 403 Turnstile ·
widget-lane normalize reddi (DoS primitifi olurdu).

> **Sınır:** `last_alert_class` **son** değerdir, geçmiş değil — sonraki sınıf öncekini ezer.
> Ve konuşma satırı olmayan alert'ler (`normalize_drift`, ilk-temas `spend_cap`) Airtable'da
> **iz bırakmaz**; yalnız Telegram'da görünür. Design "tam liste" iddiasında bulunmamalı.

### 4.d — Sistem sağlığı

| ID | Ekran | İçerik |
|---|---|---|
| D13 | **Anahtarlar** | kill-switch · dry-run · whatsappSendDisabled · ownerAlert.enabled · Turnstile — açık/kapalı göstergesi |
| D14 | **Spend metre** | `bot_metrics.cost_usd` / `bot.llmCostCapUsd` ($10/ay), `period_key`, `updated_at` |
| D15 | **Açık flag'ler** | `last_alert_class` üzerinden türetilir (kalıcı olan tek kaynak) |
| D16 | **Son hatalar** | 🕳 **KAYNAK YOK** — n8n execution log'u dışarıdan sorgulanabilir değil |
| D17 | **Boş: her şey yolunda** | |

**12 anahtar** (hepsi bugün `Load Config` Code node'unda **hard-coded literal**; değiştirmek n8n
editöründe kod düzenlemek demek): `bot.killSwitch`(false) · `bot.dryRun`(false) ·
`bot.whatsappSendDisabled`(true, **yalnız reminders**) · `ownerAlert.enabled`(true) ·
`ownerAlert.throttleMinutes`(30) · `channels.widget.turnstile.enabled`(true) ·
`bot.llmCostCapUsd`(10.00) · `bot.confidenceThreshold`(0.7) · `bot.maxTurnsPerConversation`(12) ·
`bot.reminderHoursBefore`(24) · `bot.sessionGapMinutes`(30) · `bot.cancellationCutoffHours`(2).

> ⚠ `ownerAlert.enabled=false` **tüm alert'leri sessizce keser**. D13 bunu görünür kılmalı —
> yoksa sahip "hiç sorun yok" sanır.

### 4.e — Ortak dashboard durumları

| ID | Ekran |
|---|---|
| D18 | **Yükleniyor** (4 okuma sürerken) |
| D19 | **Airtable erişilemez / 429** — "veri şu an alınamıyor", **bota öncelik verildiği** anlatılmalı |
| D20 | **Cloudflare Access oturumu düştü** — yeniden giriş |

---

## §5 — ORTAK ÖĞELER (tüm yüzeylerde)

| Öğe | Kural | Kaynak |
|---|---|---|
| **Mock/demo şeridi** | Demo yüzeylerde **gizlenmeyecek** — köşe ribbon + footer metni. Gerçek müşteri kurulumunda kalkar (§8 karar 5) | `.claude/rules/honesty-demos.md`; mockup'ta 3 sayfada da var |
| **Boş durum** | Her liste/kuyruk için ayrı — "0 kayıt" ile "henüz başlamadınız" farklı | `PHASE-6-BACKLOG.md` §1 |
| **Yükleniyor** | Widget: yazıyor göstergesi (layout kaydırmayan). Dashboard: iskelet | mockup `.typing` |
| **Hata** | Widget W54-W60 · Dashboard D19-D20 | §2.10, §4.e |
| **Mobil** | Mevcut kırılmalar: landing 840px · widget 480px (tam genişlik alt-sayfa) · dashboard 960px + 480px. **390px'e özel kural YOK** — `PHASE-6-BACKLOG.md` §3'teki iki kozmetik madde açık: widget 12px yan boşluk, dashboard pill/ribbon çakışması | mockup `@media` |
| **Erişilebilirlik** | `prefers-reduced-motion` (3 dosyada da var) · `:focus-visible` oxide outline · `scroll-margin-top:90px` · `role="log" aria-live="polite"` thread'de · `aria-hidden` dekoratiflerde · PII maskeleme mock veride bile | mockup |
| **PII maskeleme** | Telefon/sender_key **her zaman maskeli** — mockup mock veride bile maskeliyor, bu korunmalı | `dashboard-a-cream-ink.html` |

---

## §6 — CONFIG-DRIVEN vs SABİT (template iddiasının kanıtı)

**Yöntem:** `config/client.config.example.json` ↔ `schemas/client.config.schema.json` ↔ canlı
`Load Config` (main) ve `Load Config (Reminders)` karşılaştırıldı; canlı config `ajv` ile şemaya
karşı çalıştırıldı.

| Değer | Config'ten mi | Kim okuyor | Not |
|---|---|---|---|
| `business.name` | ✅ | yalnız **frontend** | mockup'ta elle yazılı → bağlanacak |
| `business.timezone` | ✅ | n8n (11 referans) + frontend | |
| `business.locale` | ✅ tanımlı | **hiçbir node okumuyor** | frontend okuyacaksa Phase 6'da bağlanır, yoksa ölü |
| `branding.{primaryColor,accentColor,logoUrl}` | ✅ | yalnız **frontend** | n8n okumaz (normal) |
| `services[].{id,name,durationMin,priceEUR}` | ✅ | n8n (FAQ, booking) + frontend | menü, chip'ler, tablo satırları |
| `workingHours.{mon..sun}` | ✅ | n8n (müsaitlik) + frontend | saatler bölümü |
| `faq.address` | ✅ | n8n (`Answer FAQ`) **+ landing L5/L7** | K7 ile bağlandı (BULGU-5 kapandı) |
| `faq.parking` | ✅ | n8n (`Answer FAQ`) · landing L5'te kullanılabilir | bugün hiçbir yüzeyde yok |
| `faq.walkin` | ✅ | n8n (`Answer FAQ`) | landing'de gerekmiyor |
| `messageTemplates.*` (27 main + `reminder` reminders'da) | ✅ | n8n | widget metinlerinin **tamamı** |
| `bot.*` (9 değer) | ✅ | n8n | eşikler, guard'lar |
| `ownerAlert.{enabled,throttleMinutes}` | ✅ | n8n (3 workflow) | ✅ example + şemaya eklendi (BULGU-3 kapandı) |
| `channels.widget.turnstile.enabled` | ✅ | n8n (`Turnstile Gate`) + snippet | ✅ example + şemaya eklendi (BULGU-3 kapandı) |
| `googleCalendarId` | ✅ | n8n | gerçek değer yalnız canlı node'da |
| Hero başlığı · zanaat/kapanış metni · nav etiketleri · demo uyarısı | ❌ **sabit** | — | normal |
| W57-W60 frontend hata metinleri | ❌ **sabit** (frontend) | frontend | taşıyıcı/güvenlik katmanı mesajı, marka sesi değil — bkz. §2.10.1 |

**Bugünkü gerçek:** mockup'ların hiçbiri config okumuyor — hepsi elle yazılmış, config ile
*tutarlı* ama *bağlı değil*. Phase 6 bunu kapatmadan "config-driven template" denemez.

> ✅ **Sözleşme artık gerçek (BULGU-3 kapandı, FIX-2).** `schemas/client.config.schema.json`
> `channels.widget.turnstile` ve `ownerAlert`'i tanıyor; kök ve `bot` nesneleri
> `additionalProperties:false` yapıldı — yani gelecekte canlıya eklenen kayıtsız bir anahtar
> **sessizce geçemez**. Yeni guard `scripts/check-config-schema.cjs`, HEM example'ı HEM de canlı
> `Load Config` literalini committed şemaya karşı ajv ile doğruluyor (4 sabotaj senaryosuyla
> FAIL-edebilirliği kanıtlandı). "Config'i doldur, çalışır" iddiası artık makine tarafından
> denetleniyor.

---

## §7 — BOŞLUKLAR ve ÇELİŞKİLER

> Çözülmedi, listelendi. Kararlar §8'de ve Phase 6 planında.

### ⚠ BULGU'lar (sistem/doküman çelişkisi — bu tarama sırasında bulundu)

**BULGU-1 — `docs/UX-ARCHITECTURE.md` "21 alert sınıfı" diyor; gerçek 24.** ✅ **KAPANDI** —
UX-ARCHITECTURE ve DATA-MODEL düzeltildi.
Koddan sayıldı: main `Build Owner Alert` **21 statik** sınıf + dinamik `zernio_send_failed`
(`Outbound Send Failed` üst-seviye `error` alanı) + `reminder_error` + `purge_error` = **24**.
21 rakamı yalnız main'in statik kümesini sayıyor. **Benim FIX-1'de yazdığım sayı hatalı.**

**BULGU-2 — `stage='handoff'` yazan node sayısı belgede 15, gerçekte 18.** ✅ **KAPANDI** —
UX-ARCHITECTURE düzeltildi.
`docs/UX-ARCHITECTURE.md` §2 "15 node (`Mark Handoff` + 14 hata builder)" diyor; parametre taraması
**18** node buluyor.

**BULGU-3 — canlı config kendi şemasını GEÇMİYOR.** ✅ **KAPANDI (FIX-2, 2026-08-31)** —
şema gerçeğe eşitlendi (`widgetChannel` + `ownerAlert`), kök ve `bot` kapatıldı, example tamamlandı,
`scripts/check-config-schema.cjs` guard'ı close-gate'e girdi (4 sabotaj kanıtı).
`ajv` ile doğrulandı: canlı `Load Config` → `HAYIR`, tek hata
`/channels/widget additionalProperties: turnstile` (şemanın `channel` tanımı
`additionalProperties:false`). `client.config.example.json` → `EVET`. Yani **şema, botun gerçekte
çalıştığı config'i reddediyor**; `ownerAlert` de şemada hiç tanımlı değil (kök `additionalProperties`
açık olduğu için sessizce geçiyor). "Config-driven template" iddiasının somut açığı.

**BULGU-4 — `design/mockups/tokens.css` yanlış paleti taşıyor.**
`--ink:#111827`, `--gold:#d4a017` — onaylı varyantların `#16150F`/`#B4472E`'siyle ve
`client.config.example.json` ile çelişiyor. Yalnız eski `design/mockups/landing.html` import ediyor;
üç onaylı varyantın **hiçbiri** etmiyor. Design bu dosyayı açarsa **yanlış palete** çalışır.

**BULGU-5 — landing adresi config'le uyuşmuyor.** ✅ **KAPANDI (K7)** — L5/L7 artık
`faq.address`'i okuyor; §1 ve §6 güncellendi. (Mockup HTML'ine dokunulmadı — uygulama Phase 6 build'i.)
Landing 3 yerde `"City Center"` yazıyor; `config.faq.address` ise
`"Musterstrasse 12, 1010 Vienna — 2 minutes from Stephansplatz U-Bahn."`. Yapılandırılmış adres
hiçbir yüzeyde gösterilmiyor.

**BULGU-6 — beş widget çıkışının motorda metni yok.** ✅ **KAPANDI (K1)** — yedi durumun
her biri §2.10.1'de gerekçeli karara bağlandı; W56 ekransız, W54/W55 mevcut config anahtarlarından,
W57-W60 frontend sabit metni (metinleri yazıldı). Yeni config anahtarı eklenmedi.
W54(503) · W55(400) · W56(duplicate) · W57(Turnstile 403) · W58(normalize 400). K4 yalnız
W54/W55'i çözüyor; kalan üçü kararsız.

**BULGU-7 — `Build Reschedule Orphan State` müşteriye BAŞARILI diyor.** ⏸ **Phase 7'ye
adlandırılmış madde olarak girdi** (ROADMAP). Design'ı bloklamıyor: CP4'te `orphan_event` flag +
owner-alert ile kabul edilmişti, yani **sessiz değil**.
`rescheduleDone` gönderiyor ama eski takvim kaydı silinemedi → takvimde **iki kayıt** kalabilir.
Sahibe `orphan_event` alert'i gider; müşteri hiçbir şey bilmez. (Kabul edilmiş davranış, ama Design
"başarılı" ekranı çizerken bunu bilmeli.)

**BULGU-8 — devir kilidinin çıkışı yok** (bilinen CANLI KUSUR). Phase 6'daki tek yazma aksiyonu
(D11) tam olarak bunu kapatmak için var.

**BULGU-9 — envanter, motorda var olan 4 erteleme ön-yazım literalini kaçırmıştı.** ✅ **KAPANDI
(Tur A grup 2, 2026-08-31)** — `Compute Reschedule Availability`'nin busy/past/closed/invalid
retleri (hepsi `stage='handoff'`, "a team member will help…" literalleri) §2.6'da satır olarak
yoktu; W36/W37'ye (yazım-SONRASI yarış durumları) sıkıştırılmış sanılıyordu ama metinleri ve
konumları farklı (yazım-ÖNCESİ ret). **W62-W65 olarak eklendi.** Aynı taramada tüm `Compute *` +
`Build * State` + `* Reply` node'ları yeniden tarandı: kalan tüm envanter-dışı metinler
`cfg.messageTemplates.X || '…'` **fallback'leri** çıktı (birincil kaynak template — ayrı ekran
değil); **başka kaçak birincil literal YOK.**

### Sistemin ürettiği ama ekranı olmayan

| Ne | Durum |
|---|---|
| Yeni ziyaretçi karşılaması | ✅ **K4 = B ile çözüldü (2026-08-31):** frontend sabit karşılaması **W61** olarak eklendi (metin §2.1'de, motor karşılığı yok, motor değişmedi) |
| Duplicate | **ekran yok — sessizce yutulur** (karar, §2.10.1) |
| Turnstile / normalize / rate-limit / offline | **YENİ — frontend metni, motor karşılığı yok** (§2.10.1'de yazılı, Design icat etmeyecek) |
| "Son hatalar" paneli | **sorgulanabilir kaynak yok** (D16) |
| Alert **geçmişi** | yalnız *son* sınıf saklanıyor |
| Kill-switch/dry-run'ı **kim ne zaman açtı** | denetim izi yok |
| `normalize_drift` / ilk-temas `spend_cap` alert'leri | Airtable'da iz bırakmaz, yalnız Telegram |

### Ekranı gerekip de sistemde karşılığı olmayan

| Ne | Not |
|---|---|
| Dashboard'dan iptal/erteleme | **Phase 7** — korumalı yol henüz yok |
| Alert'i "çözüldü" işaretleme | mekanizma da alan da yok — **yeni alan önermiyorum**, boşluk olarak duruyor |
| Müşteriye dashboard'dan mesaj yazma ("Reply") | mockup'ta buton **çizili ama bağlantısız**; güvenlik riski (keyfi numaraya mesaj primitifi) → Phase 7 |
| Konuşma transkripti | yalnız son 5 mesaj (`recent_messages`), 30 günde temizleniyor |

---

## §8 — AÇIK KARARLAR (Design'a gitmeden önce)

Her biri: soru · seçenekler · bedel · **önerim**.

### K1 — Metni olmayan çıkışlar ne gösterecek? ✅ **KARARA BAĞLANDI → §2.10.1**
W56 duplicate · W57 Turnstile reddi · W58 normalize reddi. (W54/W55 §9 K4 ile çözülmüş:
503→`handoff`, 400→`notUnderstood`.)

| Seçenek | Bedel |
|---|---|
| A. Frontend sabit metni | hızlı; marka/dil ikinci bir yerde yaşar, drift riski |
| B. Yeni config anahtarı | tek dil kaynağı; ama tüketicisi gelene kadar **ölü anahtar** — K5'te sildiğimiz tuzağın aynısı |
| C. Sessiz yut (hiç gösterme) | duplicate için doğru; Turnstile/normalize için müşteri "gönderdim ama bir şey olmadı" der |

→ **Önerim: karma.** **W56 duplicate → sessiz yut** (müşteri zaten ilk cevabı aldı; ekstra balon
kafa karıştırır). **W57/W58 → frontend sabit metni** (A), çünkü bunlar *taşıyıcı katman* hataları,
marka sesi taşımaları gerekmiyor ve config'e ölü anahtar eklemek K5 kararıyla çelişir.

### K2 — Devir kilidinde (W47) girdi çubuğu ne yapsın? ✅ **KARARA BAĞLANDI → C (Tur A brief'i, 2026-08-31)**
**Yigitcan kararı: C** — girdi çubuğu AÇIK kalır, `handoffLocked` cevabı **bir kez** gösterilir,
sonraki mesajlar sessizce kabul edilir (kullanıcı sessizliğe konuşmaz; insan okuyacak). Motor değişmez.
Müşteri kilitliyken yazmaya devam edebiliyor; her mesaja aynı `handoffLocked` cevabı geliyor.

| Seçenek | Bedel |
|---|---|
| A. Girdiyi kapat | net; ama müşteri ek bilgi veremez (insan onu okuyacak olsa bile) |
| B. Açık bırak, her mesaja aynı cevap | bugünkü davranış; tekrar eden aynı balon rahatsız edici |
| C. Açık bırak, cevabı **bir kez** göster, sonrakileri sessizce kabul et | en insancıl; motor değişmez (frontend tekrarı bastırır) |

→ **Önerim: C.** Müşteri yazmaya devam edebilsin (insan okuyacak), ama aynı balon üst üste
yığılmasın. Motor değişikliği gerektirmiyor.

### K3 — Lead durum değiştirme Phase 6'da olsun mu?
`leads.status` (`new|contacted|converted`) yıkıcı değil; §5 sözleşmesi doğrudan Airtable yazımına
izin veriyor.

| Seçenek | Bedel |
|---|---|
| A. Phase 6'ya al | sahibe gerçek fayda; +1 yazma yolu, +1 Airtable isteği |
| B. Phase 7'ye ertele | Phase 6 tamamen salt-okunur + tek istisna kalır, kapsam net |

→ **Önerim: B.** K6 kararı "salt-okunur + TEK yazma istisnası" dedi; ikinci bir yazma eklemek o
kararı sulandırır. Lead durumu Phase 7'de iptal/erteleme ile birlikte gelsin.

### K4 — Yeni ziyaretçi için ayrı karşılama ekranı olsun mu? ✅ **KARARA BAĞLANDI → B (2026-08-31)**
**Yigitcan kararı: B.** Gerekçesi: widget açılıp hiçbir şey söylememesi bir TASARIM hatası; motorun
karşılama üretmemesi bir MOTOR gerçeği — ikisi ayrı. Motor değişmez. Metin **W61**'de (§2.1),
bu belge tek kaynak.
Bugün yok — `greeting` template'i ölü config olduğu için FIX-1'de **silindi**.

| Seçenek | Bedel |
|---|---|
| A. Yok kalsın | dürüst; ilk cevap doğrudan işe girer |
| B. Frontend'de statik karşılama (motor değişmez) | widget açılınca bir balon; motor bilmez, state yazılmaz |
| C. Motora geri ekle | **motor değişikliği** — bu turda yasak |

→ **Önerim: B.** Widget açıldığında gösterilen, motorun üretmediği **frontend karşılaması**.
§7'ye "YENİ — widget açılış balonu, motor karşılığı yok" olarak girer, dürüstlük korunur, ve
kullanıcı boş bir kutuyla karşılaşmaz. C yasak, A biraz soğuk.

### K5 — Mock şeridi gerçek müşteri kurulumunda nasıl kalkacak? *(BULGU-3 kapandığı için engel kalktı)*
`honesty-demos.md` demo'da şeridin **gizlenmemesini** şart koşuyor. Ama snippet gerçek bir berbere
kurulduğunda "Mock" yazamaz.

| Seçenek | Bedel |
|---|---|
| A. Config bayrağı (`demoMode`) | temiz; **yeni config anahtarı** = §6/BULGU-3'teki şema borcunu büyütür |
| B. Build-time ayrım (demo build / client build) | config'e dokunmaz; iki build hattı |
| C. Elle silme | hata yapılır, unutulur — tehlikeli |

→ **Önerim: A**, ama **BULGU-3 kapatıldıktan sonra** — şema zaten canlı config'i reddediyor;
düzeltmeden yeni anahtar eklemek borcu artırır. Sıralama: önce şema/config uyumu, sonra `demoMode`.

### K6 — Dashboard "son hatalar" paneli (D16) ne olacak?
Sorgulanabilir kaynak yok; n8n execution log'u dışarıdan erişilemez.

| Seçenek | Bedel |
|---|---|
| A. Paneli hiç yapma | dürüst; sahip Telegram'a bakar |
| B. `last_alert_class`'tan türet | zaten D15 bunu yapıyor — ikinci panel gereksiz |
| C. Yeni alan/tablo | **yeni Airtable alanı = bu turda yasak** |

→ **Önerim: A.** D16'yı listeden çıkar, §7'de boşluk olarak kalsın. D15 (açık flag'ler) zaten
mevcut veriden türetilebilen her şeyi gösteriyor.

### K7 — Landing'de yapılandırılmış adres gösterilsin mi? ✅ **UYGULANDI**
Bugün "City Center" yazıyor, `faq.address` hiçbir yerde görünmüyor.

→ **Önerim: EVET, gösterilsin.** §1 kararı "gerçekçi berber sitesi" ise adres olmalı ve zaten
config'te var. L5 (Saatler & yer) bölümü `faq.address`'i okusun. Bedeli sıfır — veri mevcut.

---

## §9 — DESIGN'A TESLİM ÖZETİ

| | Sayı |
|---|---|
| Yüzey | **4** (demo sitesi · widget · gömülebilir snippet · dashboard) |
| Landing bölümü | 9 (L1-L9) |
| Widget ekran/durumu | **65** (W1-W65 — W61 frontend karşılaması K4 ile, W62-W65 BULGU-9 ile eklendi 2026-08-31) |
| Snippet'e özgü ekran | 4 (S1-S4) |
| Dashboard ekranı | 20 (D1-D20) |
| **Toplam tasarlanacak ekran/durum** | **98** |
| Alert sınıfı (rozet olarak) | **24** |
| Stage (durum grafiği) | 9 |
| Ortak öğe kuralı | 7 |

**Design'ın uyacağı üç sert kural:**
1. Bu belgede olmayan ekran **yok**; olan her ekran **var**.
2. Görsel dil **mevcut Cream & Ink varyantlarından** genişletilir; `tokens.css` **kullanılmaz**.
3. Metinler **`messageTemplates`'ten** gelir — Design yeni müşteri-metni **uydurmaz**; metni
   olmayan ekranlar §8 K1'de karara bağlıdır.
