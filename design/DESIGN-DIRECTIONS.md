# Salon Booking Bot — Design Directions (v1)

> Araştırma tabanlı design direction brief'i. 3 yön de **aynı wireframe'in skin'i değil** —
> üç farklı strateji: **marka-odaklı (craft)** · **ifade-odaklı (bold)** · **ürün-odaklı (conversion)**.
> Mockup fazında üçü de bu spec'e göre kurulur, sonra tek yön seçilip derinleştirilir.

---

## 0. Araştırma Özeti (kaynaklar en altta)

### İncelenen ödüllü referanslar (canlı gezildi, screenshot'landı)

| Referans | Ödül | Ne yapıyor | Bizim için ders |
|---|---|---|---|
| **Hagi's Barber Shop** (hagisbarbering.com) | Awwwards **SOTD** (7.68) | Krem (#F2F1EA) + mürekkep siyahı; yüksek kontrastlı didone serif; el yazısı imza logosu scroll ile çiziliyor; krem/siyah blok geçişleri; büyük gerçek fotoğraf | Ödüllü berber siteleri **altın-siyah değil** — krem/açık zemin + tek vurgu. Motion tek bir "signature moment"ta yoğunlaşıyor, her yere serpiştirilmiyor |
| **Rendezvous Barbers** (myrendezvous.ca) | Awwwards Honorable Mention | Tek cesur marka rengi (turuncu #F05A24 civarı) full-bleed; dev italik serif başlıklar; monospace caption'lar; **kalıcı BOOK NOW pill** (sağ alt); video içerik | Tek güçlü renk + disiplinli tipografi = kişilik. Kalıcı booking CTA'sı conversion pattern'i olarak ödüllü işte bile var |
| **DON Barber & Groom** (don-barber.gr) | Awwwards HM + CSSDA | Kemik/ivory zemin; condensed uppercase grotesk; sakin, pastel-gri fotoğraf tonları; ölçülü micro-animation | "Quiet luxury" = az renk, çok beyaz alan, kaliteli tip. Lüks hissi süslemeyle değil boşlukla kuruluyor |

### 2026 motion/tip trendleri (Figma, TheeDigital, Elementor trend raporları)
- **Kinetic typography** hero'da kullanılıyor ama anahtar kelime **restraint (ölçülülük)**: "purposeful motion" — dikkat yönlendiren, mesajı destekleyen hareket; efekt olsun diye değil.
- **Micro-interactions** (hover, buton, form feedback) arayüzü "canlı" hissettiren asıl katman.
- Scroll-driven anlatı OK, ama içerik **scroll etmeyen kullanıcıya da görünür olmalı** (CC'nin C varyantının öldüğü yer).

### Booking conversion UX (Booksy, Trafft, Baymard verileri)
- CTA **above the fold** + her sayfada; kalıcı (sticky/floating) booking girişi.
- **Guest booking**: rezervasyon için kayıt zorunluluğu = ~%24 terk (Baymard).
- **Fiyat şeffaflığı**: fiyatı sona saklamak birincil terk sebebi → fiyat listesi net, animasyonsuz.
- Mobile ayrı tasarım problemi: single-column form (~15 sn daha hızlı), büyük tap target.
- **Bizim ürün farkı:** rezervasyon bir form değil, **sohbet (bot)**. Hero bunu GÖSTERMELİ — üç CC varyantının da kaçırdığı asıl fırsat bu.

---

## 1. Ortak Temel (üç yönde de geçerli — pazarlık yok)

1. **Chat-first kanıt:** Hero'da veya hemen altında canlı görünümlü bir **conversation mock** (WhatsApp/webchat balonları, typing indicator, saniyeler içinde onay). Ürünün vitrini = botun kendisi.
2. **Fiyatlar statik.** Count-up yok. Sayı = güven.
3. **Reveal disiplini:** içerik JS olmadan da görünür (`opacity` başlangıcı asla 0'da kalmaz); reveal yalnızca `IntersectionObserver` + kısa (300–500ms) fade/translate; `prefers-reduced-motion` desteklenir.
4. **Sticky header ≠ başlık katili:** tüm section başlıklarına `scroll-margin-top`.
5. **Kontrast:** body text min **WCAG AA (4.5:1)**; hiçbir metin "atmosfer" uğruna gömülmez.
6. **Kalıcı CTA:** sağ altta pill ("Randevu için yazın 👋") kalıyor — ama hero'daki chat mock ile aynı görsel dilde, kopuk değil.
7. **Görsel placeholder yasak:** gerçek foto yoksa, sanat yönetimli duotone/grain'li stok veya AI görsel — "görsel placeholder" yazan gri kutu portfolyoda olmaz.
8. **Font seçiminde Türkçe glyph kontrolü** (ğ, ş, İ, ı) — aşağıdaki tüm öneriler Google Fonts latin-ext; mockup'ta yine de görsel doğrulanır.

**Motion bütçesi (üç yönde de):** 1 signature moment (hero) + micro-interactions (hover/press/typing) + section fade. Başka yok.

---

## 2. Direction A — «Crema & Mürekkep» *(marka-odaklı, editorial craft)*

**Referans DNA:** Hagi's. **Strateji:** zanaat + güven; "köklü dükkân" hissi.

- **Palet:** zemin `#F1EEE6` (crema) · mürekkep `#16150F` · vurgu **oxide kızılı** `#B4472E` (jilet/berber direği çağrışımı, altın YOK). Siyah full-bleed bloklar bölüm ritmi kurar (krem→siyah→krem).
- **Tipografi:** Display: **Fraunces** (variable, yüksek kontrast, karakterli) · Body/UI: **Instrument Sans**. Fiyat/saat etiketleri: Instrument Sans tabular.
- **Layout/IA:** Asimetrik editorial grid (12-col, 1.5 kolon offset başlıklar). Hero split: sol dev serif söz + sağda **telefon çerçevesiz, kartlar halinde akan chat mock**. Hizmetler = kart değil, **menü/gazete fiyat listesi** (çizgili, satır bazlı). Galeri: farklı boyutlu foto kolajı (Hagi's gibi), grid değil.
- **Motion:** Signature: hero'da jilet çizgisinin (SVG stroke) kendini çizmesi + chat balonlarının sıralı "gönderilme"si. Foto'larda %3-5 parallax. Hover: satır altı çizgi genişlemesi.
- **Risk/trade-off:** Fotoğraf kalitesine bağımlı — kötü foto bu yönü öldürür. En "zanaat", en az "tech" hissi.

## 3. Direction B — «Signal» *(ifade-odaklı, bold pop)*

**Referans DNA:** Rendezvous. **Strateji:** sokak + enerji; genç kitle, akılda kalıcılık.

- **Palet:** tek cesur renk **vermilyon** `#E8502A` (alternatif: racing green `#1E3A2F`) full-bleed + kırık beyaz `#F5F2EC` + mürekkep `#141414`. Sarı bant/caution tape YOK.
- **Tipografi:** Display: **Instrument Serif** italik dev boyut (viewport'u kesen başlıklar) · Etiket/fiyat/saat: **Space Mono** (mono = "sistem/bot konuşuyor" hissi, fiyat listesinde terminal netliği).
- **Layout/IA:** Renk-blok sayfa: turuncu hero (dev italik söz + tek satır mono alt yazı) → beyaz hizmet bloğu (mono fiyat tablosu) → siyah full-bleed video/foto bloğu → turuncu kapanış CTA. Chat mock: hero'da değil, **ikinci blokta "işte böyle çalışıyor" şeridi** olarak yatay 3 adım (mesaj → bot cevabı → onay). Kalıcı BOOK pill sağ altta (Rendezvous pattern'i).
- **Motion:** Signature: hero başlığının satır satır maske reveal'i (bir kez, load'da) + marquee şerit (marka adı, yavaş). Hover: renk inversiyonu (turuncu↔siyah). Mono rakamlar sabit.
- **Risk/trade-off:** Cesaret ister; yanlış tonda "ucuz fast-food" hissi verebilir. Premium değil, kültür/enerji satar.

## 4. Direction C — «Atelier OS» *(ürün-odaklı, quiet luxury × SaaS)*

**Referans DNA:** DON + booking-UX araştırması. **Strateji:** bu bir *ürün vitrini* — botu sat, dükkânı değil. Portfolyo için en güçlü aday (işveren "product sense" görür).

- **Palet:** kemik `#ECE9E2` · grafit `#1C1C1A` · fotoğraflar muted (düşük doygunluk, gri-yeşil tonlama) · vurgu: **tek** sıcak nötr `#C77B4F` (yalnızca CTA ve durum noktaları).
- **Tipografi:** Display: **Archivo** (condensed uppercase, DON hissi) · Body/UI: **Inter**. Chat UI kendi tip ölçeğinde (gerçek messenger metriği).
- **Layout/IA:** Hero = **açık duran chat penceresi** sahnenin merkezinde (gerçek boyut, gölgeli panel), yanında tek cümle değer önerisi + "Randevu Al" (chat'i tetikler). Altında: 3 kanıt bloğu (7/24 cevap · saniyede onay · telefon trafiği yok) → **şeffaf fiyat tablosu** (satır bazlı, mono değil ama tabular) → çalışma saatleri → mini SSS. Galeri minimal (2-3 foto yeter).
- **Motion:** Yalnız micro-interaction: chat'te typing indicator + balon spring'i (gerçekçi), buton press states, 250ms fade'ler. Scroll efekti neredeyse yok — sakinlik bilinçli tercih.
- **Risk/trade-off:** En az "wow", en çok güven. Awwwards değil müşteri kazanır; portfolyoda "bu insan ürün düşünüyor" dedirtir.

---

## 5. Mockup Fazı Planı

1. Üç yön tek `variants/` klasöründe, **her biri kendi IA'sı ile** (aynı iskelete skin giydirmek yasak).
2. Sıra: **C → A → B** (C en hızlı doğrulanır; chat mock component'i üçünde ortak kullanılır → önce onu kur).
3. Her mockup'ta test: ilk paint'te içerik görünür mü · sticky header başlık kesiyor mu · fiyatlar statik mi · mobile 390px'te kırılım · kontrast (Lighthouse a11y ≥ 90).
4. Seçim kriteri: hedef müşteri (salon sahibi) kimliği + portfolyo mesajı. Ön eğilimim **C ana yön, A'dan foto/serif dozu** — ama karar mockup'ları görünce.

## Kaynaklar
- https://www.awwwards.com/sites/hagisbarbershop · https://hagisbarbering.com
- https://www.awwwards.com/sites/rendezvous-barbers · https://www.myrendezvous.ca
- https://www.awwwards.com/sites/don-barber-groom · https://don-barber.gr/en/
- https://www.figma.com/resource-library/web-design-trends/ · https://www.theedigital.com/blog/web-design-trends · https://elementor.com/blog/web-design-trends-2026/
- https://biz.booksy.com/en-us/blog/website-booking-system-guide-implement-optimize-for-your-salon · https://trafft.com/booking-page-design/ (Baymard verileri buradan aktarım)
