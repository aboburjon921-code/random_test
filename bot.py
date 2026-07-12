
import os
import io
import asyncio
import logging

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                      InputFile)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)

import db
import parser
import docx_gen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x}
COUNTS = [10, 20, 30, 40, 50]

BTN_NEW = "➕ Yangi test"
BTN_BASES = "📚 Bazalarim"
BTN_RESULTS = "📊 Natijalar"
BTN_CLEAR = "🗑 Bazani tozalash"
BTN_HELP = "ℹ️ Yordam"


def is_admin(uid):
    return (not ADMIN_IDS) or (uid in ADMIN_IDS)

def teacher_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_NEW)],
         [KeyboardButton(BTN_BASES), KeyboardButton(BTN_RESULTS)],
         [KeyboardButton(BTN_CLEAR), KeyboardButton(BTN_HELP)]],
        resize_keyboard=True)

HELP_TEACHER = (
    "ℹ️ <b>Qo'llanma</b>\n\n"
    "1️⃣ Word bazani (.docx) shu yerga <b>yuboring</b>. Savol oldida <code>#1.</code>, "
    "to'g'ri javob oldida <code>+</code> (masalan <code>+B)</code>).\n"
    "2️⃣ <b>➕ Yangi test</b> → nechta savol → test <b>kodi</b> (Word fayllar ham keladi).\n"
    "3️⃣ Kodni o'quvchilarga bering.\n"
    "4️⃣ <b>📊 Natijalar</b> — kim nechta to'g'ri qilgani.\n\n"
    "Formula, grek, indeks (x²), rasm va jadval — hammasi saqlanadi. "
    "Word chiqishi bazadagidek, faqat aralashtirilgan bo'ladi."
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.args:
        return await offer_test(update, ctx, ctx.args[0].upper())
    uid = update.effective_user.id
    if is_admin(uid):
        await update.message.reply_html(
            "👋 <b>Random Test Generator</b>\n\n"
            "Word bazani (.docx) yuboring yoki pastdagi tugmalardan foydalaning 👇",
            reply_markup=teacher_menu())
    else:
        await update.message.reply_html(
            "👋 Salom! O'qituvchi bergan <b>kodni</b> shu yerga yuboring.",
            reply_markup=ReplyKeyboardRemove())


async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
            return await msg.edit_text(
                "❌ Savol topilmadi. Format: <code>#1.</code> va to'g'ri javobda <code>+</code>.",
                parse_mode="HTML")
        base_id = db.add_base(uid, name)
        added = await asyncio.to_thread(db.add_questions, uid, base_id, name, questions)
        total = db.question_count(uid)
        await msg.edit_text(f"✅ <b>{name}</b>: {added} ta savol qo'shildi.\n"
                            f"Jami: <b>{total}</b> ta savol.", parse_mode="HTML")
        await update.message.reply_text("➕ Yangi test tugmasini bosing.",
                                        reply_markup=teacher_menu())
    except Exception as e:
        log.exception("upload")
        await msg.edit_text(f"❌ Xatolik: {e}")


async def start_newtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    total = db.question_count(uid)
    if total == 0:
        return await update.message.reply_text("Avval Word baza yuboring (.docx).",
                                               reply_markup=teacher_menu())
    btns = [InlineKeyboardButton(f"{n} ta", callback_data=f"count:{n}")
            for n in COUNTS if n <= total]
    rows = [btns[i:i + 3] for i in range(0, len(btns), 3)] if btns else []
    rows.append([InlineKeyboardButton(f"✅ Barchasi ({total})", callback_data=f"count:{total}"),
                 InlineKeyboardButton("✏️ Boshqa son", callback_data="count:custom")])
    await update.message.reply_text(
        f"Bazangizda {total} ta savol. Nechta savoldan test tuzay?",
        reply_markup=InlineKeyboardMarkup(rows))


async def on_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_count"] = True
        return await q.edit_message_text("✏️ Nechta savol kerak? Sonini yozib yuboring:")
    await make_test(update, ctx, q.from_user.id, int(val), edit=True)


async def make_test(update, ctx, uid, count, edit):
    total = db.question_count(uid)
    count = max(1, min(count, total))
    title = f"TEST ({count} ta savol)"
    code, n = await asyncio.to_thread(db.create_test, uid, title, count, True, True, None)
    bot_username = (await ctx.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"
    text = (f"✅ <b>Test tayyor!</b>\n\n🔑 Kod: <code>{code}</code>\n📝 Savollar: {n} ta\n\n"
            f"O'quvchilar havola orqali kiradi:\n{link}\n\n"
            f"yoki botga <code>{code}</code> kodini yuborsin.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Natijalarni ko'rish",
                                                     callback_data=f"res:{code}")]])
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    # Word fayllar — bazadagi formulalar aynan saqlanadi
    chat_id = update.effective_chat.id
    try:
        qs = [db.get_question(qid) for qid in db.get_test(code)["question_ids"]]
        qs = [q for q in qs if q]
        test_b, key_b = await asyncio.to_thread(docx_gen.build, qs, title, db.get_media)
        await ctx.bot.send_document(chat_id, InputFile(io.BytesIO(test_b), f"test_{code}.docx"),
                                    caption="📘 Test (o'quvchiga)")
        await ctx.bot.send_document(chat_id, InputFile(io.BytesIO(key_b), f"javoblar_{code}.docx"),
                                    caption="🔑 Javoblar (o'qituvchiga)")
    except Exception:
        log.exception("docx")


