#!/usr/bin/env python3
"""Animatic: the whole board cut to the placeholder voiceover, one row after another.

  animatic.py <storyboard.json> [--music track.mp3] [--music-db -20] [--no-labels] [--height 1080]
              [--out "animatic/<Project> Animatic.mp4"]

Each row holds for exactly its stretch of the VO (audio/placeholder-vo/timings.csv from
placeholder_vo.py, gap included), so the cut is the read:
  - generated graphics and footage play their own file — a shared clip plays only the row's segment
    — trimmed to the row, or slowed (B-roll, down to half speed) and then held on a live frame when
    the row runs longer than the clip (never on a graphic's exit, which is empty)
  - talking-head rows show the presenter still (the row's own, its reuse_of, else the board's
    first still) with a slow push-in; placeholder rows show their placeholder card
  - a small "row · section" label sits top-left unless --no-labels
Audio: the VO, plus --music under it (looped to length, faded, and ducked by the voice through a
sidechain compressor). Per-row clips are cached in .board-cache/animatic/ and rebuilt only when
the row's source or timing changes, so re-cutting after a fix is quick.
"""
import argparse, csv, hashlib, json, os, subprocess, sys

FPS = 30
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
EXIT_GUARD = 0.6      # a graphic's last ~0.6s is its exit: hold before it, never on it
MAX_SLOW = 2.0        # B-roll may play down to half speed before it holds


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.exit("ffmpeg failed:\n" + " ".join(cmd) + "\n" + p.stderr[-2000:])


