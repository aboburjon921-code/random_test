
import time, html, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import db
import render

app = FastAPI()


def _q_html(q):
    stem = render.fragment_to_html(q["stem_xml"], db.get_media) or html.escape(q["stem"] or "")
    return stem


def _opt_html(q, orig):
    o = q["options"][orig]
    h = render.fragment_to_html(o["xml"], db.get_media) or html.escape(o["text"] or "")
    return h


# ============ O'QUVCHI TEST OYNASI ============
@app.get("/t/{token}", response_class=HTMLResponse)
def student_page(token: str):
    s = db.get_session_by_token(token)
    if not s:
        return HTMLResponse("<h3>Test topilmadi yoki muddati o'tgan.</h3>", status_code=404)
    if s["status"] == "finished":
        return HTMLResponse(_result_page(token))
    now = time.time()
    remaining = max(0, int(s["deadline"] - now))
    if remaining <= 0:
        db.submit_session(token)
        return HTMLResponse(_result_page(token))

    cards = []
    letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for i, item in enumerate(s["order"]):
        q = db.get_question(item["qid"])
        opts_html = ""
        for k, orig in enumerate(item["opt"]):
            opts_html += (
                f'<button class="opt" data-q="{i}" data-k="{k}" onclick="pick({i},{k},this)">'
                f'<span class="lbl">{letters[k]}</span>'
                f'<span class="otext">{_opt_html(q, orig)}</span></button>')
        cards.append(
            f'<div class="card" id="card{i}"><div class="qhead">{i+1}-savol</div>'
            f'<div class="stem">{_q_html(q)}</div>'
            f'<div class="opts">{opts_html}</div></div>')
    return HTMLResponse(_test_page(token, remaining, len(s["order"]), "".join(cards)))