async def show_results_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tests = db.tests_by_owner(uid)
    if not tests:
        return await update.message.reply_text("Hali test tuzmagansiz.",
                                               reply_markup=teacher_menu())
    rows = [[InlineKeyboardButton(f"🔑 {t['code']} — {t['n']} ta savol",
                                  callback_data=f"res:{t['code']}")] for t in tests[:20]]
    await update.message.reply_text("Qaysi test natijasini ko'rasiz?",
                                    reply_markup=InlineKeyboardMarkup(rows))


async def on_results(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = q.data.split(":")[1]
    t = db.get_test(code)
    if not t or t["owner_id"] != q.from_user.id:
        return await q.edit_message_text("Bunday test topilmadi.")
    res = db.results_for_test(code)
    if not res:
        return await q.edit_message_text(f"🔑 <b>{code}</b> — hali hech kim yechmagan.",
                                         parse_mode="HTML")
    lines = [f"📊 <b>{code}</b> natijalari:\n"]
    for i, r in enumerate(res, 1):
        pct = round(100 * r["score"] / r["total"]) if r["total"] else 0
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} {r['student_name']} — {r['score']}/{r['total']} ({pct}%)")
    await q.edit_message_text("\n".join(lines), parse_mode="HTML")


async def show_bases(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bl = db.base_list(uid)
    if not bl:
        return await update.message.reply_text("Baza yo'q. .docx fayl yuboring.",
                                               reply_markup=teacher_menu())
    lines = ["📚 <b>Bazalaringiz:</b>"] + [f"• {b['name']} — {b['n']} ta savol" for b in bl]
    lines.append(f"\nJami: <b>{db.question_count(uid)}</b> ta savol.")
    await update.message.reply_html("\n".join(lines), reply_markup=teacher_menu())


async def ask_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Ha, tozalash", callback_data="clr:yes"),
        InlineKeyboardButton("↩️ Bekor", callback_data="clr:no")]])
    await update.message.reply_text("Barcha bazangiz o'chiriladi. Ishonchingiz komilmi?",
                                    reply_markup=kb)


async def on_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "clr:yes":
        db.clear_owner(q.from_user.id)
        await q.edit_message_text("🗑 Barcha bazangiz tozalandi.")
    else:
        await q.edit_message_text("↩️ Bekor qilindi.")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if is_admin(uid):
        if text == BTN_NEW: return await start_newtest(update, ctx)
        if text == BTN_BASES: return await show_bases(update, ctx)
        if text == BTN_RESULTS: return await show_results_list(update, ctx)
        if text == BTN_CLEAR: return await ask_clear(update, ctx)
        if text == BTN_HELP:
            return await update.message.reply_html(HELP_TEACHER, reply_markup=teacher_menu())
        if ctx.user_data.get("await_count"):
            ctx.user_data["await_count"] = False
            if not text.isdigit():
                return await update.message.reply_text("Faqat son yuboring, masalan 30.")
            return await make_test(update, ctx, uid, int(text), edit=False)
    code = text.upper()
    if 4 <= len(code) <= 8 and code.isalnum():
        return await offer_test(update, ctx, code)
    if is_admin(uid):
        await update.message.reply_text("Word baza yuboring yoki tugmalardan tanlang 👇",
                                        reply_markup=teacher_menu())
    else:
        await update.message.reply_text("Test kodini yuboring (masalan ABC123).")


async def offer_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE, code):
    test = db.get_test(code)
    if not test:
        return await update.effective_message.reply_text("❌ Bunday kodli test topilmadi.")
    n = len(test["question_ids"])
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Testni boshlash",
                                                     callback_data=f"begin:{code}")]])
    await update.effective_message.reply_html(
        f"📝 <b>Test:</b> {code}\nSavollar: <b>{n}</b> ta\n\nTayyor bo'lsangiz boshlang 👇",
        reply_markup=kb)