def probe_dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def label_png(text, H, path):
    """The row label as a transparent PNG (ffmpeg builds without freetype have no drawtext)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(FONT, H // 40)
    x0, y0, x1, y1 = font.getbbox(text)
    pad = H // 108
    im = Image.new("RGBA", (x1 + 2 * pad + 24, y1 + 2 * pad + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([24 - pad // 2, 20 - pad // 2, 24 + x1 + pad, 20 + y1 + pad], fill=(0, 0, 0, 115))
    d.text((24 + pad // 2, 20 + pad // 2 - y0 // 2), text, font=font, fill=(255, 255, 255, 230))
    im.save(path)
    return path


def source_for(row, rows_by_id, rows, project):
    """(kind, path, in, length) for a row: 'video' with its segment, or 'still' for an image."""
    for a in row.get("assets") or []:
        f = a.get("file") or ""
        p = os.path.join(project, f)
        if f.lower().endswith((".mp4", ".mov")) and os.path.exists(p):
            seg = a.get("segment")
            if seg:
                return "video", p, float(seg[0]), float(seg[1]) - float(seg[0]), a.get("kind")
            return "video", p, 0.0, probe_dur(p), a.get("kind")
        for cand in (f, a.get("poster") or ""):
            if cand.lower().endswith((".jpg", ".jpeg", ".png")) and os.path.exists(os.path.join(project, cand)):
                return "still", os.path.join(project, cand), 0, 0, a.get("kind")
    if row.get("reuse_of") and row["reuse_of"] in rows_by_id and rows_by_id[row["reuse_of"]] is not row:
        return source_for(rows_by_id[row["reuse_of"]], rows_by_id, rows, project)
    for r in rows:                       # the board's first still (the presenter frame)
        for a in r.get("assets") or []:
            if a.get("kind") == "still" and os.path.exists(os.path.join(project, a.get("file", ""))):
                return "still", os.path.join(project, a["file"]), 0, 0, "still"
    return None


def main():
    ap = argparse.ArgumentParser(description="Cut the board to the placeholder VO.")
    ap.add_argument("storyboard")
    ap.add_argument("--music")
    ap.add_argument("--music-db", type=float, default=-20.0, help="music level under the VO, in dB")
    ap.add_argument("--no-labels", action="store_true")
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--out")
    a = ap.parse_args()

    sb = os.path.abspath(a.storyboard)
    project = os.path.dirname(sb)
    doc = json.load(open(sb))
    rows = doc["rows"]
    by_n = {r["n"]: r for r in rows}
    by_id = {r["id"]: r for r in rows}
    vo_dir = os.path.join(project, "audio", "placeholder-vo")
    vo = os.path.join(vo_dir, "placeholder-vo.wav")
    if not os.path.exists(vo):
        sys.exit("no placeholder VO — run placeholder_vo.py first")
    tim = [(int(r["row"]), float(r["start"]), float(r["end"])) for r in csv.DictReader(open(os.path.join(vo_dir, "timings.csv")))]
    total = probe_dur(vo) + 1.0
    H = a.height; W = H * 16 // 9
    cache = os.path.join(project, ".board-cache", "animatic"); os.makedirs(cache, exist_ok=True)

    parts = []
    for i, (n, start, _end) in enumerate(tim):
        slot = (tim[i + 1][1] if i + 1 < len(tim) else total) - start
        row = by_n[n]
        src = source_for(row, by_id, rows, project)
        if not src:
            sys.exit(f"row {n}: nothing to show")
        kind, path, t_in, length, akind = src
        label = "" if a.no_labels else f"{n}  ·  {row.get('section', '')}  ·  {row.get('visual_type', '')}"
        key = hashlib.sha1(json.dumps([kind, path, os.path.getmtime(path), t_in, length, round(slot, 3), label, H]).encode()).hexdigest()[:12]
        out = os.path.join(cache, f"{n:03d}_{key}.mp4")
        parts.append(out)
        if os.path.exists(out):
            continue
        lab = label_png(label, H, out[:-4] + ".label.png") if label else None

        def encode(inputs, chain, extra):
            if lab:
                cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-i", lab, "-filter_complex",
                       f"[0:v]{chain}[b];[b][1:v]overlay=0:0[o]", "-map", "[o]"]
            else:
                cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-vf", chain]
            run(cmd + extra + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                               "-r", str(FPS), out])
        fit = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
        if kind == "still":
            frames = max(1, round(slot * FPS))
            vf = (f"scale={W*2}:-2,zoompan=z='min(1.0+0.0004*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={frames}:s={W}x{H}:fps={FPS},setsar=1")
            encode(["-loop", "1", "-i", path], vf, ["-frames:v", str(frames)])
            print(f"row {n:3d}  {slot:6.2f}s  {os.path.basename(path)}  (still)", flush=True)
            continue
        graphic = akind in ("custom_graphic", "overlay")
        play = length
        speed = 1.0
        if not graphic and length < slot:          # footage: stretch toward the slot before holding
            speed = max(1 / MAX_SLOW, length / slot)
        if graphic and length < slot:
            play = max(0.5, length - EXIT_GUARD)   # hold the last settled frame, not the exit
        shown = min(play / speed, slot)
        hold = max(0.0, slot - shown)
        vf = (f"trim=start={t_in:.3f}:duration={min(play, slot*speed):.3f},setpts=(PTS-STARTPTS)/{speed:.4f},"
              f"fps={FPS},{fit},tpad=stop_mode=clone:stop_duration={hold:.3f}")
        encode(["-i", path], vf, ["-an", "-t", f"{slot:.3f}"])
        print(f"row {n:3d}  {slot:6.2f}s  {os.path.basename(path)}" + (f"  (x{speed:.2f}, hold {hold:.1f}s)" if speed < 1 or hold > 0.05 else ""), flush=True)

    listf = os.path.join(cache, "concat.txt")
    with open(listf, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    picture = os.path.join(cache, "picture.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listf, "-c", "copy", picture])

    boards = [f for f in os.listdir(project) if f.lower().endswith(".xlsx") and "storyboard" in f.lower()]
    title = (boards[0][:-5].replace("Storyboard", "").replace("storyboard", "").strip(" -") if boards
             else str(doc.get("project", "storyboard")).replace("-", " ").title())
    out = a.out or os.path.join(project, "animatic", f"{title} Animatic.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    dur = probe_dur(picture)
    if a.music:
        fc = (f"[2:a]volume={a.music_db}dB,afade=t=in:d=2,afade=t=out:st={max(0, dur-4):.2f}:d=4[m];"
              f"[1:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=600[md];"
              f"[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", picture, "-i", vo, "-stream_loop", "-1", "-i", a.music,
               "-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", picture, "-i", vo, "-map", "0:v", "-map", "1:a"]
    run(cmd + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", out])
    print(f"\n{out}  {dur/60:.1f} min" + (f", music {os.path.basename(a.music)} at {a.music_db:g} dB" if a.music else ", VO only"))


if __name__ == "__main__":
    main()
