"""Saqlangan XML bo'lakni web uchun HTMLga aylantiradi (matn + MathML + rasm)."""
import re
from lxml import etree
import omml2mml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

SYMBOL_MAP = omml2mml  # reuse emas; alohida kerak bo'lsa parser'dan
SUP = {c: s for c, s in zip("0123456789+-n()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ⁽⁾")}
SUB = {c: s for c, s in zip("0123456789+-()", "₀₁₂₃₄₅₆₇₈₉₊₋₍₎")}


def _ln(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else ""

def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _to_sup(s):
    return "".join(SUP.get(c, c) for c in s)
def _to_sub(s):
    return "".join(SUB.get(c, c) for c in s)


def _run_html(r, get_media):
    # rasm?
    if r.find(".//{%s}blip" % "http://schemas.openxmlformats.org/drawingml/2006/main") is not None \
       or r.find(".//{%s}drawing" % W) is not None:
        s = etree.tostring(r, encoding="unicode")
        mids = re.findall(r"DBMEDIA:(\d+)", s)
        out = ""
        for mid in mids:
            data = get_media(int(mid)) if get_media else None
            if data:
                import base64
                b64 = base64.b64encode(data).decode()
                out += '<img src="data:image/png;base64,%s" style="max-width:100%%;vertical-align:middle">' % b64
        return out
    va = None
    rpr = r.find("{%s}rPr" % W)
    if rpr is not None:
        v = rpr.find("{%s}vertAlign" % W)
        if v is not None:
            va = v.get("{%s}val" % W)
    text = ""
    for c in r:
        t = _ln(c)
        if t == "t":
            text += c.text or ""
        elif t in ("tab", "br"):
            text += " "
    if va == "superscript":
        return "<sup>%s</sup>" % _esc(text)
    if va == "subscript":
        return "<sub>%s</sub>" % _esc(text)
    return _esc(text)


def fragment_to_html(xml_list, get_media=None):
    """Saqlangan bo'laklar ro'yxatini bitta HTML stringiga aylantiradi."""
    out = []
    for s in xml_list:
        try:
            el = etree.fromstring(s)
        except Exception:
            continue
        t = _ln(el)
        if t in ("oMath", "oMathPara"):
            out.append(omml2mml.omml_to_mathml(el))
        elif t == "r":
            out.append(_run_html(el, get_media))
        else:
            # boshqa (masalan matn run yaratilgan) — ichidagi runlarni olamiz
            for rr in el.iter("{%s}r" % W):
                out.append(_run_html(rr, get_media))
    return "".join(out)
