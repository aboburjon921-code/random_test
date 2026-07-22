"""
Javob varag'i (OMR titul) — 2-faza.
Geometriya (langar, ID panjarasi, javob doiralari) ANIQ koordinatalarda belgilanadi;
3-fazadagi skaner aynan shu geometriyadan foydalanadi.

Koordinatalar: TOP-LEFT boshlang'ich (pt), A4. reportlab BOTTOM-LEFT bo'lgani uchun
chizishda y -> (PAGE_H - y) ga aylantiriladi.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

PAGE_W, PAGE_H = A4                      # 595.28 x 841.89 pt

ID_DIGITS   = 5                          # o'quvchi ID xonalari
N_OPTIONS    = 4                         # A B C D
LETTERS      = ["A", "B", "C", "D", "E"]
MAX_Q        = 40                        # bitta varaqqa sig'adigan savol (2 ustun x 20)

# langar markazlari (top-left pt)
ANCHOR = 16                              # kvadrat tomoni
AX0, AX1 = 34.0, PAGE_W - 34.0
AY0, AY1 = 34.0, PAGE_H - 34.0
ANCHORS = [(AX0, AY0), (AX1, AY0), (AX0, AY1), (AX1, AY1)]  # TL, TR, BL, BR

# ID panjarasi
ID_X0     = 64.0                         # 1-ustun markazi
ID_COL_DX = 33.0
ID_TOP_Y  = 214.0                        # 0-raqam qatori markazi
ID_ROW_DY = 22.0
ID_R      = 8.5                          # doira radiusi

# javob panjarasi (2 ustun)
ANS_TOP_Y   = 168.0
ANS_ROW_DY  = 22.0
ANS_PER_COL = 20
ANS_COL_X   = [270.0, 430.0]            # ustun boshlanish (savol raqami markazi)
ANS_OPT_DX  = 27.0                       # A..D oralig'i
ANS_OPT_X0  = 30.0                       # raqamdan A gacha siljish
ANS_R       = 8.5


def id_bubble_center(col, digit):
    return (ID_X0 + col * ID_COL_DX, ID_TOP_Y + digit * ID_ROW_DY)

def answer_bubble_center(q_index, opt):
    """q_index 0-based."""
    col = q_index // ANS_PER_COL
    row = q_index % ANS_PER_COL
    x0 = ANS_COL_X[col]
    return (x0 + ANS_OPT_X0 + opt * ANS_OPT_DX, ANS_TOP_Y + row * ANS_ROW_DY)

def geometry(n_questions):
    """Skaner uchun barcha markazlar (top-left pt)."""
    n = min(n_questions, MAX_Q)
    return {
        "page": (PAGE_W, PAGE_H),
        "anchors": ANCHORS, "anchor_size": ANCHOR,
        "id_digits": ID_DIGITS, "id_radius": ID_R,
        "id_bubbles": {(c, d): id_bubble_center(c, d)
                       for c in range(ID_DIGITS) for d in range(10)},
        "n_questions": n, "n_options": N_OPTIONS, "answer_radius": ANS_R,
        "answer_bubbles": {(q, o): answer_bubble_center(q, o)
                           for q in range(n) for o in range(N_OPTIONS)},
    }


# ---------- chizish ----------
def _y(y):            # top-left -> bottom-left
    return PAGE_H - y

def _sq(c, cx, cy, s, fill=1):
    c.rect(cx - s / 2, _y(cy) - s / 2, s, s, stroke=0, fill=fill)

def _circle(c, cx, cy, r, label=None, fill=0):
    c.setLineWidth(1.1)
    c.circle(cx, _y(cy), r, stroke=1, fill=fill)
    if label is not None:
        c.setFont("Helvetica", 7)
        c.setFillGray(0.45 if not fill else 1)
        c.drawCentredString(cx, _y(cy) - 2.6, label)
        c.setFillGray(0)


def build_answer_sheet_pdf(code, variant, n_questions, title="Test", total=None,
                           demo=False):
    """Javob varag'ini PDF baytlari sifatida qaytaradi."""
    n = min(n_questions, MAX_Q)
    total = total if total is not None else n_questions
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # 4 langar
    for (x, y) in ANCHORS:
        _sq(c, x, y, ANCHOR, fill=1)

    # sarlavha
    c.setFillGray(0)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(54, _y(66), "JAVOB VARAG'I")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(54, _y(84), "%s  ·  Jami: %d ta savol" % (title, total))
    c.setFont("Helvetica", 8.5)
    c.setFillGray(0.35)
    c.drawString(54, _y(100), "F.I.Sh: ______________________________")
    c.setFillGray(0)

    # QR (kod + variant) yuqori-o'ngda
    data = "%s:%d" % (code, variant)
    w = qr.QrCodeWidget(data); b = w.getBounds()
    qw, qh = b[2] - b[0], b[3] - b[1]
    size = 66
    d = Drawing(size, size, transform=[size / qw, 0, 0, size / qh, 0, 0])
    d.add(w)
    qx = PAGE_W - 46 - size
    renderPDF.draw(d, c, qx, _y(52) - size)
    # variant belgisi
    c.setFont("Helvetica-Bold", 11)
    c.roundRect(qx, _y(52) - size - 22, size, 18, 3, stroke=1, fill=0)
    c.drawCentredString(qx + size / 2, _y(52) - size - 18, "VARIANT %d" % variant)

    # ID panjarasi
    c.setFont("Helvetica-Bold", 9)
    c.drawString(54, _y(150), "O'QUVCHI ID")
    c.setFont("Helvetica", 7)
    c.setFillGray(0.4)
    c.drawString(54, _y(196), "raqamni yozing va bo'yang")
    c.setFillGray(0)
    # yozish katakchalari
    for col in range(ID_DIGITS):
        cx = ID_X0 + col * ID_COL_DX
        c.rect(cx - 11, _y(178) - 13, 22, 15, stroke=1, fill=0)
    # 0-9 doiralar
    demo_id = [0, 2, 4, 1, 5]
    for col in range(ID_DIGITS):
        for dgt in range(10):
            cx, cy = id_bubble_center(col, dgt)
            f = 1 if (demo and demo_id[col] == dgt) else 0
            _circle(c, cx, cy, ID_R, label=str(dgt), fill=f)

    # namuna
    ey = 470
    c.setFont("Helvetica-Bold", 8); c.drawString(54, _y(ey), "Namuna:")
    c.circle(120, _y(ey) + 2, 7, stroke=1, fill=1)
    c.setFont("Helvetica", 7.5); c.setFillGray(0.3)
    c.drawString(132, _y(ey), "to'g'ri (to'liq bo'yalgan)")
    c.circle(120, _y(ey + 16) + 2, 7, stroke=1, fill=0)
    c.drawString(132, _y(ey + 16), "noto'g'ri (bo'sh/yarim)")
    c.setFillGray(0)

    # javoblar sarlavhasi
    c.setFont("Helvetica-Bold", 9)
    c.drawString(ANS_COL_X[0] - 6, _y(150), "JAVOBLAR")
    # ustun tepasidagi A B C D
    for ci, x0 in enumerate(ANS_COL_X):
        if ci * ANS_PER_COL >= n:
            break
        c.setFont("Helvetica-Bold", 7.5); c.setFillGray(0.4)
        for o in range(N_OPTIONS):
            c.drawCentredString(x0 + ANS_OPT_X0 + o * ANS_OPT_DX, _y(158), LETTERS[o])
        c.setFillGray(0)

    # javob doiralari
    demo_ans = {0: 1, 1: 3, 2: 0, 5: 2, 8: 1, 21: 3, 24: 0}
    for q in range(n):
        col = q // ANS_PER_COL
        x0 = ANS_COL_X[col]
        # raqam
        c.setFont("Helvetica-Bold", 8.5)
        c.drawRightString(x0 + 12, _y(ANS_TOP_Y + (q % ANS_PER_COL) * ANS_ROW_DY) - 3,
                          "%d." % (q + 1))
        for o in range(N_OPTIONS):
            cx, cy = answer_bubble_center(q, o)
            f = 1 if (demo and demo_ans.get(q) == o) else 0
            _circle(c, cx, cy, ANS_R, label=LETTERS[o], fill=f)

    # pastki izoh
    c.setFont("Helvetica", 7); c.setFillGray(0.45)
    c.drawCentredString(PAGE_W / 2, _y(PAGE_H - 44),
                        "Doirani qora ruchka/qalam bilan to'liq bo'yang.  "
                        "Burchaklardagi qora kvadratlarga tegmang.")
    c.setFillGray(0)

    c.showPage()
    c.save()
    return buf.getvalue()
