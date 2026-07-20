import time, html, json, base64
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import db
import render

app = FastAPI()


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _q_html(q):
    return render.fragment_to_html(q["stem_xml"], db.get_media) or html.escape(q["stem"] or "")

def _opt_html(q, orig):
    o = q["options"][orig]
    return render.fragment_to_html(o["xml"], db.get_media) or html.escape(o["text"] or "")


# ─────────────────────────────────────────────
#  SHARED CSS / FONTS / BASE STYLE
# ─────────────────────────────────────────────
_BASE_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
  --bg1: #0a0a1a;
  --bg2: #0f0f2e;
  --glass: rgba(255,255,255,0.07);
  --glass-border: rgba(255,255,255,0.12);
  --neon: #6c63ff;
  --neon2: #a855f7;
  --green: #10b981;
  --red: #ef4444;
  --yellow: #f59e0b;
  --gold: #f59e0b;
  --silver: #94a3b8;
  --bronze: #cd7c2f;
  --text: #f1f5f9;
  --muted: #94a3b8;
  --card-r: 18px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg1);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}
body::before {
  content: '';
  position: fixed; inset: 0; z-index: -1;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(108,99,255,0.18) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(168,85,247,0.15) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(10,10,30,1) 0%, rgba(5,5,20,1) 100%);
}
"""

_STAR_JS = """
(function(){
  const c=document.createElement('canvas');
  c.style.cssText='position:fixed;inset:0;z-index:-1;pointer-events:none';
  document.body.prepend(c);
  const ctx=c.getContext('2d');
  let W,H,stars=[];
  function resize(){W=c.width=innerWidth;H=c.height=innerHeight;}
  function init(){resize();stars=[];for(let i=0;i<120;i++)stars.push({x:Math.random()*W,y:Math.random()*H,r:Math.random()*1.5+0.3,a:Math.random(),da:0.003+Math.random()*0.007});}
  function draw(){ctx.clearRect(0,0,W,H);stars.forEach(s=>{s.a+=s.da;if(s.a>1||s.a<0)s.da=-s.da;ctx.beginPath();ctx.arc(s.x,s.y,s.r,0,6.28);ctx.fillStyle='rgba(255,255,255,'+s.a+')';ctx.fill();});requestAnimationFrame(draw);}
  window.addEventListener('resize',resize);
  init();draw();
})();
"""


# ─────────────────────────────────────────────
#  STUDENT TEST PAGE  /t/{token}
# ─────────────────────────────────────────────
@app.get("/t/{token}", response_class=HTMLResponse)
def student_page(token: str):
    s = db.get_session_by_token(token)
    if not s:
        return HTMLResponse(_error_page("Test topilmadi yoki muddati o'tgan."), status_code=404)
    if s["status"] == "finished":
        return HTMLResponse(_result_page(token))
    now = time.time()
    remaining = max(0, int(s["deadline"] - now))
    if remaining <= 0:
        db.submit_session(token)
        return HTMLResponse(_result_page(token))

    letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    cards_data = []
    for i, item in enumerate(s["order"]):
        q = db.get_question(item["qid"])
        opts = []
        for k, orig in enumerate(item["opt"]):
            opts.append({
                "k": k,
                "letter": letters[k],
                "html": _opt_html(q, orig)
            })
        cards_data.append({
            "i": i,
            "stem": _q_html(q),
            "opts": opts
        })

    # TUZATISH: JSON'ni to'g'ridan-to'g'ri JS kodi ichiga qo'yish xavfli edi —
    # savol matnida (formula/rasm HTML'ida) uchraydigan </script, backtick,
    # maxsus tirnoq va h.k. belgilar butun <script> blokini "sindirib"
    # qo'yishi mumkin edi (aynan shu sabab oynada savollar chiqmay,
    # taymer "--" holida qotib qolayotgan edi). Endi JSON base64'ga o'rab
    # uzatiladi — base64 faqat A-Z/a-z/0-9/+//= belgilaridan iborat bo'lgani
    # uchun HECH QANDAY belgi JS yoki HTML'ni buzolmaydi.
    cards_b64 = base64.b64encode(
        json.dumps(cards_data, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    total = len(s["order"])
    name = html.escape(s.get("student_name") or "O'quvchi")
    avatar = html.escape(s.get("avatar") or "🐵")

    return HTMLResponse(_test_page_html(token, remaining, total, cards_b64, name, avatar))


def _test_page_html(token, remaining, total, cards_b64, name, avatar):
    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Test — {name}</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>window.MathJax={{tex:{{}},options:{{}},startup:{{typeset:false}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/mml-chtml.js" id="MathJax-script" async></script>
<script src="https://cdn.jsdelivr.net/npm/js-confetti@latest/dist/js-confetti.browser.js"></script>
<style>
{_BASE_STYLE}

/* ── TOPBAR ── */
.topbar {{
  position: sticky; top: 0; z-index: 50;
  padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  background: rgba(10,10,26,0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--glass-border);
}}
.user-info {{ display: flex; align-items: center; gap: 8px; }}
.user-avatar {{ font-size: 22px; }}
.user-name {{ font-size: 13px; font-weight: 700; color: var(--text); max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

/* ── RING TIMER ── */
.timer-wrap {{ position: relative; width: 52px; height: 52px; flex-shrink: 0; }}
.timer-svg {{ transform: rotate(-90deg); }}
.timer-track {{ fill: none; stroke: rgba(255,255,255,0.1); stroke-width: 4; }}
.timer-ring {{ fill: none; stroke-width: 4; stroke-linecap: round; transition: stroke-dashoffset 1s linear, stroke 1s; }}
.timer-text {{
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; letter-spacing: -0.5px;
}}

/* ── PROGRESS BAR ── */
.prog-wrap {{ flex: 1; }}
.prog-label {{ font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 5px; text-align: center; }}
.prog-bar-bg {{ height: 6px; background: rgba(255,255,255,0.08); border-radius: 99px; overflow: hidden; }}
.prog-bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--neon), var(--neon2)); border-radius: 99px; transition: width 0.4s cubic-bezier(.4,0,.2,1); width: 0%; }}

/* ── CARD CONTAINER ── */
.cards-wrap {{ padding: 16px 16px 110px; }}
.card {{
  display: none;
  background: var(--glass);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(16px);
  border-radius: var(--card-r);
  padding: 20px 18px;
  animation: fadeIn 0.35s ease;
}}
.card.active {{ display: block; }}
@keyframes fadeIn {{ from {{ opacity:0; transform: translateY(12px) scale(0.98); }} to {{ opacity:1; transform:none; }} }}

.qnum {{
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
  color: var(--neon2); margin-bottom: 14px;
}}
.qnum-badge {{
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  color: white; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 800;
}}
.stem {{ font-size: 17px; line-height: 1.6; color: var(--text); margin-bottom: 18px; }}
.stem math, .otext math {{ font-size: 1.05em; }}

/* ── OPTIONS ── */
.opts {{ display: flex; flex-direction: column; gap: 10px; }}
.opt {{
  display: flex; align-items: center; gap: 12px;
  background: rgba(255,255,255,0.04);
  border: 2px solid rgba(255,255,255,0.1);
  border-radius: 13px; padding: 13px 14px;
  cursor: pointer; transition: all 0.2s cubic-bezier(.4,0,.2,1);
  text-align: left; width: 100%; color: var(--text);
  font-size: 15px; font-family: inherit; position: relative; overflow: hidden;
}}
.opt::before {{
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  opacity: 0; transition: opacity 0.2s;
}}
.opt:active {{ transform: scale(0.98); }}
.opt.sel {{
  border-color: var(--neon);
  background: rgba(108,99,255,0.15);
  box-shadow: 0 0 0 1px var(--neon), 0 4px 20px rgba(108,99,255,0.3);
}}
.opt.sel .opt-lbl {{
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  color: white; border-color: transparent;
  box-shadow: 0 0 12px rgba(108,99,255,0.6);
}}
.opt-lbl {{
  flex-shrink: 0; width: 34px; height: 34px; border-radius: 10px;
  border: 2px solid rgba(255,255,255,0.2);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; transition: all 0.2s; position: relative; z-index: 1;
}}
.otext {{ flex: 1; min-width: 0; position: relative; z-index: 1;
  overflow-wrap: anywhere; word-break: break-word; }}
.stem, .otext {{ overflow-wrap: anywhere; }}
.stem mjx-container, .otext mjx-container {{ max-width: 100%; overflow-x: auto; overflow-y: hidden; }}
.stem img, .otext img {{ max-width: 100%; height: auto; }}

/* ── PULSE ANIM on select ── */
@keyframes pulse-ring {{
  0% {{ box-shadow: 0 0 0 0 rgba(108,99,255,0.6); }}
  100% {{ box-shadow: 0 0 0 14px rgba(108,99,255,0); }}
}}
.opt.sel {{ animation: pulse-ring 0.5s ease-out; }}

/* ── NAV BUTTONS ── */
.nav-bar {{
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 12px 16px; display: flex; gap: 10px;
  background: linear-gradient(to top, rgba(10,10,26,0.98) 60%, transparent);
  backdrop-filter: blur(10px);
}}
.btn {{
  height: 52px; border-radius: 14px; border: none; cursor: pointer;
  font-size: 15px; font-weight: 700; font-family: inherit;
  transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px;
}}
.btn:active {{ transform: scale(0.97); }}
.btn-prev {{
  background: rgba(255,255,255,0.08); color: var(--text); width: 52px; flex-shrink: 0;
  border: 1px solid var(--glass-border);
}}
.btn-next {{
  flex: 1;
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  color: white;
  box-shadow: 0 4px 20px rgba(108,99,255,0.4);
}}
.btn-finish {{
  flex: 1;
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  box-shadow: 0 4px 20px rgba(16,185,129,0.4);
}}
.btn:disabled {{ opacity: 0.45; cursor: not-allowed; transform: none; box-shadow: none; }}

/* ── RESULT OVERLAY ── */
#result-overlay {{
  position: fixed; inset: 0; z-index: 200;
  background: rgba(5,5,20,0.92); backdrop-filter: blur(20px);
  display: none; flex-direction: column; align-items: center; justify-content: center;
  padding: 24px;
}}
.result-box {{
  background: var(--glass); border: 1px solid var(--glass-border);
  border-radius: 24px; padding: 30px 24px; width: 100%; max-width: 440px;
  text-align: center; position: relative; overflow: hidden;
}}
.result-box::before {{
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(108,99,255,0.08), rgba(168,85,247,0.08));
  pointer-events: none;
}}
.result-emoji {{ font-size: 64px; line-height: 1; margin-bottom: 10px; display: block; }}
.result-title {{ font-size: 22px; font-weight: 800; margin-bottom: 6px; }}
.result-score {{
  font-size: 52px; font-weight: 900;
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin: 10px 0 4px;
}}
.result-pct {{ font-size: 16px; color: var(--muted); font-weight: 600; }}
.grade-badge {{
  display: inline-block; margin: 14px 0;
  padding: 8px 22px; border-radius: 99px;
  font-size: 17px; font-weight: 800;
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  box-shadow: 0 4px 20px rgba(108,99,255,0.4);
}}
.wrong-list {{
  text-align: left; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2);
  border-radius: 12px; padding: 12px 14px; margin-top: 14px; font-size: 13px;
}}
.wrong-list-title {{ font-weight: 700; color: #fca5a5; margin-bottom: 6px; }}
.wrong-nums {{ color: var(--muted); line-height: 1.8; }}
.result-btns {{ display: flex; gap: 10px; margin-top: 18px; }}
.rbtn {{
  flex: 1; height: 48px; border-radius: 12px; border: none; cursor: pointer;
  font-size: 14px; font-weight: 700; font-family: inherit; transition: all 0.2s;
}}
.rbtn-review {{
  background: rgba(255,255,255,0.1); color: var(--text);
  border: 1px solid var(--glass-border);
}}
.rbtn-close {{
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  color: white; box-shadow: 0 4px 14px rgba(108,99,255,0.4);
}}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <div class="user-info">
    <span class="user-avatar">{avatar}</span>
    <span class="user-name">{name}</span>
  </div>
  <div class="prog-wrap">
    <div class="prog-label" id="prog-label">0 / {total} javoblandi</div>
    <div class="prog-bar-bg"><div class="prog-bar-fill" id="prog-fill"></div></div>
  </div>
  <div class="timer-wrap">
    <svg class="timer-svg" width="52" height="52" viewBox="0 0 52 52">
      <circle class="timer-track" cx="26" cy="26" r="22"/>
      <circle class="timer-ring" id="timer-ring" cx="26" cy="26" r="22"
        stroke="url(#tg)"
        stroke-dasharray="138.2"
        stroke-dashoffset="0"/>
      <defs>
        <linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop id="tg1" offset="0%" stop-color="#10b981"/>
          <stop id="tg2" offset="100%" stop-color="#34d399"/>
        </linearGradient>
      </defs>
    </svg>
    <div class="timer-text" id="timer-txt">--</div>
  </div>
</div>

<!-- CARDS -->
<div class="cards-wrap" id="cards-wrap"></div>

<!-- NAV BAR -->
<div class="nav-bar">
  <button class="btn btn-prev" id="btn-prev" onclick="nav(-1)">‹</button>
  <button class="btn btn-next" id="btn-next" onclick="nav(1)">Keyingisi ›</button>
  <button class="btn btn-finish" id="btn-finish" onclick="submitTest()" style="display:none">✅ Yakunlash</button>
</div>

<!-- RESULT OVERLAY -->
<div id="result-overlay">
  <div class="result-box">
    <span class="result-emoji" id="res-emoji">🏆</span>
    <div class="result-title" id="res-title">Test yakunlandi!</div>
    <div class="result-score" id="res-score">0 / {total}</div>
    <div class="result-pct" id="res-pct">0%</div>
    <div class="grade-badge" id="res-grade">Baho: 5</div>
    <div class="wrong-list" id="res-wrong" style="display:none">
      <div class="wrong-list-title">❌ Xato savollar:</div>
      <div class="wrong-nums" id="res-wrong-nums"></div>
    </div>
    <div class="result-btns">
      <button class="rbtn rbtn-review" onclick="goReview()">📖 Ko'rish</button>
      <button class="rbtn rbtn-close" onclick="closeApp()">✓ Yopish</button>
    </div>
  </div>
</div>

<script>
{_STAR_JS}
const TOKEN = "{token}";
const TOTAL = {total};
// TUZATISH: JSON endi base64 orqali xavfsiz uzatiladi va JSON.parse(atob(...))
// bilan qayta tiklanadi — savol matnidagi HECH QANDAY belgi bu qatorni
// buzolmaydi (avvalgi "const CARDS = {{...}};" usuli savol ichida maxsus
// belgi bo'lganda butun skriptni to'xtatib qo'yardi).
const CARDS = JSON.parse(decodeURIComponent(escape(atob("{cards_b64}"))));
const CIRCUMFERENCE = 138.2;
let REMAINING = {remaining};
const FULL_TIME = {remaining};
const answers = {{}};
let curIdx = 0;
let submitted = false;

// ── INIT ──
try {{ Telegram.WebApp.ready(); Telegram.WebApp.expand(); Telegram.WebApp.enableClosingConfirmation(); }} catch(e) {{}}

function buildCards() {{
  const wrap = document.getElementById('cards-wrap');
  CARDS.forEach(function(cd, i) {{
    const div = document.createElement('div');
    div.className = 'card' + (i===0 ? ' active' : '');
    div.id = 'card' + i;
    let optsHtml = '';
    cd.opts.forEach(function(o) {{
      optsHtml += '<button class="opt" id="opt-' + i + '-' + o.k + '" data-q="' + i + '" data-k="' + o.k + '" onclick="pick(' + i + ',' + o.k + ',this)">' +
        '<span class="opt-lbl">' + o.letter + '</span>' +
        '<span class="otext">' + o.html + '</span>' +
        '</button>';
    }});
    div.innerHTML =
      '<div class="qnum"><span class="qnum-badge">' + (i+1) + '</span> \u2014 ' + TOTAL + ' ta savol</div>' +
      '<div class="stem">' + cd.stem + '</div>' +
      '<div class="opts">' + optsHtml + '</div>';
    wrap.appendChild(div);
  }});
  updateNav();
  if(window.MathJax) MathJax.typesetPromise().catch(function(){{}});
}}

function pick(q, k, el) {{
  answers[q] = k;
  document.querySelectorAll(`[data-q="${{q}}"]`).forEach(b => b.classList.remove('sel'));
  el.classList.add('sel');
  updateProgress();
  fetch('/api/answer', {{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{token:TOKEN,i:q,pos:k}})}}).catch(()=>{{}});
  // Auto-advance after short delay if not last
  if (q < TOTAL - 1) {{
    setTimeout(() => {{ if(answers[q]===k) nav(1); }}, 400);
  }}
}}

function nav(dir) {{
  const next = curIdx + dir;
  if(next < 0 || next >= TOTAL) return;
  document.getElementById('card'+curIdx).classList.remove('active');
  curIdx = next;
  document.getElementById('card'+curIdx).classList.add('active');
  if(window.MathJax) MathJax.typesetPromise([document.getElementById('card'+curIdx)]).catch(()=>{{}});
  updateNav();
}}

function updateNav() {{
  const prev = document.getElementById('btn-prev');
  const nxt = document.getElementById('btn-next');
  const fin = document.getElementById('btn-finish');
  prev.disabled = (curIdx === 0);
  if(curIdx === TOTAL - 1) {{
    nxt.style.display = 'none'; fin.style.display = 'flex';
  }} else {{
    nxt.style.display = 'flex'; fin.style.display = 'none';
  }}
}}

function updateProgress() {{
  const n = Object.keys(answers).length;
  document.getElementById('prog-label').textContent = n + ' / ' + TOTAL + ' javoblandi';
  document.getElementById('prog-fill').style.width = (n/TOTAL*100) + '%';
}}

// ── TIMER ──
function fmtTime(s) {{
  const m=Math.floor(s/60), x=s%60;
  return m+':'+(x<10?'0':'')+x;
}}
function tick() {{
  const ring = document.getElementById('timer-ring');
  const txt = document.getElementById('timer-txt');
  const tg1 = document.getElementById('tg1'), tg2 = document.getElementById('tg2');
  txt.textContent = fmtTime(REMAINING);
  const frac = REMAINING / FULL_TIME;
  ring.style.strokeDashoffset = CIRCUMFERENCE * (1 - frac);
  if(frac > 0.5) {{ tg1.setAttribute('stop-color','#10b981'); tg2.setAttribute('stop-color','#34d399'); }}
  else if(frac > 0.2) {{ tg1.setAttribute('stop-color','#f59e0b'); tg2.setAttribute('stop-color','#fbbf24'); }}
  else {{ tg1.setAttribute('stop-color','#ef4444'); tg2.setAttribute('stop-color','#f87171'); }}
  if(REMAINING <= 0) {{ doSubmit(true); return; }}
  REMAINING--;
  setTimeout(tick, 1000);
}}
tick();

// ── SUBMIT ──
function submitTest() {{
  const left = TOTAL - Object.keys(answers).length;
  if(left > 0) {{
    const msg = left + ' ta savol javobsiz qoldi. Baribir yakunlaysizmi?';
    try {{
      Telegram.WebApp.showConfirm(msg, ok => {{ if(ok) doSubmit(false); }});
    }} catch(e) {{
      if(confirm(msg)) doSubmit(false);
    }}
    return;
  }}
  doSubmit(false);
}}
function doSubmit(auto) {{
  if(submitted) return; submitted = true;
  document.getElementById('btn-finish').disabled = true;
  fetch('/api/submit', {{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{token:TOKEN,answers:answers}})}})
    .then(r=>r.json()).then(showResult)
    .catch(()=>{{ submitted=false; }});
}}

// ── RESULT ──
let confettiInstance;
function showResult(res) {{
  const pct = res.total ? Math.round(100*res.score/res.total) : 0;
  let emoji='📚', title='Harakat qiling!', grade='2';
  if(pct>=90) {{ emoji='🏆'; title='Ajoyib natija!'; grade='5'; }}
  else if(pct>=70) {{ emoji='🌟'; title='Yaxshi natija!'; grade='4'; }}
  else if(pct>=50) {{ emoji='🙂'; title="O‘tdi!"; grade='3'; }}

  document.getElementById('res-emoji').textContent = emoji;
  document.getElementById('res-title').textContent = title;
  document.getElementById('res-grade').textContent = 'Baho: ' + grade;
  document.getElementById('res-pct').textContent = pct + '%';

  // Animate score count-up
  let cur = 0;
  const target = res.score;
  const el = document.getElementById('res-score');
  el.textContent = '0 / ' + res.total;
  const step = () => {{
    if(cur < target) {{ cur++; el.textContent = cur+' / '+res.total; requestAnimationFrame(step); }}
    else {{ el.textContent = target+' / '+res.total; }}
  }};
  setTimeout(step, 300);

  // Wrong list
  const wrong = res.detail.filter(d=>!d.ok).map(d=>d.i+1);
  if(wrong.length) {{
    document.getElementById('res-wrong').style.display='block';
    document.getElementById('res-wrong-nums').textContent = wrong.join(', ');
  }}

  document.getElementById('result-overlay').style.display='flex';

  // Confetti
  if(pct >= 50) {{
    try {{
      confettiInstance = new JSConfetti();
      confettiInstance.addConfetti({{
        confettiColors: pct>=90 ? ['#f59e0b','#fbbf24','#ffffff','#6c63ff'] : ['#6c63ff','#a855f7','#ffffff'],
        confettiRadius: 4, confettiNumber: pct>=90 ? 400 : 150,
      }});
    }} catch(e) {{}}
  }}
}}

function goReview() {{ location.href = '/r/' + TOKEN; }}
function closeApp() {{ try {{ Telegram.WebApp.close(); }} catch(e) {{ history.back(); }} }}

// ── BUILD ──
buildCards();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
#  RESULT PAGE (already finished)
# ─────────────────────────────────────────────
def _result_page(token):
    s = db.get_session_by_token(token)
    if not s:
        return _error_page("Sessiya topilmadi.")
    sc = s["score"]; tot = s["total"]
    pct = round(100*sc/tot) if tot else 0
    emoji = "🏆" if pct>=90 else "🌟" if pct>=70 else "🙂" if pct>=50 else "📚"
    grade = "5" if pct>=90 else "4" if pct>=70 else "3" if pct>=50 else "2"
    name = html.escape(s.get("student_name") or "")
    avatar = html.escape(s.get("avatar") or "🐵")

    return f"""<!DOCTYPE html>
