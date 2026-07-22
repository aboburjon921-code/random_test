"""
OMR skaner (3-faza). Suratdan javob varag'ini o'qiydi.
Bosqichlar: langarlarni top -> to'g'rila (homografiya) -> QR (kod:variant) ->
ID bo'yalgan doiralar -> javob doiralari. omr.py geometriyasidan foydalanadi.
"""
import numpy as np
import cv2
import omr

SCALE = 2.5                     # kanonik varaq: pt * SCALE = piksel
FILL_MIN = 0.34                 # doira "bo'yalgan" deb hisoblanishi uchun min qorong'ilik
MARGIN = 0.12                   # eng qorong'i va keyingisi orasidagi farq (aniqlik uchun)


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


def _fill_ratio(gray_warp, cx_pt, cy_pt, r_pt):
    """Doira markazi atrofidagi qorong'ilik ulushi (0..1)."""
    cx, cy = int(cx_pt * SCALE), int(cy_pt * SCALE)
    r = max(3, int(r_pt * SCALE * 0.72))
    x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
    H, W = gray_warp.shape
    if x0 < 0 or y0 < 0 or x1 >= W or y1 >= H:
        return 0.0
    patch = gray_warp[y0:y1, x0:x1]
    mask = np.zeros(patch.shape, np.uint8)
    cv2.circle(mask, (r, r), r, 255, -1)
    vals = patch[mask == 255]
    if vals.size == 0:
        return 0.0
    # Otsu-ga o'xshash lokal normallashtirish o'rniga: qorong'i piksellar ulushi
    dark = np.mean(vals < 128)
    return float(dark)


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

    # QR (kod:variant)
    code, variant = None, None
    try:
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(warp)
        if not data:
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        if data and ":" in data:
            code, vs = data.rsplit(":", 1)
            variant = int(vs) if vs.isdigit() else None
    except Exception:
        pass

    # ID (5 xona)
    student_id = ""
    id_ambig = False
    for col in range(omr.ID_DIGITS):
        fills = [_fill_ratio(gw, *omr.id_bubble_center(col, d), omr.ID_R) for d in range(10)]
        idx, amb = _pick(fills)
        id_ambig = id_ambig or amb
        student_id += (str(idx) if idx is not None else "_")

    # javoblar
    n = min(n_questions, omr.MAX_Q)
    answers, ambiguous = [], []
    for q in range(n):
        fills = [_fill_ratio(gw, *omr.answer_bubble_center(q, o), omr.ANS_R)
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
