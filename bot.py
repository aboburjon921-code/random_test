"""Telegram bot (tugmali menyu). Test yaratish, web-oyna orqali yechish, jonli panel."""
import os, asyncio, logging, random
from io import BytesIO

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                      WebAppInfo, InputFile)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
import db, parser, docgen, omr

log = logging.getLogger("bot")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x}
BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
if not BASE_URL and os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    BASE_URL = "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"].strip().rstrip("/")

COUNTS = [10, 20, 30, 40, 50]
TIMES = [15, 30, 45, 60]
LIVE_TIMES = [10, 15, 20, 30]   # jonli o'yin: har savolga soniya
TOPICS_PER_PAGE = 6             # mavzu tanlashda bir sahifadagi mavzular soni

BTN_NEW = "➕ Yangi test"; BTN_BASES = "📚 Bazalarim"; BTN_RESULTS = "📊 Natijalar"
BTN_CLEAR = "🗑 Bazani tozalash"; BTN_HELP = "ℹ️ Yordam"; BTN_LIVE = "🎮 Jonli o'yin"
BTN_PRINT = "🖨 Chop etiladigan test"
BTN_SCAN = "📷 Skaner"
PRINT_VARIANTS = [1, 2, 3, 4]


def is_admin(uid): return (not ADMIN_IDS) or (uid in ADMIN_IDS)

def menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_NEW), KeyboardButton(BTN_LIVE)],
         [KeyboardButton(BTN_PRINT), KeyboardButton(BTN_SCAN)],
         [KeyboardButton(BTN_BASES), KeyboardButton(BTN_RESULTS)],
         [KeyboardButton(BTN_CLEAR), KeyboardButton(BTN_HELP)]], resize_keyboard=True)

HELP = ("ℹ️ <b>Qo'llanma</b>\n\n1️⃣ Word bazani (.docx) yuboring — <code>#1.</code> va to'g'ri javobda <code>+</code>.\n"
        "2️⃣ <b>➕ Yangi test</b> → savol soni → rejim → vaqt → test <b>kodi</b>.\n"
        "3️⃣ Kod/havolani o'quvchilarga bering. Ular web-oynada formulalarni ko'rib yechadi.\n"
        "4️⃣ <b>📊 Natijalar</b> — jonli panel: kim yechyapti, ball, o'rtacha.\n\n"
        "🎮 <b>Jonli o'yin</b> — Kahoot uslubi: savol sizning ekraningizda, o'quvchilar "
        "telefonda rang tanlab javob beradi, oxirida top-3 podium.\n\n"
        "🖨 <b>Chop etiladigan test</b> — random test (Word + PDF) yaratib beradi: toza, "
        "javob panjarasisiz, bir yoki bir nechta variant + javob kaliti bilan.\n\n"
        "📷 <b>Skaner</b> — o'quvchilar to'ldirgan javob varaqlarini telefonda suratga olib "
        "avtomatik baholaydi (ID, ball, xato savollar).\n\n"
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
    ctx.user_data.pop("nt", None); ctx.user_data.pop("topics", None)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Aralash (barchasidan)", callback_data="kind:mix")],
        [InlineKeyboardButton("📚 Mavzu bo'yicha", callback_data="kind:topic")]])
    await update.message.reply_text(
        f"Bazada {total} ta savol ({len(db.base_list(uid))} ta mavzu). Test qanday tuzilsin?",
        reply_markup=kb)

async def on_kind(update, ctx):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    kind = q.data.split(":")[1]
    if kind == "mix":
        total = db.question_count(uid)
        btns = [InlineKeyboardButton(f"{n} ta", callback_data=f"cnt:{n}") for n in COUNTS if n <= total]
        rows = [btns[i:i+3] for i in range(0, len(btns), 3)] if btns else []
        rows.append([InlineKeyboardButton(f"✅ Barchasi ({total})", callback_data=f"cnt:{total}"),
                     InlineKeyboardButton("✏️ Boshqa", callback_data="cnt:custom")])
        return await q.edit_message_text(f"Bazada {total} ta savol. Nechta savol?",
                                         reply_markup=InlineKeyboardMarkup(rows))
    # mavzu bo'yicha
    bases = db.base_list(uid)
    ctx.user_data["bases"] = {b["id"]: {"name": b["name"], "n": b["n"]} for b in bases}
    ctx.user_data["topics"] = {b["id"]: 0 for b in bases}
    ctx.user_data["tpage"] = 0
    ctx.user_data["flow"] = "homework"
    await q.edit_message_text("📚 Har mavzudan nechta savol? ➕ / ➖ bilan sozlang:",
                              reply_markup=_topics_kb(ctx))

