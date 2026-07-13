"""FastAPI web-server: o'quvchi test oynasi va o'qituvchi paneli."""
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
    '<button class="btn" style="margin-top:18px" onclick="try{{Telegram.WebApp.close()}}catch(e){{}}">Yopish</button>';
  document.getElementById('result').style.display='flex';
}}
</script></body></html>"""


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
<div style="color:#475569">❌ Xato savollar: {wrong}</div></div>
<script>try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}</script></body></html>"""


# ============ O'QITUVCHI PANELI ============
@app.get("/p/{code}/{ptoken}", response_class=HTMLResponse)
def panel_page(code: str, ptoken: str):
    t = db.get_test(code)
    if not t or t["panel_token"] != ptoken:
        return HTMLResponse("<h3>Panel topilmadi.</h3>", status_code=404)
    return HTMLResponse(_panel_html(code, ptoken))

@app.get("/api/panel/{code}/{ptoken}")
def api_panel(code: str, ptoken: str):
    t = db.get_test(code)
    if not t or t["panel_token"] != ptoken:
        return JSONResponse({"error": "no"}, status_code=404)
    db.expire_due()
    return JSONResponse(db.panel_data(code))


def _panel_html(code, ptoken):
    return f"""<!DOCTYPE html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panel {code}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:16px}}
h2{{margin:0 0 4px}} .sub{{color:#94a3b8;font-size:13px;margin-bottom:16px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}}
.stat{{background:#1e293b;border-radius:12px;padding:12px 16px;flex:1;min-width:120px}}
.stat .v{{font-size:22px;font-weight:800;color:#38bdf8}} .stat .l{{font-size:12px;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}}
th,td{{padding:10px 12px;text-align:left;font-size:14px;border-bottom:1px solid #334155}}
th{{background:#334155;font-size:12px;text-transform:uppercase;color:#cbd5e1}}
.badge{{padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700}}
.b-fin{{background:#166534;color:#bbf7d0}} .b-act{{background:#854d0e;color:#fde68a}}
.upd{{color:#64748b;font-size:11px;margin-top:10px}}
</style></head><body>
<h2>📊 {code} — jonli natijalar</h2>
<div class="sub" id="sub">yuklanmoqda…</div>
<div class="stats" id="stats"></div>
<div id="tbl"></div>
<div class="upd" id="upd"></div>
<script>
const CODE="{code}",PT="{ptoken}";
function esc(s){{return (s||'').replace(/</g,'&lt;')}}
async function load(){{
  try{{
    const r=await fetch('/api/panel/'+CODE+'/'+PT); const d=await r.json();
    document.getElementById('sub').textContent=d.title+' · vaqt: '+d.time_limit+' daqiqa';
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
  }}catch(e){{}}
}}
function stat(v,l){{return '<div class="stat"><div class="v">'+v+'</div><div class="l">'+l+'</div></div>';}}
load(); setInterval(load,5000);
</script></body></html>"""
