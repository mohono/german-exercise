"""Build the living past-tense verb list with audio.

usage: python scripts/verbs_build.py

Reads lessons/verbs/verbs.json and writes lessons/verbs/verbs.html: every verb
Fatemeh has learned, grouped by the five-box map, each with helper, participle
and the full Perfekt conjugation (6 pronouns). Every form speaks on tap, using
natural edge-tts voices (rotating per verb). Audio is embedded so the page is a
single file. After each lesson: add the new verbs to verbs.json and re-run.
"""
import asyncio
import base64
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_build import edge_path, edge_synth  # noqa: E402
from review_audio import VOICES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "lessons/verbs/verbs.json"
OUT = ROOT / "lessons/verbs/verbs.html"

GROUPS = [
    ("special", "⓪ ده فعل خاص", "در گفتار خودت همیشه شکل تنها (<span class=\"de\">war · hatte · konnte</span>). این شکل‌ها را فقط <b>بشناس</b> — در شنیداری، مخصوصاً اتریش، می‌آیند."),
    ("weak", "① باقاعده", "<span class=\"de\">ge</span> + ریشه + <span class=\"de\">t</span> · ریشه‌ی <span class=\"de\">d/t</span> ⟵ روغن: <span class=\"de\">gewartet</span>"),
    ("mixed", "①ب مختلط", "مثل باقاعده <span class=\"de\">ge…t</span>، ولی ریشه عوض می‌شود — حفظی"),
    ("sep", "② جداشدنی 🧱", "<span class=\"de\">ge</span> وسط: <span class=\"de\">ein·ge·kauft</span> · لگو الگوی فعل پایه را به ارث می‌برد (<span class=\"de\">kommen ⟵ angekommen</span>)"),
    ("strong", "③ قوی ⚡", "آخرش <span class=\"de\">-en</span>، مصوت گاهی عوض می‌شود — هر کدام یک بسته 🧳 · قوی‌های <span class=\"de\">ei</span>دار معمولاً ⟵ <span class=\"de\">ie</span>"),
    ("noge", "④ بدون ge 🔒", "جدانشدنی (<span class=\"de\">be · emp · ent · er · ge · miss · ver · zer</span> و <span class=\"de\">über/wieder</span> بی‌تکیه) و <span class=\"de\">-ieren</span>"),
]
PRON = [("ich", "ich"), ("du", "du"), ("er/sie/es", "er"), ("wir", "wir"), ("ihr", "ihr"), ("sie/Sie", "sie")]
AUX = {"haben": ["habe", "hast", "hat", "haben", "habt", "haben"],
       "sein": ["bin", "bist", "ist", "sind", "seid", "sind"]}