def _topics_kb(ctx):
    bases = ctx.user_data.get("bases", {}); topics = ctx.user_data.get("topics", {})
    items = list(bases.items())
    per = TOPICS_PER_PAGE
    pages = max(1, (len(items) + per - 1) // per)
    page = max(0, min(ctx.user_data.get("tpage", 0), pages - 1))
    ctx.user_data["tpage"] = page
    rows = []
    for bid, info in items[page * per:(page + 1) * per]:
        nm = info["name"]
        if nm.lower().endswith(".docx"): nm = nm[:-5]
        nm = nm[:22]
        rows.append([
            InlineKeyboardButton(f"{nm} · {topics.get(bid,0)}/{info['n']}", callback_data="noop"),
            InlineKeyboardButton("➖", callback_data=f"tminus:{bid}"),
            InlineKeyboardButton("➕", callback_data=f"tplus:{bid}")])
    if pages > 1:
        rows.append([
            InlineKeyboardButton("◀️", callback_data=f"tpage:{page-1}" if page > 0 else "noop"),
            InlineKeyboardButton(f"{page+1}/{pages} sahifa", callback_data="noop"),
            InlineKeyboardButton("▶️", callback_data=f"tpage:{page+1}" if page < pages - 1 else "noop")])
    total = sum(topics.values())
    rows.append([InlineKeyboardButton(f"✅ Davom — jami {total} ta", callback_data="tdone")])
    return InlineKeyboardMarkup(rows)

async def on_topic_page(update, ctx):
    q = update.callback_query; await q.answer()
    try:
        ctx.user_data["tpage"] = int(q.data.split(":")[1])
    except Exception:
        return
    try:
        await q.edit_message_reply_markup(reply_markup=_topics_kb(ctx))
    except Exception:
        pass

async def on_topic_step(update, ctx):
    q = update.callback_query
    data = q.data
    if data == "noop":
        return await q.answer()
    await q.answer()
    kind, bid = data.split(":"); bid = int(bid)
    info = ctx.user_data.get("bases", {}).get(bid)
    if not info:
        return
    cur = ctx.user_data["topics"].get(bid, 0)
    step = 5 if info["n"] >= 20 else 1
    if kind == "tplus":
        cur = min(info["n"], cur + step)
    else:
        cur = max(0, cur - step)
    ctx.user_data["topics"][bid] = cur
    try:
        await q.edit_message_reply_markup(reply_markup=_topics_kb(ctx))
    except Exception:
        pass

async def on_topic_done(update, ctx):
    q = update.callback_query; await q.answer()
    topics = ctx.user_data.get("topics", {})
    spec = [(bid, cnt) for bid, cnt in topics.items() if cnt > 0]
    if not spec:
        return await q.answer("Kamida bitta mavzuga son bering.", show_alert=True)
    if ctx.user_data.get("flow") == "live":
        ctx.user_data["live_spec"] = spec
        ctx.user_data["live"] = {"count": sum(c for _, c in spec)}
        return await q.edit_message_text("⏱ Har bir savolga necha soniya vaqt berilsin?",
                                         reply_markup=_live_time_kb())
    if ctx.user_data.get("flow") == "print":
        ctx.user_data["print_spec"] = spec
        ctx.user_data["print_count"] = None
        return await q.edit_message_text("🖨 Nechta variant tayyorlansin?",
                                         reply_markup=_print_var_kb())
    ctx.user_data["nt"] = {"topics": spec, "count": sum(c for _, c in spec)}
    await ask_mode(q)

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
    shuffle = nt.get("shuffle", 1); tlimit = nt.get("time", 30)
    if nt.get("topics"):
        spec = nt["topics"]; count = sum(c for _, c in spec)
        title = f"TEST ({count} ta, {tlimit} daq)"
        code, n = await asyncio.to_thread(db.create_test_topics, uid, title, spec, bool(shuffle), tlimit)
    else:
        total = db.question_count(uid); count = max(1, min(nt.get("count", 10), total))
        title = f"TEST ({count} ta, {tlimit} daq)"
        code, n = await asyncio.to_thread(db.create_test, uid, title, count, bool(shuffle), tlimit, None)
    test = db.get_test(code)
    bot_username = (await ctx.bot.get_me()).username
    student_link = f"https://t.me/{bot_username}?start={code}"
    txt = (f"✅ <b>Test tayyor!</b>\n\n🔑 Kod: <code>{code}</code>\n📝 Savollar: {n} ta\n"
           f"⏱ Vaqt: {tlimit} daqiqa\n🔀 Rejim: {'har xil' if shuffle else 'bir xil'}\n"
           f"🛡 Himoya: yoniq — full-screen, tab-kuzatuv, savolga qaytmaslik "
           f"(📊 Natijalar menyusidan o'zgartirish mumkin)\n\n"
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
def _results_markup(uid):
    tests = db.tests_by_owner(uid)
    rows = []
    for t in tests[:12]:
        code = t["code"]; closed = t.get("closed")
        head = f"{'🔒' if closed else '🟢'} {code} — {t['n']} ta"
        if BASE_URL:
            url = f"{BASE_URL}/p/{code}/{t['panel_token']}"
            rows.append([InlineKeyboardButton("📊 " + head, web_app=WebAppInfo(url=url))])
        else:
            rows.append([InlineKeyboardButton(head, callback_data="noop")])
        toggle = ("🔓 Ochish", f"topen:{code}") if closed else ("🔒 Yopish", f"tclose:{code}")
        proc = t.get("proctor", 1)
        rows.append([InlineKeyboardButton(toggle[0], callback_data=toggle[1]),
                     InlineKeyboardButton("🛡 Himoya ✅" if proc else "🛡 Himoya ❌",
                                          callback_data=f"tproc:{code}"),
                     InlineKeyboardButton("🗑", callback_data=f"tdel:{code}")])
    return InlineKeyboardMarkup(rows) if rows else None

async def show_results_list(update, ctx):
    uid = update.effective_user.id
    if not db.tests_by_owner(uid):
        return await update.message.reply_text("Hali test tuzmagansiz.", reply_markup=menu())
    await update.message.reply_text("📊 Testlaringiz (panel · yopish · o'chirish):",
                                    reply_markup=_results_markup(uid))

async def on_test_toggle(update, ctx):
    q = update.callback_query
    action, code = q.data.split(":")
    uid = q.from_user.id
    db.set_closed(code, uid, action == "tclose")
    await q.answer("🔒 Test yopildi" if action == "tclose" else "🔓 Test ochildi")
    try:
        await q.edit_message_reply_markup(reply_markup=_results_markup(uid))
    except Exception:
        pass

async def on_test_proctor(update, ctx):
    q = update.callback_query
    code = q.data.split(":")[1]
    uid = q.from_user.id
    test = db.get_test(code)
    if not test or test.get("owner_id") != uid:
        return await q.answer("Ruxsat yo'q.", show_alert=True)
    new = 0 if test.get("proctor", 1) else 1
    db.set_proctor(code, uid, new)
    await q.answer("🛡 Himoya yoqildi (full-screen + kuzatuv + qaytmaslik)" if new
                   else "Himoya o'chirildi", show_alert=False)
    try:
        await q.edit_message_reply_markup(reply_markup=_results_markup(uid))
    except Exception:
        pass

async def on_test_delete(update, ctx):
    q = update.callback_query; await q.answer()
    code = q.data.split(":")[1]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Ha, o'chir", callback_data=f"tdelyes:{code}"),
        InlineKeyboardButton("↩️ Bekor", callback_data="tdelno")]])
    await q.edit_message_text(f"⚠️ <b>{code}</b> testi va uning barcha natijalari o'chiriladi. Rozimisiz?",
                              parse_mode="HTML", reply_markup=kb)

