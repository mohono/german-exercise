"""Bake Piper TTS audio into a Friday-test page.

usage: python scripts/mock_build.py osd-b2/mock/<NNN-date>/test-src.html

Every <audio ... data-tts="German text"> in the source gets the synthesized
clip as an inline data: URI, and the data-tts attribute is removed so the
transcript is not visible in the finished page. Output: test.html next to the
source. Reuses drill.py's voice, speed and cache; needs ffmpeg on PATH.
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drill  # noqa: E402

TTS = re.compile(r'\sdata-tts="([^"]*)"')


def main(src_path):
    src = Path(src_path)
    page = src.read_text(encoding="utf-8")
    texts = [html.unescape(t) for t in TTS.findall(page)]
    if not texts:
        sys.exit(f"no data-tts clips in {src}")
    drill.synth_batch(texts)
    page = TTS.sub(lambda m: f' src="{drill.audio_uri(html.unescape(m.group(1)))}"', page)
    out = src.with_name("test.html")
    out.write_text(page, encoding="utf-8")
    print(f"{out}  ({len(texts)} clips, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