CSS = """
:root{--bg:#EDF1F5;--surface:#FFFFFF;--surface2:#F4F8FA;--ink:#10202C;--ink2:#46596B;--ink3:#71879A;--line:#CBD8E2;--line2:#E2EAF1;
--accent:#0B6E80;--accent-soft:#DAEEF2;--trap:#A63D2F;--trap-soft:#F9E7E3;--good:#1B6B4E;--good-soft:#DCF0E7;--warn:#8A6212;--warn-soft:#F7EEDA}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0A131A;--surface:#121F29;--surface2:#182935;--ink:#DCE8F0;--ink2:#9AAFBF;--ink3:#6F8697;--line:#22394A;--line2:#1B2E3C;--accent:#4FC0D4;--accent-soft:#10303A;--trap:#EE8A7B;--trap-soft:#361E1A;--good:#55C598;--good-soft:#11332A;--warn:#E0B45C;--warn-soft:#332A15}}
:root[data-theme="dark"]{--bg:#0A131A;--surface:#121F29;--surface2:#182935;--ink:#DCE8F0;--ink2:#9AAFBF;--ink3:#6F8697;--line:#22394A;--line2:#1B2E3C;--accent:#4FC0D4;--accent-soft:#10303A;--trap:#EE8A7B;--trap-soft:#361E1A;--good:#55C598;--good-soft:#11332A;--warn:#E0B45C;--warn-soft:#332A15}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Vazirmatn',system-ui,Tahoma,sans-serif;font-size:16px;line-height:1.75}
.wrap{max-width:860px;margin:0 auto;padding:26px 16px 90px}
h1{font-size:1.6rem;margin:0 0 4px;font-weight:800}
.meta{color:var(--ink2);font-size:.9rem}
.de{direction:ltr;unicode-bidi:isolate;font-family:'IBM Plex Mono',monospace;color:var(--accent);background:var(--accent-soft);padding:.05em .35em;border-radius:4px;font-weight:500;font-size:.93em}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.85rem;color:var(--ink2);margin:10px 0}
.pill{display:inline-block;border-radius:10px;padding:0 8px;font-size:.8rem;font-family:'IBM Plex Mono',monospace}
.pill.haben{background:var(--surface2);color:var(--ink2);border:1px solid var(--line)}
.pill.sein{background:var(--warn-soft);color:var(--warn);border:1px solid var(--warn);font-weight:600}
.tools{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 4px}
.tools input{flex:1;min-width:180px;font:inherit;padding:7px 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
.tools button{font:inherit;font-size:.85rem;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:18px;padding:5px 12px;cursor:pointer}
.tools button[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
section{border-top:2px solid var(--ink);margin-top:28px;padding-top:10px}
h2{font-size:1.2rem;margin:0 0 4px;font-weight:800}
h2 small{font-weight:500;color:var(--ink3);font-size:.85rem}
.rule{font-size:.92rem;color:var(--ink2);margin:0 0 8px}
.tw{border:1px solid var(--line2);border-radius:8px;background:var(--surface);overflow:hidden}
.v{display:grid;grid-template-columns:minmax(120px,1.1fr) 1.4fr 70px minmax(130px,1.2fr) 34px;align-items:center;gap:6px;padding:7px 10px;border-bottom:1px solid var(--line2);cursor:pointer}
.v:last-child{border-bottom:none}
.v.sein{background:linear-gradient(to left,var(--warn-soft),transparent 30%)}
.v .inf,.v .pp,.f .say{direction:ltr;text-align:left;font-family:'IBM Plex Mono',monospace;color:var(--accent);font-weight:600}
.v .pp{font-weight:700}
.v .fa{font-size:.92rem}
.v .fa small{display:block;color:var(--ink3);font-size:.78rem}
.tap{border-radius:5px;padding:1px 4px}
.tap:hover{background:var(--accent-soft)}
.on{background:var(--accent)!important;color:var(--surface)!important}
.chev{color:var(--ink3);text-align:center;transition:transform .15s}
.open .chev{transform:rotate(180deg)}
.conj{display:none;direction:ltr;grid-column:1/-1;background:var(--surface2);border-radius:6px;padding:8px;margin-top:4px}
.open .conj{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 10px}
.f{display:flex;gap:6px;align-items:baseline;direction:ltr;font-size:.9rem}
.f .p{color:var(--ink3);min-width:4.6em;font-family:'IBM Plex Sans',sans-serif;font-size:.82rem}
.f .say{font-weight:500;cursor:pointer}
.hidden{display:none!important}
.fab{position:fixed;bottom:16px;left:16px;z-index:9}
.fab button{font:inherit;font-size:.85rem;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:20px;padding:7px 13px;cursor:pointer}
@media (max-width:620px){.v{grid-template-columns:1fr 1fr 60px 26px}.v .fa{grid-column:1/-1;order:5}.v .pp{text-align:left}.open .conj{grid-template-columns:1fr 1fr}}
@media print{.tools,.fab{display:none}.conj{display:grid!important;grid-template-columns:repeat(3,1fr)}}
"""