async def on_test_delete_confirm(update, ctx):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if q.data == "tdelno":
        return await q.edit_message_text("↩️ Bekor qilindi. /results — ro'yxatni qayta oching.")
    code = q.data.split(":")[1]
    db.delete_test(code, uid)
    mk = _results_markup(uid)
    if mk:
        await q.edit_message_text(f"🗑 <b>{code}</b> o'chirildi.\n\n📊 Qolgan testlar:",
                                  parse_mode="HTML", reply_markup=mk)
    else:
        await q.edit_message_text(f"🗑 <b>{code}</b> o'chirildi. Boshqa test yo'q.", parse_mode="HTML")

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
    # o'quvchidan ism kutilyaptimi?
    if ctx.user_data.get("pending_test"):
        name = text.split()[0][:20] if text.split() else ""
        if not name:
            return await update.message.reply_text("Iltimos ismingizni yozing (bir so'z).")
        return await on_name(update, ctx, name)
    if is_admin(uid):
        if text == BTN_NEW: return await start_newtest(update, ctx)
        if text == BTN_BASES: return await show_bases(update, ctx)
        if text == BTN_RESULTS: return await show_results_list(update, ctx)
        if text == BTN_CLEAR: return await ask_clear(update, ctx)
        if text == BTN_LIVE: return await start_live(update, ctx)
        if text == BTN_PRINT: return await start_print(update, ctx)
        if text == BTN_SCAN: return await start_scan(update, ctx)
        if text == BTN_HELP: return await update.message.reply_html(HELP, reply_markup=menu())
        if ctx.user_data.get("await_pcount"):
            ctx.user_data["await_pcount"] = False
            if not text.isdigit(): return await update.message.reply_text("Faqat son yuboring.")
            ctx.user_data["print_count"] = int(text); ctx.user_data["print_spec"] = None
            return await update.message.reply_text("🖨 Nechta variant tayyorlansin?",
                                                   reply_markup=_print_var_kb())
        if ctx.user_data.get("await_lcount"):
            ctx.user_data["await_lcount"] = False
            if not text.isdigit(): return await update.message.reply_text("Faqat son yuboring.")
            ctx.user_data["live"] = {"count": int(text)}
            return await update.message.reply_text("⏱ Har bir savolga necha soniya vaqt berilsin?",
                                                   reply_markup=_live_time_kb())
        if ctx.user_data.get("await_ltime"):
            ctx.user_data["await_ltime"] = False
            if not text.isdigit(): return await update.message.reply_text("Faqat son yuboring.")
            return await _create_live(update, ctx, int(text))
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
    if test.get("closed"):
        return await update.effective_message.reply_text("🔒 Bu test yopilgan. O'qituvchiga murojaat qiling.")
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
    test = db.get_test(code)
    if test and test.get("closed"):
        return await q.edit_message_text("🔒 Bu test yopilgan.")
    if not BASE_URL:
        return await q.edit_message_text("⚠️ Server manzili sozlanmagan (BASE_URL). O'qituvchiga xabar bering.")
    ex = db.existing_session(code, user.id)
    if ex and ex["status"] == "finished":
        sc, tot = ex["score"], ex["total"]; pct = round(100*sc/tot) if tot else 0
        return await q.edit_message_text(f"✅ Allaqachon yechilgan. Natija: {sc}/{tot} ({pct}%)")
    if ex and ex["status"] == "active":
        token = ex["token"]  # davom etadi
        url = f"{BASE_URL}/t/{token}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🖥 Testni ochish", web_app=WebAppInfo(url=url))]])
        return await q.edit_message_text("✅ Testingiz davom etyapti. Ochish uchun bosing 👇",
                                         reply_markup=kb)
    # yangi o'quvchi -> ism so'raymiz
    ctx.user_data["pending_test"] = code
    await q.edit_message_text("✍️ <b>Ismingizni yozing</b> (bir so'z bilan). "
                              "Bu ism poyga oxirida natijada ko'rinadi.", parse_mode="HTML")

