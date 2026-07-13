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
