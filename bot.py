"""
Telegram bot — Random Test Generator.

O'QITUVCHI:
  • Word bazani (.docx) yuboradi  -> savollar saqlanadi
  • /newtest                      -> nechta savol tanlaydi, test KODI oladi (+ Word fayl)
  • /mytests, /results KOD        -> natijalarni ko'radi
  • /bases, /clear                -> bazalarni boshqaradi
O'QUVCHI:
  • /start KOD   (yoki havola)    -> testni A/B/C/D tugmalari bilan yechadi
  • oxirida avtomatik ball + xatolar ro'yxati
"""
import os
import io
import asyncio
import logging

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      InputFile)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)

import db
import parser
import docx_gen

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x}
COUNTS = [10, 20, 30, 40, 50]


def is_admin(uid):
    return (not ADMIN_IDS) or (uid in ADMIN_IDS)


# ============================ START ============================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if args:  # o'quvchi test kodi bilan kirdi
        code = args[0].upper()
        return await join_test(update, ctx, code)
    uid = update.effective_user.id
    if is_admin(uid):
        txt = (
            "👋 <b>Random Test Generator</b>\n\n"
            "<b>O'qituvchi uchun:</b>\n"
            "1️⃣ Word bazani (.docx) shu yerga yuboring — savol nomeri oldida <code>#</code>, "
            "to'g'ri javob oldida <code>+</code> bo'lsin.\n"
            "2️⃣ /newtest — nechta savol kerakligini tanlang, test <b>kodi</b> oling.\n"
            "3️⃣ Kodni o'quvchilarga bering. Ular yechadi, bot avtomatik baholaydi.\n\n"
            "Buyruqlar: /newtest /mytests /results /bases /clear"
        )
    else:
        txt = ("👋 Salom! Test yechish uchun o'qituvchi bergan <b>kodni</b> yuboring "
               "yoki <code>/start KOD</code> ko'rinishida kiriting.")
    await update.message.reply_html(txt)


# ====================== UPLOAD (teacher) ======================
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
                "❌ Savol topilmadi. Format: savol oldida <code>#1.</code>, "
                "to'g'ri javob oldida <code>+</code>.", parse_mode="HTML")
        base_id = db.add_base(uid, name)
        added = await asyncio.to_thread(db.add_questions, uid, base_id, name, questions)
        total = db.question_count(uid)
        await msg.edit_text(f"✅ <b>{name}</b>: {added} ta savol qo'shildi.\n"
                            f"Jami bazangizda: <b>{total}</b> ta savol.\n\n"
                            f"Test tuzish uchun /newtest", parse_mode="HTML")
    except Exception as e:
        log.exception("upload")
        await msg.edit_text(f"❌ Xatolik: {e}")


# ====================== NEW TEST (teacher) ======================
async def cmd_newtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return await update.message.reply_text("Faqat o'qituvchi test tuza oladi.")
    total = db.question_count(uid)
    if total == 0:
        return await update.message.reply_text("Avval Word baza yuboring (.docx).")
    kb = [[InlineKeyboardButton(f"{n} ta", callback_data=f"count:{n}")
           for n in COUNTS if n <= total or n == COUNTS[0]]]
    kb.append([InlineKeyboardButton(f"Barchasi ({total})", callback_data=f"count:{total}"),
               InlineKeyboardButton("Boshqa son…", callback_data="count:custom")])
    await update.message.reply_text(
        f"Bazangizda {total} ta savol. Nechta savoldan test tuzay?",
        reply_markup=InlineKeyboardMarkup(kb))


async def on_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_count"] = True
        return await q.edit_message_text("Nechta savol kerak? Sonini yozib yuboring:")
    await make_test(update, ctx, uid, int(val), edit=True)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if ctx.user_data.get("await_count") and is_admin(uid):
        ctx.user_data["await_count"] = False
        if not text.isdigit():
            return await update.message.reply_text("Faqat son yuboring, masalan 30.")
        return await make_test(update, ctx, uid, int(text), edit=False)
    # aks holda: test kodi bo'lishi mumkin
    code = text.upper()
    if 4 <= len(code) <= 8 and code.isalnum():
        return await join_test(update, ctx, code)
    await update.message.reply_text(
        "Tushunmadim. O'qituvchi bo'lsangiz baza yuboring yoki /newtest. "
        "O'quvchi bo'lsangiz test kodini yuboring.")