def _test_page(token, remaining, total, cards):
    return f"""<!DOCTYPE html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Test</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
window.MathJax={{tex:{{}},options:{{}},startup:{{typeset:false}}}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/mml-chtml.js" id="MathJax-script" async></script>
<style>
:root{{--pri:#2563eb;--bg:#f1f5f9;--card:#fff;--ok:#16a34a;}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);margin:0;padding:12px 12px 90px;color:#1e293b}}
.topbar{{position:sticky;top:0;z-index:50;background:var(--card);border-radius:14px;padding:12px 16px;
  box-shadow:0 2px 10px rgba(0,0,0,.06);display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}}
.timer{{font-size:20px;font-weight:800;color:var(--pri)}}
.timer.warn{{color:#dc2626}}
.prog{{font-size:13px;color:#64748b;font-weight:600}}
.card{{background:var(--card);border-radius:14px;padding:16px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}
.qhead{{font-size:12px;font-weight:700;color:var(--pri);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}}
.stem{{font-size:17px;margin-bottom:14px;line-height:1.5}}
.opts{{display:flex;flex-direction:column;gap:8px}}
.opt{{display:flex;align-items:center;gap:12px;width:100%;text-align:left;background:#f8fafc;border:2px solid #e2e8f0;
  border-radius:10px;padding:12px 14px;font-size:16px;cursor:pointer;transition:.15s;color:#1e293b}}
.opt .lbl{{flex:0 0 30px;height:30px;border-radius:50%;background:#e2e8f0;display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:14px}}
.opt.sel{{border-color:var(--pri);background:#eff6ff}}
.opt.sel .lbl{{background:var(--pri);color:#fff}}
.otext math{{font-size:1.05em}}
.stem math{{font-size:1.1em}}
.submitbar{{position:fixed;bottom:0;left:0;right:0;padding:12px;background:linear-gradient(transparent,var(--bg) 30%)}}
.btn{{width:100%;max-width:480px;margin:0 auto;display:block;background:var(--pri);color:#fff;border:none;
  padding:16px;border-radius:12px;font-size:17px;font-weight:700;box-shadow:0 4px 14px rgba(37,99,235,.4);cursor:pointer}}
.btn:disabled{{opacity:.6}}
#result{{position:fixed;inset:0;background:rgba(15,23,42,.6);display:none;align-items:center;justify-content:center;z-index:100;padding:20px}}
.rbox{{background:#fff;border-radius:18px;padding:26px;max-width:420px;width:100%;text-align:center;max-height:85vh;overflow:auto}}
.rbox .big{{font-size:40px;margin:6px 0}}
.rbox .sc{{font-size:26px;font-weight:800;margin:8px 0}}
.wrongs{{text-align:left;margin-top:14px;font-size:14px;color:#475569}}
</style></head><body>
<div class="topbar"><div class="timer" id="timer">--:--</div><div class="prog" id="prog">0/{total}</div></div>
{cards}
<div class="submitbar"><button class="btn" id="sbtn" onclick="submitTest()">✅ Testni yakunlash</button></div>
<div id="result"><div class="rbox" id="rbox"></div></div>
<script>
const TOKEN="{token}"; const TOTAL={total};
let remaining={remaining}; const answers={{}};
try{{Telegram.WebApp.ready();Telegram.WebApp.expand();Telegram.WebApp.disableClosingConfirmation&&Telegram.WebApp.enableClosingConfirmation();}}catch(e){{}}

function pick(q,k,el){{
  answers[q]=k;
  const card=document.getElementById('card'+q);
  card.querySelectorAll('.opt').forEach(b=>b.classList.remove('sel'));
  el.classList.add('sel');
  document.getElementById('prog').textContent=Object.keys(answers).length+'/'+TOTAL;
  fetch('/api/answer',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{token:TOKEN,i:q,pos:k}})}}).catch(()=>{{}});
}}
function fmt(s){{const m=Math.floor(s/60),x=s%60;return m+':'+(x<10?'0':'')+x;}}
function tick(){{
  const t=document.getElementById('timer');
  t.textContent=fmt(remaining);
  if(remaining<=60)t.classList.add('warn');
  if(remaining<=0){{doSubmit(true);return;}}
  remaining--; setTimeout(tick,1000);
}}
tick();
let sent=false;
function submitTest(){{
  const left=TOTAL-Object.keys(answers).length;
  if(left>0){{
    const msg=left+' ta savol javobsiz. Baribir yakunlaysizmi?';
    if(Telegram.WebApp.showConfirm){{Telegram.WebApp.showConfirm(msg,ok=>{{if(ok)doSubmit(false);}});return;}}
    if(!confirm(msg))return;
  }}
  doSubmit(false);
}}
function doSubmit(auto){{
  if(sent)return; sent=true;
  document.getElementById('sbtn').disabled=true;
  fetch('/api/submit',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{token:TOKEN,answers:answers}})}})
    .then(r=>r.json()).then(showResult).catch(()=>{{sent=false;}});
}}
function showResult(res){{
  const pct=res.total?Math.round(100*res.score/res.total):0;
  let grade='2',emoji='📚';
  if(pct>=90){{grade='5';emoji='🏆';}}else if(pct>=70){{grade='4';emoji='👍';}}else if(pct>=50){{grade='3';emoji='🙂';}}
  const wrong=res.detail.filter(d=>!d.ok).map(d=>d.i+1);
  let wh='';
  if(wrong.length)wh='<div class="wrongs">❌ Xato savollar: '+wrong.join(', ')+'</div>';
  document.getElementById('rbox').innerHTML=
    '<div class="big">'+emoji+'</div><div>Test yakunlandi!</div>'+
    '<div class="sc">'+res.score+' / '+res.total+' ('+pct+'%)</div>'+
    '<div>Baho: <b>'+grade+'</b></div>'+wh+
    '<button class="btn" style="margin-top:18px;background:#16a34a" onclick="location.href=\\'/r/\\'+TOKEN">📖 Javoblarni ko\\'rish</button>'+
    '<button class="btn" style="margin-top:10px" onclick="try{{Telegram.WebApp.close()}}catch(e){{}}">Yopish</button>';
  document.getElementById('result').style.display='flex';
}}
</script></body></html>"""