async def on_name(update, ctx, name):
    code = ctx.user_data.pop("pending_test", None)
    user = update.effective_user
    if not code:
        return
    test = db.get_test(code)
    if not test or test.get("closed"):
        return await update.message.reply_text("🔒 Bu test endi mavjud emas yoki yopilgan.")
    if not BASE_URL:
        return await update.message.reply_text("⚠️ Server manzili sozlanmagan.")
    token = await asyncio.to_thread(db.create_web_session, code, user.id, name)
    if not token:
        return await update.message.reply_text("Testni boshlab bo'lmadi.")
    url = f"{BASE_URL}/t/{token}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🖥 Testni ochish", web_app=WebAppInfo(url=url))]])
    await update.message.reply_html(f"Rahmat, <b>{name}</b>! ✅ Vaqt boshlandi.\n"
                                    "Testni ochish uchun tugmani bosing 👇", reply_markup=kb)


# ─────────────────────────────────────────────
#  JONLI O'YIN (Kahoot uslubi)
# ─────────────────────────────────────────────
def _live_count_kb(total):
    btns = [InlineKeyboardButton(f"{n} ta", callback_data=f"lcnt:{n}") for n in COUNTS if n <= total]
    rows = [btns[i:i+3] for i in range(0, len(btns), 3)] if btns else []
    rows.append([InlineKeyboardButton(f"✅ Barchasi ({total})", callback_data=f"lcnt:{total}"),
                 InlineKeyboardButton("✏️ Boshqa", callback_data="lcnt:custom")])
    return InlineKeyboardMarkup(rows)

