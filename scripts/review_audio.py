"""Add natural edge-tts audio to the sentence banks of a lesson review file.

usage: python scripts/review_audio.py lessons/09/review.html [more files...]

Every row of a <table class="bank"> whose answer cell (td.q) holds German in
<span class="de"> gets a 🔊 button in its first cell. Voices rotate between two
male and two female Microsoft neural voices at normal speed (CLAUDE.md, «صدا»).
Clips are cached in .cache/tts-edge/ and embedded as data: URIs so the page
stays a single self-contained file. The file is rewritten in place and the
script is idempotent: re-running replaces the previous audio block.

Needs internet; the German text is sent to Microsoft.
"""
import asyncio
import base64
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_build import edge_path, edge_synth  # noqa: E402

VOICES = ["de-DE-ConradNeural", "de-DE-KatjaNeural", "de-DE-KillianNeural", "de-DE-AmalaNeural"]
BEGIN, END = "<!--review-audio-->", "<!--/review-audio-->"
TABLE = re.compile(r'<table class="bank[^"]*">.*?</table>', re.S)
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td(\s[^>]*)?>(.*?)</td>", re.S)
NOTE = re.compile(r'<span class="note">.*?</span>\s*</span>|<span class="note">.*?</span>', re.S)
SAY = re.compile(r'<button class="say"[^>]*>🔊</button>')

ASSETS = BEGIN + """
<style>
.say{border:1px solid var(--line);background:var(--surface2);color:var(--accent);border-radius:50%;
  width:1.9em;height:1.9em;padding:0;margin-inline-start:.35em;cursor:pointer;font-size:.8rem;line-height:1;vertical-align:middle}
.say.on{background:var(--accent);color:var(--surface)}
</style>
<script>window.__REVIEW_AUDIO=__DATA__;</script>
<script>
(function(){
  var cur=null, btn=null;
  document.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('button.say'):null; if(!b)return;
    e.stopPropagation();
    if(cur){cur.pause(); if(btn)btn.classList.remove('on');}
    if(btn===b){cur=null;btn=null;return;}
    var src=(window.__REVIEW_AUDIO||{})[b.getAttribute('data-a')]; if(!src)return;
    cur=new Audio(src); window.__reviewAudioCur=cur; btn=b; b.classList.add('on');
    cur.onended=function(){b.classList.remove('on'); cur=null; btn=null;};
    cur.play().catch(function(){b.classList.remove('on');});
  },true);
})();
</script>
""" + END


def german(cell_html):
    """Spoken text of an answer cell: the German spans, without side notes."""
    body = NOTE.sub("", cell_html)
    parts = re.findall(r'<span class="de[^"]*">(.*?)</span>', body, re.S)
    text = " ".join(re.sub(r"<[^>]+>", "", p) for p in parts)
    text = re.sub(r"([?!.])? / ", lambda m: (m.group(1) or ".") + " ", html.unescape(text)).strip()
    return re.sub(r"\s+", " ", text)


def process(path):
    page = Path(path).read_text(encoding="utf-8")
    page = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), "", page, flags=re.S)
    page = SAY.sub("", page)

    jobs, n = [], 0

    def fix_table(m):
        nonlocal n

        def fix_row(r):
            nonlocal n
            cells = list(CELL.finditer(r.group(1)))
            q = [c for c in cells if c.group(1) and 'class="q"' in c.group(1)]
            if not cells or not q:
                return r.group(0)
            text = german(q[0].group(2))
            if not text:
                return r.group(0)
            dv = re.search(r'data-voice="([^"]+)"', q[0].group(1))
            voice = dv.group(1) if dv else VOICES[n % len(VOICES)]  # a cell may fix its speaker (dialogues)
            key = f"a{n}"
            jobs.append((key, voice, text))
            n += 1
            first = cells[0]
            new_first = first.group(0)[: -len("</td>")] + f'<button class="say" data-a="{key}" title="{html.escape(voice)}">🔊</button></td>'
            inner = r.group(1)
            inner = inner[: first.start()] + new_first + inner[first.end():]
            return f"<tr>{inner}</tr>"

        return ROW.sub(fix_row, m.group(0))

    page = TABLE.sub(fix_table, page)
    if not jobs:
        sys.exit(f"no bank sentences in {path}")

    asyncio.run(edge_synth([(v, t) for _, v, t in jobs]))
    data = "{" + ",".join(
        f'"{k}":"data:audio/mpeg;base64,{base64.b64encode(edge_path(v, t).read_bytes()).decode("ascii")}"'
        for k, v, t in jobs) + "}"
    page = page.replace("</body>", ASSETS.replace("__DATA__", data) + "\n</body>", 1)
    Path(path).write_text(page, encoding="utf-8")
    print(f"{path}: {len(jobs)} sentences, {Path(path).stat().st_size // 1024} KB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        process(p)
