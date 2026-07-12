"""Testni Word (.docx) qilib chiqarish. Chiqish doim Times New Roman."""
import io
import random
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

LETTERS = [chr(65 + i) for i in range(26)]


def _set_default_font(doc):
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), "Times New Roman")


def _add_images(doc, media_list):
    for data in media_list:
        try:
            doc.add_paragraph().add_run().add_picture(io.BytesIO(data), width=Inches(2.2))
        except Exception:
            pass


def build(questions, title, shuffle_options=True):
    """
    questions: [{stem, stem_media:[bytes], options:[{text,media:[bytes]}], correct_index}]
    return: (test_bytes, key_bytes)
    """
    test = Document(); _set_default_font(test)
    key = Document(); _set_default_font(key)

    tp = test.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = tp.add_run(title); r.bold = True; r.font.size = Pt(15)
    test.add_paragraph()

    kp = key.add_paragraph(); kp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = kp.add_run(title + " — JAVOBLAR"); r.bold = True; r.font.size = Pt(15)
    key.add_paragraph()

    key_line = []
    for i, q in enumerate(questions):
        opts = list(enumerate(q["options"]))  # (orig_index, opt)
        if shuffle_options:
            random.shuffle(opts)
        # stem
        p = test.add_paragraph()
        rr = p.add_run(f"#{i+1}. "); rr.bold = True
        p.add_run(q["stem"])
        _add_images(test, q.get("stem_media", []))
        # options
        correct_letter = "?"
        for j, (orig_idx, opt) in enumerate(opts):
            op = test.add_paragraph()
            lr = op.add_run(f"{LETTERS[j]}) "); lr.bold = True
            op.add_run(opt["text"])
            _add_images(test, opt.get("media", []))
            if orig_idx == q["correct_index"]:
                correct_letter = LETTERS[j]
        test.add_paragraph()
        key_line.append(f"{i+1}-{correct_letter}")
        if len(key_line) == 10 or i == len(questions) - 1:
            key.add_paragraph("     ".join(key_line))
            key_line = []

    tb, kb = io.BytesIO(), io.BytesIO()
    test.save(tb); key.save(kb)
    return tb.getvalue(), kb.getvalue()