<html lang="uz"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Natija</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script src="https://cdn.jsdelivr.net/npm/js-confetti@latest/dist/js-confetti.browser.js"></script>
<style>
{_BASE_STYLE}
body {{ display:flex; align-items:center; justify-content:center; min-height:100vh; padding:24px; }}
.box {{
  background: var(--glass); border:1px solid var(--glass-border);
  backdrop-filter:blur(20px); border-radius:24px; padding:32px 24px;
  width:100%; max-width:420px; text-align:center;
}}
.av {{ font-size:48px; margin-bottom:8px; }}
.who {{ font-size:15px; font-weight:700; color:var(--muted); margin-bottom:20px; }}
.big-emoji {{ font-size:72px; display:block; margin-bottom:8px; }}
.score-wrap {{ margin:16px 0; }}
.score {{
  font-size:56px; font-weight:900; line-height:1;
  background: linear-gradient(135deg, var(--neon), var(--neon2));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}}
.of {{ font-size:18px; color:var(--muted); font-weight:600; margin-top:4px; }}
.pct {{ font-size:16px; color:var(--muted); margin-top:2px; }}
.grade {{
  display:inline-block; margin:14px 0;
  padding:10px 26px; border-radius:99px; font-size:18px; font-weight:800;
  background:linear-gradient(135deg,var(--neon),var(--neon2));
  box-shadow:0 4px 20px rgba(108,99,255,.4);
}}
.btns {{ display:flex; gap:10px; margin-top:20px; }}
.btn {{
  flex:1; height:50px; border-radius:13px; border:none; cursor:pointer;
  font-size:15px; font-weight:700; font-family:inherit; transition:all .2s;
}}
.btn-r {{ background:rgba(255,255,255,.08); color:var(--text); border:1px solid var(--glass-border); }}
.btn-c {{ background:linear-gradient(135deg,var(--neon),var(--neon2)); color:white; }}
.btn:active {{ transform:scale(.97); }}
</style>
</head><body>
<div class="box">
  <div class="av">{avatar}</div>
  <div class="who">{name}</div>
  <span class="big-emoji">{emoji}</span>
  <div class="score-wrap">
    <div class="score">{sc}</div>
    <div class="of">/ {tot} ta savol</div>
    <div class="pct">{pct}%</div>
  </div>
  <div class="grade">Baho: {grade}</div>
  <div class="btns">
    <button class="btn btn-r" onclick="location.href='/r/{token}'">📖 Ko'rish</button>
    <button class="btn btn-c" onclick="try{{Telegram.WebApp.close()}}catch(e){{}}">✓ Yopish</button>
  </div>
