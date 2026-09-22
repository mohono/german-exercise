#!/usr/bin/env python3
"""Build and verify German TED-Ed drill pages from a compact text source.

  python3 scripts/drill.py build sources/<NNN-Slug>.txt   # writes texts/<NNN-Slug>.html (overwrites)
  python3 scripts/drill.py check sources/<NNN-Slug>.txt   # verifies source, transcript match and the built HTML

Source format (blocks separated by a blank line; the first block is the header):

  video: <videoId>
  fa-title: <Persian title>

  de: <one German unit, exactly as in transcripts/<videoId>.txt>
  fa: <natural Persian translation>
  +para                                  (optional: this unit starts a new paragraph)
  - <word> | <meaning> | <grammar note, optional>
  - ...                                  (one line per word of `de`, in order)
  * <note in Persian, may contain <de>…</de>>   (optional, repeatable)

`build` also synthesizes real German audio for every unique word and every full
sentence with Piper TTS (see PIPER_MODEL below), caches it under .cache/tts/,
and inlines it as base64 into the built HTML so each page stays a single file.
"""
import base64, hashlib, json, re, subprocess, sys, tempfile, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / ".claude/skills/teded-german-drill/assets/drill-template.html"
MARKER = "\n];\n\n/* ══"
FA = re.compile(r"[؀-ۿ]")

PIPER_MODEL = Path.home() / ".cache/piper-voices/de_DE-thorsten-medium.onnx"
AUDIO_CACHE = ROOT / ".cache/tts"


def tokens(de):
    """Whitespace tokens that contain a letter or digit, stripped of edge punctuation."""
    out = []
    for t in de.split():
        if any(c.isalnum() for c in t):
            out.append(re.sub(r"^\W+|\W+$", "", t))
    return out


def parse(path):
    text = Path(path).read_text(encoding="utf-8")
    blocks = [b for b in re.split(r"\n\s*\n", text.strip("\n")) if b.strip()]
    head = {}
    for line in blocks[0].splitlines():
        k, _, v = line.partition(":")
        head[k.strip()] = v.strip()
    items, errs = [], []
    for n, b in enumerate(blocks[1:], 1):
        it = {"de": None, "fa": None, "words": [], "notes": []}
        for line in b.splitlines():
            if line.startswith("de:"):
                it["de"] = line[3:].strip()
            elif line.startswith("fa:"):
                it["fa"] = line[3:].strip()
            elif line.strip() == "+para":
                it["newPara"] = True
            elif line.startswith("- "):
                f = [x.strip() for x in line[2:].split("|")]
                if len(f) not in (2, 3):
                    errs.append(f"unit {n}: word line needs 2 or 3 '|' fields: {line[:70]!r}")
                    continue
                w = {"w": f[0], "m": f[1]}
                if len(f) == 3 and f[2]:
                    w["g"] = f[2]
                it["words"].append(w)
            elif line.startswith("* "):
                it["notes"].append(line[2:].strip())
            else:
                errs.append(f"unit {n}: unrecognised line {line[:70]!r}")
        if not it["notes"]:
            del it["notes"]
        items.append(it)
    return head, items, errs


def validate(head, items, errs, vid):
    bad = list(errs)
    if head.get("video") != vid:
        bad.append(f"header video is {head.get('video')!r}, expected {vid!r}")
    if not FA.search(head.get("fa-title", "")):
        bad.append("fa-title is missing or has no Persian letters")
    for n, it in enumerate(items, 1):
        if not it["de"] or not it["fa"]:
            bad.append(f"unit {n}: needs both de: and fa:")
            continue
        if not FA.search(it["fa"]):
            bad.append(f"unit {n}: fa has no Persian letters")
        want, got = tokens(it["de"]), [w["w"] for w in it["words"]]
        if want != got:
            i = next((k for k, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
            bad.append(f"unit {n} ({it['de'][:40]!r}…): word list differs from the sentence at word {i + 1}: "
                       f"sentence has {want[i:i + 2]}, list has {got[i:i + 2]}")
        for w in it["words"]:
            if not FA.search(w["m"]):
                bad.append(f"unit {n}, {w['w']!r}: meaning has no Persian letters: {w['m']!r}")
        for s in it.get("notes", []):
            if s.count("<de>") != s.count("</de>"):
                bad.append(f"unit {n}: unbalanced <de> tags in a note")
    got = " ".join(it["de"] or "" for it in items)
    want = (ROOT / "transcripts" / f"{vid}.txt").read_text(encoding="utf-8").strip()
    if got != want:
        i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
        bad.append("German units differ from the transcript at char "
                   f"{i}:\n  units:      …{got[max(0, i - 50):i + 50]!r}\n  transcript: …{want[max(0, i - 50):i + 50]!r}")
    return bad


def _load_voice():
    from piper import PiperVoice
    if not PIPER_MODEL.exists():
        sys.exit(f"missing Piper voice model: {PIPER_MODEL}\n"
                 "download it once (see SKILL.md setup) before building.")
    return PiperVoice.load(str(PIPER_MODEL))


def _cache_key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def synth_batch(texts):
    """Ensure every text in `texts` is cached as Opus, loading the Piper voice at most once."""
    pending = {key: t for t in texts if not (AUDIO_CACHE / f"{(key := _cache_key(t))}.opus").exists()}
    if not pending:
        return
    voice = _load_voice()
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        for key, text in pending.items():
            wav_path = Path(td) / f"{key}.wav"
            with wave.open(str(wav_path), "wb") as wav_file:
                params_set = False
                for chunk in voice.synthesize(text):
                    if not params_set:
                        wav_file.setframerate(chunk.sample_rate)
                        wav_file.setsampwidth(chunk.sample_width)
                        wav_file.setnchannels(chunk.sample_channels)
                        params_set = True
                    wav_file.writeframes(chunk.audio_int16_bytes)
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                                 "-ac", "1", "-c:a", "libopus", "-b:a", "32k",
                                 str(AUDIO_CACHE / f"{key}.opus")], capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"ffmpeg failed for {text!r}: {r.stderr.strip()[:400]}")


