"""Add natural edge-tts audio to a lesson review file.

usage: python scripts/review_audio.py lessons/09/review.html [more files...]

Two kinds of audio, both idempotent (re-running replaces the previous block):

1. Sentence banks: every row of a <table class="bank"> whose answer cell (td.q)
   holds German in <span class="de"> gets a 🔊 button in its first cell.
2. Tap anywhere (20 Mehr 1405, her request: «جزوه‌ی ساکت به دردم نمی‌خوره»):
   every other <span class="de"> in the page speaks when tapped. Never spoken:
   wrong forms (inside .no, in a «نوشتم»/«جزوه» column, or holding .x/.m marks),
   unpronounceable fragments (-en, ge, ei), and spans marked class="de mute".

Voices rotate between two male and two female Microsoft neural voices at normal
speed (CLAUDE.md, «صدا»). Clips are cached in .cache/tts-edge/ and embedded as
data: URIs so the page stays a single self-contained file.

Needs internet; the German text is sent to Microsoft.
"""
import asyncio
import base64
import html
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_build import EDGE_CACHE, edge_path, edge_proxy  # noqa: E402

# male voices switched 17 Mehr 1405 at her request: Conrad/Killian sounded read-aloud; Florian (new generation) and Jonas (Austrian) natural
VOICES = ["de-DE-FlorianMultilingualNeural", "de-DE-KatjaNeural", "de-AT-JonasNeural", "de-DE-AmalaNeural"]
BEGIN, END = "<!--review-audio-->", "<!--/review-audio-->"
TABLE = re.compile(r'<table class="bank[^"]*">.*?</table>', re.S)
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td(\s[^>]*)?>(.*?)</td>", re.S)
NOTE = re.compile(r'<span class="note">.*?</span>\s*</span>|<span class="note">.*?</span>', re.S)
SAY = re.compile(r'<button class="say"[^>]*>🔊</button>')
TAG = re.compile(r"<(/?)([a-zA-Z0-9]+)([^>]*)>")
VOID = {"br", "hr", "img", "input", "meta", "link"}
WRONG_HEAD = ("نوشتم", "جزوه")  # header of a column that holds wrong forms
SHORT = {"er", "du", "es", "zu", "um", "ob", "da", "an", "in", "so", "ja", "im", "am", "wo"}