</div>
<script>
{_STAR_JS}
try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}
if({pct}>=50){{
  try{{
    const c=new JSConfetti();
    c.addConfetti({{confettiColors:{json.dumps(["#f59e0b","#6c63ff","#a855f7","#ffffff"] if pct>=90 else ["#6c63ff","#a855f7","#10b981"])},confettiNumber:{400 if pct>=90 else 180}}});
  }}catch(e){{}}
}}
</script>
</body></html>"""


# ─────────────────────────────────────────────
#  REVIEW PAGE  /r/{token}
# ─────────────────────────────────────────────
@app.get("/r/{token}", response_class=HTMLResponse)
def review_page(token: str):
    s = db.get_session_by_token(token)
    if not s:
        return HTMLResponse(_error_page("Topilmadi."), status_code=404)
    if s["status"] != "finished":
        return HTMLResponse(_error_page("Avval testni yakunlang."), status_code=403)

    live = s["live"]
    letters = ["A","B","C","D","E","F","G","H"]
    cards_html = []
    sc = s["score"]; tot = s["total"]

    for i, item in enumerate(s["order"]):
        q = db.get_question(item["qid"])
        chosen = live.get(str(i))
        chosen = int(chosen) if chosen is not None else None
        correct = item["correct"]
        ok = (chosen == correct)
        card_cls = "card-ok" if ok else "card-err"

        opts_html = ""
        for k, orig in enumerate(item["opt"]):
            o_html = _opt_html(q, orig)
            cls = ""
            mark = ""
            if k == correct:
                cls = "opt-correct"; mark = " ✅"
            if k == chosen and k != correct:
                cls = "opt-wrong"; mark = " ❌"
            opts_html += f'<div class="rev-opt {cls}"><span class="opt-lbl">{letters[k]}</span><span class="otext">{o_html}{mark}</span></div>'

        cards_html.append(f"""
<div class="rev-card {card_cls}">
  <div class="rev-qnum">
    <span class="qnum-badge">{i+1}</span>
    {"<span class='badge-ok'>✓</span>" if ok else "<span class='badge-err'>✗</span>"}
  </div>
  <div class="stem rev-stem">{_q_html(q)}</div>
  <div class="rev-opts">{opts_html}</div>
