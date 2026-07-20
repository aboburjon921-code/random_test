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