@app.get("/r/{token}", response_class=HTMLResponse)
def review_page(token: str):
    s = db.get_session_by_token(token)
    if not s:
        return HTMLResponse("<h3>Topilmadi.</h3>", status_code=404)
    if s["status"] != "finished":
        return HTMLResponse("<h3>Avval testni yakunlang.</h3>", status_code=403)
    live = s["live"]
    letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    cards = []
    for i, item in enumerate(s["order"]):
        q = db.get_question(item["qid"])
        chosen = live.get(str(i))
        chosen = int(chosen) if chosen is not None else None
        correct = item["correct"]
        ok = (chosen == correct)
        opts_html = ""
        for k, orig in enumerate(item["opt"]):
            cls = ""
            tag = ""
            if k == correct:
                cls = "correct"; tag = '<span class="tag tg">✓ to\'g\'ri</span>'
            if chosen is not None and k == chosen and k != correct:
                cls = "wrong"; tag = '<span class="tag tw">✗ siz</span>'
            elif chosen is not None and k == chosen and k == correct:
                tag = '<span class="tag tg">✓ siz</span>'
            opts_html += (f'<div class="opt {cls}"><span class="lbl">{letters[k]}</span>'
                          f'<span class="otext">{_opt_html(q, orig)}</span>{tag}</div>')
        mark = "✅" if ok else ("❌" if chosen is not None else "⬜")
        cards.append(f'<div class="card"><div class="qhead">{mark} {i+1}-savol</div>'
                     f'<div class="stem">{_q_html(q)}</div><div class="opts">{opts_html}</div></div>')
    score = s["score"]; total = s["total"]; pct = round(100*score/total) if total else 0
    return HTMLResponse(f"""<!DOCTYPE html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Javoblar</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>window.MathJax={{startup:{{typeset:true}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/mml-chtml.js" async></script>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f1f5f9;margin:0;padding:12px 12px 30px;color:#1e293b}}
.top{{position:sticky;top:0;background:#fff;border-radius:14px;padding:14px 16px;margin-bottom:12px;
  box-shadow:0 2px 10px rgba(0,0,0,.06);text-align:center}}
.top .sc{{font-size:22px;font-weight:800;color:#2563eb}}
.card{{background:#fff;border-radius:14px;padding:16px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}
.qhead{{font-size:13px;font-weight:700;color:#475569;margin-bottom:8px}}
.stem{{font-size:17px;margin-bottom:12px;line-height:1.5}}
.opts{{display:flex;flex-direction:column;gap:7px}}
.opt{{display:flex;align-items:center;gap:10px;background:#f8fafc;border:2px solid #e2e8f0;
  border-radius:10px;padding:10px 12px;font-size:16px;position:relative}}
.opt .lbl{{flex:0 0 28px;height:28px;border-radius:50%;background:#e2e8f0;display:flex;
  align-items:center;justify-content:center;font-weight:700;font-size:13px}}
.opt.correct{{border-color:#16a34a;background:#f0fdf4}}
.opt.correct .lbl{{background:#16a34a;color:#fff}}
.opt.wrong{{border-color:#dc2626;background:#fef2f2}}
.opt.wrong .lbl{{background:#dc2626;color:#fff}}
.tag{{margin-left:auto;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;white-space:nowrap}}
.tag.tg{{background:#16a34a;color:#fff}} .tag.tw{{background:#dc2626;color:#fff}}
.stem math{{font-size:1.1em}} .otext math{{font-size:1.05em}}
.btn{{display:block;width:100%;max-width:480px;margin:10px auto;background:#2563eb;color:#fff;border:none;
  padding:14px;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer}}
</style></head><body>
<div class="top"><div class="sc">{score} / {total} ({pct}%)</div>
<div style="color:#64748b;font-size:13px">🟢 to'g'ri javob · 🔴 sizning xato tanlovingiz</div></div>
{''.join(cards)}
<button class="btn" onclick="try{{Telegram.WebApp.close()}}catch(e){{location.href='about:blank'}}">Yopish</button>
<script>try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}</script>
</body></html>""")