</div>""")

    pct = round(100*sc/tot) if tot else 0
    name = html.escape(s.get("student_name") or "")

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="uz"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Javoblar ko'rish</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>window.MathJax={{tex:{{}},options:{{}},startup:{{typeset:false}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/mml-chtml.js" id="MathJax-script" async></script>
<style>
{_BASE_STYLE}
.header {{
  position:sticky; top:0; z-index:50;
  background:rgba(10,10,26,.92); backdrop-filter:blur(20px);
  border-bottom:1px solid var(--glass-border);
  padding:14px 16px; display:flex; align-items:center; justify-content:space-between;
}}
.hname {{ font-size:14px; font-weight:700; }}
.hscore {{
  font-size:13px; font-weight:800; padding:5px 14px; border-radius:99px;
  background:linear-gradient(135deg,var(--neon),var(--neon2));
}}
.rev-wrap {{ padding:14px 14px 30px; display:flex; flex-direction:column; gap:12px; }}
.rev-card {{
  background:var(--glass); border:1px solid var(--glass-border);
  backdrop-filter:blur(12px); border-radius:var(--card-r); padding:16px;
}}
.card-ok {{ border-color:rgba(16,185,129,.35); background:rgba(16,185,129,.06); }}
.card-err {{ border-color:rgba(239,68,68,.35); background:rgba(239,68,68,.06); }}
.rev-qnum {{ display:flex; align-items:center; gap:8px; margin-bottom:12px; }}
.qnum-badge {{ background:linear-gradient(135deg,var(--neon),var(--neon2)); color:white; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:800; }}
.badge-ok {{ color:var(--green); font-size:15px; font-weight:800; }}
.badge-err {{ color:var(--red); font-size:15px; font-weight:800; }}
.rev-stem {{ font-size:16px; line-height:1.55; margin-bottom:14px; }}
.rev-opts {{ display:flex; flex-direction:column; gap:8px; }}
.rev-opt {{
  display:flex; align-items:center; gap:10px;
  padding:11px 12px; border-radius:11px; font-size:14px;
  background:rgba(255,255,255,.04); border:1.5px solid rgba(255,255,255,.08);
}}
.opt-correct {{ background:rgba(16,185,129,.12); border-color:rgba(16,185,129,.4); color:#6ee7b7; }}
.opt-wrong {{ background:rgba(239,68,68,.12); border-color:rgba(239,68,68,.4); color:#fca5a5; }}
.opt-lbl {{ flex-shrink:0; width:30px; height:30px; border-radius:8px; border:1.5px solid rgba(255,255,255,.15); display:flex; align-items:center; justify-content:center; font-weight:800; font-size:13px; }}
.opt-correct .opt-lbl {{ background:rgba(16,185,129,.3); border-color:var(--green); }}
.opt-wrong .opt-lbl {{ background:rgba(239,68,68,.3); border-color:var(--red); }}
.otext {{ flex:1; }}
</style>
</head><body>
<div class="header">
  <span class="hname">📖 {name}</span>
  <span class="hscore">{sc}/{tot} · {pct}%</span>
</div>
<div class="rev-wrap">{''.join(cards_html)}</div>
<script>
try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}
if(window.MathJax) MathJax.typesetPromise().catch(()=>{{}});
</script>
</body></html>""")


# ─────────────────────────────────────────────
#  API ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/api/answer")
async def api_answer(req: Request):
    d = await req.json()
    db.save_live(d["token"], d["i"], d["pos"])
    return JSONResponse({"ok": True})

@app.post("/api/submit")
async def api_submit(req: Request):
    d = await req.json()
    result = db.submit_session(d["token"], d.get("answers"))
    return JSONResponse(result or {"error": "not found"})

@app.get("/api/panel/{code}")
def api_panel(code: str, t: str = ""):
    data = db.panel_data(code)
    if not data:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(data)

@app.post("/api/expire")
async def api_expire():
    n = db.expire_due()
    return JSONResponse({"expired": n})


# ─────────────────────────────────────────────
#  TEACHER PANEL  /p/{code}/{panel_token}
# ─────────────────────────────────────────────
@app.get("/p/{code}/{panel_token}", response_class=HTMLResponse)
def panel_page(code: str, panel_token: str):
    test = db.get_test(code)
    if not test or test.get("panel_token") != panel_token:
        return HTMLResponse(_error_page("Panel topilmadi yoki token noto'g'ri."), status_code=404)
    return HTMLResponse(_panel_html(code, panel_token))


