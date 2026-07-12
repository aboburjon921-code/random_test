
import re
import io
import copy
import zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
V = "urn:schemas-microsoft-com:vml"
XMLNS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W, "m": M, "r": R, "a": A, "v": V}

SKIP = {"pPr", "bookmarkStart", "bookmarkEnd", "proofErr", "sectPr",
        "commentRangeStart", "commentRangeEnd", "commentReference",
        "lastRenderedPageBreak"}

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
SUP = {c: s for c, s in zip("0123456789+-n i()axb",
       "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ ⁱ⁽⁾ᵃˣᵇ")}
SUB = {c: s for c, s in zip("0123456789+-()aexn",
       "₀₁₂₃₄₅₆₇₈₉₊₋₍₎ₐₑₓₙ")}

LABEL_RE = re.compile(r"^\s*(\+?)\s*([A-Za-z])\s*\)\s*(.*)$", re.S)
LABEL_TEST = re.compile(r"(^|\s)(\+?)\s*[A-Za-z]\s*\)")
HASH_RE = re.compile(r"^\s*#\s*(\d+)\s*\.\s*(.*)$", re.S)


def ln(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else ""

def _to_sup(s):
    return "".join(SUP.get(ch, ch) for ch in s) if all(ch in SUP for ch in s) else "^" + s
def _to_sub(s):
    return "".join(SUB.get(ch, ch) for ch in s) if all(ch in SUB for ch in s) else "_" + s


# ---------- MATN chiqarish (interaktiv uchun) ----------
def _omml_text(node):
    t = ln(node)
    if t == "t":
        return node.text or ""
    if t == "r":
        return "".join(_omml_text(c) for c in node)
    if t == "sSup":
        e = node.find("m:e", NS); sup = node.find("m:sup", NS)
        return _omml_kids(e) + _to_sup(_omml_kids(sup))
    if t == "sSub":
        e = node.find("m:e", NS); sub = node.find("m:sub", NS)
        return _omml_kids(e) + _to_sub(_omml_kids(sub))
    if t == "sSubSup":
        e = node.find("m:e", NS); sub = node.find("m:sub", NS); sup = node.find("m:sup", NS)
        return _omml_kids(e) + _to_sub(_omml_kids(sub)) + _to_sup(_omml_kids(sup))
    if t == "f":
        return "(" + _omml_kids(node.find("m:num", NS)) + ")/(" + _omml_kids(node.find("m:den", NS)) + ")"
    if t == "rad":
        return "√(" + _omml_kids(node.find("m:e", NS)) + ")"
    if t == "d":
        return "(" + ", ".join(_omml_kids(e) for e in node.findall("m:e", NS)) + ")"
    if t == "nary":
        s = "∑"
        sub = node.find("m:sub", NS); sup = node.find("m:sup", NS); e = node.find("m:e", NS)
        if sub is not None: s += _to_sub(_omml_kids(sub))
        if sup is not None: s += _to_sup(_omml_kids(sup))
        return s + _omml_kids(e)
    return _omml_kids(node)

def _omml_kids(node):
    return "".join(_omml_text(c) for c in node) if node is not None else ""

def _run_text(run):
    va = None
    rpr = run.find("w:rPr", NS)
    if rpr is not None:
        v = rpr.find("w:vertAlign", NS)
        if v is not None:
            va = v.get("{%s}val" % W)
    out = []
    has_img = run.find(".//w:drawing", NS) is not None or run.find(".//w:pict", NS) is not None
    for c in run:
        t = ln(c)
        if t == "t":
            out.append(c.text or "")
        elif t in ("tab", "br", "cr"):
            out.append(" ")
        elif t == "sym":
            font = c.get("{%s}font" % W) or ""
            char = c.get("{%s}char" % W) or ""
            if re.search("symbol", font, re.I) and char:
                out.append(SYMBOL_MAP.get(int(char, 16) & 0xFF, ""))
    text = "".join(out)
    if va == "superscript": text = _to_sup(text)
    elif va == "subscript": text = _to_sub(text)
    if has_img and not text:
        return "🖼"
    return text

def _node_text(node):
    t = ln(node)
    if t == "r":
        return _run_text(node)
    if t in ("oMath", "oMathPara"):
        return _omml_kids(node) if t == "oMathPara" else _omml_text(node)
    if t in ("hyperlink", "smartTag", "ins"):
        return "".join(_run_text(r) for r in node if ln(r) == "r")
    return ""

def _nodes_text(nodes):
    return "".join(_node_text(n) for n in nodes).strip()


# ---------- XML chiqarish (Word uchun, AYNAN nusxa) ----------
def _make_text_run(text):
    r = etree.Element("{%s}r" % W)
    t = etree.SubElement(r, "{%s}t" % W)
    t.set("{%s}space" % XMLNS, "preserve")
    t.text = text
    return r

def _media_from_rid(rid, rels, zf):
    if not rid or rid not in rels:
        return None
    target = rels[rid].lstrip("./")
    for path in ("word/" + target, target):
        try:
            return zf.read(path)
        except KeyError:
            continue
    return None

def _serialize(nodes, rels, zf):
    """nodes -> (xml_strings, images_bytes). Rasm r:embed -> LOCALMEDIA:k tokeni."""
    xml_list, images = [], []
    for node in nodes:
        c = copy.deepcopy(node)
        for blip in c.findall(".//{%s}blip" % A):
            rid = blip.get("{%s}embed" % R) or blip.get("{%s}link" % R)
            data = _media_from_rid(rid, rels, zf)
            if data is not None:
                blip.set("{%s}embed" % R, "LOCALMEDIA:%d" % len(images)); images.append(data)
        for img in c.findall(".//{%s}imagedata" % V):
            rid = img.get("{%s}id" % R)
            data = _media_from_rid(rid, rels, zf)
            if data is not None:
                img.set("{%s}id" % R, "LOCALMEDIA:%d" % len(images)); images.append(data)
        xml_list.append(etree.tostring(c, encoding="unicode"))
    return xml_list, images


# ---------- content node oqimi ----------
def _content_nodes(nodes):
    out = []
    for n in nodes:
        t = ln(n)
        if t == "p":
            for c in n:
                if ln(c) not in SKIP:
                    out.append(c)
        elif t == "tbl":
            for row in n:
                if ln(row) == "tr":
                    for cell in row:
                        if ln(cell) == "tc":
                            for cp in cell:
                                if ln(cp) == "p":
                                    for c in cp:
                                        if ln(c) not in SKIP:
                                            out.append(c)
    return out


def _split_options(stream):
  
    options = []
    cur = None
    pending_plus = False
    for node in stream:
        if ln(node) == "r":
            txt = _run_text(node)
            stripped = txt.strip()
            m = LABEL_RE.match(stripped)
            if m and len(m.group(2)) == 1:
                correct = (m.group(1) == "+") or pending_plus
                pending_plus = False
                cur = {"correct": correct, "nodes": []}
                options.append(cur)
                rem = m.group(3)
                if rem.strip():
                    cur["nodes"].append(_make_text_run(rem))
                continue
            if stripped == "+":
                pending_plus = True
                continue
            if cur is not None:
                cur["nodes"].append(node)
        else:
            if cur is not None:
                cur["nodes"].append(node)
    return options


def _extract_stem(stem_p):
    content, consumed, started = [], "", False
    for c in stem_p:
        t = ln(c)
        if t in SKIP:
            continue
        if not started:
            if t == "r":
                consumed += _run_text(c)
                m = HASH_RE.match(consumed)
                if m and re.search(r"#\s*\d+\s*\.", consumed):
                    started = True
                    rem = m.group(2)
                    if rem.strip():
                        content.append(_make_text_run(rem))
                continue
            else:
                started = True
                content.append(c)
        else:
            content.append(c)
    return content


def _load_rels(zf):
    rels = {}
    try:
        root = etree.fromstring(zf.read("word/_rels/document.xml.rels"))
    except KeyError:
        return rels
    for rel in root:
        rid, target = rel.get("Id"), rel.get("Target")
        if rid and target:
            rels[rid] = target
    return rels


def parse_docx(data, topic=""):
    zf = zipfile.ZipFile(io.BytesIO(data))
    rels = _load_rels(zf)
    root = etree.fromstring(zf.read("word/document.xml"))
    body = root.find("{%s}body" % W)
    if body is None:
        return []

    blocks, cur = [], None
    for node in body:
        t = ln(node)
        if t not in ("p", "tbl"):
            continue
        text = "".join(node.itertext()).strip()
        if t == "p" and re.match(r"^\s*#\s*\d+\s*\.", text):
            if cur: blocks.append(cur)
            cur = {"stem_p": node, "following": []}
        elif cur:
            cur["following"].append(node)
    if cur: blocks.append(cur)

    questions = []
    for b in blocks:
        stem_nodes = _extract_stem(b["stem_p"])

        # stem qatorida variant bo'lsa (kamdan-kam) — ajratmaymiz, following'dan olamiz
        opt_source = []
        for node in b["following"]:
            if LABEL_TEST.search("".join(node.itertext())) or opt_source:
                opt_source.append(node)
            else:
                stem_nodes.append(node)  # stem davomi (rasm/jadval/matn)

        options = _split_options(_content_nodes(opt_source))
        if len(options) < 2:
            continue

        stem_xml, stem_imgs = _serialize(stem_nodes, rels, zf)
        stem_text = _nodes_text(stem_nodes)

        opt_out = []
        for o in options:
            oxml, oimgs = _serialize(o["nodes"], rels, zf)
            opt_out.append({"text": _nodes_text(o["nodes"]), "correct": o["correct"],
                            "xml": oxml, "images": oimgs})

        correct_index = next((i for i, o in enumerate(opt_out) if o["correct"]), -1)
        if not stem_text and not stem_imgs and not any(o["text"] for o in opt_out):
            continue

        questions.append({
            "topic": topic,
            "stem": stem_text, "stem_xml": stem_xml, "stem_images": stem_imgs,
            "options": opt_out, "correct_index": correct_index,
        })
    return questions