async def make_test(update, ctx, uid, count, edit):
    total = db.question_count(uid)
    count = max(1, min(count, total))
    title = f"TEST ({count} ta savol)"
    code, n = await asyncio.to_thread(db.create_test, uid, title, count, True, True, None)
    send = (update.callback_query.edit_message_text if edit
            else update.message.reply_text)
    bot_username = (await ctx.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"
    await send(
        f"✅ Test tayyor!\n\n🔑 Kod: <code>{code}</code>\n📝 Savollar: {n} ta\n\n"
        f"O'quvchilar shu havola orqali kiradi:\n{link}\n\n"
        f"Yoki botga <code>{code}</code> kodini yuborsin.\n"
        f"Natijalar: <code>/results {code}</code>", parse_mode="HTML")
    # Word fayllarni ham yuboramiz
    chat_id = update.effective_chat.id
    try:
        qs = [db.get_question(qid) for qid in db.get_test(code)["question_ids"]]
        qs = [{"stem": q["stem"],
               "stem_media": [db.get_media(m) for m in q["stem_media"]],
               "options": [{"text": o["text"], "media": [db.get_media(m) for m in o["media"]]}
                           for o in q["options"]],
               "correct_index": q["correct_index"]} for q in qs if q]
        test_b, key_b = await asyncio.to_thread(docx_gen.build, qs, title)
        await ctx.bot.send_document(chat_id, InputFile(io.BytesIO(test_b), f"test_{code}.docx"),
                                    caption="📘 Test (o'quvchiga)")
        await ctx.bot.send_document(chat_id, InputFile(io.BytesIO(key_b), f"javoblar_{code}.docx"),
                                    caption="🔑 Javoblar (o'qituvchiga)")
    except Exception:
        log.exception("docx")


# ====================== RESULTS / BASES ======================
async def cmd_results(update, ctx):
    uid = update.effective_user.id
    if not ctx.args:
        tests = db.tests_by_owner(uid)
        if not tests:
            return await update.message.reply_text("Hali test tuzmagansiz.")
        lines = ["Testlaringiz:"] + [f"• <code>{t['code']}</code> — {t['n']} ta savol"
                                     for t in tests[:20]]
        lines.append("\nNatija: <code>/results KOD</code>")
        return await update.message.reply_html("\n".join(lines))
    code = ctx.args[0].upper()
    t = db.get_test(code)
    if not t or t["owner_id"] != uid:
        return await update.message.reply_text("Bunday test topilmadi.")
    res = db.results_for_test(code)
    if not res:
        return await update.message.reply_text("Hali hech kim yechmagan.")
    lines = [f"📊 <b>{code}</b> natijalari:"]
    for i, r in enumerate(res, 1):
        pct = round(100 * r["score"] / r["total"]) if r["total"] else 0
        lines.append(f"{i}. {r['student_name']} — {r['score']}/{r['total']} ({pct}%)")
    await update.message.reply_html("\n".join(lines))


async def cmd_bases(update, ctx):
    uid = update.effective_user.id
    bl = db.base_list(uid)
    if not bl:
        return await update.message.reply_text("Baza yo'q. .docx fayl yuboring.")
    lines = ["📚 Bazalaringiz:"] + [f"• {b['name']} — {b['n']} ta savol" for b in bl]
    lines.append(f"\nJami: {db.question_count(uid)} ta. Tozalash: /clear")
    await update.message.reply_text("\n".join(lines))


async def cmd_clear(update, ctx):
    uid = update.effective_user.id
    db.clear_owner(uid)
    await update.message.reply_text("🗑 Barcha bazangiz tozalandi.")


# ====================== STUDENT: take test ======================
async def join_test(update, ctx, code):
    user = update.effective_user
    test = db.get_test(code)
    if not test:
        return await update.effective_message.reply_text(
            "❌ Bunday kodli test topilmadi. Kodni tekshiring.")
    name = user.full_name + (f" (@{user.username})" if user.username else "")
    sid = await asyncio.to_thread(db.start_session, code, user.id, name)
    if not sid:
        return await update.effective_message.reply_text("Testni boshlab bo'lmadi.")
    ctx.user_data["sid"] = sid
    await update.effective_message.reply_text(
        f"📝 Test boshlandi! Jami {test and len(test['question_ids'])} ta savol.\n"
        "Har savolda bitta javobni tanlang.")
    await send_question(update.effective_chat.id, ctx, sid)


async def send_question(chat_id, ctx, sid):
    s = db.get_session(sid)
    if not s:
        return
    i = s["current"]
    if i >= len(s["order"]):
        return await finish(chat_id, ctx, sid)
    item = s["order"][i]
    q = db.get_question(item["qid"])
    # rasmlarni yuborish
    for mid in q["stem_media"]:
        data = db.get_media(mid)
        if data:
            await ctx.bot.send_photo(chat_id, io.BytesIO(data))
    # variant matnlari (tartiblangan) + tugmalar (harflar)
    letters = [chr(65 + k) for k in range(len(item["opt"]))]
    body = [f"❓ <b>Savol {i+1}/{len(s['order'])}</b>\n{q['stem']}", ""]
    for k, orig in enumerate(item["opt"]):
        body.append(f"<b>{letters[k]})</b> {q['options'][orig]['text']}")
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
        return await q.answer("Bu sessiya faol emas.", show_alert=False)
    i = s["current"]
    if i >= len(s["order"]):
        return await q.answer()
    item = s["order"][i]
    correct_pos = item["correct"]
    is_ok = (pos == correct_pos)
    await q.answer("✅ To'g'ri!" if is_ok else "❌ Xato", show_alert=False)
    # xabarni yakuniy ko'rinishga keltiramiz (tugmalarsiz)
    letters = [chr(65 + k) for k in range(len(item["opt"]))]
    mark = "✅" if is_ok else "❌"
    extra = "" if is_ok else f"\nTo'g'ri javob: <b>{letters[correct_pos]}</b>"
    try:
        await q.edit_message_text(q.message.text_html +
                                  f"\n\n{mark} Sizning javob: <b>{letters[pos]}</b>{extra}",
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
    # xato savollar
    wrong = [a["i"] + 1 for a in s["answers"] if not a["ok"]]
    txt = (f"{emoji} <b>Test yakunlandi!</b>\n\n"
           f"Natija: <b>{score}/{total}</b> ({pct}%)\nBaho: <b>{grade}</b>")
    if wrong:
        txt += "\n\nXato savollar: " + ", ".join(map(str, wrong))
    await ctx.bot.send_message(chat_id, txt, parse_mode="HTML")


# ============================ MAIN ============================
def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN muhit o'zgaruvchisi kiritilmagan!")
    db.init()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newtest", cmd_newtest))
    app.add_handler(CommandHandler("results", cmd_results))
    app.add_handler(CommandHandler("mytests", cmd_results))
    app.add_handler(CommandHandler("bases", cmd_bases))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CallbackQueryHandler(on_count, pattern=r"^count:"))
    app.add_handler(CallbackQueryHandler(on_answer, pattern=r"^ans:"))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Bot ishga tushdi.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