def _live_time_kb():
    row = [InlineKeyboardButton(f"{t} s", callback_data=f"lt:{t}") for t in LIVE_TIMES]
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("✏️ Boshqa", callback_data="lt:custom")]])

async def start_live(update, ctx):
    uid = update.effective_user.id
    total = db.question_count(uid)
    if total == 0:
        return await update.message.reply_text("Avval Word baza (.docx) yuboring.", reply_markup=menu())
    if not BASE_URL:
        return await update.message.reply_text("⚠️ Server manzili sozlanmagan (BASE_URL). Jonli o'yin ishlamaydi.",
                                               reply_markup=menu())
    ctx.user_data.pop("live", None); ctx.user_data.pop("live_spec", None)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Aralash (barchasidan)", callback_data="lkind:mix")],
        [InlineKeyboardButton("📚 Mavzu bo'yicha", callback_data="lkind:topic")]])
    await update.message.reply_text(
        "🎮 <b>Jonli o'yin</b> (Kahoot uslubi)\n\nSavollar qanday tanlansin?",
        parse_mode="HTML", reply_markup=kb)

async def on_live_kind(update, ctx):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    kind = q.data.split(":")[1]
    if kind == "mix":
        total = db.question_count(uid)
        return await q.edit_message_text(f"Bazada {total} ta savol. Nechta savol o'ynaymiz?",
                                         reply_markup=_live_count_kb(total))
    bases = db.base_list(uid)
    ctx.user_data["bases"] = {b["id"]: {"name": b["name"], "n": b["n"]} for b in bases}
    ctx.user_data["topics"] = {b["id"]: 0 for b in bases}
    ctx.user_data["tpage"] = 0
    ctx.user_data["flow"] = "live"
    await q.edit_message_text("📚 Har mavzudan nechta savol? ➕ / ➖ bilan sozlang:",
                              reply_markup=_topics_kb(ctx))

async def on_live_count(update, ctx):
    q = update.callback_query; await q.answer()
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_lcount"] = True
        return await q.edit_message_text("✏️ Nechta savol? Sonini yozing:")
    ctx.user_data["live"] = {"count": int(val)}
    await q.edit_message_text("⏱ Har bir savolga necha soniya vaqt berilsin?",
                              reply_markup=_live_time_kb())

async def on_live_time(update, ctx):
    q = update.callback_query; await q.answer()
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_ltime"] = True
        return await q.edit_message_text("✏️ Necha soniya? Sonini yozing (masalan 20):")
    await _create_live(update, ctx, int(val))