# ============ API ============
@app.post("/api/answer")
async def api_answer(req: Request):
    d = await req.json()
    db.save_live(d.get("token", ""), int(d.get("i")), int(d.get("pos")))
    return JSONResponse({"ok": True})

@app.post("/api/submit")
async def api_submit(req: Request):
    d = await req.json()
    res = db.submit_session(d.get("token", ""), d.get("answers"))
    if not res:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(res)


def _result_page(token):
    s = db.get_session_by_token(token)
    res = db.finalized_result(s)
    pct = round(100 * res["score"] / res["total"]) if res["total"] else 0
    wrong = ", ".join(str(d["i"] + 1) for d in res["detail"] if not d["ok"]) or "yo'q"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>body{{font-family:sans-serif;background:#f1f5f9;text-align:center;padding:40px 20px}}
.b{{background:#fff;border-radius:18px;padding:30px;max-width:420px;margin:auto;box-shadow:0 4px 20px rgba(0,0,0,.1)}}
.sc{{font-size:30px;font-weight:800;color:#2563eb;margin:10px 0}}</style></head>
<body><div class="b"><h2>✅ Test allaqachon yakunlangan</h2>
<div class="sc">{res['score']} / {res['total']} ({pct}%)</div>
<div style="color:#475569">❌ Xato savollar: {wrong}</div>
<a href="/r/{token}" style="display:inline-block;margin-top:16px;background:#16a34a;color:#fff;
  text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:700">📖 Javoblarni ko'rish</a></div>
<script>try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}</script></body></html>"""


# ============ O'QITUVCHI PANELI ============
@app.get("/p/{code}/{ptoken}", response_class=HTMLResponse)
def panel_page(code: str, ptoken: str):
    import os as _os
    t = db.get_test(code)
    if not t or t["panel_token"] != ptoken:
        return HTMLResponse("<h3>Panel topilmadi.</h3>", status_code=404)
    username = _os.environ.get("BOT_USERNAME", "")
    student_link = f"https://t.me/{username}?start={code}" if username else ""
    return HTMLResponse(_panel_html(code, ptoken, student_link))

@app.get("/api/panel/{code}/{ptoken}")
def api_panel(code: str, ptoken: str):
    t = db.get_test(code)
    if not t or t["panel_token"] != ptoken:
        return JSONResponse({"error": "no"}, status_code=404)
    db.expire_due()
    return JSONResponse(db.panel_data(code))


def _panel_html(code, ptoken, student_link=""):
    qr_block = ""
    if student_link:
        qr_block = f"""
<div class="qrbox">
  <div id="qr"></div>
  <div class="qrinfo">
    <div class="qrcode">🔑 Kod: <b>{code}</b></div>
    <div class="qrhint">O'quvchilar QR-kodni telefon kamerasi bilan skanerlasin<br>yoki havoladan kirsin:</div>
    <a class="qrlink" href="{student_link}" target="_blank">{student_link}</a>
    <button class="qrbtn" onclick="toggleBig()">🔍 Kattalashtirish (proyektor uchun)</button>
  </div>
</div>
<div id="qrbig" onclick="toggleBig()"><div id="qrbigInner"><div id="qrbigCode"></div></div></div>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
const LINK="{student_link}";
function makeQR(el,size){{ el.innerHTML=""; new QRCode(el,{{text:LINK,width:size,height:size,correctLevel:QRCode.CorrectLevel.M}}); }}
window.addEventListener('load',()=>{{ try{{makeQR(document.getElementById('qr'),150);}}catch(e){{}} }});
function toggleBig(){{
  const b=document.getElementById('qrbig');
  if(b.style.display==='flex'){{b.style.display='none';return;}}
  const inner=document.getElementById('qrbigCode');
  makeQR(inner,Math.min(window.innerWidth,window.innerHeight)*0.75);
  b.style.display='flex';
}}
</script>"""
    return f"""<!DOCTYPE html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panel {code}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:16px}}
h2{{margin:0 0 4px}} .sub{{color:#94a3b8;font-size:13px;margin-bottom:16px}}
.qrbox{{display:flex;gap:16px;align-items:center;background:#1e293b;border-radius:14px;padding:16px;margin-bottom:16px;flex-wrap:wrap}}
#qr{{background:#fff;padding:8px;border-radius:8px;flex:0 0 auto}}
#qr img{{display:block}}
.qrinfo{{flex:1;min-width:200px}}
.qrcode{{font-size:20px;margin-bottom:6px}} .qrcode b{{color:#38bdf8;letter-spacing:1px}}
.qrhint{{font-size:12px;color:#94a3b8;margin-bottom:6px}}
.qrlink{{color:#38bdf8;font-size:13px;word-break:break-all;text-decoration:none}}
.qrbtn{{display:block;margin-top:10px;background:#2563eb;color:#fff;border:none;padding:9px 14px;
  border-radius:8px;font-weight:700;font-size:13px;cursor:pointer}}
#qrbig{{display:none;position:fixed;inset:0;background:rgba(255,255,255,.98);z-index:200;
  align-items:center;justify-content:center;cursor:pointer;flex-direction:column}}
#qrbigInner{{text-align:center}} #qrbigCode{{background:#fff}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}}
.stat{{background:#1e293b;border-radius:12px;padding:12px 16px;flex:1;min-width:120px}}
.stat .v{{font-size:22px;font-weight:800;color:#38bdf8}} .stat .l{{font-size:12px;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}}
th,td{{padding:10px 12px;text-align:left;font-size:14px;border-bottom:1px solid #334155}}
th{{background:#334155;font-size:12px;text-transform:uppercase;color:#cbd5e1}}
.badge{{padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700}}
.b-fin{{background:#166534;color:#bbf7d0}} .b-act{{background:#854d0e;color:#fde68a}}
.upd{{color:#64748b;font-size:11px;margin-top:10px}}
.racebtn{{display:block;width:100%;background:linear-gradient(90deg,#7c3aed,#2563eb);color:#fff;border:none;
  padding:14px;border-radius:12px;font-size:16px;font-weight:800;cursor:pointer;margin-bottom:16px;
  box-shadow:0 4px 14px rgba(124,58,237,.4)}}
/* ===== Poyga (Mentimeter uslubi) ===== */
#race{{display:none;position:fixed;inset:0;z-index:300;background:radial-gradient(circle at 50% 0%,#1e2a52,#0b1220);
  color:#fff;flex-direction:column;padding:18px 26px;overflow:hidden}}
#race .rhead{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
#race .rhead .t{{font-size:30px;font-weight:900;letter-spacing:.5px}}
#race .rhead .btns{{display:flex;gap:8px}}
#race .rbtn{{background:rgba(255,255,255,.12);color:#fff;border:none;border-radius:10px;padding:9px 15px;
  font-weight:700;cursor:pointer;font-size:15px}}
#race .rbtn:hover{{background:rgba(255,255,255,.22)}}
#race .fin{{font-size:17px;color:#a5b4fc;font-weight:700;margin-bottom:14px}}
#lanes{{flex:1;position:relative;margin-top:4px}}
.row{{position:absolute;left:0;right:0;height:56px;display:flex;align-items:center;gap:14px;
  transition:transform .8s cubic-bezier(.4,0,.2,1);will-change:transform}}
.rank{{flex:0 0 40px;text-align:center;font-size:22px;font-weight:900;color:#64748b}}
.bar-wrap{{flex:1;position:relative;height:42px}}
.bar{{position:absolute;left:0;top:0;height:100%;border-radius:10px;min-width:42px;
  transition:width .8s cubic-bezier(.4,0,.2,1);display:flex;align-items:center;justify-content:flex-end}}
.bar .av{{width:46px;height:46px;border-radius:50%;background:#fff;display:flex;align-items:center;
  justify-content:center;font-size:26px;box-shadow:0 3px 8px rgba(0,0,0,.35);margin-right:-6px;
  position:absolute;right:-6px;top:50%;transform:translateY(-50%);border:3px solid rgba(255,255,255,.5)}}
.pts{{flex:0 0 auto;font-size:20px;font-weight:900;min-width:56px;color:#fde047}}
/* katta rejim */
#race.big .rhead .t{{font-size:44px}} #race.big .row{{height:74px}} #race.big .bar-wrap{{height:56px}}
#race.big .bar .av{{width:60px;height:60px;font-size:34px}} #race.big .pts{{font-size:28px}}
#race.big .rank{{font-size:30px}}
/* Podium (Kahoot uslubi) */
#podium{{display:none;position:fixed;inset:0;z-index:310;background:radial-gradient(circle at 50% 20%,#3b2a72,#0b1220);
  color:#fff;flex-direction:column;align-items:center;padding:26px 18px;overflow:auto}}
#podium h1{{font-size:38px;margin:6px 0 26px;font-weight:900;text-shadow:0 3px 12px rgba(0,0,0,.4)}}
.pods{{display:flex;align-items:flex-end;gap:20px;justify-content:center;flex-wrap:nowrap}}
.pod{{display:flex;flex-direction:column;align-items:center}}
.pod .pav{{width:76px;height:76px;border-radius:50%;background:#fff;display:flex;align-items:center;
  justify-content:center;font-size:44px;margin-bottom:8px;box-shadow:0 4px 14px rgba(0,0,0,.4)}}
.pod .pname{{font-size:19px;font-weight:800;margin-bottom:8px}}
.pod .stand{{width:120px;border-radius:14px 14px 0 0;display:flex;flex-direction:column;
  align-items:center;justify-content:flex-start;padding-top:12px;color:#0b1220;font-weight:900}}
.pod .medal{{font-size:38px}} .pod .ps{{font-size:20px;margin-top:2px}}
.stand.s1{{height:200px;background:linear-gradient(#fde047,#f59e0b)}}
.stand.s2{{height:150px;background:linear-gradient(#e5e7eb,#94a3b8)}}
.stand.s3{{height:115px;background:linear-gradient(#fdba74,#d97706)}}
.runners{{margin-top:26px;width:100%;max-width:520px}}
.runners .rt{{text-align:center;color:#a5b4fc;font-weight:800;margin-bottom:10px;font-size:15px}}
.runrow{{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.08);border-radius:12px;
  padding:9px 14px;margin-bottom:7px}}
.runrow .rr{{font-weight:900;color:#94a3b8;min-width:26px}}
.runrow .ra{{font-size:22px}} .runrow .rn{{flex:1;font-weight:700}} .runrow .rp{{font-weight:900;color:#fde047}}
#podium .pclose{{margin-top:24px;background:rgba(255,255,255,.15);color:#fff;border:none;border-radius:12px;
  padding:13px 26px;font-weight:800;cursor:pointer;font-size:15px}}
</style></head><body>
<h2>📊 {code} — jonli natijalar</h2>
<div class="sub" id="sub">yuklanmoqda…</div>
{qr_block}
<div class="stats" id="stats"></div>
<button class="racebtn" onclick="openRace()">🏁 Poyga rejimi (proyektor uchun)</button>
<div id="tbl"></div>
<div class="upd" id="upd"></div>

<div id="race">
  <div class="rhead">
    <div class="t">🏁 Poyga</div>
    <div class="btns">
      <button class="rbtn" onclick="toggleBig2()">⛶ Katta rejim</button>
      <button class="rbtn" onclick="revealPodium()">🏆 Natija</button>
      <button class="rbtn" onclick="closeRace()">✕</button>
    </div>
  </div>
  <div class="fin" id="rfin">0/0 yakunladi</div>
  <div id="lanes"></div>
</div>
<div id="podium">
  <h1>🎉 G'oliblar!</h1>
  <div class="pods" id="pods"></div>
  <div class="runners" id="runners"></div>
  <button class="pclose" onclick="document.getElementById('podium').style.display='none'">✕ Yopish</button>
</div>
<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js"></script>
<script>
const CODE="{code}",PT="{ptoken}";
function esc(s){{return (s||'').replace(/</g,'&lt;')}}
async function load(){{
  try{{
    const r=await fetch('/api/panel/'+CODE+'/'+PT); const d=await r.json();
    document.getElementById('sub').textContent=d.title+' · vaqt: '+d.time_limit+' daqiqa'+(d.closed?' · 🔒 yopiq':'');
    const hardest=d.hardest?('#'+d.hardest.q+' ('+d.hardest.miss_pct+'% xato)'):'—';
    document.getElementById('stats').innerHTML=
      stat(d.finished+'/'+d.total_students,'Yakunladi')+
      stat(d.avg,"O'rtacha ball")+
      stat(hardest,'Eng qiyin savol');
    let rows=d.students.map(s=>{{
      const st=s.status==='finished'
        ?'<span class="badge b-fin">yakunladi</span>'
        :'<span class="badge b-act">yechyapti ('+s.answered+')</span>';
      const sc=s.status==='finished'?(s.score+'/'+s.total):'—';
      const tm=s.spent!=null?(Math.floor(s.spent/60)+'m '+(s.spent%60)+'s'):'—';
      return '<tr><td>'+esc(s.name)+'</td><td>'+st+'</td><td>'+sc+'</td><td>'+tm+'</td></tr>';
    }}).join('');
    if(!rows)rows='<tr><td colspan=4 style="color:#64748b">Hali hech kim kirmadi</td></tr>';
    document.getElementById('tbl').innerHTML=
      '<table><tr><th>O\\'quvchi</th><th>Holat</th><th>Ball</th><th>Vaqt</th></tr>'+rows+'</table>';
    document.getElementById('upd').textContent='yangilandi: '+new Date().toLocaleTimeString();
    window.__last=d; if(window.raceOn) renderRace(d);
  }}catch(e){{}}
}}
function stat(v,l){{return '<div class="stat"><div class="v">'+v+'</div><div class="l">'+l+'</div></div>';}}

// ===== Poyga (Mentimeter/Kahoot uslubi) =====
window.raceOn=false; window.podiumShown=false;
const BAR_COLORS=['#ec4899','#3b82f6','#22c55e','#f59e0b','#8b5cf6','#ef4444','#14b8a6','#eab308',
  '#f97316','#06b6d4','#a855f7','#84cc16','#e11d48','#0ea5e9','#10b981','#d946ef'];
let sid2color={{}};
function assignColor(id,idx){{ if(!(id in sid2color)) sid2color[id]=BAR_COLORS[Object.keys(sid2color).length%BAR_COLORS.length]; return sid2color[id]; }}

function openRace(){{
  window.raceOn=true; window.podiumShown=false;
  document.getElementById('lanes').innerHTML='';
  document.getElementById('race').style.display='flex';
  if(window.__last) renderRace(window.__last);
  load();
}}
function closeRace(){{ window.raceOn=false; document.getElementById('race').style.display='none'; }}
function toggleBig2(){{
  const r=document.getElementById('race'); r.classList.toggle('big');
  try{{ if(!document.fullscreenElement) r.requestFullscreen(); else document.exitFullscreen(); }}catch(e){{}}
}}

function renderRace(d){{
  const studs=(d.students||[]).slice();
  const maxC=Math.max(1, ...studs.map(s=>s.correct||0), Math.ceil((d.q_total||1)*0.3));
  document.getElementById('rfin').textContent='🏁 '+d.finished+'/'+d.total_students+' yakunladi';
  // tartiblаsh: ball bo'yicha (jonli)
  studs.forEach((s,i)=>{{ s._id=s.name+'#'+i; }});
  const sorted=[...studs].sort((a,b)=> (b.correct||0)-(a.correct||0) || (a.answered-b.answered));
  const lanes=document.getElementById('lanes');
  const rowH = document.getElementById('race').classList.contains('big')?74:56;

  sorted.forEach((s,rank)=>{{
    const id=cssId(s._id);
    let row=document.getElementById('row_'+id);
    if(!row){{
      row=document.createElement('div'); row.className='row'; row.id='row_'+id;
      const col=assignColor(s._id);
      row.innerHTML='<div class="rank" id="rk_'+id+'"></div>'+
        '<div class="bar-wrap"><div class="bar" id="bar_'+id+'" style="background:'+col+'">'+
        '<div class="av">'+(s.avatar||'🐵')+'</div></div></div>'+
        '<div class="pts" id="pt_'+id+'"></div>';
      lanes.appendChild(row);
    }}
    row.style.transform='translateY('+(rank*rowH)+'px)';
    document.getElementById('rk_'+id).textContent=(rank+1);
    const frac=Math.min(1,(s.correct||0)/maxC);
    document.getElementById('bar_'+id).style.width=(8+frac*92)+'%';
    document.getElementById('pt_'+id).textContent=(s.correct||0);
  }});
  lanes.style.height=(sorted.length*rowH+10)+'px';

  if(d.total_students>0 && d.finished===d.total_students && !window.podiumShown){{
    setTimeout(()=>revealPodium(),1000);
  }}
}}
function cssId(name){{ return name.replace(/[^a-zA-Z0-9]/g,'_'); }}

function revealPodium(){{
  const d=window.__last; if(!d)return;
  window.podiumShown=true;
  const studs=[...(d.students||[])].sort((a,b)=> b.score-a.score || ((a.spent||1e9)-(b.spent||1e9)));
  const top=studs.slice(0,3), rest=studs.slice(3);
  const medals=['🥇','🥈','🥉']; const cls=['s1','s2','s3']; const orderIdx=[1,0,2];
  const pods=document.getElementById('pods'); pods.innerHTML='';
  orderIdx.forEach(i=>{{
    if(!top[i])return; const s=top[i];
    pods.innerHTML+='<div class="pod"><div class="pav">'+(s.avatar||'🐵')+'</div>'+
      '<div class="pname">'+esc(s.name)+'</div>'+
      '<div class="stand '+cls[i]+'"><div class="medal">'+medals[i]+'</div>'+
      '<div class="ps">'+s.score+'/'+s.total+'</div></div></div>';
  }});
  const runners=document.getElementById('runners');
  if(rest.length){{
    runners.innerHTML='<div class="rt">Qolgan ishtirokchilar</div>'+rest.map((s,i)=>
      '<div class="runrow"><span class="rr">'+(i+4)+'</span><span class="ra">'+(s.avatar||'🐵')+
      '</span><span class="rn">'+esc(s.name)+'</span><span class="rp">'+s.score+'/'+s.total+'</span></div>'
    ).join('');
  }} else runners.innerHTML='';
  document.getElementById('podium').style.display='flex';
  fireConfetti();
}}
function fireConfetti(){{
  try{{
    const end=Date.now()+3000;
    (function frame(){{
      confetti({{particleCount:6,angle:60,spread:75,origin:{{x:0}},startVelocity:55}});
      confetti({{particleCount:6,angle:120,spread:75,origin:{{x:1}},startVelocity:55}});
      if(Date.now()<end)requestAnimationFrame(frame);
    }})();
  }}catch(e){{}}
}}

load(); setInterval(load,3000);
</script></body></html>"""
