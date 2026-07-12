import sqlite3
import json
import os
import random
import string
import time

DB_PATH = os.environ.get("DB_PATH", "data.db")
_conn = None


def conn():
    global _conn
    if _conn is None:
        # DB papkasi mavjud bo'lmasa — yaratamiz (masalan /data)
        folder = os.path.dirname(os.path.abspath(DB_PATH))
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS media(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data BLOB
    );
    CREATE TABLE IF NOT EXISTS bases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, name TEXT, created_at REAL
    );
    CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, base_id INTEGER, topic TEXT,
        stem TEXT, stem_media TEXT, stem_xml TEXT, options TEXT, correct_index INTEGER
    );
    CREATE TABLE IF NOT EXISTS tests(
        code TEXT PRIMARY KEY,
        owner_id INTEGER, title TEXT,
        question_ids TEXT, shuffle_q INTEGER, shuffle_o INTEGER,
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, student_id INTEGER, student_name TEXT,
        order_json TEXT, current INTEGER, answers TEXT,
        score INTEGER, total INTEGER, finished INTEGER,
        started_at REAL, finished_at REAL
    );
    """)
    # eski baza uchun migratsiya: stem_xml ustuni bo'lmasa qo'shamiz
    cols = [r["name"] for r in c.execute("PRAGMA table_info(questions)").fetchall()]
    if "stem_xml" not in cols:
        c.execute("ALTER TABLE questions ADD COLUMN stem_xml TEXT DEFAULT '[]'")
    c.commit()


# ---------------- media ----------------
def add_media(data):
    c = conn()
    cur = c.execute("INSERT INTO media(data) VALUES(?)", (sqlite3.Binary(data),))
    c.commit()
    return cur.lastrowid

def get_media(mid):
    row = conn().execute("SELECT data FROM media WHERE id=?", (mid,)).fetchone()
    return bytes(row["data"]) if row else None


# ---------------- bases / questions ----------------
def add_base(owner_id, name):
    c = conn()
    cur = c.execute("INSERT INTO bases(owner_id,name,created_at) VALUES(?,?,?)",
                    (owner_id, name, time.time()))
    c.commit()
    return cur.lastrowid

def _swap_media_tokens(xml_list, images):
    """images (bytes) -> media jadvaliga; xml ichidagi LOCALMEDIA:k -> DBMEDIA:{id}."""
    ids = [add_media(b) for b in images]
    out = []
    for s in xml_list:
        for k, mid in enumerate(ids):
            s = s.replace("LOCALMEDIA:%d" % k, "DBMEDIA:%d" % mid)
        out.append(s)
    return out, ids

def add_questions(owner_id, base_id, topic, parsed_questions):
    c = conn()
    count = 0
    for q in parsed_questions:
        stem_xml, stem_ids = _swap_media_tokens(q.get("stem_xml", []), q.get("stem_images", []))
        opts = []
        for o in q["options"]:
            oxml, oids = _swap_media_tokens(o.get("xml", []), o.get("images", []))
            opts.append({"text": o["text"], "media": oids, "xml": oxml})
        c.execute(
            "INSERT INTO questions(owner_id,base_id,topic,stem,stem_media,stem_xml,options,correct_index)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (owner_id, base_id, topic, q["stem"], json.dumps(stem_ids),
             json.dumps(stem_xml, ensure_ascii=False),
             json.dumps(opts, ensure_ascii=False), q["correct_index"]))
        count += 1
    c.commit()
    return count

def question_count(owner_id):
    return conn().execute("SELECT COUNT(*) n FROM questions WHERE owner_id=?",
                          (owner_id,)).fetchone()["n"]

def base_list(owner_id):
    rows = conn().execute(
        "SELECT b.id,b.name,COUNT(q.id) n FROM bases b "
        "LEFT JOIN questions q ON q.base_id=b.id WHERE b.owner_id=? GROUP BY b.id ORDER BY b.id",
        (owner_id,)).fetchall()
    return [dict(r) for r in rows]

def get_question(qid):
    row = conn().execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["stem_media"] = json.loads(d["stem_media"])
    d["stem_xml"] = json.loads(d["stem_xml"] or "[]")
    d["options"] = json.loads(d["options"])
    return d

def clear_owner(owner_id):
    c = conn()
    c.execute("DELETE FROM questions WHERE owner_id=?", (owner_id,))
    c.execute("DELETE FROM bases WHERE owner_id=?", (owner_id,))
    c.commit()


# ---------------- tests ----------------
def _gen_code(n=6):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(n))
        if not conn().execute("SELECT 1 FROM tests WHERE code=?", (code,)).fetchone():
            return code

def create_test(owner_id, title, count, shuffle_q=True, shuffle_o=True, base_ids=None):
    c = conn()
    if base_ids:
        q = ("SELECT id FROM questions WHERE owner_id=? AND base_id IN (%s)"
             % ",".join("?" * len(base_ids)))
        rows = c.execute(q, (owner_id, *base_ids)).fetchall()
    else:
        rows = c.execute("SELECT id FROM questions WHERE owner_id=?", (owner_id,)).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return None, 0
    random.shuffle(ids)
    chosen = ids[:count]
    code = _gen_code()
    c.execute("INSERT INTO tests(code,owner_id,title,question_ids,shuffle_q,shuffle_o,created_at)"
              " VALUES(?,?,?,?,?,?,?)",
              (code, owner_id, title, json.dumps(chosen),
               int(shuffle_q), int(shuffle_o), time.time()))
    c.commit()
    return code, len(chosen)

def get_test(code):
    row = conn().execute("SELECT * FROM tests WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["question_ids"] = json.loads(d["question_ids"])
    return d

def tests_by_owner(owner_id):
    rows = conn().execute("SELECT code,title,question_ids,created_at FROM tests "
                          "WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["n"] = len(json.loads(d["question_ids"])); out.append(d)
    return out


# ---------------- sessions ----------------
REF_WORDS = ("barcha", "hammasi", "yuqorid", "hech bir", "hech qa",
             "all of", "none of")

def _is_reference(opts):
    import re
    for o in opts:
        t = (o["text"] or "").lower()
        if any(w in t for w in REF_WORDS):
            return True
        if re.search(r"\b[a-z]\s*(,|va|and|и)\s*[a-z]\b", t):
            return True
    return False

def start_session(code, student_id, student_name):
    test = get_test(code)
    if not test:
        return None
    qids = test["question_ids"][:]
    if test["shuffle_q"]:
        random.shuffle(qids)
    order = []
    for qid in qids:
        q = get_question(qid)
        if not q:
            continue
        n = len(q["options"])
        pos = list(range(n))
        if test["shuffle_o"] and not _is_reference(q["options"]):
            random.shuffle(pos)
        correct_pos = pos.index(q["correct_index"]) if q["correct_index"] in pos else -1
        order.append({"qid": qid, "opt": pos, "correct": correct_pos})
    c = conn()
    cur = c.execute(
        "INSERT INTO sessions(code,student_id,student_name,order_json,current,answers,"
        "score,total,finished,started_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (code, student_id, student_name, json.dumps(order), 0, json.dumps([]),
         0, len(order), 0, time.time(), 0))
    c.commit()
    return cur.lastrowid

def get_session(sid):
    row = conn().execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["order"] = json.loads(d["order_json"])
    d["answers"] = json.loads(d["answers"])
    return d

def active_session_for(student_id, code):
    row = conn().execute(
        "SELECT id FROM sessions WHERE student_id=? AND code=? AND finished=0 "
        "ORDER BY id DESC LIMIT 1", (student_id, code)).fetchone()
    return row["id"] if row else None

def record_answer(sid, chosen_pos, correct):
    s = get_session(sid)
    answers = s["answers"]
    answers.append({"i": s["current"], "chosen": chosen_pos, "ok": bool(correct)})
    new_current = s["current"] + 1
    new_score = s["score"] + (1 if correct else 0)
    c = conn()
    c.execute("UPDATE sessions SET current=?,answers=?,score=? WHERE id=?",
              (new_current, json.dumps(answers), new_score, sid))
    c.commit()

def finish_session(sid):
    c = conn()
    c.execute("UPDATE sessions SET finished=1,finished_at=? WHERE id=?", (time.time(), sid))
    c.commit()

def results_for_test(code):
    rows = conn().execute(
        "SELECT student_name,score,total,finished FROM sessions "
        "WHERE code=? AND finished=1 ORDER BY score DESC,finished_at ASC", (code,)).fetchall()
    return [dict(r) for r in rows]
