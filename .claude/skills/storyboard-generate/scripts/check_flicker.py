#!/usr/bin/env python3
"""check_flicker.py — find frames that FLICKER in a rendered video, and say why.

A flicker frame differs from both of its neighbours while those neighbours match each other
(an A-B-A pattern). Real motion does not do that; a frame drawn inconsistently does.

The report groups flicker frames by `frame % workers`. HyperFrames splits frames across parallel
Chrome workers, so if every flicker frame lands on the SAME residue, one worker is drawing the
page differently from the rest (e.g. a capture-path fallback, or a layer snapped to a different
pixel grid) — a renderer inconsistency, not a problem in the art. Flicker spread across all
residues points at the composition itself (a non-seek-safe tween, an asset that pops).

usage: check_flicker.py <video.mp4> [--workers 3] [--scale 480] [--min-px 25]
       [--windows "6.6-10.3,12.4-16.3"]   # restrict to camera holds, where nothing should change
Without --windows, fast motion also produces A-B-A pixels at moving edges, so whole-clip counts
spread evenly over every residue are usually motion, not flicker. Check holds for a verdict.
exit 1 if any flicker frame is found (inside --windows when given).
"""
import argparse, collections, glob, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--scale", type=int, default=480); ap.add_argument("--min-px", type=int, default=25)
ap.add_argument("--windows", default=""); ap.add_argument("--fps", type=float, default=30.0)
a = ap.parse_args()

tmp = tempfile.mkdtemp(prefix="flicker_")
subprocess.run(["ffmpeg", "-loglevel", "error", "-i", a.video, "-vf", f"scale={a.scale}:-2",
                os.path.join(tmp, "f_%05d.png")], check=True)
fs = sorted(glob.glob(os.path.join(tmp, "f_*.png")))
F = [np.asarray(Image.open(f).convert("L")).astype(np.int16) for f in fs]
k = 1920 / F[0].shape[1]

hits = []
for i in range(1, len(F) - 1):
    m = (np.abs(F[i] - F[i-1]) > 28) & (np.abs(F[i+1] - F[i]) > 28) & (np.abs(F[i+1] - F[i-1]) < 10)
    n = int(m.sum())
    if n > a.min_px:
        ys, xs = np.nonzero(m)
        hits.append((i, n, int(xs.min()*k), int(ys.min()*k), int(xs.max()*k), int(ys.max()*k)))

wins = []
for w in filter(None, a.windows.split(",")):
    t0, t1 = map(float, w.split("-")); wins.append((t0, t1))
def inwin(i): return not wins or any(t0 * a.fps <= i <= t1 * a.fps for t0, t1 in wins)

sel = [h for h in hits if inwin(h[0])]
print(f"{len(F)} frames, {len(sel)} flicker frames" + (" inside windows" if wins else ""))
if sel:
    res = collections.Counter(h[0] % a.workers for h in sel)
    print(f"by frame % {a.workers}: {dict(res)}")
    top = res.most_common(1)[0]
    # needs a real sample: one stray hit always lands on 'a single residue'
    if len(sel) >= 5 and (len(res) == 1 or top[1] >= 0.9 * len(sel)):
        print(f"  -> all on residue {top[0]}: ONE render worker draws differently (renderer, not the art)")
    for h in sel[:40]:
        print(f"  frame {h[0]:5d}  t={h[0]/a.fps:7.2f}s  px={h[1]:5d}  box x{h[2]}-{h[4]} y{h[3]}-{h[5]}")
sys.exit(1 if sel else 0)
