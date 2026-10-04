#!/usr/bin/env python3
"""export_still.py — deterministic single-frame still export for a HyperFrames composition.

Reuses check_row.py's storyboard/composition resolution and static-file-serving approach
(resolve_composition, read_composition_meta, rows_referencing, serve_dir, free_port), and a
small sibling Node driver (_still.mjs — same puppeteer-core-driving-system-Chrome recipe as
_probe.mjs) to seek the composition's registered GSAP timeline to one deterministic time and
screenshot it at full resolution. All cropping/resizing/alpha-reporting happens here in PIL.

Usage:
  export_still.py <storyboard.json> <row|name-fragment> [--at T] [--size WxH]
                   [--crop l,t,w,h] [--scale S] [--transparent]
                   [--set "css-or-js"] -o out.png

  --at T          seek time in seconds. Default: the row's poster_t, else 0.78 of the way
                  through its segment (asset["segment"]), else 3.0.
  --size WxH      fit the (cropped) frame to WxH: center-crop to the target aspect ratio,
                  then LANCZOS resize. e.g. --scale 2 --size 900x600 downsamples from a
                  crisp 3840x2160 capture.
  --crop l,t,w,h  crop BEFORE sizing, in frame px (i.e. in the 1920x1080 logical composition
                  frame — scaled internally by --scale to match the actual capture).
  --scale S       deviceScaleFactor for the headless capture (default 1; use 2 for crisp
                  downscales).
  --transparent   hide the background layer ([data-sb-layer="bg"], plus legacy #bg/#vign/#meshfx), set html/body background transparent, and capture
                  with omitBackground so the PNG carries real alpha. Reports how many pixels
                  in the (cropped) output actually came out with alpha < 255.
  --set SNIPPET   "css:...' or 'js:...' (leading prefix selects which; CSS is the default
                  with no prefix) run before the timeline is seeked — e.g. hide an overlay
                  for a variant export: --set 'css:#ttl,.corner{display:none}'
"""
import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STILL_JS = os.path.join(SCRIPT_DIR, "_still.mjs")

# --- reuse check_row.py's storyboard/composition/server helpers instead of reimplementing ---
_spec = importlib.util.spec_from_file_location("check_row", os.path.join(SCRIPT_DIR, "check_row.py"))
check_row = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_row)

DEFAULT_GRAPHICS_DIR = check_row.DEFAULT_GRAPHICS_DIR
load_storyboard = check_row.load_storyboard
resolve_composition = check_row.resolve_composition
read_composition_meta = check_row.read_composition_meta
rows_referencing = check_row.rows_referencing
free_port = check_row.free_port
serve_dir = check_row.serve_dir


def pick_row(refs, query):
    """refs: [(row, asset), ...] all referencing this composition. Narrow to the row the
    caller actually asked for when the composition covers more than one (e.g. row 10/11
    share one split-screen graphic) — by row number if the query was numeric, else by slug
    substring; fall back to the first ref if nothing narrows it further."""
    if not refs:
        return None, None
    q = str(query).strip()
    if q.isdigit():
        n = int(q)
        for row, asset in refs:
            if row.get("n") == n:
                return row, asset
    for row, asset in refs:
        if q.lower() in (row.get("slug") or "").lower():
            return row, asset
    return refs[0]


def default_at(row, asset, duration):
    if asset and asset.get("poster_t") is not None:
        return float(asset["poster_t"])
    seg = asset.get("segment") if asset else None
    if seg and len(seg) == 2:
        lo, hi = float(seg[0]), float(seg[1])
        return lo + 0.78 * (hi - lo)
    return 3.0


def parse_size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def parse_crop(s):
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 4:
        raise SystemExit("--crop needs l,t,w,h")
    return parts


def parse_set(s):
    if s is None:
        return None, None
    if s.startswith("js:"):
        return "js", s[3:]
    if s.startswith("css:"):
        return "css", s[4:]
    return "css", s


