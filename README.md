# 📝 Random Test — Telegram bot + web imtihon

Word bazadan random test tuzadi. O'quvchilar **web-oynada** (formulalar chiroyli
ko'rinadi, A/B/C/D tugmalari, taymer) yechadi, bot **avtomatik baholaydi**.
O'qituvchida **jonli panel**.

## Ishlash tartibi
- O'qituvchi Word bazani (.docx) yuboradi → **➕ Yangi test** → savol soni → rejim (har xil/bir xil) → vaqt → **test kodi**.
- O'quvchi kod/havola bilan kiradi → **Boshlash** (vaqt ketadi) → web-oynada savollarni ko'rib yechadi → **Yakunlash** → darrov natija.
- O'qituvchi **📊 Natijalar** → jonli panel: kim yechyapti/yechdi, ball, o'rtacha, eng qiyin savol.

Savol formati: savol oldida `#1.`, to'g'ri javob oldida `+` (masalan `+B)`).

---

## 1. Token
[@BotFather](https://t.me/BotFather) → `/newbot` → token oling.
O'z Telegram ID'ingizni [@userinfobot](https://t.me/userinfobot) dan biling.

## 2. GitHub
Shu papkadagi barcha fayllarni repoga yuklang (`.env` YUKLANMAYDI).

## 3. Railway
1. **New Project → Deploy from GitHub repo** → repongiz.
2. **Settings → Networking → Generate Domain** bosing.
   Bu web-oyna uchun **shart**. Railway `RAILWAY_PUBLIC_DOMAIN` ni avtomatik beradi,
   bot uni o'qiydi (BASE_URL'ni qo'lda yozish shart emas).
3. **Variables** ga qo'shing:
   - `BOT_TOKEN` = tokeningiz
   - `ADMIN_IDS` = Telegram ID'ingiz
   - `DB_PATH` = `/data/data.db`
   - (Agar web havolalar ishlamasa) `BASE_URL` = `https://<domeningiz>`
4. **Volume ulang** (ma'lumot yo'qolmasligi uchun): servis → **Volume** →
   Mount path `/data`.
5. **Deploy**. Log'da `Bot va web-server ishga tushdi` chiqsa — tayyor.

> Eslatma: start buyrug'i endi **`python main.py`** (Procfile'da). U botni ham,
> web-serverni ham birga yuritadi.

## Muhim
- Deploy'dan keyin bazani bir marta **🗑 tozalab, qayta yuklang** (formulalar to'liq saqlanishi uchun).
- Faqat `.docx` (eski `.doc` emas).
- Web-oyna Telegram ichida ochiladi; formulalar MathJax bilan chiziladi.

---

## 🎮 Jonli o'yin (Kahoot uslubi) — YANGI

Uy-vazifa rejimiga tegmasdan qo'shildi. Ikki rejim yonma-yon ishlaydi.

**O'qituvchi (Telegram bot):**
1. `🎮 Jonli o'yin` tugmasi → savol soni → har savolga vaqt (soniya).
2. Bot **PIN kod** + **Host ekran havolasi** beradi.
3. Host havolasini proyektor/TV ulangan kompyuterda oching (`/host/<PIN>/<token>`).

**O'quvchilar (Telegramsiz, brauzer):**
- Telefon brauzerida `BASE_URL/join` (yoki QR skaner) → PIN + ism → o'yinga kirishadi.
- Ularda faqat **4 rang/shakl** tugmasi chiqadi; savol matni faqat host ekranda.

**Oqim:** Lobby → savol (taymer + jonli javob hisoblagichi) → to'g'ri javob + diagramma →
reyting → yakunda **top-3 podium** (konfetti). Ball Kahootdek: tezlikka qarab 500–1000 +
ketma-ket to'g'ri javob uchun streak bonusi (+100…+500).

### Yangi qismlar
- `db.py` — `games`, `gplayers`, `ganswers` jadvallari + o'yin mantiqi (`create_live_pick`,
  `join_game`, `submit_answer`, `host_advance`, `host_state`, `player_state`).
