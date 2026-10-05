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


def spoken(text):
    """Script text as it should be read: one paragraph, stage marks out."""
    t = re.sub(r"\s*\n\s*", " ", text or "").strip()
    t = t.replace("&", " and ").replace("–", ",").replace("—", ",")
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
