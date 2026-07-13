"""Telegram bot (tugmali menyu). Test yaratish, web-oyna orqali yechish, jonli panel."""
import os, asyncio, logging

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                      WebAppInfo)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
import db, parser

log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x}
BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
if not BASE_URL and os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    BASE_URL = "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"].strip().rstrip("/")

COUNTS = [10, 20, 30, 40, 50]
TIMES = [15, 30, 45, 60]

BTN_NEW = "➕ Yangi test"; BTN_BASES = "📚 Bazalarim"; BTN_RESULTS = "📊 Natijalar"
BTN_CLEAR = "🗑 Bazani tozalash"; BTN_HELP = "ℹ️ Yordam"


def is_admin(uid): return (not ADMIN_IDS) or (uid in ADMIN_IDS)

def menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_NEW)], [KeyboardButton(BTN_BASES), KeyboardButton(BTN_RESULTS)],
         [KeyboardButton(BTN_CLEAR), KeyboardButton(BTN_HELP)]], resize_keyboard=True)

HELP = ("ℹ️ <b>Qo'llanma</b>\n\n1️⃣ Word bazani (.docx) yuboring — <code>#1.</code> va to'g'ri javobda <code>+</code>.\n"
        "2️⃣ <b>➕ Yangi test</b> → savol soni → rejim → vaqt → test <b>kodi</b>.\n"
        "3️⃣ Kod/havolani o'quvchilarga bering. Ular web-oynada formulalarni ko'rib yechadi.\n"
        "4️⃣ <b>📊 Natijalar</b> — jonli panel: kim yechyapti, ball, o'rtacha.\n\n"
        "Formula, grek, indeks, rasm — web-oynada chiroyli ko'rinadi.")


async def cmd_start(update, ctx):
    if ctx.args:
        return await offer_test(update, ctx, ctx.args[0].upper())
    uid = update.effective_user.id
    if is_admin(uid):
        await update.message.reply_html("👋 <b>Random Test Generator</b>\n\n"
            "Word bazani (.docx) yuboring yoki tugmalardan foydalaning 👇", reply_markup=menu())
    else:
        await update.message.reply_html("👋 Salom! O'qituvchi bergan <b>kodni</b> yuboring.",
                                        reply_markup=ReplyKeyboardRemove())


async def on_document(update, ctx):
    uid = update.effective_user.id
    if not is_admin(uid):
        return await update.message.reply_text("Faqat o'qituvchi baza yuklay oladi.")
    doc = update.message.document
    name = doc.file_name or "baza.docx"
    if not name.lower().endswith(".docx"):
        return await update.message.reply_text("Iltimos .docx fayl yuboring (.doc emas).")
    msg = await update.message.reply_text("⏳ O'qilmoqda…")
    try:
        f = await doc.get_file()
        data = bytes(await f.download_as_bytearray())
        questions = await asyncio.to_thread(parser.parse_docx, data, name)
        if not questions:
            return await msg.edit_text("❌ Savol topilmadi. <code>#1.</code> va <code>+</code> ni tekshiring.",
                                       parse_mode="HTML")
        base_id = db.add_base(uid, name)
        added = await asyncio.to_thread(db.add_questions, uid, base_id, name, questions)
        await msg.edit_text(f"✅ <b>{name}</b>: {added} ta savol.\nJami: <b>{db.question_count(uid)}</b> ta.",
                            parse_mode="HTML")
        await update.message.reply_text("➕ Yangi test tugmasini bosing.", reply_markup=menu())
    except Exception as e:
        log.exception("upload"); await msg.edit_text(f"❌ Xatolik: {e}")


# ---- Yangi test: son -> rejim -> vaqt ----
async def start_newtest(update, ctx):
    uid = update.effective_user.id
    total = db.question_count(uid)
    if total == 0:
        return await update.message.reply_text("Avval Word baza yuboring.", reply_markup=menu())
    btns = [InlineKeyboardButton(f"{n} ta", callback_data=f"cnt:{n}") for n in COUNTS if n <= total]
    rows = [btns[i:i+3] for i in range(0, len(btns), 3)] if btns else []
    rows.append([InlineKeyboardButton(f"✅ Barchasi ({total})", callback_data=f"cnt:{total}"),
                 InlineKeyboardButton("✏️ Boshqa", callback_data="cnt:custom")])
    await update.message.reply_text(f"Bazada {total} ta savol. Nechta savol?",
                                    reply_markup=InlineKeyboardMarkup(rows))

async def on_count(update, ctx):
    q = update.callback_query; await q.answer()
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_count"] = True
        return await q.edit_message_text("✏️ Nechta savol? Sonini yozing:")
    ctx.user_data["nt"] = {"count": int(val)}
    await ask_mode(q)

