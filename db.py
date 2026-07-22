"""SQLite ombori: bazalar, savollar, testlar, web-sessiyalar, jonli natijalar."""
import sqlite3, json, os, random, string, time, threading

DB_PATH = os.environ.get("DB_PATH", "data.db")
_local = threading.local()

def conn():
    c = getattr(_local, "c", None)
    if c is None:
        folder = os.path.dirname(os.path.abspath(DB_PATH))
        try: os.makedirs(folder, exist_ok=True)
        except Exception: pass
        c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=8000")
        _local.c = c
    return c

def _cols(table):
    return [r["name"] for r in conn().execute("PRAGMA table_info(%s)" % table).fetchall()]

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS media(id INTEGER PRIMARY KEY AUTOINCREMENT, data BLOB);
    CREATE TABLE IF NOT EXISTS bases(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, name TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, base_id INTEGER, topic TEXT,
        stem TEXT, stem_media TEXT, stem_xml TEXT, options TEXT, correct_index INTEGER);
    CREATE TABLE IF NOT EXISTS tests(code TEXT PRIMARY KEY,
        owner_id INTEGER, title TEXT, question_ids TEXT,
        shuffle_per_student INTEGER, time_limit INTEGER, panel_token TEXT,
        closed INTEGER DEFAULT 0, created_at REAL);
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, token TEXT, student_id INTEGER, student_name TEXT, avatar TEXT,
        order_json TEXT, live TEXT, score INTEGER, total INTEGER,
        status TEXT, started_at REAL, deadline REAL, finished_at REAL);
    CREATE TABLE IF NOT EXISTS games(pin TEXT PRIMARY KEY,
        owner_id INTEGER, title TEXT, question_ids TEXT, host_token TEXT,
        state TEXT DEFAULT 'lobby', current_idx INTEGER DEFAULT -1,
        q_started_at REAL DEFAULT 0, per_q_time INTEGER DEFAULT 20, created_at REAL);
    CREATE TABLE IF NOT EXISTS gplayers(id INTEGER PRIMARY KEY AUTOINCREMENT,
        pin TEXT, name TEXT, token TEXT, avatar TEXT,
        score INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, joined_at REAL);
    CREATE TABLE IF NOT EXISTS ganswers(id INTEGER PRIMARY KEY AUTOINCREMENT,
        pin TEXT, q_idx INTEGER, player_id INTEGER, choice INTEGER,
        correct INTEGER, points INTEGER, elapsed REAL, answered_at REAL);
    CREATE INDEX IF NOT EXISTS ix_gplayers_pin ON gplayers(pin);
    CREATE INDEX IF NOT EXISTS ix_ganswers_pin ON ganswers(pin, q_idx);
    CREATE TABLE IF NOT EXISTS ptests(code TEXT PRIMARY KEY, owner_id INTEGER,
        title TEXT, n_questions INTEGER, n_variants INTEGER, keys TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS pscans(id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, owner_id INTEGER, variant INTEGER, student_id TEXT,
        correct INTEGER, total INTEGER, answers TEXT, wrong TEXT, ambiguous TEXT, name_img TEXT, created_at REAL);
    CREATE INDEX IF NOT EXISTS ix_pscans_code ON pscans(code);
    """)
    for col, ddl in [("stem_xml", "ALTER TABLE questions ADD COLUMN stem_xml TEXT DEFAULT '[]'")]:
        if col not in _cols("questions"):
            c.execute(ddl)
    if "closed" not in _cols("tests"):
        c.execute("ALTER TABLE tests ADD COLUMN closed INTEGER DEFAULT 0")
    if "avatar" not in _cols("sessions"):
        c.execute("ALTER TABLE sessions ADD COLUMN avatar TEXT DEFAULT ''")
    if "name_img" not in _cols("pscans"):
        c.execute("ALTER TABLE pscans ADD COLUMN name_img TEXT")
    c.commit()

# ---------- media ----------
def add_media(data):
    c = conn(); cur = c.execute("INSERT INTO media(data) VALUES(?)", (sqlite3.Binary(data),)); c.commit()
    return cur.lastrowid
def get_media(mid):
    row = conn().execute("SELECT data FROM media WHERE id=?", (mid,)).fetchone()
    return bytes(row["data"]) if row else None

# ---------- bases / questions ----------
def add_base(owner_id, name):
    c = conn(); cur = c.execute("INSERT INTO bases(owner_id,name,created_at) VALUES(?,?,?)",
                                (owner_id, name, time.time())); c.commit()
    return cur.lastrowid

def _swap(xml_list, images):
    ids = [add_media(b) for b in images]
    out = []
    for s in xml_list:
        for k, mid in enumerate(ids):
            s = s.replace("LOCALMEDIA:%d" % k, "DBMEDIA:%d" % mid)
        out.append(s)
    return out, ids

def add_questions(owner_id, base_id, topic, parsed):
    c = conn(); count = 0
    for q in parsed:
        stem_xml, stem_ids = _swap(q.get("stem_xml", []), q.get("stem_images", []))
        opts = []
        for o in q["options"]:
            oxml, oids = _swap(o.get("xml", []), o.get("images", []))
            opts.append({"text": o["text"], "media": oids, "xml": oxml})
        c.execute("INSERT INTO questions(owner_id,base_id,topic,stem,stem_media,stem_xml,options,correct_index)"
                  " VALUES(?,?,?,?,?,?,?,?)",
                  (owner_id, base_id, topic, q["stem"], json.dumps(stem_ids),
                   json.dumps(stem_xml, ensure_ascii=False),
                   json.dumps(opts, ensure_ascii=False), q["correct_index"]))
        count += 1
    c.commit(); return count

def question_count(owner_id):
    return conn().execute("SELECT COUNT(*) n FROM questions WHERE owner_id=?", (owner_id,)).fetchone()["n"]

def base_list(owner_id):
    rows = conn().execute("SELECT b.id,b.name,COUNT(q.id) n FROM bases b "
        "LEFT JOIN questions q ON q.base_id=b.id WHERE b.owner_id=? GROUP BY b.id ORDER BY b.id",
        (owner_id,)).fetchall()
    return [dict(r) for r in rows]

def get_question(qid):
    row = conn().execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    if not row: return None
    d = dict(row)
    d["stem_media"] = json.loads(d["stem_media"]); d["stem_xml"] = json.loads(d["stem_xml"] or "[]")
    d["options"] = json.loads(d["options"]); return d

def clear_owner(owner_id):
    c = conn()
    c.execute("DELETE FROM questions WHERE owner_id=?", (owner_id,))
    c.execute("DELETE FROM bases WHERE owner_id=?", (owner_id,))
    c.commit()

# ---------- tests ----------
def _code(n=6):
    a = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(a) for _ in range(n))
        if not conn().execute("SELECT 1 FROM tests WHERE code=?", (code,)).fetchone():
            return code

def _tok(n=24):
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

def create_test(owner_id, title, count, shuffle_per_student=True, time_limit=30, base_ids=None):
    c = conn()
    if base_ids:
        q = "SELECT id FROM questions WHERE owner_id=? AND base_id IN (%s)" % ",".join("?"*len(base_ids))
        rows = c.execute(q, (owner_id, *base_ids)).fetchall()
    else:
        rows = c.execute("SELECT id FROM questions WHERE owner_id=?", (owner_id,)).fetchall()
    ids = [r["id"] for r in rows]
    if not ids: return None, 0
    random.shuffle(ids); chosen = ids[:count]
    code = _code(); ptok = _tok()
    c.execute("INSERT INTO tests(code,owner_id,title,question_ids,shuffle_per_student,time_limit,panel_token,created_at)"
              " VALUES(?,?,?,?,?,?,?,?)",
              (code, owner_id, title, json.dumps(chosen), int(shuffle_per_student),
               int(time_limit), ptok, time.time()))
    c.commit(); return code, len(chosen)

def _new_test_row(owner_id, title, chosen, shuffle_per_student, time_limit):
    code = _code(); ptok = _tok()
    conn().execute("INSERT INTO tests(code,owner_id,title,question_ids,shuffle_per_student,time_limit,panel_token,created_at)"
                   " VALUES(?,?,?,?,?,?,?,?)",
                   (code, owner_id, title, json.dumps(chosen), int(shuffle_per_student),
                    int(time_limit), ptok, time.time()))
    conn().commit()
    return code

def create_test_topics(owner_id, title, spec, shuffle_per_student=True, time_limit=30):
    """spec: [(base_id, count), ...] — har mavzudan tasodifiy 'count' ta savol."""
    c = conn()
    chosen = []
    for base_id, count in spec:
        if count <= 0:
            continue
        rows = c.execute("SELECT id FROM questions WHERE owner_id=? AND base_id=?",
                         (owner_id, base_id)).fetchall()
        ids = [r["id"] for r in rows]
        random.shuffle(ids)
        chosen.extend(ids[:count])
    if not chosen:
        return None, 0
    random.shuffle(chosen)  # mavzular aralashsin
    code = _new_test_row(owner_id, title, chosen, shuffle_per_student, time_limit)
    return code, len(chosen)

def get_test(code):
    row = conn().execute("SELECT * FROM tests WHERE code=?", (code,)).fetchone()
    if not row: return None
    d = dict(row); d["question_ids"] = json.loads(d["question_ids"]); return d

def tests_by_owner(owner_id):
    rows = conn().execute("SELECT code,title,question_ids,created_at,panel_token,closed FROM tests "
                          "WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["n"] = len(json.loads(d["question_ids"])); out.append(d)
    return out

def set_closed(code, owner_id, closed):
    c = conn()
    cur = c.execute("UPDATE tests SET closed=? WHERE code=? AND owner_id=?",
                    (1 if closed else 0, code, owner_id))
    c.commit()
    return cur.rowcount > 0

def delete_test(code, owner_id):
    c = conn()
    row = c.execute("SELECT 1 FROM tests WHERE code=? AND owner_id=?", (code, owner_id)).fetchone()
    if not row:
        return False
    c.execute("DELETE FROM sessions WHERE code=?", (code,))
    c.execute("DELETE FROM tests WHERE code=? AND owner_id=?", (code, owner_id))
    c.commit()
    return True

# ---------- web sessions ----------
REF_WORDS = ("barcha", "hammasi", "yuqorid", "hech bir", "hech qa", "all of", "none of")
def _is_ref(opts):
    import re
    for o in opts:
        t = (o["text"] or "").lower()
        if any(w in t for w in REF_WORDS): return True
        if re.search(r"\b[a-z]\s*(,|va|and|и)\s*[a-z]\b", t): return True
    return False

def existing_session(code, student_id):
    row = conn().execute("SELECT * FROM sessions WHERE code=? AND student_id=? ORDER BY id DESC LIMIT 1",
                         (code, student_id)).fetchone()
    return dict(row) if row else None

AVATARS = ["🦊","🐼","🐸","🦁","🐯","🐨","🐵","🐷","🐰","🐻","🐺","🦄","🐙","🐳",
           "🦉","🦈","🐝","🦋","🐢","🦖","🐬","🦩","🦚","🐧","🐳","🦔","🐌","🦦",
           "🦥","🦭","🐲","🦕","🐡","🦑","🦞","🐴","🐮","🐔","🦇","🦅"]

def create_web_session(code, student_id, name, avatar=None):
    test = get_test(code)
    if not test: return None
    if not avatar:
        avatar = random.choice(AVATARS)
    qids = test["question_ids"][:]
    random.shuffle(qids)  # savol tartibi har o'quvchida boshqacha
    order = []
    for qid in qids:
        q = get_question(qid)
        if not q: continue
        pos = list(range(len(q["options"])))
        if test["shuffle_per_student"] and not _is_ref(q["options"]):
            random.shuffle(pos)
        correct_pos = pos.index(q["correct_index"]) if q["correct_index"] in pos else -1
        order.append({"qid": qid, "opt": pos, "correct": correct_pos})
    token = _tok()
    now = time.time()
    deadline = now + int(test["time_limit"]) * 60
    c = conn()
    c.execute("INSERT INTO sessions(code,token,student_id,student_name,avatar,order_json,live,score,total,"
              "status,started_at,deadline,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (code, token, student_id, name, avatar, json.dumps(order), json.dumps({}),
               0, len(order), "active", now, deadline, 0))
    c.commit()
    return token

def get_session_by_token(token):
    row = conn().execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
    if not row: return None
    d = dict(row); d["order"] = json.loads(d["order_json"]); d["live"] = json.loads(d["live"] or "{}")
    return d

def save_live(token, qindex, pos):
    s = get_session_by_token(token)
    if not s or s["status"] != "active": return
    live = s["live"]; live[str(qindex)] = pos
    conn().execute("UPDATE sessions SET live=? WHERE token=?", (json.dumps(live), token)); conn().commit()

def _grade(s, answers):
    """answers: {qindex: pos}. return (score, detail list)."""
    score = 0; detail = []
    for i, item in enumerate(s["order"]):
        chosen = answers.get(str(i), answers.get(i))
        ok = (chosen is not None and int(chosen) == item["correct"])
        if ok: score += 1
        detail.append({"i": i, "chosen": chosen, "correct": item["correct"], "ok": ok})
    return score, detail

def submit_session(token, answers=None):
    s = get_session_by_token(token)
    if not s: return None
    if s["status"] == "finished":
        return finalized_result(s)
    ans = answers if answers is not None else s["live"]
    score, detail = _grade(s, ans)
    conn().execute("UPDATE sessions SET live=?,score=?,status='finished',finished_at=? WHERE token=?",
                   (json.dumps(ans), score, time.time(), token)); conn().commit()
    s = get_session_by_token(token)
    return finalized_result(s)

def finalized_result(s):
    score, detail = _grade(s, s["live"])
    return {"score": s["score"] if s["status"] == "finished" else score,
            "total": s["total"], "detail": detail, "status": s["status"],
            "name": s["student_name"], "code": s["code"]}

def expire_due():
    """Muddati tugagan faol sessiyalarni avtomatik yakunlaydi."""
    now = time.time()
    rows = conn().execute("SELECT token FROM sessions WHERE status='active' AND deadline<?", (now,)).fetchall()
    for r in rows:
        submit_session(r["token"])
    return len(rows)

# ---------- panel ----------
def panel_data(code):
    test = get_test(code)
    if not test: return None
    rows = conn().execute("SELECT student_name,avatar,score,total,status,started_at,finished_at,live,order_json "
                          "FROM sessions WHERE code=? ORDER BY status,score DESC", (code,)).fetchall()
    students = []
    q_miss = {}   # qindex -> [wrong, total_answered]
    total_score = 0; finished_n = 0
    for r in rows:
        d = dict(r)
        order = json.loads(d["order_json"]); live = json.loads(d["live"] or "{}")
        answered = len(live)
        # jonli to'g'ri javoblar soni (test davomida ham — poyga uchun)
        correct_live = 0
        for i, item in enumerate(order):
            ch = live.get(str(i))
            if ch is not None and int(ch) == item["correct"]:
                correct_live += 1
        spent = None
        if d["status"] == "finished" and d["finished_at"]:
            spent = int(d["finished_at"] - d["started_at"])
        students.append({"name": d["student_name"], "avatar": d["avatar"] or "🐵",
                         "score": d["score"], "total": d["total"],
                         "status": d["status"], "answered": answered, "spent": spent,
                         "correct": correct_live})
        if d["status"] == "finished":
            finished_n += 1; total_score += d["score"]
            for i, item in enumerate(order):
                chosen = live.get(str(i))
                st = q_miss.setdefault(i, [0, 0])
                st[1] += 1
                if chosen is None or int(chosen) != item["correct"]:
                    st[0] += 1
    avg = round(total_score / finished_n, 1) if finished_n else 0
    hardest = None
    if q_miss:
        hi = max(q_miss.items(), key=lambda kv: (kv[1][0] / kv[1][1]) if kv[1][1] else 0)
        if hi[1][1]:
            hardest = {"q": hi[0] + 1, "miss_pct": round(100 * hi[1][0] / hi[1][1])}
    return {"title": test["title"], "code": code, "time_limit": test["time_limit"],
            "students": students, "avg": avg, "finished": finished_n,
            "total_students": len(students), "hardest": hardest,
            "closed": bool(test.get("closed")),
            "q_total": len(test["question_ids"])}


# ─────────────────────────────────────────────
#  JONLI O'YIN (Kahoot uslubi)
# ─────────────────────────────────────────────
POINT_BASE = 1000          # to'g'ri javob uchun maksimal ball
STREAK_STEP = 100          # ketma-ket to'g'ri javob bonusi (har biriga)
STREAK_MAX = 5             # bonus soni cheklovi (maks +500)
LATE_GRACE = 1.5           # taymer tugagach qabul qilinadigan qo'shimcha soniya

def _pin(n=6):
    while True:
        p = "".join(random.choice(string.digits) for _ in range(n))
        if not conn().execute("SELECT 1 FROM games WHERE pin=? AND state!='ended'", (p,)).fetchone():
            return p

def create_live_game(owner_id, title, question_ids, per_q_time=20):
    if not question_ids:
        return None, None
    pin = _pin(); tok = _tok()
    conn().execute(
        "INSERT INTO games(pin,owner_id,title,question_ids,host_token,state,current_idx,"
        "q_started_at,per_q_time,created_at) VALUES(?,?,?,?,?,'lobby',-1,0,?,?)",
        (pin, owner_id, title, json.dumps(question_ids), tok, int(per_q_time), time.time()))
    conn().commit()
    return pin, tok

def create_live_pick(owner_id, title, count, per_q_time=20, base_ids=None):
    """Egasining savollaridan tasodifiy 'count' ta olib jonli o'yin yaratadi."""
    c = conn()
    if base_ids:
        q = "SELECT id FROM questions WHERE owner_id=? AND base_id IN (%s)" % ",".join("?" * len(base_ids))
        rows = c.execute(q, (owner_id, *base_ids)).fetchall()
    else:
        rows = c.execute("SELECT id FROM questions WHERE owner_id=?", (owner_id,)).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return None, None, 0
    random.shuffle(ids); chosen = ids[:count]
    pin, tok = create_live_game(owner_id, title, chosen, per_q_time)
    return pin, tok, len(chosen)

def create_live_topics(owner_id, title, spec, per_q_time=20):
    """spec: [(base_id, count), ...] — har mavzudan tasodifiy 'count' ta savol (jonli o'yin)."""
    c = conn(); chosen = []
    for base_id, count in spec:
        if count <= 0:
            continue
        rows = c.execute("SELECT id FROM questions WHERE owner_id=? AND base_id=?",
                         (owner_id, base_id)).fetchall()
        ids = [r["id"] for r in rows]
        random.shuffle(ids); chosen.extend(ids[:count])
    if not chosen:
        return None, None, 0
    random.shuffle(chosen)   # mavzular aralashsin
    pin, tok = create_live_game(owner_id, title, chosen, per_q_time)
    return pin, tok, len(chosen)

def get_game(pin):
    row = conn().execute("SELECT * FROM games WHERE pin=?", (pin,)).fetchone()
    if not row:
        return None
    d = dict(row); d["question_ids"] = json.loads(d["question_ids"]); return d

def get_game_by_host(host_token):
    row = conn().execute("SELECT * FROM games WHERE host_token=?", (host_token,)).fetchone()
    if not row:
        return None
    d = dict(row); d["question_ids"] = json.loads(d["question_ids"]); return d

def _game_question(g, idx):
    if idx is None or idx < 0 or idx >= len(g["question_ids"]):
        return None
    return get_question(g["question_ids"][idx])

def game_players(pin):
    rows = conn().execute("SELECT name,avatar FROM gplayers WHERE pin=? ORDER BY id", (pin,)).fetchall()
    return [dict(r) for r in rows]

def _players_scored(pin):
    rows = conn().execute(
        "SELECT id,name,avatar,score,streak FROM gplayers WHERE pin=? ORDER BY score DESC, joined_at ASC",
        (pin,)).fetchall()
    return [dict(r) for r in rows]

def join_game(pin, name):
    g = get_game(pin)
    if not g:
        return {"error": "notfound"}
    if g["state"] != "lobby":
        return {"error": "started"}
    name = (name or "").strip()[:20] or "O'quvchi"
    existing = [r["name"] for r in conn().execute("SELECT name FROM gplayers WHERE pin=?", (pin,)).fetchall()]
    base, k = name, 2
    while name in existing:
        name = f"{base}{k}"; k += 1
    tok = _tok(); av = random.choice(AVATARS)
    cur = conn().execute(
        "INSERT INTO gplayers(pin,name,token,avatar,score,streak,joined_at) VALUES(?,?,?,?,0,0,?)",
        (pin, name, tok, av, time.time()))
    conn().commit()
    return {"pin": pin, "player_id": cur.lastrowid, "token": tok, "name": name, "avatar": av}

def _auth_player(pin, player_id, token):
    row = conn().execute("SELECT * FROM gplayers WHERE id=? AND pin=? AND token=?",
                         (player_id, pin, token)).fetchone()
    return dict(row) if row else None

def submit_answer(pin, player_id, token, choice):
    g = get_game(pin)
    if not g:
        return {"ok": False, "reason": "gone"}
    if not _auth_player(pin, player_id, token):
        return {"ok": False, "reason": "auth"}
    if g["state"] != "question":
        return {"ok": False, "reason": "closed"}
    idx = g["current_idx"]
    ex = conn().execute("SELECT 1 FROM ganswers WHERE pin=? AND q_idx=? AND player_id=?",
                        (pin, idx, player_id)).fetchone()
    if ex:
        return {"ok": True, "locked": True}
    now = time.time(); elapsed = now - g["q_started_at"]; limit = max(1, g["per_q_time"])
    if elapsed > limit + LATE_GRACE:
        return {"ok": False, "reason": "late"}
    q = _game_question(g, idx)
    if not q:
        return {"ok": False, "reason": "noq"}
    try:
        choice = int(choice)
    except Exception:
        return {"ok": False, "reason": "bad"}
    is_ok = (choice == int(q["correct_index"]))
    p = conn().execute("SELECT streak FROM gplayers WHERE id=?", (player_id,)).fetchone()
    streak = p["streak"] if p else 0
    pts = 0
    if is_ok:
        frac = min(max(elapsed, 0) / limit, 1.0)
        pts = round(POINT_BASE * (1 - frac / 2))          # 1000 → 500
        streak += 1
        if streak >= 2:
            pts += min(streak - 1, STREAK_MAX) * STREAK_STEP
    else:
        streak = 0
    conn().execute(
        "INSERT INTO ganswers(pin,q_idx,player_id,choice,correct,points,elapsed,answered_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (pin, idx, player_id, choice, 1 if is_ok else 0, pts, elapsed, now))
    conn().execute("UPDATE gplayers SET score=score+?, streak=? WHERE id=?", (pts, streak, player_id))
    conn().commit()
    return {"ok": True, "locked": True}

def host_advance(host_token, action):
    g = get_game_by_host(host_token)
    if not g:
        return None
    pin, st, idx, n = g["pin"], g["state"], g["current_idx"], len(g["question_ids"])
    c = conn()
    if action == "start" and st == "lobby":
        c.execute("UPDATE games SET state='question',current_idx=0,q_started_at=? WHERE pin=?",
                  (time.time(), pin))
    elif action == "reveal" and st == "question":
        c.execute("UPDATE games SET state='reveal' WHERE pin=?", (pin,))
    elif action == "scoreboard" and st in ("question", "reveal"):
        c.execute("UPDATE games SET state='scoreboard' WHERE pin=?", (pin,))
    elif action == "next" and st in ("scoreboard", "reveal"):
        if idx + 1 < n:
            c.execute("UPDATE games SET state='question',current_idx=?,q_started_at=? WHERE pin=?",
                      (idx + 1, time.time(), pin))
        else:
            c.execute("UPDATE games SET state='ended' WHERE pin=?", (pin,))
    elif action == "end":
        c.execute("UPDATE games SET state='ended' WHERE pin=?", (pin,))
    c.commit()
    return host_state(pin)

def _answer_counts(pin, idx):
    counts = [0, 0, 0, 0]
    for r in conn().execute("SELECT choice, COUNT(*) c FROM ganswers WHERE pin=? AND q_idx=? GROUP BY choice",
                            (pin, idx)).fetchall():
        if r["choice"] is not None and 0 <= r["choice"] < 4:
            counts[r["choice"]] = r["c"]
    return counts

def host_state(pin):
    g = get_game(pin)
    if not g:
        return None
    st, idx, n = g["state"], g["current_idx"], len(g["question_ids"])
    out = {"state": st, "idx": idx, "total": n, "pin": pin, "title": g["title"],
           "per_q_time": g["per_q_time"], "players_n": len(game_players(pin))}
    if st == "lobby":
        out["players"] = game_players(pin)
    if st in ("question", "reveal"):
        q = _game_question(g, idx)
        out["q_number"] = idx + 1
        out["qid"] = q["id"] if q else None
        out["correct"] = int(q["correct_index"]) if q else 0
        out["n_opts"] = min(len(q["options"]), 4) if q else 4
        out["counts"] = _answer_counts(pin, idx)
        out["answered"] = sum(out["counts"])
        out["remaining"] = max(0, int(g["q_started_at"] + g["per_q_time"] - time.time())) if st == "question" else 0
    if st in ("scoreboard", "ended"):
        out["scoreboard"] = _players_scored(pin)[:5]
        out["podium"] = _players_scored(pin)[:3]
    return out

def player_state(pin, player_id, token):
    g = get_game(pin)
    if not g:
        return {"state": "gone"}
    p = _auth_player(pin, player_id, token)
    if not p:
        return {"state": "gone"}
    st, idx = g["state"], g["current_idx"]
    out = {"state": st, "idx": idx, "name": p["name"], "avatar": p["avatar"], "score": p["score"]}
    if st == "question":
        q = _game_question(g, idx)
        out["n_opts"] = min(len(q["options"]), 4) if q else 4
        out["remaining"] = max(0, int(g["q_started_at"] + g["per_q_time"] - time.time()))
        a = conn().execute("SELECT choice FROM ganswers WHERE pin=? AND q_idx=? AND player_id=?",
                           (pin, idx, player_id)).fetchone()
        out["answered"] = a is not None
        out["my_choice"] = a["choice"] if a else None
    if st in ("reveal", "scoreboard", "ended"):
        a = None
        if idx is not None and idx >= 0:
            a = conn().execute("SELECT choice,correct,points FROM ganswers WHERE pin=? AND q_idx=? AND player_id=?",
                               (pin, idx, player_id)).fetchone()
        out["answered"] = a is not None
        out["correct"] = bool(a["correct"]) if a else False
        out["points"] = a["points"] if a else 0
        ranked = _players_scored(pin)
        out["rank"] = next((i + 1 for i, r in enumerate(ranked) if r["id"] == player_id), None)
        out["total_players"] = len(ranked)
    if st == "ended":
        out["podium"] = _players_scored(pin)[:3]
    return out


# ─────────────────────────────────────────────
#  CHOP ETILADIGAN TEST (Word/PDF) — 1-faza
# ─────────────────────────────────────────────
def pick_ids(owner_id, count=None, spec=None):
    """Savol id larini tanlaydi. spec=[(base_id,count),...] yoki count (aralash)."""
    c = conn(); ids = []
    if spec:
        for bid, cnt in spec:
            rows = c.execute("SELECT id FROM questions WHERE owner_id=? AND base_id=?",
                             (owner_id, bid)).fetchall()
            b = [r["id"] for r in rows]; random.shuffle(b); ids.extend(b[:cnt])
        random.shuffle(ids)
    else:
        rows = c.execute("SELECT id FROM questions WHERE owner_id=?", (owner_id,)).fetchall()
        ids = [r["id"] for r in rows]; random.shuffle(ids)
        if count:
            ids = ids[:count]
    return ids

def _pcode(n=6):
    alpha = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alpha) for _ in range(n))
        if not conn().execute("SELECT 1 FROM ptests WHERE code=?", (code,)).fetchone():
            return code

