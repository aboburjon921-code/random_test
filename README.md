# 📝 Random Test Generator — Telegram bot

Word bazadan random test tuzadigan, o'quvchilarga A/B/C/D tugmalari bilan yechtiradigan va
**avtomatik baholaydigan** Telegram bot.

- O'qituvchi Word bazani (`.docx`) yuboradi → savollar saqlanadi
- `/newtest` → nechta savol kerakligini tanlaydi → **test kodi** oladi (+ Word/kalit fayllari)
- O'quvchilar kod (yoki havola) orqali kiradi, tugmalar bilan yechadi
- Bot darrov ball, baho va xato savollarni chiqaradi; o'qituvchi `/results` bilan barcha natijani ko'radi

Savol formati (Word ichida): savol oldida `#1.` `#2.` …, to'g'ri javob oldida `+` — masalan `+B)`.
Formulalar, grek harflari, yuqori/pastki indeks, rasm va jadvallar ham qo'llab-quvvatlanadi.

---

## 1. BotFather'dan token olish

1. Telegramda [@BotFather](https://t.me/BotFather) ni oching → `/newbot`
2. Bot nomi va username bering (username `_bot` bilan tugashi kerak)
3. Sizga **token** beriladi: `123456789:AAE...` — buni saqlab qo'ying

O'zingizning Telegram ID raqamingizni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing.

## 2. GitHub'ga joylash

1. GitHub'da yangi (private) repo oching
2. Shu papkadagi barcha fayllarni repога yuklang (`.env` faylini YUKLAMANG — u `.gitignore`da)

```bash
git init
git add .
git commit -m "test bot"
git branch -M main
git remote add origin https://github.com/FOYDALANUVCHI/REPO.git
git push -u origin main
```

## 3. Railway'ga ulash

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → repongizni tanlang
2. **Variables** bo'limiga o'zgaruvchilar qo'shing:
   - `BOT_TOKEN` = BotFather bergan token
   - `ADMIN_IDS` = sizning Telegram ID'ingiz (masalan `123456789`). Bir nechta bo'lsa vergul bilan.
   - `DB_PATH` = `/data/data.db`  *(quyidagi Volume bilan birga)*
3. **Settings → Start Command** ni tekshiring: `python bot.py` (Procfile ni avtomatik oladi)

### ⚠️ Muhim: ma'lumotlar saqlanishi uchun Volume ulang

Railway konteynerining diski har qayta ishga tushganda **tozalanadi**. Bazangiz va natijalar
yo'qolmasligi uchun **Volume** ulash SHART:

1. Railway loyihasida servisni oching → **Variables** yonidagi **+ New** → **Volume**
2. **Mount path** ni `/data` qilib bering
3. `DB_PATH` o'zgaruvchisi `/data/data.db` ga ishora qilsin (yuqorida qo'shdik)

Shundан keyin **Deploy** bosing. Bot bir-ikki daqiqada ishga tushadi.

## 4. Tekshirish

Telegramda botingizni oching → `/start`. O'qituvchi sifatida Word baza yuboring → `/newtest`.

---

## Buyruqlar

**O'qituvchi:**
| Buyruq | Vazifa |
|---|---|
| `.docx` fayl yuborish | Bazaga savol qo'shish |
| `/newtest` | Yangi test tuzish (kod olish) |
| `/mytests` | Testlar ro'yxati |
| `/results KOD` | Test natijalari |
| `/bases` | Bazalar ro'yxati |
| `/clear` | Barcha bazani tozalash |

**O'quvchi:**
| Buyruq | Vazifa |
|---|---|
| `/start KOD` yoki kodni yuborish | Testni boshlash |

---

## Mahalliy (kompyuterda) sinash

```bash
pip install -r requirements.txt
export BOT_TOKEN="sizning_token"
export ADMIN_IDS="sizning_id"
python bot.py
```

## Eslatmalar

- Faqat `.docx` qo'llanadi (eski `.doc` emas — Word'da "Farqli saqlash → .docx" qiling).
- Interaktiv rejimda formulalar Unicode matn ko'rinishida chiqadi (`x²`, `α`, `(a)/(b)`).
  Murakkab formulalar uchun o'quvchiga **Word/PDF** varianti aniqroq — bot uni ham yuboradi.
- Bir test kodini istagancha o'quvchi yechishi mumkin; har biriga variantlar alohida aralashadi.