async def ask_mode(q):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔀 Har xil (aralash)", callback_data="mode:1")],
        [InlineKeyboardButton("📋 Hammaga bir xil", callback_data="mode:0")]])
    await q.edit_message_text("Variantlar qanday bo'lsin?\n\n"
        "🔀 <b>Har xil</b> — har o'quvchida savol/variant boshqacha aralashadi (ko'chirishga qarshi)\n"
        "📋 <b>Bir xil</b> — hammaga bir tartib", parse_mode="HTML", reply_markup=kb)

async def on_mode(update, ctx):
    q = update.callback_query; await q.answer()
    ctx.user_data.setdefault("nt", {})["shuffle"] = int(q.data.split(":")[1])
    kb = [[InlineKeyboardButton(f"{t} daqiqa", callback_data=f"tm:{t}") for t in TIMES[:2]],
          [InlineKeyboardButton(f"{t} daqiqa", callback_data=f"tm:{t}") for t in TIMES[2:]],
          [InlineKeyboardButton("✏️ Boshqa", callback_data="tm:custom")]]
    await q.edit_message_text("⏱ Test necha daqiqa davom etsin?", reply_markup=InlineKeyboardMarkup(kb))

async def on_time(update, ctx):
    q = update.callback_query; await q.answer()
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_time"] = True
        return await q.edit_message_text("✏️ Necha daqiqa? Sonini yozing:")
    ctx.user_data.setdefault("nt", {})["time"] = int(val)
    await finalize_test(update, ctx, edit=True)

async def finalize_test(update, ctx, edit):
    uid = update.effective_user.id
    nt = ctx.user_data.get("nt", {})
    count = nt.get("count", 10); shuffle = nt.get("shuffle", 1); tlimit = nt.get("time", 30)
    total = db.question_count(uid); count = max(1, min(count, total))
    title = f"TEST ({count} ta, {tlimit} daq)"
    code, n = await asyncio.to_thread(db.create_test, uid, title, count, bool(shuffle), tlimit, None)
    test = db.get_test(code)
    bot_username = (await ctx.bot.get_me()).username
    student_link = f"https://t.me/{bot_username}?start={code}"
    txt = (f"✅ <b>Test tayyor!</b>\n\n🔑 Kod: <code>{code}</code>\n📝 Savollar: {n} ta\n"
           f"⏱ Vaqt: {tlimit} daqiqa\n🔀 Rejim: {'har xil' if shuffle else 'bir xil'}\n\n"
           f"👨‍🎓 O'quvchilar havolasi:\n{student_link}\n\nyoki <code>{code}</code> kodini yuborsin.")
    rows = []
    if BASE_URL:
        panel_url = f"{BASE_URL}/p/{code}/{test['panel_token']}"
        rows.append([InlineKeyboardButton("📊 Jonli panel (faqat siz)", web_app=WebAppInfo(url=panel_url))])
    else:
        txt += "\n\n⚠️ Panel uchun BASE_URL sozlanmagan."
    kb = InlineKeyboardMarkup(rows) if rows else None
    if edit:
        await update.callback_query.edit_message_text(txt, parse_mode="HTML", reply_markup=kb,
                                                      disable_web_page_preview=True)
    else:
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb,
                                        disable_web_page_preview=True)
    ctx.user_data.pop("nt", None)


# ---- Natijalar / bazalar / tozalash ----
async def show_results_list(update, ctx):
    uid = update.effective_user.id
    tests = db.tests_by_owner(uid)
    if not tests:
        return await update.message.reply_text("Hali test tuzmagansiz.", reply_markup=menu())
    rows = []
    for t in tests[:15]:
        if BASE_URL:
            url = f"{BASE_URL}/p/{t['code']}/{t['panel_token']}"
            rows.append([InlineKeyboardButton(f"📊 {t['code']} — {t['n']} ta savol",
                                              web_app=WebAppInfo(url=url))])
        else:
            rows.append([InlineKeyboardButton(f"🔑 {t['code']} — {t['n']} ta", callback_data="noop")])
    await update.message.reply_text("Test panelini oching:", reply_markup=InlineKeyboardMarkup(rows))

async def show_bases(update, ctx):
    uid = update.effective_user.id
    bl = db.base_list(uid)
    if not bl:
        return await update.message.reply_text("Baza yo'q. .docx yuboring.", reply_markup=menu())
    lines = ["📚 <b>Bazalaringiz:</b>"] + [f"• {b['name']} — {b['n']} ta" for b in bl]
    lines.append(f"\nJami: <b>{db.question_count(uid)}</b> ta.")
    await update.message.reply_html("\n".join(lines), reply_markup=menu())

async def ask_clear(update, ctx):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Ha", callback_data="clr:yes"),
                               InlineKeyboardButton("↩️ Bekor", callback_data="clr:no")]])
    await update.message.reply_text("Barcha bazangiz o'chiriladi. Rozimisiz?", reply_markup=kb)