def center_crop_to_aspect(img, target_w, target_h):
    w, h = img.size
    target_aspect = target_w / target_h
    cur_aspect = w / h
    if cur_aspect > target_aspect:
        # too wide: crop left/right
        new_w = round(h * target_aspect)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    elif cur_aspect < target_aspect:
        # too tall: crop top/bottom
        new_h = round(w / target_aspect)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("storyboard")
    ap.add_argument("row")
    ap.add_argument("--at", type=float, default=None)
    ap.add_argument("--size", default=None, help="WxH")
    ap.add_argument("--crop", default=None, help="l,t,w,h in frame px")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--transparent", action="store_true")
    ap.add_argument("--set", dest="set_snippet", default=None)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    storyboard_path = os.path.abspath(args.storyboard)
    project_dir = os.path.dirname(storyboard_path)
    storyboard = load_storyboard(storyboard_path)
    graphics_dir = storyboard.get("graphics_dir") or DEFAULT_GRAPHICS_DIR
    graphics_root = os.path.join(project_dir, graphics_dir)

    html_path = resolve_composition(project_dir, graphics_dir, args.row)
    basename = os.path.splitext(os.path.basename(html_path))[0]
    comp_id, duration = read_composition_meta(html_path)

    refs = rows_referencing(storyboard, basename)
    row, asset = pick_row(refs, args.row)

    at_t = args.at if args.at is not None else default_at(row, asset, duration)
    at_t = max(0.0, min(duration, at_t))

    set_type, set_code = parse_set(args.set_snippet)

    # Serve GRAPHICS root exactly like check_row.py does, so relative asset paths ("assets/...",
    # "shared/...") resolve the same way they do for the real hyperframes renderer.
    tmp_html = os.path.join(graphics_root, f"_still_probe_{basename}_{os.getpid()}.html")
    with open(html_path, encoding="utf-8") as f:
        html_text = f.read()
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_text)

    port = free_port()
    httpd = serve_dir(graphics_root, port)
    raw_png = None
    try:
        import socket, time
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/{os.path.basename(tmp_html)}"

        fd, raw_png = tempfile.mkstemp(suffix=".png", prefix="export_still_raw_")
        os.close(fd)

        still_args = {
            "url": url,
            "compId": comp_id,
            "t": at_t,
            "scale": args.scale,
            "transparent": bool(args.transparent),
            "setType": set_type,
            "setCode": set_code,
            "outPng": raw_png,
        }
        fd2, args_json = tempfile.mkstemp(suffix=".json", prefix="export_still_args_")
        with os.fdopen(fd2, "w") as f:
            json.dump(still_args, f)

        try:
            proc = subprocess.run(
                ["node", STILL_JS, args_json], capture_output=True, text=True, timeout=120
            )
        finally:
            os.remove(args_json)

        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            raise SystemExit(f"_still.mjs failed (exit {proc.returncode})")
        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as e:
            sys.stderr.write(proc.stdout + "\n" + proc.stderr)
            raise SystemExit(f"could not parse _still.mjs output: {e}")
    finally:
        httpd.shutdown()
        try:
            os.remove(tmp_html)
        except OSError:
            pass

    img = Image.open(raw_png)
    if args.transparent:
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    scale = args.scale
    if args.crop:
        l, t, w, h = parse_crop(args.crop)
        box = (round(l * scale), round(t * scale), round((l + w) * scale), round((t + h) * scale))
        img = img.crop(box)

    alpha_report = None
    if args.transparent:
        import numpy as np
        arr = np.asarray(img)
        alpha = arr[:, :, 3]
        below = int((alpha < 255).sum())
        alpha_report = (below, alpha.size)

    if args.size:
        tw, th = parse_size(args.size)
        img = center_crop_to_aspect(img, tw, th)
        img = img.resize((tw, th), Image.LANCZOS)

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path)
    try:
        os.remove(raw_png)
    except OSError:
        pass

    print(f"wrote {out_path}  ({img.size[0]}x{img.size[1]})  t={at_t:.3f}s  comp={basename}")
    if alpha_report is not None:
        below, total = alpha_report
        pct = 100.0 * below / total if total else 0.0
        print(f"alpha: {below}/{total} px ({pct:.1f}%) have alpha < 255")


if __name__ == "__main__":
    main()
