#!/usr/bin/env python3
"""Helpers for /generate: download a result, strip its audio (video is always delivered
silent — the editor sets sound), extract a poster, and register produced assets into
storyboard.json. Supports single rows, a continuous asset spanning a row range (register_span),
and a style-linked series (series_id tag). Rendering itself is driven by the skill (HyperFrames
CLI locally, Higgsfield MCP for video); this file is the plumbing so naming and row bookkeeping
stay consistent.
"""
import json, os, sys, urllib.request, subprocess

def load(p): return json.load(open(p))
def save(p, d): json.dump(d, open(p, "w"), indent=2)
def row_by_n(doc, n): return next((r for r in doc["rows"] if r["n"] == int(n)), None)
def name_for(row, ext): return f"{row['n']:03d}_{row.get('slug','shot')}.{ext}"

def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return dest

def silence(path):
    """Strip the audio track in place — video is delivered without sound."""
    tmp = path + ".silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", path, "-c:v", "copy", "-an", tmp],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(tmp, path)
    return path

def poster_from(video_path, at="0.5"):
    png = os.path.splitext(video_path)[0] + ".png"
    subprocess.run(["ffmpeg", "-y", "-ss", at, "-i", video_path, "-frames:v", "1", png],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png

def register(sb_path, n, file_rel, poster_rel, kind, source, duration=None,
             status="Generated", series_id=None):
    doc = load(sb_path); row = row_by_n(doc, n)
    asset = {"file": file_rel, "poster": poster_rel, "kind": kind,
             "source": source, "duration": duration}
    if series_id: asset["series_id"] = series_id
    row["assets"] = [asset]; row["status"] = status
    save(sb_path, doc)
    print(f"row {n}: {file_rel} ({status})" + (f" series={series_id}" if series_id else ""))

def register_span(sb_path, a, b, file_rel, poster_rel, kind, source, total_dur, cuts=None):
    """Point every row in [a,b] at ONE shared file, each with its own in/out segment.
    cuts: optional explicit boundary times in seconds (len = rows+1). Otherwise split evenly."""
    a, b, total = int(a), int(b), float(total_dur)
    doc = load(sb_path)
    rows = [r for r in doc["rows"] if a <= r["n"] <= b]
    if not rows:
        print(f"no rows in {a}-{b}"); return
    k = len(rows)
    if cuts and len(cuts) == k + 1:
        bounds = [float(c) for c in cuts]
    else:
        step = total / k
        bounds = [round(i * step, 3) for i in range(k)] + [round(total, 3)]
    span_group = f"span_{a:03d}_{b:03d}"
    for i, r in enumerate(rows):
        r["assets"] = [{"file": file_rel, "poster": poster_rel, "kind": kind, "source": source,
                        "duration": round(bounds[i+1] - bounds[i], 3),
                        "segment": [bounds[i], bounds[i+1]], "span_group": span_group}]
        r["status"] = "Generated"
    save(sb_path, doc)
    print(f"span {span_group}: {file_rel} across rows {a}-{b}")
    for i, r in enumerate(rows):
        print(f"  row {r['n']}: {bounds[i]:.2f}-{bounds[i+1]:.2f}s")

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "download":
        v = download(sys.argv[2], sys.argv[3]); print(v)
    elif cmd == "silence":
        print(silence(sys.argv[2]))
    elif cmd == "poster":
        print(poster_from(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "0.5"))
    elif cmd == "register":
        # register <sb> <n> <file> <poster> <kind> <source> [dur] [series_id]
        register(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7],
                 sys.argv[8] if len(sys.argv) > 8 else None,
                 series_id=sys.argv[9] if len(sys.argv) > 9 else None)
    elif cmd == "register_span":
        # register_span <sb> <a> <b> <file> <poster> <kind> <source> <total_dur> [t0 t1 ...]
        cuts = sys.argv[10:] or None
        register_span(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6],
                      sys.argv[7], sys.argv[8], sys.argv[9], cuts=cuts)
    else:
        print("commands: download | silence | poster | register | register_span"); sys.exit(1)