def audio_uri(text):
    cache = AUDIO_CACHE / f"{_cache_key(text)}.opus"
    data = base64.b64encode(cache.read_bytes()).decode("ascii")
    return f"data:audio/ogg;base64,{data}"


def render(head, items):
    title = head["fa-title"]
    if any(c in title for c in '"<&'):
        sys.exit('fa-title must not contain " < &')
    vid = head["video"]

    word_texts = {}
    for it in items:
        for w in it["words"]:
            key = w["w"].lower()
            w["ak"] = key
            word_texts.setdefault(key, w["w"])
    synth_batch(list(word_texts.values()) + [it["de"] for it in items])
    word_audio_map = {key: audio_uri(text) for key, text in word_texts.items()}
    for it in items:
        it["sa"] = audio_uri(it["de"])

    html = TEMPLATE.read_text(encoding="utf-8")
    for old, new in [
        ("<title>آلمانی با TED-Ed</title>", f"<title>{title}</title>"),
        ('const TITLE     = "آلمانی با TED-Ed";', f'const TITLE     = "{title}";'),
        ('const STORE_KEY = "german-VIDEOID";', f'const STORE_KEY = "german-{vid}";'),
        ('const SOURCE    = "";', f'const SOURCE    = "https://www.youtube.com/watch?v={vid}";'),
        ('const WORD_AUDIO = {};', f'const WORD_AUDIO = {json.dumps(word_audio_map, ensure_ascii=False)};'),
    ]:
        assert html.count(old) == 1, old
        html = html.replace(old, new)
    lines = [json.dumps(it, ensure_ascii=False).replace("</", "<\\/") for it in items]
    block = f'  {{ title: {json.dumps(title, ensure_ascii=False)}, items: [\n    ' + ",\n    ".join(lines) + "\n  ] }"
    assert html.count(MARKER) == 1
    head_, tail = html.split(MARKER)
    assert head_.rstrip().endswith("["), "TEXTS is not empty in the template"
    return head_ + "\n" + block + MARKER + tail


def load(src):
    src = Path(src)
    head, items, errs = parse(src)
    return src, head, items, errs


def build(src):
    src, head, items, errs = load(src)
    if errs:
        sys.exit("\n".join(errs))
    out = ROOT / "texts" / (src.stem + ".html")
    out.write_text(render(head, items), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


def check(src):
    src, head, items, errs = load(src)
    vid = head.get("video", "")
    bad = validate(head, items, errs, vid)

    others = [p.name for p in (ROOT / "sources").glob("*.txt")
              if p.resolve() != src.resolve() and re.search(rf"^video:\s*{re.escape(vid)}\s*$", p.read_text(encoding="utf-8"), re.M)]
    if others:
        bad.append(f"video {vid} is already used by {others}")

    out = ROOT / "texts" / (src.stem + ".html")
    if not out.exists():
        bad.append(f"{out.relative_to(ROOT)} is missing; run build")
    elif not bad:
        s = out.read_text(encoding="utf-8")
        if s != render(head, items):
            bad.append(f"{out.relative_to(ROOT)} is out of date (source or template changed); run build")
        script = re.search(r"<script>(.*?)</script>", s, re.S).group(1)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(script)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        if r.returncode:
            bad.append("JS syntax error:\n" + r.stderr.strip()[:600])

    if bad:
        print("FAILED")
        for b in bad:
            print(" -", b)
        sys.exit(1)
    nw = sum(len(it["words"]) for it in items)
    nn = sum(len(it.get("notes", [])) for it in items)
    print(f"OK: {len(items)} units, {nw} word rows, {nn} notes, key german-{vid}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["build"] and len(a) == 2:
        build(a[1])
    elif a[:1] == ["check"] and len(a) == 2:
        check(a[1])
    else:
        sys.exit(__doc__)
