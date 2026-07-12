"""
Word (.docx) bazani o'qish moduli.
core.js dagi sinovdan o'tgan mantiqning Python porti.

Har bir savolni quyidagicha ajratadi:
  - #N.  -> savol boshlanishi
  - +X)  -> to'g'ri javob
  - A) B) C) ...  -> variantlar (belgilar matnga yopishgan/bir bo'lakda bo'lsa ham)
Formula (OMML), grek (Unicode / Symbol shrift), yuqori/pastki indeks -> matnga aylantiriladi.
Rasm -> baytlari ajratib olinadi (bot rasmni photo qilib yuboradi).
Jadval -> kataklari o'qiladi.
"""
import re
import zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W, "m": M, "r": R}

OBJ_OPEN, OBJ_CLOSE = "\ue000", "\ue001"

SYMBOL_MAP = {
    0x61: "α", 0x62: "β", 0x63: "χ", 0x64: "δ", 0x65: "ε", 0x66: "φ", 0x67: "γ",
    0x68: "η", 0x69: "ι", 0x6A: "ϕ", 0x6B: "κ", 0x6C: "λ", 0x6D: "μ", 0x6E: "ν",
    0x6F: "ο", 0x70: "π", 0x71: "θ", 0x72: "ρ", 0x73: "σ", 0x74: "τ", 0x75: "υ",
    0x76: "ϖ", 0x77: "ω", 0x78: "ξ", 0x79: "ψ", 0x7A: "ζ",
    0x41: "Α", 0x42: "Β", 0x43: "Χ", 0x44: "Δ", 0x45: "Ε", 0x46: "Φ", 0x47: "Γ",
    0x48: "Η", 0x49: "Ι", 0x4B: "Κ", 0x4C: "Λ", 0x4D: "Μ", 0x4E: "Ν", 0x4F: "Ο",
    0x50: "Π", 0x51: "Θ", 0x52: "Ρ", 0x53: "Σ", 0x54: "Τ", 0x55: "Υ", 0x56: "ς",
    0x57: "Ω", 0x58: "Ξ", 0x59: "Ψ", 0x5A: "Ζ",
    0xB1: "±", 0xB3: "≥", 0xA3: "≤", 0xB9: "≠", 0xAE: "→", 0xAC: "←",
    0xA5: "∞", 0xD6: "√", 0xF7: "÷", 0xB4: "×", 0xB6: "∂", 0xF2: "∫",
    0xE5: "∑", 0xD5: "∏", 0xCE: "∈", 0xB7: "·", 0xB0: "°",
}
SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
       "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "n": "ⁿ", "i": "ⁱ",
       "(": "⁽", ")": "⁾", "a": "ᵃ", "b": "ᵇ", "x": "ˣ"}
SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
       "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "(": "₍", ")": "₎",
       "a": "ₐ", "e": "ₑ", "x": "ₓ", "n": "ₙ"}

LABEL_G = re.compile(r"(^|\s)(\+?)\s*([A-Za-z])\s*\)")
LABEL_TEST = re.compile(r"(^|\s)(\+?)\s*[A-Za-z]\s*\)")
HASH_RE = re.compile(r"^#\s*(\d+)\s*\.")

SKIP = {"pPr", "bookmarkStart", "bookmarkEnd", "proofErr", "sectPr",
        "commentRangeStart", "commentRangeEnd", "commentReference",
        "lastRenderedPageBreak"}


def _tag(el):
    if not isinstance(el.tag, str):
        return ""
    return etree.QName(el).localname


def _to_super(s):
    return "".join(SUP.get(ch, None) or ch for ch in s) if all(ch in SUP for ch in s) else "^" + s
def _to_sub(s):
    return "".join(SUB.get(ch, None) or ch for ch in s) if all(ch in SUB for ch in s) else "_" + s