def save_print_test(owner_id, title, keys):
    """keys: [[letter,...] variant bo'yicha]. Skanerlash uchun kalitlarni saqlaydi."""
    code = _pcode()
    conn().execute(
        "INSERT INTO ptests(code,owner_id,title,n_questions,n_variants,keys,created_at)"
        " VALUES(?,?,?,?,?,?,?)",
        (code, owner_id, title, len(keys[0]) if keys else 0, len(keys),
         json.dumps(keys), time.time()))
    conn().commit()
    return code

def get_print_test(code):
    row = conn().execute("SELECT * FROM ptests WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    d = dict(row); d["keys"] = json.loads(d["keys"]); return d


def save_scan(code, variant, student_id, correct, total, answers, wrong, ambiguous, name_img=None):
    pt = get_print_test(code)
    owner = pt["owner_id"] if pt else None
    cur = conn().execute(
        "INSERT INTO pscans(code,owner_id,variant,student_id,correct,total,answers,wrong,ambiguous,name_img,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (code, owner, variant, student_id, correct, total,
         json.dumps(answers), json.dumps(wrong), json.dumps(ambiguous), name_img, time.time()))
    conn().commit()
    return cur.lastrowid

def scan_results(code):
    rows = conn().execute("SELECT * FROM pscans WHERE code=? ORDER BY created_at DESC", (code,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["answers"] = json.loads(d["answers"] or "[]")
        d["wrong"] = json.loads(d["wrong"] or "[]")
        d["ambiguous"] = json.loads(d["ambiguous"] or "[]")
        out.append(d)
    return out

def delete_scan(scan_id):
    conn().execute("DELETE FROM pscans WHERE id=?", (scan_id,))
    conn().commit()

def update_scan_answers(scan_id, code, variant, answers):
    """Qo'lda tuzatishdan keyin qayta baholaydi."""
    pt = get_print_test(code)
    if not pt:
        return None
    key = pt["keys"][variant - 1] if 1 <= variant <= len(pt["keys"]) else []
    correct = sum(1 for i, k in enumerate(key) if i < len(answers) and answers[i] == k)
    wrong = [i + 1 for i, k in enumerate(key) if not (i < len(answers) and answers[i] == k)]
    conn().execute("UPDATE pscans SET answers=?, correct=?, wrong=?, ambiguous=? WHERE id=?",
                   (json.dumps(answers), correct, json.dumps(wrong), json.dumps([]), scan_id))
    conn().commit()
    return {"correct": correct, "total": len(key), "wrong": wrong}


def scan_report(code):
    """Skaner natijalari hisoboti. Har ID bo'yicha (eng oxirgi skani): ball + xato tafsilotlari."""
    pt = get_print_test(code)
    if not pt:
        return None
    keys = pt["keys"]; n = pt["n_questions"]
    scans = scan_results(code)          # eng yangisi birinchi
    seen, rows = set(), []
    miss = [0] * (n + 1)                # savol bo'yicha xato soni
    for s in scans:
        sid = s["student_id"]
        if sid in seen:
            continue
        seen.add(sid)
        variant = s["variant"] or 1
        key = keys[variant - 1] if 1 <= variant <= len(keys) else []
        ans = s["answers"]
        detail = []
        for q in s["wrong"]:
            marked = ans[q - 1] if 0 <= q - 1 < len(ans) else None
            corr = key[q - 1] if 0 <= q - 1 < len(key) else "?"
            detail.append({"q": q, "marked": marked or "—", "correct": corr})
            if 1 <= q <= n:
                miss[q] += 1
        rows.append({"student_id": sid, "variant": variant, "correct": s["correct"],
                     "total": s["total"], "wrong": detail,
                     "ambiguous": s["ambiguous"], "created_at": s["created_at"],
                     "name_img": s.get("name_img")})
    rows.sort(key=lambda r: r["student_id"])
    cnt = len(rows)
    avg = round(sum(r["correct"] for r in rows) / cnt, 1) if cnt else 0
    hardest = sorted(range(1, n + 1), key=lambda q: miss[q], reverse=True)
    hardest = [{"q": q, "miss": miss[q]} for q in hardest if miss[q] > 0][:5]
    return {"code": code, "title": pt["title"], "n": n, "count": cnt,
            "avg": avg, "rows": rows, "hardest": hardest}
