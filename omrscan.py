"""
OMR skaner (3-faza). Suratdan javob varag'ini o'qiydi.
Bosqichlar: langarlarni top -> to'g'rila (homografiya) -> QR (kod:variant) ->
ID bo'yalgan doiralar -> javob doiralari. omr.py geometriyasidan foydalanadi.
"""
import numpy as np
import cv2
import omr

# pyzbar (ZBar) — OpenCV'nikidan ancha kuchli QR o'qigich. Agar tizimda
# libzbar0 o'rnatilmagan bo'lsa, import xato beradi va biz jimgina OpenCV'ga
# qaytamiz (funksionallik buzilmaydi, faqat biroz kamroq ishonchli bo'ladi).
try:
    from pyzbar.pyzbar import decode as _zbar_decode
    _HAS_ZBAR = True
except Exception:
    _HAS_ZBAR = False

SCALE = 2.5                     # kanonik varaq: pt * SCALE = piksel
FILL_MIN = 0.34                 # doira "bo'yalgan" deb hisoblanishi uchun min qorong'ilik
MARGIN = 0.12                   # eng qorong'i va keyingisi orasidagi farq (aniqlik uchun)


def _decode_qr(images):
    """Bir nechta dekoder va tasvirni sinab, QR matnini qaytaradi (yoki None).
    Tartib: pyzbar (agar bor bo'lsa) -> OpenCV QRCodeDetector. Har bir dekoder
    to'g'rilangan (warp) va asl tasvirda sinaladi."""
    grays = []
    for im in images:
        if im is None:
            continue
        grays.append(im if im.ndim == 2 else cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    # 1) pyzbar — eng ishonchli
    if _HAS_ZBAR:
        for g in grays:
            try:
                for sym in _zbar_decode(g):
                    val = (sym.data or b"").decode("utf-8", "ignore").strip()
                    if val:
                        return val
            except Exception:
                pass
    # 2) OpenCV — zaxira
    det = cv2.QRCodeDetector()
    for g in grays:
        try:
            data, _, _ = det.detectAndDecode(g)
            if data:
                return data.strip()
        except Exception:
            pass
    return None


def _load(image_bytes):
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _find_anchors(gray):
    """4 ta to'la qora kvadrat langarni topadi -> [TL,TR,BL,BR] (piksel) yoki None."""
    H, W = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_img = W * H
    cand = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < area_img * 0.00004 or a > area_img * 0.006:   # QR va shovqinni chiqarib tashlaydi
            continue
        x, y, w, h = cv2.boundingRect(c)
        if h == 0:
            continue
        ar = w / float(h)
        if ar < 0.65 or ar > 1.55:
            continue
        if a / float(w * h) < 0.72:      # to'la (solid) bo'lishi kerak
            continue
        cand.append((x + w / 2.0, y + h / 2.0, a))
    if len(cand) < 4:
        return None
    corners = [(0, 0), (W, 0), (0, H), (W, H)]     # TL,TR,BL,BR
    chosen = []
    used = set()
    for (cxr, cyr) in corners:
        best, bi = None, None
        for i, (cx, cy, a) in enumerate(cand):
            if i in used:
                continue
            d = (cx - cxr) ** 2 + (cy - cyr) ** 2
            if best is None or d < best:
                best, bi = d, i
        if bi is None:
            return None
        used.add(bi)
        chosen.append((cand[bi][0], cand[bi][1]))
    return chosen


def _warp(img, anchors_px):
    aw = int(omr.PAGE_W * SCALE)
    ah = int(omr.PAGE_H * SCALE)
    dst = np.float32([(x * SCALE, y * SCALE) for (x, y) in omr.ANCHORS])   # TL,TR,BL,BR
    src = np.float32(anchors_px)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (aw, ah))