def _omml_text(node):
    t = _tag(node)
    if t == "t":
        return node.text or ""
    if t == "r":
        return "".join(_omml_text(c) for c in node)
    if t == "sSup":
        e = node.find("m:e", NS); sup = node.find("m:sup", NS)
        base = _omml_children(e) if e is not None else ""
        ex = _omml_children(sup) if sup is not None else ""
        return base + _to_super(ex)
    if t == "sSub":
        e = node.find("m:e", NS); sub = node.find("m:sub", NS)
        base = _omml_children(e) if e is not None else ""
        ix = _omml_children(sub) if sub is not None else ""
        return base + _to_sub(ix)
    if t == "sSubSup":
        e = node.find("m:e", NS); sub = node.find("m:sub", NS); sup = node.find("m:sup", NS)
        return (_omml_children(e) + _to_sub(_omml_children(sub)) + _to_super(_omml_children(sup)))
    if t == "f":
        num = node.find("m:num", NS); den = node.find("m:den", NS)
        return "(" + _omml_children(num) + ")/(" + _omml_children(den) + ")"
    if t == "rad":
        e = node.find("m:e", NS)
        return "√(" + (_omml_children(e) if e is not None else "") + ")"
    if t == "d":
        es = node.findall("m:e", NS)
        return "(" + ", ".join(_omml_children(e) for e in es) + ")"
    if t == "nary":
        sub = node.find("m:sub", NS); sup = node.find("m:sup", NS); e = node.find("m:e", NS)
        s = "∑"
        if sub is not None: s += _to_sub(_omml_children(sub))
        if sup is not None: s += _to_super(_omml_children(sup))
        if e is not None: s += _omml_children(e)
        return s
    return _omml_children(node)


def _omml_children(node):
    if node is None:
        return ""
    return "".join(_omml_text(c) for c in node)


