"""Bake TTS audio into a Friday-test page.

usage: python scripts/mock_build.py osd-b2/mock/<NNN-date>/test-src.html

Every <audio ... data-tts="German text"> in the source gets the synthesized
clip as an inline data: URI, and the data-tts attribute is removed so the
transcript is not visible in the finished page. Output: test.html next to the
source.

A clip with data-voice="de-DE-KatjaNeural" (any edge-tts voice) is spoken by
that Microsoft neural voice at normal speed — natural enough for Hören, but it
needs internet and sends the text to Microsoft. A clip without data-voice falls
back to drill.py's offline Piper voice (needs ffmpeg on PATH).
"""
import asyncio
import base64
import hashlib
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drill  # noqa: E402

AUDIO = re.compile(r'<audio\b[^>]*>')
ATTR = re.compile(r'\s(data-tts|data-voice)="([^"]*)"')
EDGE_CACHE = drill.ROOT / ".cache/tts-edge"


def edge_path(voice, text):
    key = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()
    return EDGE_CACHE / f"{key}.mp3"


async def edge_synth(jobs):
    import edge_tts
    EDGE_CACHE.mkdir(parents=True, exist_ok=True)
    for voice, text in jobs:
        out = edge_path(voice, text)
        if not out.exists():
            await edge_tts.Communicate(text, voice).save(str(out))


def main(src_path):
    src = Path(src_path)
    page = src.read_text(encoding="utf-8")
    clips = []
    for tag in AUDIO.findall(page):
        attrs = {k: html.unescape(v) for k, v in ATTR.findall(tag)}
        if "data-tts" in attrs:
            clips.append((tag, attrs["data-tts"], attrs.get("data-voice")))
    if not clips:
        sys.exit(f"no data-tts clips in {src}")

    asyncio.run(edge_synth([(v, t) for _, t, v in clips if v]))
    drill.synth_batch([t for _, t, v in clips if not v])

    for tag, text, voice in clips:
        if voice:
            uri = "data:audio/mpeg;base64," + base64.b64encode(edge_path(voice, text).read_bytes()).decode("ascii")
        else:
            uri = drill.audio_uri(text)
        page = page.replace(tag, ATTR.sub("", tag)[:-1] + f' src="{uri}">', 1)

    out = src.with_name("test.html")
    out.write_text(page, encoding="utf-8")
    voices = sorted({v or "piper" for _, _, v in clips})
    print(f"{out}  ({len(clips)} clips: {', '.join(voices)}; {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