- `webapp.py` — `/join` (o'quvchi), `/host/<pin>/<token>` (katta ekran) sahifalari va
  `/live/api/*` endpointlari (polling, ~1 s).
- `bot.py` — `🎮 Jonli o'yin` tugmasi va yaratish oqimi.

### Server eslatmasi
- `BASE_URL` (yoki `RAILWAY_PUBLIC_DOMAIN`) sozlangan bo'lishi shart — host va join havolalari
  shundan hosil bo'ladi.
- Real-time uchun oddiy **polling** ishlatilgan — qo'shimcha kutubxona/servis shart emas,
  bepul xostinglarda ham ishlaydi.
- Bot hozircha **polling** rejimida. Doim-tirik bepul xosting uchun keyinchalik **webhook**'ga
  o'tkazish tavsiya etiladi (ixtiyoriy, alohida qadam).

---

## 🖨 Chop etiladigan test (Word + PDF) — 1-faza

Qog'ozli test tizimining birinchi qismi. Random test yaratib, **Word va PDF** qilib beradi —
toza, javob panjarasisiz, `+` belgisisiz (o'quvchilarga tarqatishga tayyor material).

**Ishlatish:** `🖨 Chop etiladigan test` → 🎲 Aralash yoki 📚 Mavzu bo'yicha → savol soni →
**variantlar soni** (1–4) → bot har variant uchun **Word + PDF + javob kaliti** yuboradi.

- Formula/rasm/bezaklar asl Word XML'dan **aynan** tiklanadi.
- Har variantda savol va variantlar aralashtiriladi (ko'chirishga qarshi), kaliti alohida.
- Sarlavhada jami savol soni.
- Javob kalitlari serverda saqlanadi (`ptests`) — keyingi fazada skanerlash uchun.

### Yangi qism
- `docgen.py` — **YANGI FAYL**. Word yasash (zip+XML, faqat stdlib) va `docx→pdf` (LibreOffice).
- `db.py` — `ptests` jadvali + `pick_ids`, `save_print_test`, `get_print_test`.
- `bot.py` — `🖨 Chop etiladigan test` tugmasi va oqimi.

### ⚠️ PDF uchun server sozlamasi
PDF `docx→pdf` uchun serverda **LibreOffice** bo'lishi kerak (`soffice`). Bo'lmasa — Word baribir
ishlaydi, PDF o'rniga ogohlantirish chiqadi. Railway/nixpacks'da qo'shish uchun loyiha ildiziga
`nixpacks.toml`:

```toml
[phases.setup]
nixPkgs = ["...", "libreoffice"]
```

(Aniq sozlamani qaysi xostingda ekaningizga qarab beramiz.) Yangi pip kutubxona shart emas —
Word faqat standart kutubxonalar bilan yasaladi.

---

## 📝 Javob varag'i (OMR titul) — 2-faza

Chop etiladigan test yaratilganda **har variant bilan javob varag'i (PDF)** ham keladi:
- 4 burchakda **langar** kvadratlari (skaner varaqni topib to'g'rilaydi)
- **QR kod** = test kodi + variant (skaner qaysi kalit ekanini biladi)
- **5 xonali ID** panjarasi (o'quvchi raqamini bo'yaydi)
- Har savolga **A–D** doiralari
- Bitta varaqqa 40 tagacha savol (2 ustun)

### Yangi qism
- `omr.py` — **YANGI FAYL**. Javob varag'i geometriyasi (`geometry()`) va PDF (`build_answer_sheet_pdf()`).
  3-fazadagi skaner aynan shu geometriyadan foydalanadi.
- `bot.py` — chop etish oqimi endi javob varag'ini ham yuboradi.

Yangi pip kutubxona: **reportlab** (javob varag'i PDF uchun). `requirements.txt` ga qo'shildi.

---

## 📷 Skaner (OMR) — 3-faza

O'quvchilar to'ldirgan javob varaqlarini telefon kamerasi bilan suratga olib avtomatik baholaydi.

**Ishlatish:** `📷 Skaner` → tugma orqali telefon brauzerida `/scan` ochiladi → har varaqni
suratga olasiz → natija darhol: ID, ball (to'g'ri/jami), xato savollar. Shubhali/bo'sh/ikki marta
bo'yalgan javoblar belgilanadi — ularni joyida tuzatib qayta hisoblaysiz.

**Qanday ishlaydi:** 4 burchak langari bo'yicha varaqni to'g'rilaydi → QR'dan test kodi va variantni
oladi → ID va bo'yalgan doiralarni o'qiydi → saqlangan kalit bilan solishtiradi → natijani saqlaydi.

### Yangi qism
- `omrscan.py` — **YANGI FAYL**. OpenCV OMR dvigateli (`scan`, `grade`).
- `db.py` — `pscans` jadvali + `save_scan`, `scan_results`, `update_scan_answers`.
- `webapp.py` — `/scan` sahifasi va `/omr/api/*` (scan, confirm, results).
- `bot.py` — `📷 Skaner` tugmasi.

### ⚠️ Server sozlamasi
Skaner uchun **opencv-python-headless** kerak (`requirements.txt` ga qo'shildi) va `python-multipart`
(rasm yuklash uchun). OpenCV serverga ~50–70MB qo'shadi. Agar bepul hostingda og'irlik qilsa,
skanerni telefon brauzeriga (OpenCV.js) ko'chirish mumkin — ayting, o'sha variantni ham beraman.

---

## 📊 Skaner natijalari paneli — 4-faza

Chop etilgan test yaratilganda xabarda **📊 Natijalar** havolasi keladi (yoki `/natija KOD`).
Sahifa **jonli yangilanadi** — skaner qilgan sari o'quvchilar paydo bo'ladi.

Jadval ustunlari:
- **ID** (o'quvchi raqami) + variant
- **To'g'ri** — nechta to'g'ri / jami + foiz
- **Xato savollar** — har biri `2A(B)` ko'rinishida: *2-savol, o'quvchi A belgilagan, to'g'risi B*
  (bo'sh qoldirsa `5—(A)`)

Yuqorida: o'quvchilar soni, o'rtacha ball. Pastda: eng ko'p xato qilingan savollar.
**⬇️ Excel (CSV)** tugmasi bilan yuklab olinadi.

### Yangi qism
- `db.py` — `scan_report(code)`.
- `webapp.py` — `/results/{code}` sahifasi, `/results/{code}.csv`, `/omr/api/report`.
- `bot.py` — chop-test xabarida natijalar havolasi + `/natija KOD` buyrug'i.