async def _create_live(update, ctx, secs):
    uid = update.effective_user.id
    secs = max(5, min(secs, 120))
    spec = ctx.user_data.get("live_spec")
    if spec:
        pin, tok, n = await asyncio.to_thread(db.create_live_topics, uid, "Jonli o'yin (mavzu)", spec, secs)
    else:
        count = ctx.user_data.get("live", {}).get("count", 10)
        total = db.question_count(uid)
        count = max(1, min(count, total))
        pin, tok, n = await asyncio.to_thread(db.create_live_pick, uid, f"Jonli o'yin ({count} ta)", count, secs, None)
    if not pin:
        return await update.effective_message.reply_text("Savol topilmadi.", reply_markup=menu())
    host_url = f"{BASE_URL}/host/{pin}/{tok}"
    join_url = f"{BASE_URL}/join"
    txt = (f"🎮 <b>Jonli o'yin tayyor!</b>\n\n"
           f"🔑 PIN: <code>{pin}</code>\n"
           f"📝 Savollar: {n} ta · ⏱ har biriga {secs} s\n\n"
           f"👨‍🏫 <b>Host ekran</b> (proyektor/TV — kompyuterda oching):\n{host_url}\n\n"
           f"👨‍🎓 <b>O'quvchilar</b>: {join_url}\n"
           f"      sahifaga kirib PIN <b>{pin}</b> va ismini yozadi.")
    rows = [[InlineKeyboardButton("🖥 Host ekranini ochish", web_app=WebAppInfo(url=host_url))]]
    await update.effective_message.reply_html(txt, reply_markup=InlineKeyboardMarkup(rows))
    ctx.user_data.pop("live", None); ctx.user_data.pop("live_spec", None); ctx.user_data.pop("flow", None)


# ─────────────────────────────────────────────
#  CHOP ETILADIGAN TEST (Word + PDF) — 1-faza
# ─────────────────────────────────────────────
def _print_count_kb(total):
    btns = [InlineKeyboardButton(f"{n} ta", callback_data=f"pcnt:{n}") for n in COUNTS if n <= total]
    rows = [btns[i:i+3] for i in range(0, len(btns), 3)] if btns else []
    rows.append([InlineKeyboardButton(f"✅ Barchasi ({total})", callback_data=f"pcnt:{total}"),
                 InlineKeyboardButton("✏️ Boshqa", callback_data="pcnt:custom")])
    return InlineKeyboardMarkup(rows)

def _print_var_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        ("1 variant" if v == 1 else f"{v} variant"), callback_data=f"pvar:{v}") for v in PRINT_VARIANTS]])

async def start_print(update, ctx):
    uid = update.effective_user.id
    total = db.question_count(uid)
    if total == 0:
        return await update.message.reply_text("Avval Word baza (.docx) yuboring.", reply_markup=menu())
    ctx.user_data.pop("print_spec", None); ctx.user_data.pop("print_count", None)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Aralash (barchasidan)", callback_data="pkind:mix")],
        [InlineKeyboardButton("📚 Mavzu bo'yicha", callback_data="pkind:topic")]])
    await update.message.reply_text(
        "🖨 <b>Chop etiladigan test</b>\n\nSavollar qanday tanlansin?",
        parse_mode="HTML", reply_markup=kb)

async def start_scan(update, ctx):
    if not BASE_URL:
        return await update.message.reply_text("⚠️ Server manzili (BASE_URL) sozlanmagan.", reply_markup=menu())
    url = f"{BASE_URL}/scan"
    txt = ("📷 <b>Skaner</b>\n\nQuyidagi tugma orqali telefon brauzerida oching va "
           "javob varaqlarini birma-bir suratga oling — natija darhol chiqadi.\n\n"
           "Yaxshi yorug'lik, varaqning 4 burchagi ko'rinsin.")
    rows = [[InlineKeyboardButton("📷 Skanerni ochish", url=url)]]
    await update.message.reply_html(txt, reply_markup=InlineKeyboardMarkup(rows))