def _panel_html(code, panel_token):
    return f"""<!DOCTYPE html>
<html lang="uz"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Panel — {code}</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
{_BASE_STYLE}

/* ── HEADER ── */
.panel-header {{
  background:rgba(10,10,26,.92); backdrop-filter:blur(20px);
  border-bottom:1px solid var(--glass-border);
  padding:14px 16px;
  display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;
}}
.panel-title {{ font-size:17px; font-weight:800; }}
.panel-code {{ font-size:13px; color:var(--muted); }}
.live-badge {{
  display:flex; align-items:center; gap:6px;
  background:rgba(239,68,68,.15); border:1px solid rgba(239,68,68,.3);
  border-radius:99px; padding:5px 12px; font-size:12px; font-weight:700; color:#fca5a5;
}}
.live-dot {{
  width:8px; height:8px; border-radius:50%; background:#ef4444;
  animation:blink 1s infinite;
}}
@keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:0.2}} }}

/* ── STAT CARDS ── */
.stats-row {{
  display:grid; grid-template-columns:repeat(3,1fr); gap:10px;
  padding:14px 14px 0;
}}
.stat-card {{
  background:var(--glass); border:1px solid var(--glass-border);
  backdrop-filter:blur(12px); border-radius:14px; padding:14px 12px; text-align:center;
}}
.stat-num {{ font-size:26px; font-weight:900; }}
.stat-num.gold {{ background:linear-gradient(135deg,#f59e0b,#fbbf24); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.stat-num.purple {{ background:linear-gradient(135deg,var(--neon),var(--neon2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.stat-num.green {{ background:linear-gradient(135deg,#10b981,#34d399); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.stat-lbl {{ font-size:11px; color:var(--muted); font-weight:600; margin-top:4px; }}

/* ── PODIUM ── */
.podium-wrap {{
  padding:16px 14px 0;
}}
.podium-title {{ font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:var(--muted); margin-bottom:12px; }}
.podium {{
  display:flex; align-items:flex-end; justify-content:center; gap:8px; height:120px;
}}
.podium-item {{
  flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end;
  max-width:110px;
}}
.podium-av {{ font-size:22px; margin-bottom:4px; }}
.podium-name {{ font-size:11px; font-weight:700; color:var(--text); text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; width:100%; padding:0 2px; }}
.podium-score {{ font-size:12px; color:var(--muted); font-weight:600; }}
.podium-bar {{
  width:100%; border-radius:8px 8px 0 0; margin-top:6px;
  display:flex; align-items:center; justify-content:center;
  font-size:18px; font-weight:900;
}}
.podium-bar.gold {{ background:linear-gradient(180deg,#f59e0b,#d97706); height:80px; }}
.podium-bar.silver {{ background:linear-gradient(180deg,#94a3b8,#64748b); height:60px; }}
.podium-bar.bronze {{ background:linear-gradient(180deg,#cd7c2f,#92400e); height:44px; }}

/* ── RACE LIST ── */
.race-wrap {{ padding:14px; display:flex; flex-direction:column; gap:8px; padding-bottom:30px; }}
.race-item {{
  background:var(--glass); border:1px solid var(--glass-border);
  backdrop-filter:blur(10px); border-radius:14px; padding:12px 14px;
  transition:all 0.4s ease;
}}
.race-top {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; }}
.race-rank {{ font-size:13px; font-weight:800; width:24px; color:var(--muted); text-align:center; }}
.race-av {{ font-size:20px; }}
.race-name {{ flex:1; font-size:14px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.race-status-active {{ font-size:11px; color:#34d399; font-weight:700; animation:blink 1.5s infinite; }}
.race-status-done {{ font-size:11px; color:var(--muted); font-weight:600; }}
.race-score {{ font-size:14px; font-weight:800; }}
.race-bar-bg {{ height:6px; background:rgba(255,255,255,.08); border-radius:99px; overflow:hidden; }}
.race-bar-fill {{ height:100%; border-radius:99px; transition:width 0.6s cubic-bezier(.4,0,.2,1); }}
.fill-active {{ background:linear-gradient(90deg,var(--neon),var(--neon2)); }}
.fill-done {{ background:linear-gradient(90deg,#10b981,#34d399); }}
.fill-waiting {{ background:rgba(255,255,255,.2); }}
.race-meta {{ display:flex; justify-content:space-between; margin-top:5px; font-size:11px; color:var(--muted); font-weight:600; }}

/* ── HARDEST Q card ── */
.hardest-wrap {{ padding:0 14px 14px; }}
.hardest-card {{
  background:rgba(239,68,68,.08); border:1px solid rgba(239,68,68,.2);
  border-radius:14px; padding:14px; display:flex; align-items:center; gap:12px;
}}
.hardest-icon {{ font-size:28px; }}
.hardest-txt .label {{ font-size:11px; color:#fca5a5; font-weight:700; text-transform:uppercase; letter-spacing:.5px; }}
.hardest-txt .val {{ font-size:16px; font-weight:800; }}

/* ── CLOSED BANNER ── */
.closed-banner {{
  background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.25);
  border-radius:12px; padding:10px 14px; margin:12px 14px 0;
  font-size:13px; font-weight:700; color:#fca5a5; text-align:center;
}}

/* ── REFRESH indicator ── */
.refresh-bar {{
  position:fixed; bottom:0; left:0; right:0; height:3px;
  background:rgba(255,255,255,.05);
}}
.refresh-fill {{
  height:100%; background:linear-gradient(90deg,var(--neon),var(--neon2));
  width:100%; transform-origin:left; animation:progress 3s linear infinite;
}}
@keyframes progress {{ from{{transform:scaleX(0)}} to{{transform:scaleX(1)}} }}
</style>
</head><body>

<div id="app"></div>
<div class="refresh-bar"><div class="refresh-fill"></div></div>

<script>
{_STAR_JS}
try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}

const CODE = "{code}";

function fmtTime(s) {{
  if(s===null||s===undefined) return '';
  const m=Math.floor(s/60),x=s%60;
  return m+'daq '+x+'s';
}}

function render(data) {{
  const st = data.students || [];
  const finished = st.filter(s=>s.status==='finished');
  const active = st.filter(s=>s.status==='active');
  const qTotal = data.q_total || 1;

  // Sort by score desc, then by answered desc
  const sorted = [...st].sort((a,b)=>{{
    if(b.score!==a.score) return b.score-a.score;
    return b.answered-a.answered;
  }});

  // PODIUM (top 3 finished)
  const podiumPeople = sorted.filter(s=>s.status==='finished').slice(0,3);
  let podiumHtml = '';
  if(podiumPeople.length>=1) {{
    const order = podiumPeople.length===1 ? [podiumPeople[0]] :
                  podiumPeople.length===2 ? [podiumPeople[1],podiumPeople[0]] :
                  [podiumPeople[1],podiumPeople[0],podiumPeople[2]];
    const cls = podiumPeople.length===1 ? ['gold'] :
                podiumPeople.length===2 ? ['silver','gold'] :
                ['silver','gold','bronze'];
    const medals = podiumPeople.length===1 ? ['🥇'] :
                   podiumPeople.length===2 ? ['🥈','🥇'] :
                   ['🥈','🥇','🥉'];
    podiumHtml = `<div class="podium-wrap">
      <div class="podium-title">🏆 Reyting</div>
      <div class="podium">` +
      order.map((p,i)=>`
        <div class="podium-item">
          <div class="podium-av">${{p.avatar||'🐵'}}</div>
          <div class="podium-name">${{esc(p.name)}}</div>
          <div class="podium-score">${{p.score}}/${{p.total}}</div>
          <div class="podium-bar ${{cls[i]}}">${{medals[i]}}</div>
        </div>`).join('') +
      `</div></div>`;
  }}

  // STATS
  const statsHtml = `<div class="stats-row">
    <div class="stat-card">
      <div class="stat-num gold">${{data.avg||0}}</div>
      <div class="stat-lbl">O'rtacha ball</div>
    </div>
    <div class="stat-card">
      <div class="stat-num green">${{data.finished||0}}/${{data.total_students||0}}</div>
      <div class="stat-lbl">Yakunladi</div>
    </div>
    <div class="stat-card">
      <div class="stat-num purple">${{active.length}}</div>
      <div class="stat-lbl">Yechyapti</div>
    </div>
  </div>`;

  // HARDEST
  let hardestHtml = '';
  if(data.hardest) {{
    hardestHtml = `<div class="hardest-wrap">
      <div class="hardest-card">
        <div class="hardest-icon">🔥</div>
        <div class="hardest-txt">
          <div class="label">Eng qiyin savol</div>
          <div class="val">${{data.hardest.q}}-savol — ${{data.hardest.miss_pct}}% xato</div>
        </div>
      </div>
    </div>`;
  }}

  // CLOSED
  const closedHtml = data.closed ? `<div class="closed-banner">🔒 Test yopilgan — yangi o'quvchi kira olmaydi</div>` : '';

  // RACE
  const raceHtml = sorted.map((s,i)=>{{
    const pct = s.total ? Math.round(100*s.answered/s.total) : 0;
    const scorePct = s.total ? Math.round(100*s.score/s.total) : 0;
    const fillCls = s.status==='finished' ? 'fill-done' : s.answered>0 ? 'fill-active' : 'fill-waiting';
    const statusHtml = s.status==='finished'
      ? `<span class="race-status-done">🏁 ${{fmtTime(s.spent)}}</span>`
      : s.answered>0
        ? `<span class="race-status-active">⏳ yechyapti…</span>`
        : `<span class="race-status-done">⌛ kutmoqda</span>`;
    const rankEmoji = i===0?'🥇':i===1?'🥈':i===2?'🥉':`${{i+1}}.`;
    return `<div class="race-item">
      <div class="race-top">
        <span class="race-rank">${{rankEmoji}}</span>
        <span class="race-av">${{s.avatar||'🐵'}}</span>
        <span class="race-name">${{esc(s.name)}}</span>
        ${{statusHtml}}
        <span class="race-score">${{s.score||0}}/${{s.total||0}}</span>
      </div>
      <div class="race-bar-bg"><div class="race-bar-fill ${{fillCls}}" style="width:${{pct}}%"></div></div>
      <div class="race-meta">
        <span>${{s.answered}}/${{s.total}} javob (${{pct}}%)</span>
        <span>${{scorePct}}% to'g'ri</span>
      </div>
    </div>`;
  }}).join('');

  document.getElementById('app').innerHTML = `
    <div class="panel-header">
      <div>
        <div class="panel-title">${{esc(data.title||'')}}</div>
        <div class="panel-code">Kod: ${{CODE}} · ${{data.q_total}} ta savol · ${{data.time_limit}} daq</div>
      </div>
      <div class="live-badge"><span class="live-dot"></span> LIVE ${{active.length}}</div>
    </div>
    ${{closedHtml}}
    ${{statsHtml}}
    ${{podiumHtml}}
    ${{data.hardest?hardestHtml:''}}
    <div class="race-wrap">${{raceHtml}}</div>
  `;
}}

function esc(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function load() {{
  fetch('/api/panel/'+CODE)
    .then(r=>r.json()).then(render).catch(()=>{{}});
}}

load();
setInterval(load, 3000);
</script>
</body></html>"""


# ─────────────────────────────────────────────
#  ERROR PAGE
# ─────────────────────────────────────────────
def _error_page(msg):
    return f"""<!DOCTYPE html>
<html lang="uz"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
{_BASE_STYLE}
body {{ display:flex; align-items:center; justify-content:center; min-height:100vh; padding:24px; text-align:center; }}
.box {{ max-width:360px; }}
.ico {{ font-size:56px; margin-bottom:16px; }}
.msg {{ font-size:17px; font-weight:600; color:#94a3b8; }}
</style></head><body>
<div class="box">
  <div class="ico">⚠️</div>
  <div class="msg">{html.escape(msg)}</div>
</div>
</body></html>"""

# ═════════════════════════════════════════════════════════════════
#  JONLI O'YIN (Kahoot uslubi) — host ekran + o'quvchi sahifasi
# ═════════════════════════════════════════════════════════════════
def _opt_html_i(q, i):
    o = q["options"][i]
    return render.fragment_to_html(o["xml"], db.get_media) or html.escape(o["text"] or "")


# ---------- API ----------
@app.post("/live/api/join")
async def live_join(req: Request):
    d = await req.json()
    res = db.join_game(str(d.get("pin", "")).strip(), d.get("name", ""))
    if res.get("error"):
        return JSONResponse(res, status_code=400)
    return JSONResponse(res)

@app.get("/live/api/pstate")
def live_pstate(pin: str, pid: int, tok: str):
    return JSONResponse(db.player_state(pin, pid, tok))

@app.post("/live/api/answer")
async def live_answer(req: Request):
    d = await req.json()
    try:
        res = db.submit_answer(str(d.get("pin", "")), int(d.get("pid")), d.get("tok", ""), d.get("choice"))
    except Exception:
        res = {"ok": False, "reason": "bad"}
    return JSONResponse(res)

@app.get("/live/api/hstate")
def live_hstate(pin: str, tok: str):
    g = db.get_game_by_host(tok)
    if not g or g["pin"] != pin:
        return JSONResponse({"error": "auth"}, status_code=403)
    data = db.host_state(pin)
    if data and data.get("qid"):
        q = db.get_question(data["qid"])
        data["q_html"] = _q_html(q)
        data["opts_html"] = [_opt_html_i(q, i) for i in range(min(len(q["options"]), 4))]
    return JSONResponse(data)

@app.post("/live/api/host")
async def live_host(req: Request):
    d = await req.json()
    data = db.host_advance(d.get("tok", ""), d.get("action", ""))
    if data is None:
        return JSONResponse({"error": "auth"}, status_code=403)
    return JSONResponse(data)


# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def live_root():
    return HTMLResponse("<!DOCTYPE html><meta charset='utf-8'>"
                        "<meta http-equiv='refresh' content='0; url=/join'>"
                        "<a href='/join'>Jonli o'yinga qo'shilish</a>")

@app.get("/join", response_class=HTMLResponse)
def join_page():
    return HTMLResponse(_player_html())

@app.get("/host/{pin}/{host_token}", response_class=HTMLResponse)
def host_page(pin: str, host_token: str):
    g = db.get_game_by_host(host_token)
    if not g or g["pin"] != pin:
        return HTMLResponse(_error_page("O'yin topilmadi yoki havola noto'g'ri."), status_code=404)
    return HTMLResponse(_host_html(pin, host_token))


_LIVE_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg1:#0a0a1a;--bg2:#12123a;--neon:#6c63ff;--neon2:#a855f7;--text:#f1f5f9;--muted:#94a3b8;
--glass:rgba(255,255,255,.06);--gb:rgba(255,255,255,.12);
--red:#e21b3c;--blue:#1368ce;--yellow:#d89e00;--green:#26890c;
--gold:#f5b301;--silver:#c8d0dc;--bronze:#cd7c2f}
body{font-family:'Inter',-apple-system,sans-serif;color:var(--text);min-height:100vh;
background:radial-gradient(ellipse at 18% 12%,rgba(108,99,255,.20),transparent 55%),
radial-gradient(ellipse at 85% 85%,rgba(168,85,247,.18),transparent 55%),
radial-gradient(ellipse at 50% 50%,var(--bg2),var(--bg1) 80%);}
.shp{font-weight:900}
.opt>span{min-width:0;overflow-wrap:anywhere;word-break:break-word}
mjx-container{max-width:100%;overflow-x:auto;overflow-y:hidden}
.fade{animation:fade .35s ease}@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes drop{0%{opacity:1;transform:translateY(0) rotate(0)}100%{opacity:0;transform:translateY(90vh) rotate(540deg)}}
"""


# ─────────────────────────────────────────────
#  HOST (katta ekran)  /host/{pin}/{host_token}
# ─────────────────────────────────────────────
def _host_html(pin, host_token):
    cfg = json.dumps({"pin": pin, "tok": host_token})
    tpl = """<!DOCTYPE html><html lang="uz"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jonli Test — Host</title>