async def on_begin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = q.data.split(":")[1]
    user = q.from_user
    name = user.full_name + (f" (@{user.username})" if user.username else "")
    sid = await asyncio.to_thread(db.start_session, code, user.id, name)
    if not sid:
        return await q.edit_message_text("Testni boshlab bo'lmadi.")
    await q.edit_message_text("📝 Test boshlandi! Har savolda bitta javobni tanlang. Omad! 🍀")
    await send_question(q.message.chat_id, ctx, sid)


async def send_question(chat_id, ctx, sid):
    s = db.get_session(sid)
    if not s:
        return
    i = s["current"]
    if i >= len(s["order"]):
        return await finish(chat_id, ctx, sid)
    item = s["order"][i]
    q = db.get_question(item["qid"])
    for mid in q["stem_media"]:
        data = db.get_media(mid)
        if data:
            await ctx.bot.send_photo(chat_id, io.BytesIO(data))
    letters = [chr(65 + k) for k in range(len(item["opt"]))]
    body = [f"❓ <b>Savol {i+1}/{len(s['order'])}</b>\n{q['stem'] or '(formula — Word faylga qarang)'}", ""]
    for k, orig in enumerate(item["opt"]):
        otext = q["options"][orig]["text"] or "(formula)"
        body.append(f"<b>{letters[k]})</b> {otext}")
    rows, row = [], []
    for k in range(len(item["opt"])):
        row.append(InlineKeyboardButton(letters[k], callback_data=f"ans:{sid}:{k}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    await ctx.bot.send_message(chat_id, "\n".join(body), parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(rows))


async def on_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, sid, pos = q.data.split(":")
    sid, pos = int(sid), int(pos)
    s = db.get_session(sid)
    if not s or s["finished"] or s["student_id"] != q.from_user.id:
        return await q.answer("Bu sessiya faol emas.")
    i = s["current"]
    if i >= len(s["order"]):
        return await q.answer()
    item = s["order"][i]
    correct_pos = item["correct"]
    is_ok = (pos == correct_pos)
    await q.answer("✅ To'g'ri!" if is_ok else "❌ Xato")
    letters = [chr(65 + k) for k in range(len(item["opt"]))]
    mark = "✅" if is_ok else "❌"
    extra = "" if is_ok else f"\nTo'g'ri javob: <b>{letters[correct_pos]}</b>"
    try:
        await q.edit_message_text(
            q.message.text_html + f"\n\n{mark} Sizning javob: <b>{letters[pos]}</b>{extra}",
            parse_mode="HTML")
    except Exception:
        pass
    await asyncio.to_thread(db.record_answer, sid, pos, is_ok)
    await send_question(q.message.chat_id, ctx, sid)


async def finish(chat_id, ctx, sid):
    s = db.get_session(sid)
    await asyncio.to_thread(db.finish_session, sid)
    score, total = s["score"], s["total"]
    pct = round(100 * score / total) if total else 0
    if pct >= 90: grade, emoji = "5", "🏆"
    elif pct >= 70: grade, emoji = "4", "👍"
    elif pct >= 50: grade, emoji = "3", "🙂"
    else: grade, emoji = "2", "📚"
    wrong = [a["i"] + 1 for a in s["answers"] if not a["ok"]]
    txt = (f"{emoji} <b>Test yakunlandi!</b>\n\n"
           f"Natija: <b>{score}/{total}</b> ({pct}%)\nBaho: <b>{grade}</b>")
    if wrong:
        txt += "\n\n❌ Xato savollar: " + ", ".join(map(str, wrong))
    await ctx.bot.send_message(chat_id, txt, parse_mode="HTML")


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN muhit o'zgaruvchisi kiritilmagan!")
    db.init()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newtest", start_newtest))
    app.add_handler(CommandHandler("bases", show_bases))
    app.add_handler(CommandHandler("results", show_results_list))
    app.add_handler(CommandHandler("mytests", show_results_list))
    app.add_handler(CallbackQueryHandler(on_count, pattern=r"^count:"))
    app.add_handler(CallbackQueryHandler(on_results, pattern=r"^res:"))
    app.add_handler(CallbackQueryHandler(on_clear, pattern=r"^clr:"))
    app.add_handler(CallbackQueryHandler(on_begin, pattern=r"^begin:"))
    app.add_handler(CallbackQueryHandler(on_answer, pattern=r"^ans:"))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Bot ishga tushdi.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