async def cmd_natija(update, ctx):
    if not BASE_URL:
        return await update.message.reply_text("⚠️ Server manzili (BASE_URL) sozlanmagan.")
    args = (ctx.args if hasattr(ctx, "args") else [])
    if not args:
        return await update.message.reply_html(
            "Foydalanish: <code>/natija KOD</code>\n(KOD — chop etilgan test kodi).")
    code = args[0].strip().upper()
    pt = db.get_print_test(code)
    if not pt:
        return await update.message.reply_text("Bunday kod topilmadi.")
    url = f"{BASE_URL}/results/{code}"
    rows = [[InlineKeyboardButton("📊 Natijalarni ochish", url=url)]]
    await update.message.reply_html(
        f"📊 <b>{pt['title']}</b> · kod <code>{code}</code>\n{url}",
        reply_markup=InlineKeyboardMarkup(rows))

async def on_print_kind(update, ctx):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if q.data.split(":")[1] == "mix":
        total = db.question_count(uid)
        return await q.edit_message_text("Nechta savol bo'lsin?", reply_markup=_print_count_kb(total))
    bases = db.base_list(uid)
    ctx.user_data["bases"] = {b["id"]: {"name": b["name"], "n": b["n"]} for b in bases}
    ctx.user_data["topics"] = {b["id"]: 0 for b in bases}
    ctx.user_data["tpage"] = 0
    ctx.user_data["flow"] = "print"
    await q.edit_message_text("📚 Har mavzudan nechta savol? ➕ / ➖ bilan sozlang:",
                              reply_markup=_topics_kb(ctx))

async def on_print_count(update, ctx):
    q = update.callback_query; await q.answer()
    val = q.data.split(":")[1]
    if val == "custom":
        ctx.user_data["await_pcount"] = True
        return await q.edit_message_text("✏️ Nechta savol? Sonini yozing:")
    ctx.user_data["print_count"] = int(val); ctx.user_data["print_spec"] = None
    await q.edit_message_text("🖨 Nechta variant tayyorlansin?", reply_markup=_print_var_kb())

async def on_print_var(update, ctx):
    q = update.callback_query; await q.answer()
    n = int(q.data.split(":")[1])
    await _gen_and_send_print(update, ctx, n)

def _build_print(uid, title, count, spec, n_variants):
    ids = db.pick_ids(uid, count=count, spec=spec)
    questions = [x for x in (db.get_question(i) for i in ids) if x]
    if not questions:
        return None
    n_q = len(questions)
    docxs, pdfs, keys = [], [], []
    for v in range(n_variants):
        order = list(questions); random.shuffle(order)
        vtitle = title if n_variants == 1 else f"{title} · Variant {v+1}"
        docx, key = docgen.build_test_docx(order, title=vtitle, shuffle_opts=True,
                                           get_media=db.get_media, seed=random.random())
        docxs.append(docx); keys.append(key)
        pdfs.append(docgen.docx_to_pdf(docx))
    code = db.save_print_test(uid, title, keys)
    sheets = [omr.build_answer_sheet_pdf(code, vi + 1, n_q, title=title, total=n_q)
              for vi in range(n_variants)]

    pdf_ok = all(pdfs)
    test_pdf = docgen.merge_pdfs(pdfs, pad_even=True) if pdf_ok else None   # har variant juft bet
    sheet_pdf = docgen.merge_pdfs(sheets, pad_even=False)                    # varaqlar birma-bir
    return {"code": code, "n_q": n_q, "keys": keys, "docxs": docxs,
            "test_pdf": test_pdf, "sheet_pdf": sheet_pdf, "pdf_ok": pdf_ok,
            "n_variants": n_variants}