ASSETS = BEGIN + """
<style>
.say{border:1px solid var(--line);background:var(--surface2);color:var(--accent);border-radius:50%;
  width:1.9em;height:1.9em;padding:0;margin-inline-start:.35em;cursor:pointer;font-size:.8rem;line-height:1;vertical-align:middle}
.say.on{background:var(--accent);color:var(--surface)}
.de[data-a]{cursor:pointer}
.de[data-a]:hover{box-shadow:0 0 0 1px var(--accent)}
.de[data-a].on{background:var(--accent);color:var(--surface)}
.de[data-a].on *{color:inherit;border-color:currentColor}
</style>
<script>window.__REVIEW_AUDIO=__DATA__;</script>
<script>
(function(){
  var cur=null, btn=null;
  document.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('button.say, .de[data-a]'):null; if(!b)return;
    if(b.tagName==='BUTTON')e.stopPropagation();
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


def speakable(inner):
    """Spoken text of a free-standing German span, or None if it should stay silent."""
    if re.search(r'class="(x|m)"', inner):
        return None
    text = html.unescape(re.sub(r"<[^>]+>", "", inner))
    if re.search(r"[+_/\\]|\.html|\.txt|[؀-ۿ]", text.replace(" / ", " , ")):
        return None
    text = re.sub(r"\s*(·|⟵|↔|≠|=| / )\s*", ", ", text.replace("…", " "))
    text = re.sub(r"\s+", " ", text).strip(" ,;–—")
    if not text or text.startswith("-") or text.endswith("-") or "·" in text:
        return None
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+", text)
    if not words or not (any(len(w) >= 3 for w in words) or all(w.lower() in SHORT for w in words)):
        return None
    return text


def tap_spans(page, first_key):
    """Give every speakable German span outside the banks a data-a key. Returns (page, jobs)."""
    out, jobs, keys = [], [], {}
    stack = []            # (tag, classes)
    tables = []           # per open table: {"wrong": set(), "col": int, "bank": bool}
    pos, skip_until = 0, None
    for m in TAG.finditer(page):
        close, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if skip_until:
            if close and tag == skip_until:
                skip_until = None
            continue
        if tag in ("script", "style") and not close:
            skip_until = tag
            continue
        if tag in VOID or attrs.rstrip().endswith("/"):
            continue
        if close:
            while stack and stack[-1][0] != tag:
                stack.pop()
            if stack:
                stack.pop()
            if tag == "table" and tables:
                tables.pop()
            continue
        cls = (re.search(r'class="([^"]*)"', attrs) or [None, ""])[1].split()
        if tag == "table":
            tables.append({"wrong": set(), "col": -1, "bank": "bank" in cls})
        elif tag == "tr" and tables:
            tables[-1]["col"] = -1
        elif tag in ("td", "th") and tables:
            t = tables[-1]
            t["col"] += 1
            if tag == "th":
                end = page.find("</th>", m.end())
                head = re.sub(r"<[^>]+>", "", page[m.end():end])
                if any(w in head for w in WRONG_HEAD):
                    t["wrong"].add(t["col"])
        stack.append((tag, cls))
        if tag != "span" or "de" not in cls:
            continue
        # matching </span> for this German span
        depth, end = 1, None
        for n in re.finditer(r"<(/?)span\b[^>]*>", page[m.end():]):
            depth += -1 if n.group(1) else 1
            if depth == 0:
                end = m.end() + n.start()
                break
        if end is None or "mute" in cls:
            continue
        in_no = any("no" in c for _, c in stack)
        cell = next(((t, c) for t, c in reversed(stack) if t in ("td", "th")), None)
        in_wrong = bool(tables) and cell is not None and tables[-1]["col"] in tables[-1]["wrong"]
        in_bank_q = bool(tables) and tables[-1]["bank"] and cell is not None and "q" in cell[1]
        if in_no or in_wrong or in_bank_q or any(t == "span" and "de" in c for t, c in stack[:-1]):
            continue
        text = speakable(page[m.end():end])
        if not text:
            continue
        if text not in keys:
            keys[text] = f"k{first_key + len(keys)}"
            jobs.append((keys[text], VOICES[zlib.crc32(text.encode("utf-8")) % len(VOICES)], text))
        out.append(page[pos:m.start()])
        out.append(f'<span{attrs} data-a="{keys[text]}">')
        pos = m.end()
    out.append(page[pos:])
    return "".join(out), jobs


async def synth(jobs, workers=3):
    """Like mock_build.edge_synth, but gently concurrent — a tap-anywhere page has hundreds of clips.

    20 Mehr 1405: 8 workers on 452 clips got every request answered 403 (the service blocked the
    connection). So: few workers, a pause between requests, and stop early once the service refuses —
    the cache makes the next run pick up where this one stopped.
    """
    import edge_tts
    EDGE_CACHE.mkdir(parents=True, exist_ok=True)
    todo = sorted({(v, t) for v, t in jobs if not edge_path(v, t).exists() or edge_path(v, t).stat().st_size == 0})
    sem = asyncio.Semaphore(workers)
    state = {"ok": 0, "bad": 0, "blocked": False}

    async def one(voice, text):
        out = edge_path(voice, text)
        tmp = out.with_suffix(f".{zlib.crc32(text.encode('utf-8'))}.part")
        async with sem:
            for attempt in range(2):
                if state["blocked"]:
                    return
                try:
                    await edge_tts.Communicate(text, voice, proxy=edge_proxy()).save(str(tmp))
                    tmp.replace(out)  # atomic: an interrupted run never leaves a half-written clip in the cache
                    state["ok"] += 1
                    state["bad"] = 0
                    await asyncio.sleep(0.3)
                    return
                except Exception as e:  # noqa: BLE001 — network hiccup: retry once, then count it
                    state["bad"] += 1
                    if state["bad"] >= 6:  # six refusals in a row: the service is refusing us, stop knocking
                        if not state["blocked"]:
                            print(f"  ! service refuses requests ({str(e)[:40]}…) — stopping; re-run later")
                        state["blocked"] = True
                        return
                    await asyncio.sleep(2 + 2 * attempt)

    await asyncio.gather(*(one(v, t) for v, t in todo))
    for stray in EDGE_CACHE.glob("*.part"):
        stray.unlink(missing_ok=True)
    return state["ok"]


def process(path):
    page = Path(path).read_text(encoding="utf-8")
    page = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), "", page, flags=re.S)
    page = SAY.sub("", page)
    page = re.sub(r'(<span class="de[^"]*"[^>]*?) data-a="k\d+"', r"\1", page)

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
    page, taps = tap_spans(page, 0)
    bank = len(jobs)
    jobs += taps
    if not jobs:
        sys.exit(f"no German to speak in {path}")

    made = asyncio.run(synth([(v, t) for _, v, t in jobs]))
    missing = [t for _, v, t in jobs if not edge_path(v, t).exists()]
    # a clip that could not be made leaves no dead control behind: the span/button simply stays silent
    for k, v, t in jobs:
        if not edge_path(v, t).exists():
            page = page.replace(f' data-a="{k}">', ">") if k.startswith("k") else \
                re.sub(rf'<button class="say" data-a="{k}"[^>]*>🔊</button>', "", page)
    data = "{" + ",".join(
        f'"{k}":"data:audio/mpeg;base64,{base64.b64encode(edge_path(v, t).read_bytes()).decode("ascii")}"'
        for k, v, t in jobs if edge_path(v, t).exists()) + "}"
    page = page.replace("</body>", ASSETS.replace("__DATA__", data) + "\n</body>", 1)
    Path(path).write_text(page, encoding="utf-8")
    print(f"{path}: {bank} bank sentences + {len(taps)} tap clips ({made} new, {len(missing)} missing), "
          f"{Path(path).stat().st_size // 1024} KB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        process(p)
