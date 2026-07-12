# Random Test Telegram Bot

Word (.docx) test bazalaridan random test tuzib beruvchi Telegram bot.
Bot foydalanuvchi tashlagan `.docx` fayllardan savollarni o'qiydi, kerakli
sondagi savolni tasodifiy tanlaydi, variantlarini aralashtiradi va ikkita
Word fayl qaytaradi: **test** (o'quvchiga) va **javoblar** (o'qituvchiga).
Shundan so'ng, o'quvchilar javoblarini **Telegram Mini App** orqali kiritib,
natijani shu zahoti ko'rishlari mumkin.

## Tuzilma

```
src/
  core.js    — .docx parsing/generatsiya "yadrosi" (asl HTML fayldan ko'chirilgan)
  db.js      — javob kalitlarini saqlaydigan oddiy JSON-fayl "baza"
  bot.js     — Telegram bot (Telegraf)
  server.js  — Express server: webapp + API + botni ishga tushiradi
public/webapp/ — javoblarni kiritish/tekshirish uchun Telegram Mini App
```

## Word fayl formati (o'zgarmadi)

- Har bir savol `#1.` `#2.` … ko'rinishida boshlanadi
- Variantlar `A)` `B)` `C)` `D)` ko'rinishida, to'g'ri javob oldida `+`: `+B)`
- Shrift muhim emas — natija doim Times New Roman
- Rasm/jadval saqlanadi

## Lokal ishga tushirish

```bash
npm install
cp .env.example .env
# .env faylga BOT_TOKEN ni yozing (@BotFather dan oling)
npm start
```

`WEBAPP_URL` ni lokal test qilishda bo'sh qoldirsangiz ham bo'ladi — bot ishlayveradi,
faqat "javoblarni tekshirish" tugmasi ko'rinmaydi (chunki Telegram WebApp uchun
**https** ochiq manzil kerak, localhost ishlamaydi).

## Railway'ga deploy qilish (GitHub orqali)

1. Shu papkani GitHub repo qilib yuklang.
2. Railway → **New Project → Deploy from GitHub repo** → shu repo'ni tanlang.
3. Railway avtomatik `npm install` va `npm start`ni bajaradi (package.json orqali aniqlaydi).
4. **Variables** bo'limiga qo'shing:
   - `BOT_TOKEN` — @BotFather'dan olingan token
   - `WEBAPP_URL` — hozircha bo'sh qoldiring
5. **Settings → Networking → Generate Domain** — Railway sizga
   `https://xxxxx.up.railway.app` kabi manzil beradi.
6. `WEBAPP_URL` o'zgaruvchisini `https://xxxxx.up.railway.app/webapp/` qilib
   yangilang (oxiridagi `/webapp/` shart) va qayta deploy bo'lishini kuting.
7. @BotFather'da botingiz uchun ixtiyoriy: `/setmenubutton` yoki webapp
   tugmasi — lekin bu shart emas, chunki bot javob sifatida o'zi webapp
   tugmasini yuboradi (test generatsiya qilingandan keyin).

Shu bilan tayyor — botga `.docx` tashlab ko'ring.

## Eslatma: ma'lumotlar bazasi

Hozir javob kalitlari oddiy `data/tests.json` faylida saqlanadi. Bu MVP uchun
yetarli, lekin Railway konteyneri qayta deploy bo'lganda fayl tizimi
tozalanishi mumkin (agar persistent volume ulanmagan bo'lsa). Agar bu muhim
bo'lsa:
- Railway'da **Volume** qo'shib, `DB_PATH` env o'zgaruvchisini shu volume
  ichidagi yo'lga ko'rsating, YOKI
- `src/db.js`ni Postgres/Redis'ga almashtiring (funksiyalar interfeysi bir xil
  qoladi: `saveTest`, `getTest`, `saveAttempt`).

## Cheklovlar

- Hozircha PDF emas, faqat **.docx** chiqadi (asl vositangizdagi kabi, "chop
  etish → PDF saqlash" orqali o'quvchi/o'qituvchi o'zi PDF qilishi mumkin).
  Agar avtomatik PDF kerak bo'lsa, aytib qo'ying — LibreOffice orqali
  server-side konvertatsiya qo'shib beraman.
- Har bir foydalanuvchining yuklagan fayllari xotirada (RAM) saqlanadi —
  bot qayta ishga tushsa, `.docx` fayllarni qayta tashlash kerak bo'ladi
  (`/reset` orqali tozalash mumkin).
