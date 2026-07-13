"""
OMML (Word formula) -> MathML.
Maktab matematikasi uchun: kasr, daraja, indeks, ildiz, qavs, funksiya,
yig'indi/integral, grek harflari. MathJax MathMLni to'g'ridan-to'g'ri chizadi.
"""
from lxml import etree

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _ln(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else ""

def _get(node, name):
    if node is None:
        return None
    for c in node:
        if _ln(c) == name:
            return c
    return None

def _val(node, name):
    """m:XXX/@m:val yoki m:val ni oladi (chr, begChr, ...)."""
    if node is None:
        return None
    child = _get(node, name)
    if child is None:
        return None
    return child.get("{%s}val" % M) or child.get("val")


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


FUNCS = ["arcsin", "arccos", "arctan", "arcctg", "arccot", "sinh", "cosh",
         "tanh", "coth", "sin", "cos", "tan", "tg", "ctg", "cot", "sec",
         "csc", "log", "lg", "ln", "lim", "exp", "max", "min", "gcd", "lcm",
         "mod", "det", "deg"]

def _text_to_mml(text):
    """Oddiy matnni <mn>/<mi>/<mo> tokenlariga ajratadi. Funksiya nomlari tik."""
    out = []
    i, n = 0, len(text)
    OPS = set("+-=<>*/±×÷·∙⋅≤≥≠≈≡∈∉⊂⊃∪∩→←↔⇒⇔∀∃∑∏∫√,;:!|%")
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit():
            j = i
            while j < n and (text[j].isdigit() or (text[j] in ".," and j + 1 < n and text[j+1].isdigit())):
                j += 1
            out.append("<mn>%s</mn>" % _esc(text[i:j]))
            i = j
        elif ch in OPS or ch in "()[]{}":
            out.append("<mo>%s</mo>" % _esc(ch))
            i += 1
        elif ch.isalpha():
            # funksiya nomi bilan boshlanadimi?
            low = text[i:].lower()
            fn = next((f for f in FUNCS if low.startswith(f)), None)
            if fn:
                out.append("<mi mathvariant='normal'>%s</mi>" % text[i:i+len(fn)])
                i += len(fn)
            else:
                out.append("<mi>%s</mi>" % _esc(ch))
                i += 1
        else:
            out.append("<mo>%s</mo>" % _esc(ch))
            i += 1
    return "".join(out)


def _row(node):
    """konteyner ichini MathMLga (mrowsiz, ketma-ket)."""
    if node is None:
        return ""
    return "".join(_conv(c) for c in node)

def _mrow(node):
    inner = _row(node)
    return "<mrow>%s</mrow>" % inner


def _conv(node):
    t = _ln(node)
    if t == "t":
        return _text_to_mml(node.text or "")
    if t == "r":
        return "".join(_conv(c) for c in node)
    if t in ("rPr", "ctrlPr", "fPr", "radPr", "naryPr", "dPr", "sSupPr",
             "sSubPr", "sSubSupPr", "funcPr", "limLowPr", "limUppPr",
             "mPr", "accPr", "barPr", "groupChrPr", "boxPr", "argPr"):
        return ""
    if t == "sSup":
        e = _get(node, "e"); sup = _get(node, "sup")
        return "<msup>%s%s</msup>" % (_mrow(e), _mrow(sup))
    if t == "sSub":
        e = _get(node, "e"); sub = _get(node, "sub")
        return "<msub>%s%s</msub>" % (_mrow(e), _mrow(sub))
    if t == "sSubSup":
        e = _get(node, "e"); sub = _get(node, "sub"); sup = _get(node, "sup")
        return "<msubsup>%s%s%s</msubsup>" % (_mrow(e), _mrow(sub), _mrow(sup))
    if t == "f":
        num = _get(node, "num"); den = _get(node, "den")
        return "<mfrac>%s%s</mfrac>" % (_mrow(num), _mrow(den))
    if t == "rad":
        e = _get(node, "e"); deg = _get(node, "deg")
        if deg is not None and len(deg):
            return "<mroot>%s%s</mroot>" % (_mrow(e), _mrow(deg))
        return "<msqrt>%s</msqrt>" % _row(e)
    if t == "d":
        beg = _val(_get(node, "dPr"), "begChr")
        end = _val(_get(node, "dPr"), "endChr")
        beg = "(" if beg is None else beg
        end = ")" if end is None else end
        es = [c for c in node if _ln(c) == "e"]
        inner = "<mo>,</mo>".join(_row(e) for e in es)
        b = "<mo>%s</mo>" % _esc(beg) if beg else ""
        en = "<mo>%s</mo>" % _esc(end) if end else ""
        return "<mrow>%s%s%s</mrow>" % (b, inner, en)
    if t == "func":
        fn = _get(node, "fName"); e = _get(node, "e")
        return "<mrow>%s<mo>&#x2061;</mo>%s</mrow>" % (_row(fn), _mrow(e))
    if t == "fName":
        return _row(node)
    if t == "nary":
        pr = _get(node, "naryPr")
        chr_ = _val(pr, "chr") or "∫"
        sub = _get(node, "sub"); sup = _get(node, "sup"); e = _get(node, "e")
        op = "<mo>%s</mo>" % _esc(chr_)
        has_sub = sub is not None and len(sub)
        has_sup = sup is not None and len(sup)
        if has_sub and has_sup:
            base = "<munderover>%s%s%s</munderover>" % (op, _mrow(sub), _mrow(sup))
        elif has_sub:
            base = "<munder>%s%s</munder>" % (op, _mrow(sub))
        elif has_sup:
            base = "<mover>%s%s</mover>" % (op, _mrow(sup))
        else:
            base = op
        return "<mrow>%s%s</mrow>" % (base, _row(e))
    if t in ("limLow", "limUpp"):
        e = _get(node, "e"); lim = _get(node, "lim")
        tag = "munder" if t == "limLow" else "mover"
        return "<%s>%s%s</%s>" % (tag, _mrow(e), _mrow(lim), tag)
    if t == "acc":
        e = _get(node, "e")
        chr_ = _val(_get(node, "accPr"), "chr") or "^"
        return "<mover>%s<mo>%s</mo></mover>" % (_mrow(e), _esc(chr_))
    if t == "bar":
        e = _get(node, "e")
        return "<menclose notation='top'>%s</menclose>" % _row(e)
    if t == "groupChr":
        e = _get(node, "e")
        return _mrow(e)
    if t == "box":
        e = _get(node, "e")
        return _row(e)
    if t == "m":  # matritsa
        rows = []
        for mr in node:
            if _ln(mr) != "mr":
                continue
            cells = ["<mtd>%s</mtd>" % _row(e) for e in mr if _ln(e) == "e"]
            rows.append("<mtr>%s</mtr>" % "".join(cells))
        return "<mtable>%s</mtable>" % "".join(rows)
    if t in ("e", "num", "den", "sup", "sub", "deg", "lim", "oMathPara"):
        return _row(node)
    # noma'lum -> ichiga kiramiz
    return _row(node)


def omml_to_mathml(node, display=False):
    """oMath elementini <math>...</math> stringiga aylantiradi."""
    inner = _row(node)
    d = "block" if display else "inline"
    return ('<math xmlns="http://www.w3.org/1998/Math/MathML" display="%s">%s</math>'
            % (d, inner))
