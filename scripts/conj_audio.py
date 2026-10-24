"""Make every form in the 10-verb conjugation reference speak when tapped.

usage: python scripts/conj_audio.py lessons/07/sarf-kamel-10-fel.html

Each form cell (td.f) plays "pronoun + form" ("ich kann", "sie können"), and the
participle line plays "er hat gekonnt". One natural edge-tts voice per verb card,
rotating between two male and two female voices. Audio is embedded as data: URIs;
the file is rewritten in place and re-running is safe.
"""
import asyncio
import base64
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_build import edge_path, edge_synth  # noqa: E402
from review_audio import VOICES  # noqa: E402

BEGIN, END = "<!--conj-audio-->", "<!--/conj-audio-->"
CARD = re.compile(r'<section class="card">.*?</section>', re.S)
ROW = re.compile(r"<tr><td class='p'>([^<]*)</td>(.*?)</tr>", re.S)
FORM = re.compile(r"<td class='f ([a-z]+)'( data-a=\"[^\"]*\")?>(.*?)</td>", re.S)
PP = re.compile(r'<p class="pp"( data-a="[^"]*")?>(.*?)</p>', re.S)
PRONOUN = {"er/sie/es": "er", "sie/Sie": "sie"}

ASSETS = BEGIN + """
<style>
td.f[data-a],p.pp[data-a]{cursor:pointer}
td.f[data-a]:hover,p.pp[data-a]:hover{outline:1px dashed var(--line);outline-offset:-2px}
td.f.on,p.pp.on{background:var(--accent-soft)}
.say-hint{font-size:.8rem;color:var(--ink3)}
@media print{.say-hint{display:none}}
</style>
<script>window.__CONJ_AUDIO=__DATA__;</script>
<script>
(function(){
  var cur=null, el=null;
  document.addEventListener('click',function(e){
    var t=e.target.closest?e.target.closest('[data-a]'):null; if(!t)return;
    var src=(window.__CONJ_AUDIO||{})[t.getAttribute('data-a')]; if(!src)return;
    if(cur){cur.pause(); if(el)el.classList.remove('on');}
    if(el===t){cur=null; el=null; return;}
    cur=new Audio(src); window.__conjAudioCur=cur; el=t; t.classList.add('on');
    cur.onended=function(){t.classList.remove('on'); cur=null; el=null;};
    cur.play().catch(function(){t.classList.remove('on');});
  });
})();
</script>
""" + END


def plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s)).replace("★", "")).strip()


def main(path):
    page = Path(path).read_text(encoding="utf-8")
    page = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), "", page, flags=re.S)
    jobs = []

    def card(m):
        mono = [v for v in VOICES if "Multilingual" not in v]  # short forms: Multilingual reads them as English
        voice = mono[card.n % len(mono)]
        card.n += 1

        def row(r):
            pron = PRONOUN.get(r.group(1).strip(), r.group(1).strip())

            def form(f):
                text = f"{pron} {plain(f.group(3))}"
                key = f"c{len(jobs)}"
                jobs.append((key, voice, text))
                return f"<td class='f {f.group(1)}' data-a=\"{key}\">{f.group(3)}</td>"

            return f"<tr><td class='p'>{r.group(1)}</td>{FORM.sub(form, r.group(2))}</tr>"

        body = ROW.sub(row, m.group(0))

        def pp(p):
            de = re.search(r'<span class="de">(.*?)</span>', p.group(2), re.S)
            if not de:
                return p.group(0)
            text = "er " + plain(de.group(1)).replace("…", "").replace("  ", " ")
            key = f"c{len(jobs)}"
            jobs.append((key, voice, re.sub(r"\s+", " ", text)))
            return f'<p class="pp" data-a="{key}">{p.group(2)}</p>'

        return PP.sub(pp, body)

    card.n = 0
    page = CARD.sub(card, page)
    if not jobs:
        sys.exit("no conjugation cards found")
    page = re.sub(r'\s*<p class="say-hint">.*?</p>', "", page)
    page = page.replace("</header>", '  <p class="say-hint">🔊 روی هر شکل بزن تا با ضمیرش تلفظ شود</p>\n</header>', 1)

    asyncio.run(edge_synth([(v, t) for _, v, t in jobs]))
    data = "{" + ",".join(
        f'"{k}":"data:audio/mpeg;base64,{base64.b64encode(edge_path(v, t).read_bytes()).decode("ascii")}"'
        for k, v, t in jobs) + "}"
    page = page.replace("</body>", ASSETS.replace("__DATA__", data) + "\n</body>", 1)
    Path(path).write_text(page, encoding="utf-8")
    print(f"{path}: {len(jobs)} clips, {Path(path).stat().st_size // 1024} KB")
    for _, v, t in jobs[:3] + jobs[18:20] + jobs[-2:]:
        print("  ", v, "|", t)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
