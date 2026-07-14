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
        shuffle_per_student INTEGER, time_limit INTEGER, panel_token TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, token TEXT, student_id INTEGER, student_name TEXT,
        order_json TEXT, live TEXT, score INTEGER, total INTEGER,
        status TEXT, started_at REAL, deadline REAL, finished_at REAL);
    """)
    for col, ddl in [("stem_xml", "ALTER TABLE questions ADD COLUMN stem_xml TEXT DEFAULT '[]'")]:
        if col not in _cols("questions"):
            c.execute(ddl)
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
    rows = conn().execute("SELECT code,title,question_ids,created_at,panel_token FROM tests "
                          "WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["n"] = len(json.loads(d["question_ids"])); out.append(d)
    return out

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

def create_web_session(code, student_id, name):
    test = get_test(code)
    if not test: return None
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
    c.execute("INSERT INTO sessions(code,token,student_id,student_name,order_json,live,score,total,"
              "status,started_at,deadline,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (code, token, student_id, name, json.dumps(order), json.dumps({}),
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
    rows = conn().execute("SELECT student_name,score,total,status,started_at,finished_at,live,order_json "
                          "FROM sessions WHERE code=? ORDER BY status,score DESC", (code,)).fetchall()
    students = []
    q_miss = {}   # qindex -> [wrong, total_answered]
    total_score = 0; finished_n = 0
    for r in rows:
        d = dict(r)
        order = json.loads(d["order_json"]); live = json.loads(d["live"] or "{}")
        answered = len(live)
        spent = None
        if d["status"] == "finished" and d["finished_at"]:
            spent = int(d["finished_at"] - d["started_at"])
        students.append({"name": d["student_name"], "score": d["score"], "total": d["total"],
                         "status": d["status"], "answered": answered, "spent": spent})
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
            "total_students": len(students), "hardest": hardest}