async def on_clear(update, ctx):
    q = update.callback_query; await q.answer()
    if q.data == "clr:yes":
        db.clear_owner(q.from_user.id); await q.edit_message_text("🗑 Tozalandi.")
    else:
        await q.edit_message_text("↩️ Bekor qilindi.")


async def on_text(update, ctx):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if is_admin(uid):
        if text == BTN_NEW: return await start_newtest(update, ctx)
        if text == BTN_BASES: return await show_bases(update, ctx)
        if text == BTN_RESULTS: return await show_results_list(update, ctx)
        if text == BTN_CLEAR: return await ask_clear(update, ctx)
        if text == BTN_HELP: return await update.message.reply_html(HELP, reply_markup=menu())
        if ctx.user_data.get("await_count"):
            ctx.user_data["await_count"] = False
            if not text.isdigit(): return await update.message.reply_text("Faqat son yuboring.")
            ctx.user_data["nt"] = {"count": int(text)}
            # rejim so'raymiz (yangi xabar bilan)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔀 Har xil (aralash)", callback_data="mode:1")],
                [InlineKeyboardButton("📋 Hammaga bir xil", callback_data="mode:0")]])
            return await update.message.reply_html("Variantlar qanday bo'lsin?", reply_markup=kb)
        if ctx.user_data.get("await_time"):
            ctx.user_data["await_time"] = False
            if not text.isdigit(): return await update.message.reply_text("Faqat son yuboring.")
            ctx.user_data.setdefault("nt", {})["time"] = int(text)
            return await finalize_test(update, ctx, edit=False)
    code = text.upper()
    if 4 <= len(code) <= 8 and code.isalnum():
        return await offer_test(update, ctx, code)
    if is_admin(uid):
        await update.message.reply_text("Baza yuboring yoki tugmalardan tanlang 👇", reply_markup=menu())
    else:
        await update.message.reply_text("Test kodini yuboring (masalan ABC123).")


# ---- O'quvchi: web-oyna ----
async def offer_test(update, ctx, code):
    test = db.get_test(code)
    if not test:
        return await update.effective_message.reply_text("❌ Bunday kodli test topilmadi.")
    user = update.effective_user
    ex = db.existing_session(code, user.id)
    if ex and ex["status"] == "finished":
        sc = ex["score"]; tot = ex["total"]; pct = round(100*sc/tot) if tot else 0
        return await update.effective_message.reply_html(
            f"✅ Siz bu testni allaqachon yechdingiz.\nNatija: <b>{sc}/{tot}</b> ({pct}%)")
    n = len(test["question_ids"])
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Testni boshlash", callback_data=f"begin:{code}")]])
    await update.effective_message.reply_html(
        f"📝 <b>Test:</b> {code}\nSavollar: <b>{n}</b> ta\n⏱ Vaqt: <b>{test['time_limit']}</b> daqiqa\n\n"
        "«Boshlash»ni bosgach vaqt ketadi va web-oyna ochiladi 👇", reply_markup=kb)

async def on_begin(update, ctx):
    q = update.callback_query; await q.answer()
    code = q.data.split(":")[1]
    user = q.from_user
    if not BASE_URL:
        return await q.edit_message_text("⚠️ Server manzili sozlanmagan (BASE_URL). O'qituvchiga xabar bering.")
    ex = db.existing_session(code, user.id)
    if ex and ex["status"] == "finished":
        sc, tot = ex["score"], ex["total"]; pct = round(100*sc/tot) if tot else 0
        return await q.edit_message_text(f"✅ Allaqachon yechilgan. Natija: {sc}/{tot} ({pct}%)")
    if ex and ex["status"] == "active":
        token = ex["token"]  # davom etadi
    else:
        name = user.full_name + (f" (@{user.username})" if user.username else "")
        token = await asyncio.to_thread(db.create_web_session, code, user.id, name)
        if not token:
            return await q.edit_message_text("Testni boshlab bo'lmadi.")
    url = f"{BASE_URL}/t/{token}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🖥 Testni ochish", web_app=WebAppInfo(url=url))]])
    await q.edit_message_text("✅ Vaqt boshlandi! Testni ochish uchun tugmani bosing 👇", reply_markup=kb)


def build_app():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newtest", start_newtest))
    app.add_handler(CommandHandler("bases", show_bases))
    app.add_handler(CommandHandler("results", show_results_list))
    app.add_handler(CallbackQueryHandler(on_count, pattern=r"^cnt:"))
    app.add_handler(CallbackQueryHandler(on_mode, pattern=r"^mode:"))
    app.add_handler(CallbackQueryHandler(on_time, pattern=r"^tm:"))
    app.add_handler(CallbackQueryHandler(on_clear, pattern=r"^clr:"))
    app.add_handler(CallbackQueryHandler(on_begin, pattern=r"^begin:"))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app