def _run_text(run, images, imgmap, rels, zf):
    """Bitta run -> matn (yoki rasm placeholder)."""
    # rasm bormi?
    if run.find(".//w:drawing", NS) is not None or run.find(".//w:pict", NS) is not None:
        rid = None
        blip = run.find(".//a:blip", {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"})
        if blip is not None:
            rid = blip.get("{%s}embed" % R) or blip.get("{%s}link" % R)
        if rid is None:
            imgd = run.find(".//v:imagedata", {"v": "urn:schemas-microsoft-com:vml"})
            if imgd is not None:
                rid = imgd.get("{%s}id" % R)
        if rid and rid in rels:
            data = _read_media(zf, rels[rid])
            if data:
                idx = len(images)
                images.append(data)
                return OBJ_OPEN + str(idx) + OBJ_CLOSE
        return ""
    out = []
    # vertAlign (superscript/subscript via format button)
    va = None
    rpr = run.find("w:rPr", NS)
    if rpr is not None:
        v = rpr.find("w:vertAlign", NS)
        if v is not None:
            va = v.get("{%s}val" % W)
    for c in run:
        ct = _tag(c)
        if ct == "t":
            out.append(c.text or "")
        elif ct in ("tab", "br", "cr"):
            out.append(" ")
        elif ct == "sym":
            font = c.get("{%s}font" % W) or ""
            char = c.get("{%s}char" % W) or ""
            if re.search("symbol", font, re.I) and char:
                out.append(SYMBOL_MAP.get(int(char, 16) & 0xFF, ""))
    text = "".join(out)
    if va == "superscript":
        text = _to_super(text)
    elif va == "subscript":
        text = _to_sub(text)
    return text


def _encode_para(p, images, imgmap, rels, zf):
    parts = []
    for c in p:
        t = _tag(c)
        if t in SKIP:
            continue
        if t == "r":
            parts.append(_run_text(c, images, imgmap, rels, zf))
        elif t in ("oMath", "oMathPara"):
            parts.append(_omml_children(c) if t == "oMathPara" else _omml_text(c))
        elif t in ("hyperlink", "smartTag", "ins"):
            for rr in c:
                if _tag(rr) == "r":
                    parts.append(_run_text(rr, images, imgmap, rels, zf))
    return "".join(parts)


def _encode_nodes(nodes, images, rels, zf):
    """Blok tugunlar (w:p / w:tbl) -> yagona matn (rasm placeholderlari bilan)."""
    imgmap = {}
    chunks = []
    for n in nodes:
        t = _tag(n)
        if t == "p":
            chunks.append(_encode_para(n, images, imgmap, rels, zf))
        elif t == "tbl":
            cells = []
            for row in n:
                if _tag(row) != "tr":
                    continue
                for cell in row:
                    if _tag(cell) != "tc":
                        continue
                    for cp in cell:
                        if _tag(cp) == "p":
                            cells.append(_encode_para(cp, images, imgmap, rels, zf))
            chunks.append(" ".join(cells))
        chunks.append(" ")
    return "".join(chunks)


def _segment_clean(seg, images):
    """placeholderlarni ajratib, matn + shu segmentga tegishli rasm indekslarini qaytaradi."""
    imgs = []
    def repl(m):
        imgs.append(int(m.group(1)))
        return ""
    text = re.sub(OBJ_OPEN + r"(\d+)" + OBJ_CLOSE, repl, seg)
    return text.strip(), imgs


def _split_options(combined, images):
    marks = []
    for m in LABEL_G.finditer(combined):
        label_start = m.start() + len(m.group(1))
        marks.append((label_start, m.end(), m.group(2) == "+"))
    options = []
    for i, (ls, ce, correct) in enumerate(marks):
        frm = ce
        to = marks[i + 1][0] if i + 1 < len(marks) else len(combined)
        text, imgs = _segment_clean(combined[frm:to], images)
        if text or imgs:
            options.append({"text": text, "correct": correct, "images": imgs})
    return options


def _read_media(zf, target):
    target = target.lstrip("./")
    for path in ("word/" + target, target):
        try:
            return zf.read(path)
        except KeyError:
            continue
    return None


def _load_rels(zf):
    rels = {}
    try:
        data = zf.read("word/_rels/document.xml.rels")
    except KeyError:
        return rels
    root = etree.fromstring(data)
    for rel in root:
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            rels[rid] = target
    return rels


def parse_docx(data, topic=""):
    """
    data: bytes (docx fayl)
    return: [ {topic, stem, stem_images:[bytes], options:[{text,correct,images:[bytes]}], correct_index} , ... ]
    """
    zf = zipfile.ZipFile(__import__("io").BytesIO(data))
    rels = _load_rels(zf)
    xml = zf.read("word/document.xml")
    root = etree.fromstring(xml)
    body = root.find("w:body", NS)
    if body is None:
        return []

    # bloklarga bo'lish
    blocks = []
    cur = None
    for node in body:
        t = _tag(node)
        if t not in ("p", "tbl"):
            continue
        text = "".join(node.itertext()).strip()
        if t == "p" and HASH_RE.match(text):
            if cur:
                blocks.append(cur)
            cur = {"stem_p": node, "following": []}
        elif cur:
            cur["following"].append(node)
    if cur:
        blocks.append(cur)

    questions = []
    for b in blocks:
        images = []  # bu savolga tegishli barcha rasm baytlari
        stem_combined = _encode_nodes([b["stem_p"]], images, rels, zf)
        stem_combined = re.sub(r"^\s*#\s*\d+\s*\.\s*", "", stem_combined)

        # savol qatorida variant bormi?
        inline = ""
        mm = LABEL_TEST.search(stem_combined)
        if mm:
            inline = stem_combined[mm.start():]
            stem_combined = stem_combined[:mm.start()]

        # following: stem-extra vs option nodes
        opt_nodes = []
        started = bool(inline)
        for node in b["following"]:
            has_label = bool(LABEL_TEST.search("".join(node.itertext())))
            if not started and not has_label:
                # stem davomi (rasm/jadval/matn) -> stem matniga qo'shamiz
                extra = _encode_nodes([node], images, rels, zf)
                stem_combined += " " + extra
            else:
                started = True
                opt_nodes.append(node)

        opt_combined = inline
        if opt_nodes:
            opt_combined += " " + _encode_nodes(opt_nodes, images, rels, zf)

        options = _split_options(opt_combined, images)
        stem_text, stem_imgs = _segment_clean(stem_combined, images)

        if len(options) < 2:
            continue
        if not stem_text and not stem_imgs:
            continue

        correct_index = next((i for i, o in enumerate(options) if o["correct"]), -1)

        # placeholder indekslarni haqiqiy baytlarga aylantirish
        q = {
            "topic": topic,
            "stem": stem_text,
            "stem_images": [images[i] for i in stem_imgs if i < len(images)],
            "options": [{"text": o["text"],
                         "correct": o["correct"],
                         "images": [images[i] for i in o["images"] if i < len(images)]}
                        for o in options],
            "correct_index": correct_index,
        }
        questions.append(q)
    return questions
