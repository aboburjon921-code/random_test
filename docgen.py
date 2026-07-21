"""
Chop etishga tayyor test yaratish (1-faza).
Savollar bazada asl Word XML ko'rinishida saqlangani uchun formula/rasm/bezaklar
AYNAN tiklanadi. Chiqish: toza student test (panjarasiz, + belgisiz).

  build_test_docx(questions, title, opts) -> bytes (.docx)
  docx_to_pdf(docx_bytes) -> bytes | None   (LibreOffice bo'lsa)

`questions` — db.get_question() qaytaradigan dict ro'yxati:
  {stem, stem_xml:[xml...], options:[{xml:[...], text, correct}], correct_index}
Rasm tokenlari: xml ichida DBMEDIA:<media_id>.
"""
import io
import re
import os
import zipfile
import tempfile
import subprocess
import random

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DBMEDIA_RE = re.compile(r"DBMEDIA:(\d+)")

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="jpeg" ContentType="image/jpeg"/>
<Default Extension="jpg" ContentType="image/jpeg"/>
<Default Extension="gif" ContentType="image/gif"/>
<Default Extension="emf" ContentType="image/x-emf"/>
<Default Extension="wmf" ContentType="image/x-wmf"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"'
)

_SECTPR = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" '
           'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>')

LETTERS = ["A", "B", "C", "D", "E", "F"]


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _img_ext(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"\xd7\xcd\xc6\x9a":
        return "wmf"
    if data[:4] == b"\x01\x00\x00\x00":
        return "emf"
    return "png"


class _MediaReg:
    """DBMEDIA:<id> -> rId ; rasmlarni to'playdi."""
    def __init__(self, get_media):
        self.get_media = get_media
        self.by_dbid = {}          # dbid -> (rid, filename)
        self.files = []            # (filename, bytes)
        self._n = 0

    def rid_for(self, dbid):
        if dbid in self.by_dbid:
            return self.by_dbid[dbid][0]
        data = self.get_media(dbid) if self.get_media else None
        if not data:
            return None
        self._n += 1
        ext = _img_ext(data)
        fn = "image%d.%s" % (self._n, ext)
        rid = "rIdImg%d" % self._n
        self.by_dbid[dbid] = (rid, fn)
        self.files.append((fn, data))
        return rid

    def rels_xml(self):
        rows = "".join(
            '<Relationship Id="%s" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="media/%s"/>' % (rid, fn)
            for rid, fn in self.by_dbid.values()
        )
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + rows + "</Relationships>")


def _fix_media(xml_str, reg):
    """DBMEDIA:<id> tokenlarini rId ga almashtiradi (rasm ro'yxatga olinadi)."""
    def repl(m):
        rid = reg.rid_for(int(m.group(1)))
        return rid if rid else "rIdMissing"
    return DBMEDIA_RE.sub(repl, xml_str)


def _run(text, bold=False, size=None):
    rpr = ""
    if bold or size:
        rpr = "<w:rPr>" + ("<w:b/>" if bold else "")
        if size:
            rpr += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size)
        rpr += "</w:rPr>"
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, _esc(text))


def _para(inner, bold=False, size=None, space_after=120):
    ppr = '<w:pPr><w:spacing w:after="%d" w:line="276" w:lineRule="auto"/>' % space_after
    if size or bold:
        ppr += "<w:rPr>" + ("<w:b/>" if bold else "")
        if size:
            ppr += '<w:sz w:val="%d"/>' % size
        ppr += "</w:rPr>"
    ppr += "</w:pPr>"
    return "<w:p>%s%s</w:p>" % (ppr, inner)


def _frags_inline(xml_list, reg):
    """Saqlangan bo'laklarni bitta paragraf ichi (runlar/oMath) qatoriga aylantiradi."""
    return "".join(_fix_media(s, reg) for s in (xml_list or []))


def build_test_docx(questions, title="Test", shuffle_opts=True, get_media=None, seed=None):
    """Toza student testini .docx baytlari sifatida qaytaradi. Javob kaliti ham qaytadi.

    return: (docx_bytes, answer_key)  — answer_key: [correct_letter, ...] (savollar tartibida)
    """
    rng = random.Random(seed)
    reg = _MediaReg(get_media)
    total = len(questions)
    body = []

    # sarlavha
    body.append(_para(_run(title, bold=True, size=32), space_after=40))
    body.append(_para(_run("Jami: %d ta savol" % total, bold=True, size=24), space_after=200))

    answer_key = []
    for i, q in enumerate(questions, 1):
        # savol matni: "N. " + stem bo'laklari
        stem = _run("%d. " % i, bold=True) + _frags_inline(q.get("stem_xml", []), reg)
        body.append(_para(stem, space_after=60))

        # variantlar (kerak bo'lsa aralashtiriladi)
        opts = list(enumerate(q.get("options", [])))
        if shuffle_opts:
            rng.shuffle(opts)
        correct_letter = "?"
        for pos, (orig_idx, o) in enumerate(opts):
            letter = LETTERS[pos] if pos < len(LETTERS) else "?"
            if orig_idx == q.get("correct_index"):
                correct_letter = letter
            inner = _run("%s) " % letter, bold=True) + _frags_inline(o.get("xml", []), reg)
            body.append(_para(inner, space_after=40))
        answer_key.append(correct_letter)
        body.append(_para("", space_after=120))  # savollar orasida bo'shliq

    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document %s><w:body>%s%s</w:body></w:document>'
                % (_DOC_NS, "".join(body), _SECTPR))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", reg.rels_xml())
        for fn, data in reg.files:
            z.writestr("word/media/" + fn, data)
    return buf.getvalue(), answer_key


def merge_pdfs(pdf_list, pad_even=False):
    """Bir nechta PDF'ni bitta faylga birlashtiradi.
    pad_even=True bo'lsa, har bir PDF juft betga to'ldiriladi (kerak bo'lsa bo'sh bet)."""
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for pdf in pdf_list:
        if not pdf:
            continue
        r = PdfReader(io.BytesIO(pdf))
        for p in r.pages:
            w.add_page(p)
        if pad_even and (len(r.pages) % 2 == 1):
            last = r.pages[-1]
            w.add_blank_page(width=float(last.mediabox.width),
                             height=float(last.mediabox.height))
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def docx_to_pdf(docx_bytes):
    """LibreOffice bilan .docx -> .pdf. Bo'lmasa None qaytaradi."""
    soffice = None
    for cand in ("soffice", "libreoffice"):
        from shutil import which
        if which(cand):
            soffice = cand
            break
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "test.docx")
        with open(src, "wb") as f:
            f.write(docx_bytes)
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                            "--outdir", d, src],
                           check=True, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            return None
        pdf = os.path.join(d, "test.pdf")
        if os.path.exists(pdf):
            with open(pdf, "rb") as f:
                return f.read()
    return None