JS = """
(function(){
  var cur=null, el=null, A=window.__VERB_AUDIO||{};
  function play(t){
    var src=A[t.getAttribute('data-a')]; if(!src)return;
    if(cur){cur.pause(); if(el)el.classList.remove('on');}
    if(el===t){cur=null; el=null; return;}
    cur=new Audio(src); window.__verbAudioCur=cur; el=t; t.classList.add('on');
    cur.onended=function(){t.classList.remove('on'); cur=null; el=null;};
    cur.play().catch(function(){t.classList.remove('on');});
  }
  document.addEventListener('click',function(e){
    var t=e.target.closest('[data-a]');
    if(t){e.stopPropagation(); play(t); return;}
    var v=e.target.closest('.v'); if(v) v.classList.toggle('open');
  });
  var q=document.getElementById('q'), onlySein=document.getElementById('sein'), openAll=document.getElementById('all');
  function filter(){
    var s=(q.value||'').trim().toLowerCase(), si=onlySein.getAttribute('aria-pressed')==='true';
    document.querySelectorAll('.v').forEach(function(v){
      var hit=(!s||v.getAttribute('data-k').indexOf(s)>-1)&&(!si||v.classList.contains('sein'));
      v.classList.toggle('hidden',!hit);
    });
    document.querySelectorAll('section[data-g]').forEach(function(sec){
      sec.classList.toggle('hidden',!sec.querySelector('.v:not(.hidden)'));
    });
  }
  q.addEventListener('input',filter);
  onlySein.addEventListener('click',function(){onlySein.setAttribute('aria-pressed',onlySein.getAttribute('aria-pressed')==='true'?'false':'true');filter();});
  openAll.addEventListener('click',function(){
    var on=openAll.getAttribute('aria-pressed')!=='true'; openAll.setAttribute('aria-pressed',on);
    document.querySelectorAll('.v').forEach(function(v){v.classList.toggle('open',on);});
  });
  var th=document.getElementById('theme');
  try{var t0=localStorage.getItem('verbs-theme'); if(t0)document.documentElement.setAttribute('data-theme',t0);}catch(e){}
  th.addEventListener('click',function(){
    var c=document.documentElement.getAttribute('data-theme');
    var dark=c?c==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
    var n=dark?'light':'dark'; document.documentElement.setAttribute('data-theme',n);
    try{localStorage.setItem('verbs-theme',n);}catch(e){}
  });
})();
"""


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    verbs = data["verbs"]
    jobs = []

    def clip(voice, text):
        key = f"v{len(jobs)}"
        jobs.append((key, voice, text))
        return key

    e = html.escape
    sections = []
    n = 0
    for gid, title, rule in GROUPS:
        rows = []
        for vb in [v for v in verbs if v["group"] == gid]:
            voice = VOICES[n % len(VOICES)]
            n += 1
            k_inf = clip(voice, vb["inf"])
            k_pp = clip(voice, vb["pp"])
            forms = []
            for (shown, spoken), aux in zip(PRON, AUX[vb["aux"]]):
                k = clip(voice, f"{spoken} {aux} {vb['pp']}")
                forms.append(f'<div class="f"><span class="p">{e(shown)}</span><span class="say tap" data-a="{k}">{e(aux)} {e(vb["pp"])}</span></div>')
            note = f'<small>{e(vb["note"])}</small>' if vb.get("note") else ""
            key = e(f'{vb["inf"]} {vb["pp"]} {vb["fa"]}'.lower())
            rows.append(
                f'<div class="v {vb["aux"]}" data-k="{key}">'
                f'<span class="inf"><span class="tap" data-a="{k_inf}">{e(vb["inf"])}</span></span>'
                f'<span class="fa">{e(vb["fa"])}{note}</span>'
                f'<span><span class="pill {vb["aux"]}">{vb["aux"]}</span></span>'
                f'<span class="pp"><span class="tap" data-a="{k_pp}">{e(vb["pp"])}</span></span>'
                f'<span class="chev">▾</span>'
                f'<div class="conj">{"".join(forms)}</div></div>')
        if rows:
            sections.append(f'<section data-g="{gid}"><h2>{title} <small>{len(rows)} فعل</small></h2>'
                            f'<p class="rule">{rule}</p><div class="tw">{"".join(rows)}</div></section>')

    asyncio.run(edge_synth([(v, t) for _, v, t in jobs]))
    audio = "{" + ",".join(
        f'"{k}":"data:audio/mpeg;base64,{base64.b64encode(edge_path(v, t).read_bytes()).decode("ascii")}"'
        for k, v, t in jobs) + "}"

    sein_n = sum(1 for v in verbs if v["aux"] == "sein")
    page = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>فعل‌های من — گذشته</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>🗂️ فعل‌های من — گذشته‌ی گفتاری</h1>
  <div class="meta">{len(verbs)} فعل · {sein_n} تا با <span class="de">sein</span> · به‌روز: {e(data["updated"])} · این لیست با هر درس بزرگ‌تر می‌شود</div>
  <div class="legend">
    <span><span class="pill haben">haben</span> پیش‌فرض</span>
    <span><span class="pill sein">sein</span> حرکت A⟵B یا تغییر · <span class="de">bleiben</span>/<span class="de">sein</span> حفظی</span>
    <span>🔊 روی هر شکل بزن · روی ردیف بزن ⟵ صرف کامل با ۶ ضمیر</span>
  </div>
  <div class="tools">
    <input id="q" type="search" placeholder="جستجو: آلمانی یا فارسی…" autocomplete="off">
    <button id="sein" aria-pressed="false">فقط sein‌دارها</button>
    <button id="all" aria-pressed="false">باز کردن همه</button>
  </div>
</header>
{"".join(sections)}
</div>
<div class="fab"><button id="theme">🌗</button></div>
<script>window.__VERB_AUDIO={audio};</script>
<script>{JS}</script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(verbs)} verbs, {len(jobs)} clips, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