async def _gen_and_send_print(update, ctx, n_variants):
    uid = update.effective_user.id
    spec = ctx.user_data.get("print_spec")
    count = ctx.user_data.get("print_count")
    title = "Test"
    msg = await update.effective_message.reply_text("⏳ Testlar va javob varaqlari tayyorlanmoqda…")
    try:
        res = await asyncio.to_thread(_build_print, uid, title, count, spec, n_variants)
    except Exception:
        log.exception("print gen")
        return await msg.edit_text("Xatolik yuz berdi. Qayta urinib ko'ring.")
    if not res:
        return await msg.edit_text("Savol topilmadi.")
    code, n_q = res["code"], res["n_q"]
    await msg.edit_text(
        f"✅ Tayyor! Test kodi: <code>{code}</code> · {n_variants} variant · {n_q} savol",
        parse_mode="HTML")

    m = res["n_variants"]
    if res["pdf_ok"] and res["test_pdf"]:
        await update.effective_message.reply_document(
            InputFile(BytesIO(res["test_pdf"]), filename=f"testlar_{code}.pdf"),
            caption=f"📄 Testlar — {m} ta variant (har biri juft bet, printer uchun)")
    else:
        await update.effective_message.reply_text(
            "⚠️ PDF yaratilmadi (serverda LibreOffice yo'q). Word variantlar yuborilyapti:")
        for vi, docx in enumerate(res["docxs"], 1):
            await update.effective_message.reply_document(
                InputFile(BytesIO(docx), filename=f"test_v{vi}.docx"), caption=f"📄 Variant {vi} (Word)")

    await update.effective_message.reply_document(
        InputFile(BytesIO(res["sheet_pdf"]), filename=f"javob_varaqlari_{code}.pdf"),
        caption=f"📝 Javob varaqlari — {m} ta variant")

    lines = ["🔑 <b>Javob kalitlari</b>"]
    for vi, key in enumerate(res["keys"], 1):
        lines.append(f"<b>V{vi}:</b> " + "  ".join(f"{i+1}-{l}" for i, l in enumerate(key)))
    rmk = None
    if BASE_URL:
        rmk = InlineKeyboardMarkup([[InlineKeyboardButton(
            "📊 Natijalar (skanerdan)", url=f"{BASE_URL}/results/{code}")]])
    await update.effective_message.reply_html("\n".join(lines), reply_markup=rmk)

    for k in ("print_spec", "print_count", "flow"):
        ctx.user_data.pop(k, None)


def build_app():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newtest", start_newtest))
    app.add_handler(CommandHandler("bases", show_bases))
    app.add_handler(CommandHandler("results", show_results_list))
    app.add_handler(CallbackQueryHandler(on_kind, pattern=r"^kind:"))
    app.add_handler(CallbackQueryHandler(on_topic_step, pattern=r"^(tplus:|tminus:|noop$)"))
    app.add_handler(CallbackQueryHandler(on_topic_page, pattern=r"^tpage:"))
    app.add_handler(CallbackQueryHandler(on_topic_done, pattern=r"^tdone$"))
    app.add_handler(CallbackQueryHandler(on_count, pattern=r"^cnt:"))
    app.add_handler(CallbackQueryHandler(on_mode, pattern=r"^mode:"))
    app.add_handler(CallbackQueryHandler(on_time, pattern=r"^tm:"))
    app.add_handler(CallbackQueryHandler(on_clear, pattern=r"^clr:"))
    app.add_handler(CallbackQueryHandler(on_test_toggle, pattern=r"^(tclose|topen):"))
    app.add_handler(CallbackQueryHandler(on_test_proctor, pattern=r"^tproc:"))
    app.add_handler(CallbackQueryHandler(on_test_delete, pattern=r"^tdel:"))
    app.add_handler(CallbackQueryHandler(on_test_delete_confirm, pattern=r"^(tdelyes:|tdelno$)"))
    app.add_handler(CallbackQueryHandler(on_begin, pattern=r"^begin:"))
    app.add_handler(CommandHandler("live", start_live))
    app.add_handler(CallbackQueryHandler(on_live_kind, pattern=r"^lkind:"))
    app.add_handler(CallbackQueryHandler(on_live_count, pattern=r"^lcnt:"))
    app.add_handler(CallbackQueryHandler(on_live_time, pattern=r"^lt:"))
    app.add_handler(CommandHandler("print", start_print))
    app.add_handler(CommandHandler("scan", start_scan))
    app.add_handler(CommandHandler("natija", cmd_natija))
    app.add_handler(CallbackQueryHandler(on_print_kind, pattern=r"^pkind:"))
    app.add_handler(CallbackQueryHandler(on_print_count, pattern=r"^pcnt:"))
    app.add_handler(CallbackQueryHandler(on_print_var, pattern=r"^pvar:"))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app
