#!/usr/bin/env python3
"""Placeholder voiceover for a board: every row's script spoken by a local TTS voice (HyperFrames'
Kokoro-82M, free, offline), one clip per row plus the whole read joined into one track.

  placeholder_vo.py <storyboard.json> [--voice am_michael] [--speed 1.0] [--gap 0.35] [--rows A-B]

Writes <project>/audio/placeholder-vo/:
  NNN_slug.wav           one clip per row (re-used when the row's text and voice are unchanged)
  placeholder-vo.wav     every row in order with --gap seconds between them
  timings.csv            row, start, end, duration — where each row sits on the joined track
and prints the rows whose graphic is shorter than the read (beat timing to fix, or a faster read).

It is a stand-in for the editor's timing and the stakeholders' first watch, never the final VO.
Needs kokoro-onnx + soundfile in the python HyperFrames uses: set HYPERFRAMES_PYTHON to a venv
that has them (the skills repo .venv does) — this script does that when it finds one.
"""
import argparse, csv, hashlib, json, os, re, subprocess, sys

HF_PKG = "hyperframes@0.8.34"
REPO_VENV = os.path.expanduser("~/Developer/projects/storyboarding-app/.venv/bin/python")


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand")]


def words(n):
    """Integer to words, US style: 22000 -> 'twenty-two thousand', 297 -> 'two hundred ninety-seven'."""
    n = int(n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" " + words(n % 100) if n % 100 else "")
    for size, name in SCALES:
        if n >= size:
            return words(n // size) + " " + name + (" " + words(n % size) if n % size else "")


def decimal_words(s):
    """'1.37' -> 'one point three seven'; '10' -> 'ten'."""
    whole, _, frac = s.replace(",", "").partition(".")
    return words(int(whole or 0)) + ("" if not frac else " point " + " ".join(ONES[int(d)] for d in frac))


def year_words(y):
    """2022 -> 'twenty twenty-two', 2005 -> 'two thousand five', 1990 -> 'nineteen ninety'."""
    hi, lo = divmod(int(y), 100)
    if hi == 20 and lo < 10:
        return "two thousand" + (" " + words(lo) if lo else "")
    return words(hi) + " " + ("hundred" if lo == 0 else ("oh " + words(lo) if lo < 10 else words(lo)))


def say_numbers(t):
    """Every figure in words before the TTS sees it, so '$10,000' is 'ten thousand dollars', never
    'dollar ten comma zero zero zero' or 'ten dollars thousand'."""
    scale = r"(?:\s*(million|billion|trillion|thousand|[MBK])\b)?"
    big = {"M": "million", "B": "billion", "K": "thousand"}

    # an amount describing a noun is said "a ten-thousand-dollar investment", not "ten thousand dollars investment"
    function_words = {"a", "an", "the", "per", "in", "to", "for", "of", "and", "or", "or", "each", "every", "is",
                      "was", "a", "right", "now", "today", "back", "up", "down", "on", "at", "into", "with", "from"}

    def money(m):
        amt, sc, nxt = m.group(1), m.group(2), m.group(3) or ""
        attributive = nxt[:1].isalpha() and nxt[:1].islower() and nxt.lower() not in function_words
        if sc:
            body = f"{decimal_words(amt)} {big.get(sc, sc)}"
        else:
            whole, _, cents = amt.replace(",", "").partition(".")
            body = words(int(whole))
            if cents and int(cents) and not attributive:
                return f"{body} dollars and {words(int(cents))} cents{(' ' + nxt) if nxt else ''}"
            if not attributive and int(whole) == 1:
                return f"one dollar{(' ' + nxt) if nxt else ''}"
        if attributive:
            return body.replace(" ", "-") + "-dollar " + nxt
        return f"{body} dollars{(' ' + nxt) if nxt else ''}"
    t = re.sub(r"\$\s?(\d[\d,]*(?:\.\d+)?)" + scale + r"(?:\s+([A-Za-z][\w'’-]*))?", money, t)
    t = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s?%", lambda m: decimal_words(m.group(1)) + " percent", t)
    t = re.sub(r"\b(\d[\d,]*)\s?[x×]\b", lambda m: words(int(m.group(1).replace(",", ""))) + " times", t)
    t = re.sub(r"\b(1[89]\d\d|20\d\d)\b(?!,\d)", lambda m: year_words(m.group(1)), t)   # bare 4-digit years
    t = re.sub(r"\d[\d,]*(?:\.\d+)?", lambda m: decimal_words(m.group(0)), t)
    return t


def spoken(text):
    """Script text as it should be read: one paragraph, stage marks out, numbers in words."""
    t = re.sub(r"\s*\n\s*", " ", text or "").strip()
    t = t.replace("&", " and ").replace("–", ",").replace("—", ",")
    t = re.sub(r"\s*/\s*mo(nth)?\b", " a month", t); t = re.sub(r"\s*/\s*y(ea)?r\b", " a year", t)
    t = say_numbers(t)
    return re.sub(r"\s{2,}", " ", t)


def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(p.stdout.strip() or 0)


def main():
    ap = argparse.ArgumentParser(description="Placeholder TTS voiceover for every row.")
    ap.add_argument("storyboard")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", default="1.0")
    ap.add_argument("--gap", type=float, default=0.35)
    ap.add_argument("--rows")
    a = ap.parse_args()

    sb = os.path.abspath(a.storyboard)
    project = os.path.dirname(sb)
    doc = json.load(open(sb))
    out = os.path.join(project, "audio", "placeholder-vo")
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ)
    if "HYPERFRAMES_PYTHON" not in env and os.path.exists(REPO_VENV):
        env["HYPERFRAMES_PYTHON"] = REPO_VENV
    gdir = os.path.join(project, doc.get("graphics_dir", "videos/vsl-graphics"))
    cwd = gdir if os.path.isdir(gdir) else project

    lo, hi = (int(x) for x in a.rows.split("-")) if a.rows else (0, 10**6)
    rows = [r for r in doc["rows"] if lo <= r["n"] <= hi and spoken(r.get("script"))]
    clips = []
    for r in rows:
        text = spoken(r["script"])
        key = hashlib.sha1(f"{a.voice}|{a.speed}|{text}".encode()).hexdigest()[:10]
        wav = os.path.join(out, f"{r['n']:03d}_{r.get('slug', 'row')}.wav")
        stamp = wav + ".key"
        if not (os.path.exists(wav) and os.path.exists(stamp) and open(stamp).read() == key):
            p = subprocess.run(["npx", "--yes", HF_PKG, "tts", text, "-v", a.voice, "-s", str(a.speed), "-o", wav],
                               capture_output=True, text=True, cwd=cwd, env=env)
            if p.returncode != 0 or not os.path.exists(wav):
                sys.exit(f"row {r['n']}: tts failed\n{p.stdout}{p.stderr}")
            open(stamp, "w").write(key)
        clips.append((r, wav, duration(wav)))
        print(f"row {r['n']:3d}  {clips[-1][2]:6.2f}s  {os.path.basename(wav)}", flush=True)

    # join: clip, gap, clip, … (gap as generated silence so every clip keeps its own length)
    listf = os.path.join(out, ".concat.txt")
    gap = os.path.join(out, ".gap.wav")
    sr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=sample_rate",
                         "-of", "csv=p=0", clips[0][1]], capture_output=True, text=True).stdout.strip() or "24000"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=mono",
                    "-t", str(a.gap), "-c:a", "pcm_s16le", gap], check=True)
    rows_out, t = [], 0.0
    with open(listf, "w") as f:
        for i, (r, wav, d) in enumerate(clips):
            f.write(f"file '{wav}'\n")
            rows_out.append((r["n"], round(t, 3), round(t + d, 3), round(d, 3)))
            t += d
            if i < len(clips) - 1:
                f.write(f"file '{gap}'\n"); t += a.gap
    full = os.path.join(out, "placeholder-vo.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listf,
                    "-ar", sr, "-ac", "1", "-c:a", "pcm_s16le", full], check=True)
    os.remove(listf); os.remove(gap)
    with open(os.path.join(out, "timings.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["row", "start", "end", "duration"]); w.writerows(rows_out)
    print(f"\n{full}  {t/60:.1f} min, {len(clips)} rows (voice {a.voice}, speed {a.speed})")

    # where the read outruns the graphic that has to cover it
    short = []
    for r, _wav, d in clips:
        for asset in r.get("assets") or []:
            seg = asset.get("segment")
            dur = (seg[1] - seg[0]) if seg else asset.get("duration")
            if asset.get("kind") == "custom_graphic" and dur and d > float(dur) + 0.25:
                short.append((r["n"], float(dur), d))
    if short:
        print("\nGraphic shorter than the placeholder read (retime the beat, or the read will be faster):")
        for n, g, d in short:
            print(f"  row {n:3d}  graphic {g:5.2f}s  read {d:5.2f}s  (+{d-g:.2f}s)")


if __name__ == "__main__":
    main()