def _fill_ratio(bw, cx_pt, cy_pt, r_pt):
    """Doira ichидаги bo'yalган (oq=255) piksellar ulushi (0..1).
    `bw` — adaptив chegара bilan tayyorlanган ikkilик tasvir (qorong'и joylar 255)."""
    cx, cy = int(cx_pt * SCALE), int(cy_pt * SCALE)
    r = max(3, int(r_pt * SCALE * 0.72))
    x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
    H, W = bw.shape
    if x0 < 0 or y0 < 0 or x1 >= W or y1 >= H:
        return 0.0
    patch = bw[y0:y1, x0:x1]
    mask = np.zeros(patch.shape, np.uint8)
    cv2.circle(mask, (r, r), r, 255, -1)
    vals = patch[mask == 255]
    if vals.size == 0:
        return 0.0
    return float(np.mean(vals > 0))


def _pick(fills):
    """fills ro'yxatidan eng bo'yalganini tanlaydi. -> (index|None, ambiguous)."""
    order = sorted(range(len(fills)), key=lambda i: fills[i], reverse=True)
    top = order[0]
    top_v = fills[top]
    second_v = fills[order[1]] if len(order) > 1 else 0.0
    if top_v < FILL_MIN:
        return None, False                 # hech biri bo'yalmagan
    if top_v - second_v < MARGIN:
        return top, True                   # ikki doira yaqin -> shubhali
    return top, False


def scan(image_bytes, n_questions):
    """Suratni o'qiydi. -> dict."""
    img = _load(image_bytes)
    if img is None:
        return {"ok": False, "reason": "image"}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    anchors = _find_anchors(gray)
    if not anchors:
        return {"ok": False, "reason": "anchors"}
    warp = _warp(img, anchors)
    gw = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)

    # Yoritilishni tekislash (flat-field): fonni baholab, unga bo'lamiz -> soya/notekis
    # yorug'lik yo'qoladi. So'ng Otsu bilan ikkilik. Bu qat'iy "128" chegarasidan
    # ancha ishonchli — telefon suratidagi soyalarda ham to'g'ri o'qiydi.
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))
    bg = cv2.morphologyEx(gw, cv2.MORPH_CLOSE, k)            # doiralar fonga "yutiladi"
    norm = cv2.divide(gw, bg, scale=255)                     # yoritilish tekislanadi
    bw = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))  # ingichka harf/shovqin ketadi

    # QR (kod:variant) — pyzbar (bo'lsa) -> OpenCV, to'g'rilangan va asl tasvirda
    code, variant = None, None
    data = _decode_qr([warp, img])
    if data and ":" in data:
        code, vs = data.rsplit(":", 1)
        variant = int(vs) if vs.isdigit() else None

    # ID (5 xona)
    student_id = ""
    id_ambig = False
    for col in range(omr.ID_DIGITS):
        fills = [_fill_ratio(bw, *omr.id_bubble_center(col, d), omr.ID_R) for d in range(10)]
        idx, amb = _pick(fills)
        id_ambig = id_ambig or amb
        student_id += (str(idx) if idx is not None else "_")

    # javoblar
    n = min(n_questions, omr.MAX_Q)
    answers, ambiguous = [], []
    for q in range(n):
        fills = [_fill_ratio(bw, *omr.answer_bubble_center(q, o), omr.ANS_R)
                 for o in range(omr.N_OPTIONS)]
        idx, amb = _pick(fills)
        answers.append(omr.LETTERS[idx] if idx is not None else None)
        if amb or idx is None:
            ambiguous.append(q + 1)

    return {"ok": True, "code": code, "variant": variant,
            "student_id": student_id, "id_ambiguous": id_ambig,
            "answers": answers, "ambiguous": ambiguous}


def grade(answers, key):
    """answers: ['A',None,...]; key: ['B','A',...]. -> (score, correct, wrong_list)."""
    correct = 0
    wrong = []
    for i, k in enumerate(key):
        a = answers[i] if i < len(answers) else None
        if a == k:
            correct += 1
        else:
            wrong.append(i + 1)
    total = len(key)
    return correct, total, wrong