<script>window.MathJax={tex:{},options:{},startup:{typeset:false}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/mml-chtml.js" id="MathJax-script" async></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>__BASE__
.wrap{max-width:1080px;margin:0 auto;padding:20px 18px 120px;min-height:100vh;display:flex;flex-direction:column}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;font-weight:900;font-size:22px}
.brand .dot{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--neon),var(--neon2));display:grid;place-items:center;font-size:18px}
.brand b{background:linear-gradient(135deg,#c4b5fd,#f0abfc);-webkit-background-clip:text;background-clip:text;color:transparent}
.qbadge{font-size:14px;font-weight:800;color:#c4b5fd;background:rgba(108,99,255,.16);border:1px solid rgba(108,99,255,.3);padding:6px 14px;border-radius:99px}
.stage{flex:1;background:linear-gradient(160deg,#0c0d20,#131638);border:1px solid var(--gb);border-radius:20px;padding:26px;display:flex;flex-direction:column;position:relative;overflow:hidden}
/* lobby */
.pincard{background:#fff;color:#111;border-radius:16px;padding:16px 22px;display:flex;align-items:center;gap:22px;align-self:center;margin-bottom:16px;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.pincard .lab{font-size:12px;font-weight:800;color:#555;text-transform:uppercase;letter-spacing:.5px}
.pincard .pin{font-size:52px;font-weight:900;letter-spacing:6px;line-height:1}
.pincard .join{font-size:14px;color:#333;font-weight:700}
#qr{width:104px;height:104px;background:#fff;border-radius:10px;display:grid;place-items:center;overflow:hidden}
#qr img,#qr canvas{width:100%!important;height:100%!important}
.cnt{text-align:center;font-size:17px;color:var(--muted);font-weight:700;margin-bottom:14px}
.cnt b{color:#fff;font-size:26px}
.players{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;align-content:flex-start;flex:1}
.chip{display:flex;align-items:center;gap:8px;background:var(--glass);border:1px solid var(--gb);border-radius:99px;padding:7px 16px 7px 8px;font-weight:800;font-size:16px;animation:pop .3s ease}
.chip .av{font-size:22px}
.empty{margin:auto;color:var(--muted);font-weight:700;font-size:17px;text-align:center}
/* question */
.qhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.ring-wrap{position:relative;width:72px;height:72px}.ring-wrap svg{transform:rotate(-90deg)}
.ring-txt{position:absolute;inset:0;display:grid;place-items:center;font-weight:900;font-size:26px}
.alive{text-align:right;font-weight:800;color:var(--muted);font-size:15px}.alive b{display:block;color:#fff;font-size:30px}
.qtext{font-size:30px;font-weight:800;line-height:1.35;text-align:center;margin:16px 10px;flex:1;display:flex;align-items:center;justify-content:center}
.qtext img{max-height:240px;max-width:100%;border-radius:10px;background:#fff;padding:6px}
.opts{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.opt{display:flex;align-items:center;gap:14px;border-radius:14px;padding:20px 22px;font-weight:800;font-size:22px;color:#fff;min-height:74px}
.opt img{max-height:60px;background:#fff;border-radius:6px;padding:3px}
.opt.red{background:var(--red)}.opt.blue{background:var(--blue)}.opt.yellow{background:var(--yellow)}.opt.green{background:var(--green)}
.opt.dim{opacity:.3}.opt.win{outline:5px solid #fff;box-shadow:0 0 0 4px rgba(255,255,255,.25);transform:scale(1.02)}
.opt .mk{margin-left:auto;font-size:26px;font-weight:900}
/* reveal */
.rev-h{text-align:center;font-size:24px;font-weight:800;margin-bottom:14px}.rev-h b{color:#34d399}
.bars{display:flex;align-items:flex-end;justify-content:center;gap:26px;height:170px;margin:6px 0 16px}
.bar{width:60px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.bar .fill{width:100%;border-radius:8px 8px 0 0;color:#fff;font-weight:900;text-align:center;padding-top:5px;transition:height .8s cubic-bezier(.4,0,.2,1);height:0;min-height:2px}
.bar.red .fill{background:var(--red)}.bar.blue .fill{background:var(--blue)}.bar.yellow .fill{background:var(--yellow)}.bar.green .fill{background:var(--green)}
.bar .s{margin-top:8px;font-size:22px}
/* board */
.btitle{text-align:center;font-size:24px;font-weight:900;margin-bottom:18px}
.row{display:flex;align-items:center;gap:14px;background:var(--glass);border:1px solid var(--gb);border-radius:14px;padding:14px 18px;margin-bottom:11px;font-weight:800;animation:pop .35s ease backwards}
.row .rk{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,var(--neon),var(--neon2));display:grid;place-items:center;font-weight:900;font-size:16px}
.row .av{font-size:28px}.row .nm{flex:1;font-size:19px}.row .sc{font-size:20px;font-weight:900}
/* podium */
.pod-t{text-align:center;font-size:30px;font-weight:900;margin:6px 0}
.pod-s{text-align:center;color:var(--muted);font-weight:700;margin-bottom:auto}
.podium{display:flex;align-items:flex-end;justify-content:center;gap:20px;margin-top:16px}
.pod{display:flex;flex-direction:column;align-items:center;width:150px}
.pod .av{font-size:56px;margin-bottom:8px;animation:bob 2s ease-in-out infinite}
.pod .pil{width:100%;border-radius:14px 14px 0 0;background:linear-gradient(180deg,rgba(108,99,255,.5),rgba(108,99,255,.14));border:1px solid var(--gb);border-bottom:none;display:flex;flex-direction:column;align-items:center;padding:16px 8px 20px}
.pod .med{width:44px;height:44px;border-radius:11px;display:grid;place-items:center;font-weight:900;font-size:20px;color:#1a1a1a;margin-bottom:10px}
.pod.p1 .med{background:var(--gold)}.pod.p2 .med{background:var(--silver)}.pod.p3 .med{background:var(--bronze)}
.pod .nm{font-weight:900;font-size:19px}.pod .sc{color:var(--muted);font-weight:800}
.pod.p1 .pil{height:200px}.pod.p2 .pil{height:150px}.pod.p3 .pil{height:118px}
.confetti{position:absolute;top:-12px;width:11px;height:16px;border-radius:2px;pointer-events:none}
/* control bar */
.ctrl{position:fixed;left:0;right:0;bottom:0;background:rgba(8,9,20,.92);backdrop-filter:blur(14px);border-top:1px solid var(--gb);padding:14px 18px;display:flex;align-items:center;justify-content:center;gap:16px;z-index:20}
.dots{display:flex;gap:6px}.dots .d{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.18)}
.dots .d.on{background:var(--neon);width:26px;border-radius:99px;box-shadow:0 0 10px var(--neon)}
.cbtn{background:linear-gradient(135deg,var(--neon),var(--neon2));border:none;color:#fff;font-weight:800;font-size:17px;padding:13px 30px;border-radius:99px;cursor:pointer;font-family:inherit}
.cbtn.ghost{background:var(--glass);border:1px solid var(--gb)}
.cbtn:disabled{opacity:.4;cursor:default}
@media(max-width:640px){.qtext{font-size:22px}.opt{font-size:17px;padding:14px}.pincard .pin{font-size:38px}}
</style></head><body>
<div class="wrap">
  <div class="top">
    <div class="brand"><span class="dot">⚡</span>Jonli <b>Test!</b></div>
    <div class="qbadge" id="qbadge">Lobby</div>
  </div>
  <div class="stage" id="stage"><div class="empty">Yuklanmoqda…</div></div>
</div>
<div class="ctrl">
  <div class="dots" id="dots"></div>
  <button class="cbtn" id="primary" onclick="doPrimary()">…</button>
</div>
<script>
const CFG=__CFG__;
const SHAPES=['▲','◆','●','■'], COLORS=['red','blue','yellow','green'];
const STATES=['lobby','question','reveal','scoreboard','ended'];
let last=null, autoReveal=false, confDone=false, qrDone=false;

async function poll(){
  try{
    const r=await fetch('/live/api/hstate?pin='+CFG.pin+'&tok='+encodeURIComponent(CFG.tok));
    if(!r.ok){return;}
    const d=await r.json(); render(d);
  }catch(e){}
}
async function act(action){
  autoReveal=false;
  try{await fetch('/live/api/host',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({tok:CFG.tok,action:action})});}catch(e){}
  poll();
}
function doPrimary(){
  if(!last)return; const s=last.state;
  if(s==='lobby')act('start');
  else if(s==='question')act('reveal');
  else if(s==='reveal')act('scoreboard');
  else if(s==='scoreboard')act('next');
}
function setDots(i){const el=document.getElementById('dots');el.innerHTML='';
  for(let k=0;k<5;k++){const d=document.createElement('div');d.className='d'+(k===i?' on':'');el.appendChild(d);}}
function typeset(){if(window.MathJax&&MathJax.typesetPromise)MathJax.typesetPromise([document.getElementById('stage')]).catch(()=>{});}

function render(d){
  if(d.error)return;
  last=d; const st=document.getElementById('stage'); const s=d.state;
  document.getElementById('qbadge').textContent = (s==='question'||s==='reveal')?('Savol '+d.q_number+'/'+d.total):
     (s==='lobby'?'Lobby':(s==='ended'?'Yakun':'Reyting'));
  setDots(STATES.indexOf(s));
  const pb=document.getElementById('primary');
  pb.style.display='';
  if(s==='lobby'){pb.textContent=(d.players_n>0?'Boshlash ▶':'O\\'quvchilarni kuting…');pb.disabled=d.players_n===0;}
  else if(s==='question'){pb.textContent='Javobni ochish ▶';pb.disabled=false;}
  else if(s==='reveal'){pb.textContent='Reyting ▶';pb.disabled=false;}
  else if(s==='scoreboard'){pb.textContent=(d.idx+1<d.total)?'Keyingi savol ▶':'Yakuniy natija 🏆';pb.disabled=false;}
  else{pb.style.display='none';}

  if(s==='lobby')renderLobby(d,st);
  else if(s==='question')renderQuestion(d,st);
  else if(s==='reveal')renderReveal(d,st);
  else if(s==='scoreboard')renderBoard(d,st);
  else if(s==='ended')renderPodium(d,st);
}

function renderLobby(d,st){
  const url=CFG.joinurl;
  const qrurl=CFG.joinurl+'?pin='+d.pin;
  const chips=(d.players||[]).map(p=>'<div class="chip"><span class="av">'+p.avatar+'</span>'+esc(p.name)+'</div>').join('');
  st.innerHTML=
   '<div class="pincard"><div><div class="lab">Qo\\'shilish uchun</div>'+
   '<div class="pin">'+d.pin.replace(/(\\d{3})(\\d{3})/,'$1 $2')+'</div>'+
   '<div class="join">'+esc(url.replace(/^https?:\\/\\//,''))+'</div></div><div id="qr"></div></div>'+
   '<div class="cnt"><b>'+d.players_n+'</b> o\\'quvchi qo\\'shildi</div>'+
   '<div class="players">'+(chips||'<div class="empty">Birinchi o\\'quvchini kutmoqdamiz…</div>')+'</div>';
  if(!qrDone){try{new QRCode(document.getElementById('qr'),{text:qrurl,width:104,height:104,correctLevel:QRCode.CorrectLevel.M});qrDone=true;}catch(e){}}
}

function optTile(html,i,cls,mark){
  return '<div class="opt '+COLORS[i]+(cls||'')+'"><span class="shp">'+SHAPES[i]+'</span><span>'+html+'</span>'+(mark?'<span class="mk">'+mark+'</span>':'')+'</div>';
}
function renderQuestion(d,st){
  const n=d.n_opts||4;
  let opts='';for(let i=0;i<n;i++)opts+=optTile(d.opts_html[i],i,'','');
  const per=d.per_q_time||20, rem=d.remaining!=null?d.remaining:per;
  const C=150.8, off=C*(1-rem/per);
  const col=rem<=5?'#ef4444':(rem<=10?'#f59e0b':'#6c63ff');
  st.innerHTML=
   '<div class="qhead"><div class="qbadge">Savol '+d.q_number+'/'+d.total+'</div>'+
   '<div class="ring-wrap"><svg width="72" height="72"><circle cx="36" cy="36" r="24" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="6"/>'+
   '<circle cx="36" cy="36" r="24" fill="none" stroke="'+col+'" stroke-width="6" stroke-linecap="round" stroke-dasharray="150.8" stroke-dashoffset="'+off+'" style="transition:stroke-dashoffset 1s linear,stroke .5s"/></svg>'+
   '<div class="ring-txt">'+rem+'</div></div>'+
   '<div class="alive"><b>'+d.answered+'</b>javob</div></div>'+
   '<div class="qtext">'+d.q_html+'</div><div class="opts">'+opts+'</div>';
  typeset();
  if(rem<=0 && !autoReveal){autoReveal=true;act('reveal');}
}
function renderReveal(d,st){
  const n=d.n_opts||4, cor=d.correct, mx=Math.max(1,...d.counts);
  let bars='';for(let i=0;i<n;i++){const h=Math.round(d.counts[i]/mx*100);
    bars+='<div class="bar '+COLORS[i]+'"><div class="fill" data-h="'+h+'">'+d.counts[i]+'</div><div class="s">'+SHAPES[i]+'</div></div>';}
  let opts='';for(let i=0;i<n;i++)opts+=optTile(d.opts_html[i],i,i===cor?' win':' dim',i===cor?'✓':'✕');
  st.innerHTML='<div class="rev-h">To\\'g\\'ri javob: <b>'+SHAPES[cor]+'</b></div>'+
   '<div class="bars">'+bars+'</div><div class="opts">'+opts+'</div>';
  typeset();
  requestAnimationFrame(()=>{st.querySelectorAll('.fill').forEach(f=>f.style.height=f.dataset.h+'%');});
}
function renderBoard(d,st){
  const rows=(d.scoreboard||[]).map((p,i)=>
   '<div class="row" style="animation-delay:'+(i*.06)+'s"><div class="rk">'+(i+1)+'</div>'+
   '<div class="av">'+p.avatar+'</div><div class="nm">'+esc(p.name)+'</div><div class="sc">'+p.score+'</div></div>').join('');
  st.innerHTML='<div class="btitle">🏆 Reyting</div>'+(rows||'<div class="empty">—</div>');
}
function renderPodium(d,st){
  const p=d.podium||[]; const slot=(x,cls,pos)=> x?
   '<div class="pod '+cls+'"><div class="av">'+x.avatar+'</div><div class="pil"><div class="med">'+pos+'</div>'+
   '<div class="nm">'+esc(x.name)+'</div><div class="sc">'+x.score+'</div></div></div>':'';
  st.innerHTML='<div class="pod-t">🎉 Tabriklaymiz!</div><div class="pod-s">Eng ko\\'p ball to\\'plaganlar</div>'+
   '<div class="podium">'+slot(p[1],'p2',2)+slot(p[0],'p1',1)+slot(p[2],'p3',3)+'</div>';
  if(!confDone){confDone=true;confetti(st);}
}
function confetti(st){const cols=['#f5b301','#6c63ff','#e21b3c','#26890c','#1368ce','#a855f7'];
  for(let i=0;i<50;i++){const c=document.createElement('div');c.className='confetti';
    c.style.left=Math.random()*100+'%';c.style.background=cols[i%cols.length];
    c.style.animation='drop '+(1.8+Math.random()*1.6)+'s linear '+(Math.random()*.6)+'s forwards';st.appendChild(c);}}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

CFG.joinurl=location.origin+'/join';
poll();setInterval(poll,1000);
</script></body></html>"""
    return tpl.replace("__BASE__", _LIVE_BASE).replace("__CFG__", cfg)


# ─────────────────────────────────────────────
#  O'QUVCHI (telefon)  /join
# ─────────────────────────────────────────────
def _player_html():
    tpl = """<!DOCTYPE html><html lang="uz"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Jonli Test</title>
<style>__BASE__
.app{max-width:460px;margin:0 auto;min-height:100vh;padding:18px 16px;display:flex;flex-direction:column}
.brand{text-align:center;font-weight:900;font-size:30px;margin:18px 0 22px}
.brand .dot{display:inline-grid;place-items:center;width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,var(--neon),var(--neon2));vertical-align:middle;margin-right:8px}
.brand b{background:linear-gradient(135deg,#c4b5fd,#f0abfc);-webkit-background-clip:text;background-clip:text;color:transparent}
.card{background:var(--glass);border:1px solid var(--gb);border-radius:18px;padding:20px;display:flex;flex-direction:column;gap:12px}
input{background:#fff;color:#111;border:none;border-radius:12px;padding:15px 16px;font-size:17px;font-weight:700;font-family:inherit;text-align:center;width:100%}
input::placeholder{color:#9aa}
.pinput{letter-spacing:5px;font-size:24px;font-weight:900}
.btn{background:linear-gradient(135deg,var(--neon),var(--neon2));border:none;color:#fff;font-weight:800;font-size:18px;padding:15px;border-radius:12px;cursor:pointer;font-family:inherit;width:100%}
.btn:disabled{opacity:.5}
.err{color:#fca5a5;font-weight:700;font-size:14px;text-align:center;min-height:18px}
.hint{color:var(--muted);font-size:14px;font-weight:600;text-align:center;line-height:1.6}
.view{flex:1;display:flex;flex-direction:column}
.center{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:12px}
.av{font-size:64px;animation:bob 2.4s ease-in-out infinite}
.you{font-weight:900;font-size:22px}
.quad{flex:1;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:12px;min-height:60vh}
.pad{border:none;border-radius:18px;cursor:pointer;display:grid;place-items:center;color:#fff;font-size:46px;transition:transform .1s;font-weight:900}
.pad:active{transform:scale(.94)}.pad:disabled{opacity:.4}
.pad.red{background:var(--red)}.pad.blue{background:var(--blue)}.pad.yellow{background:var(--yellow)}.pad.green{background:var(--green)}
.toplab{text-align:center;font-size:14px;color:var(--muted);font-weight:700;margin-bottom:10px}
.toplab b{color:#fff}
.result{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:8px;border-radius:20px;margin:6px}
.result.good{background:rgba(38,137,12,.18);border:1px solid rgba(52,211,153,.4)}
.result.bad{background:rgba(226,27,60,.14);border:1px solid rgba(226,27,60,.4)}
.result .big{font-size:64px}.result .ttl{font-size:28px;font-weight:900}
.result .pts{font-size:20px;font-weight:800}.result.good .pts{color:#34d399}
.result .rk{font-size:15px;color:var(--muted);font-weight:800;margin-top:6px}
.medal{font-size:70px}
</style></head><body>
<div class="app">
  <div class="brand"><span class="dot">⚡</span>Jonli <b>Test!</b></div>
  <div class="view" id="view"></div>
</div>
<script>
const SHAPES=['▲','◆','●','■'],COLORS=['red','blue','yellow','green'];
let sess=null, myChoice=null, lastState=null, poller=null;
try{sess=JSON.parse(localStorage.getItem('jt_sess')||'null');}catch(e){}

const view=document.getElementById('view');
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

function showJoin(msg){
  stopPoll();
  view.innerHTML=
   '<div class="card"><input id="pin" class="pinput" inputmode="numeric" maxlength="6" placeholder="PIN kod">'+
   '<input id="nm" maxlength="20" placeholder="Ismingiz">'+
   '<div class="err" id="err">'+(msg||'')+'</div>'+
   '<button class="btn" id="jbtn">Kirish</button></div>'+
   '<div class="center" style="flex:0;margin-top:18px"><div class="hint">O\\'qituvchi ekranidagi PIN kodni va ismingizni kiriting</div></div>';
  document.getElementById('jbtn').onclick=join;
  document.getElementById('nm').addEventListener('keydown',e=>{if(e.key==='Enter')join();});
  const pref=(new URLSearchParams(location.search).get('pin')||'').replace(/\\D/g,'').slice(0,6);
  if(pref){document.getElementById('pin').value=pref;setTimeout(()=>document.getElementById('nm').focus(),50);}
}
async function join(){
  const pin=(document.getElementById('pin').value||'').trim();
  const name=(document.getElementById('nm').value||'').trim();
  const err=document.getElementById('err');
  if(pin.length<4){err.textContent='PIN kodni kiriting';return;}
  if(!name){err.textContent='Ismingizni yozing';return;}
  document.getElementById('jbtn').disabled=true;
  try{
    const r=await fetch('/live/api/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin,name})});
    const d=await r.json();
    if(d.error){err.textContent=d.error==='notfound'?'Bunday o\\'yin yo\\'q':(d.error==='started'?'O\\'yin allaqachon boshlangan':'Xatolik');document.getElementById('jbtn').disabled=false;return;}
    sess=d;localStorage.setItem('jt_sess',JSON.stringify(d));myChoice=null;startPoll();
  }catch(e){err.textContent='Ulanish xatosi';document.getElementById('jbtn').disabled=false;}
}
function leave(){localStorage.removeItem('jt_sess');sess=null;showJoin('');}

function startPoll(){stopPoll();poll();poller=setInterval(poll,1000);}
function stopPoll(){if(poller){clearInterval(poller);poller=null;}}
async function poll(){
  if(!sess)return;
  try{
    const r=await fetch('/live/api/pstate?pin='+sess.pin+'&pid='+sess.player_id+'&tok='+encodeURIComponent(sess.token));
    const d=await r.json();render(d);
  }catch(e){}
}
async function answer(i){
  if(myChoice!=null)return;myChoice=i;renderAnswered();
  try{await fetch('/live/api/answer',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({pin:sess.pin,pid:sess.player_id,tok:sess.token,choice:i})});}catch(e){}
}

function render(d){
  if(!d||d.state==='gone'){leave();return;}
  if(d.state!==lastState){myChoiceReset(d);}
  lastState=d.state;
  if(d.state==='lobby')renderWait(d);
  else if(d.state==='question'){ if(d.answered||myChoice!=null){myChoice=d.my_choice!=null?d.my_choice:myChoice;renderAnswered();} else renderPads(d);}
  else if(d.state==='reveal'||d.state==='scoreboard')renderResult(d);
  else if(d.state==='ended')renderEnd(d);
}
function myChoiceReset(d){ if(d.state==='question'){ myChoice = d.my_choice!=null?d.my_choice:null; } }

function renderWait(d){
  view.innerHTML='<div class="center"><div class="av">'+d.avatar+'</div><div class="you">'+esc(d.name)+'</div>'+
   '<div class="hint">Siz o\\'yindasiz! 🎉<br>Katta ekranga qarang —<br>o\\'yin boshlanishini kuting.</div></div>';
}
function renderPads(d){
  const n=d.n_opts||4;let pads='';
  for(let i=0;i<n;i++)pads+='<button class="pad '+COLORS[i]+'" onclick="answer('+i+')">'+SHAPES[i]+'</button>';
  view.innerHTML='<div class="toplab">Savol ekranda 👆 · javob rangini bosing · <b>'+(d.remaining!=null?d.remaining+'s':'')+'</b></div>'+
   '<div class="quad">'+pads+'</div>';
}
function renderAnswered(){
  const sh=myChoice!=null?SHAPES[myChoice]:'✓',cl=myChoice!=null?COLORS[myChoice]:'';
  view.innerHTML='<div class="center"><div class="av" style="animation:none;color:var(--'+cl+')">'+sh+'</div>'+
   '<div class="you">Javob qabul qilindi</div><div class="hint">Boshqalarni kutmoqdamiz…<br>Natija tez orada.</div></div>';
}
function renderResult(d){
  const good=d.correct;
  view.innerHTML='<div class="result '+(good?'good':'bad')+'">'+
   '<div class="big">'+(good?'✓':(d.answered?'✕':'⏱'))+'</div>'+
   '<div class="ttl">'+(good?'To\\'g\\'ri!':(d.answered?'Xato':'Ulgurmading'))+'</div>'+
   '<div class="pts">'+(good?'+'+d.points+' ball':'0 ball')+'</div>'+
   '<div class="rk">'+(d.rank?('Hozircha '+d.rank+'-o\\'rin · '+d.score+' ball'):'')+'</div></div>';
}
function renderEnd(d){
  const medals=['🥇','🥈','🥉'];const m=d.rank&&d.rank<=3?medals[d.rank-1]:'🏁';
  view.innerHTML='<div class="center"><div class="medal">'+m+'</div>'+
   '<div class="you">'+(d.rank?d.rank+'-o\\'rin!':'Yakunlandi')+'</div>'+
   '<div class="hint">'+d.score+' ball · '+esc(d.name)+'<br>Zo\\'r o\\'ynading! 👏</div>'+
   '<button class="btn" style="margin-top:10px;max-width:200px" onclick="leave()">Yangi o\\'yin</button></div>';
  stopPoll();
}

if(sess){startPoll();}else{showJoin('');}
</script></body></html>"""
    return tpl.replace("__BASE__", _LIVE_BASE)
