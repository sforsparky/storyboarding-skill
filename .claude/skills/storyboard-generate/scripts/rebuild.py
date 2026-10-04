#!/usr/bin/env python3
"""Rebuild one HyperFrames graphic composition and put the result back on the board.

  rebuild.py <storyboard.json> <row-number|name-fragment> [--no-xlsx] [--no-check] [--dry-run] [--range IN OUT]

Replaces the old rebuild-row.sh + poster-times.json combo. Posters are no longer cut from a
side file: every row on the board whose assets[].file points at the rendered mp4 gets its
poster re-cut straight from that row's own asset (poster_t, or a segment-derived fallback),
so a shared clip's per-beat posters and a single-row graphic's poster both come from one
source of truth — storyboard.json.

Steps: resolve the graphics dir (recorded on the board), resolve the composition file the
same way rebuild-row.sh did, lint the project, render at high quality, copy the result into
the project's assets/, register the rows, cut every referencing row's poster, and refresh the xlsx.

Registration comes from <graphics_dir>/plan.json when the composition has an entry there:
  {"<composition name>": {"rows": [first, last], "cuts": [0, t1, ..., dur],
                          "poster_times": [t, ...], "kind": "custom_graphic"}}
— one pass: render, then point those rows at the file (segments, poster_t, layers) and cut
their posters. Without an entry, rows that already reference assets/<name>.mp4 are re-cut as
before. The board is re-read and patched under a lock at each write (generate_row.editing),
never held across the render, so edits made while a render runs survive.

Python 3 stdlib only.
"""
import argparse
import datetime as dt
import glob
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from generate_row import (load, editing, assign_clip, clip_bounds,  # noqa: E402
                          BEAT_POSTER_AT)                              # (reuse skill conventions)
import layers  # noqa: E402

HF_VERSION = "0.8.34"
HF_PKG = f"hyperframes@{HF_VERSION}"
DEFAULT_GRAPHICS_DIR = "videos/vsl-graphics"
SB_TO_XLSX = os.path.expanduser(
    "~/.claude/skills/storyboard-build/scripts/sb_to_xlsx.py")
INGEST_SHEET_COMMENTS = os.path.expanduser(
    "~/.claude/skills/storyboard-build/scripts/ingest_sheet_comments.py")
CHECK_ROW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_row.py")

# Candidate flag names a future hyperframes render might expose for a partial/windowed
# render. None of these exist in 0.8.34 (checked via `render --help`) — kept as a probe so
# this script notices automatically if a later version adds one, instead of silently
# pretending to support --range.
RANGE_FLAG_CANDIDATES = ("--start", "--end", "--range", "--frame-window",
                          "--in-point", "--out-point", "--trim-start", "--trim-end")


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError as e:
        die(f"could not run {cmd[0]!r}: {e}")


def ensure_graphics_dir(sb_path, doc, dry_run):
    """storyboard.json['graphics_dir'], relative to the project. Added (and persisted) if
    missing, unless this is a dry run."""
    if "graphics_dir" in doc:
        return doc["graphics_dir"], False
    if dry_run:
        return DEFAULT_GRAPHICS_DIR, True
    with editing(sb_path) as live:
        live.setdefault("graphics_dir", DEFAULT_GRAPHICS_DIR)
    return DEFAULT_GRAPHICS_DIR, True


def load_plan(graphics_dir_abs):
    """<graphics_dir>/plan.json — which rows each composition covers. {} when absent."""
    import json
    p = os.path.join(graphics_dir_abs, "plan.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def planned_rows(doc, entry, asset_file_rel):
    """Apply a plan.json entry to an in-memory doc (rows, segments, poster_t). Returns the rows."""
    a, b = entry["rows"]
    k = sum(1 for r in doc["rows"] if a <= r["n"] <= b)
    cuts = entry.get("cuts")
    total = float(entry.get("duration") or (cuts[-1] if cuts else 0))
    return assign_clip(doc, a, b, asset_file_rel, entry.get("kind", "custom_graphic"), "hyperframes",
                       clip_bounds(k, total, cuts), entry.get("poster_times"))


def poster_plan_for(doc, asset_file_rel):
    out = []
    for row in doc["rows"]:
        for asset in row.get("assets", []):
            if asset.get("file") == asset_file_rel and "poster" in asset:
                t, how = poster_time_for(asset)
                out.append((row["n"], asset["poster"], t, how))
    return out


def resolve_composition(graphics_dir_abs, query):
    """Same rule as rebuild-row.sh: zero-pad a pure number to 3 digits, then a case-
    insensitive substring match against compositions/*.html. Errors list the candidates."""
    q = f"{int(query):03d}" if query.isdigit() else query
    comp_dir = os.path.join(graphics_dir_abs, "compositions")
    candidates = sorted(glob.glob(os.path.join(comp_dir, "*.html")))
    matches = [c for c in candidates if q.lower() in os.path.basename(c).lower()]
    if not matches:
        listing = "\n".join("  " + os.path.basename(c) for c in candidates)
        die(f"no composition matches {query!r}\navailable:\n{listing}")
    if len(matches) > 1:
        listing = "\n".join("  " + os.path.basename(c) for c in matches)
        die(f"{query!r} is ambiguous:\n{listing}")
    return matches[0]


def poster_time_for(asset):
    """poster_t if the board recorded one; else segment-derived (in + (out-in)*0.78); else a
    flat 3.0s. Mirrors generate_row.py's BEAT_POSTER_AT convention."""
    if asset.get("poster_t") is not None:
        return float(asset["poster_t"]), "poster_t"
    seg = asset.get("segment")
    if seg:
        lo, hi = float(seg[0]), float(seg[1])
        return lo + (hi - lo) * BEAT_POSTER_AT, f"segment {lo:g}-{hi:g} * {BEAT_POSTER_AT}"
    return 3.0, "default 3.0s (no poster_t, no segment)"


def find_xlsx(project_dir, doc):
    existing = [f for f in os.listdir(project_dir)
                if f.lower().endswith(".xlsx") and not f.startswith("~$")]
    sb_named = [f for f in existing if "storyboard" in f.lower()]
    if len(sb_named) == 1:
        return sb_named[0]
    if len(existing) == 1:
        return existing[0]
    proj = str(doc.get("project", "storyboard")).replace("-", " ").replace("_", " ").title()
    return f"{proj} - Storyboard.xlsx"


def archive_if_commented(project_dir, xlsx_name):
    """A workbook downloaded back from Google Sheets/Excel carries the reviewers' comment
    threads inside it, and sb_to_xlsx.py is about to overwrite it in place. Copy it aside
    first so a rebuild can never silently destroy feedback nobody has read yet."""
    import zipfile
    path = os.path.join(project_dir, xlsx_name)
    if not os.path.exists(path):
        return None
    import re
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if any(n.startswith("xl/threadedComments/") for n in names):
                has_comments = True                # Excel threads are always a person's
            else:
                # Legacy comment parts: only a REVIEWER's count. Notes authored "storyboard" were
                # written by an older sb_to_xlsx.py itself; archiving on those saved a full copy
                # of the board on every rebuild with nothing in it anyone wrote.
                has_comments = False
                for n in names:
                    if re.match(r"xl/comments(/comment)?\d*\.xml$", n):
                        x = zf.read(n).decode("utf8", "ignore")
                        authors = re.findall(r"<author>(.*?)</author>", x)
                        ids = re.findall(r'<comment [^>]*authorId="(\d+)"', x)
                        if any((authors[int(i)] if int(i) < len(authors) else "") != "storyboard" for i in ids):
                            has_comments = True
                            break
    except zipfile.BadZipFile:
        return None
    if not has_comments:
        return None
    dest_dir = os.path.join(project_dir, "feedback")
    os.makedirs(dest_dir, exist_ok=True)
    stamp = dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    base = os.path.basename(xlsx_name)
    dest = os.path.join(dest_dir, base if base.startswith(stamp) else f"{stamp}_{base}")
    if not os.path.exists(dest):
        shutil.copy2(path, dest)
    return os.path.relpath(dest, project_dir)


def detect_range_flags(graphics_dir_abs):
    proc = run(["npx", "--yes", HF_PKG, "render", "--help"], cwd=graphics_dir_abs)
    text = (proc.stdout or "") + (proc.stderr or "")
    return [f for f in RANGE_FLAG_CANDIDATES if f in text]


def do_range(graphics_dir_abs, name, in_t, out_t, dry_run):
    flags = detect_range_flags(graphics_dir_abs)
    if not flags:
        print(f"range rendering not supported by hyperframes {HF_VERSION}")
        sys.exit(2)

    out_rel = f"renders/{name}_{in_t}-{out_t}.mp4"
    print(f"  range render appears supported via {', '.join(flags)}")
    if dry_run:
        print(f"[dry-run] would render window {in_t}-{out_t} -> {out_rel}")
        return

    cmd = ["npx", "--yes", HF_PKG, "render", "--composition", f"compositions/{name}.html",
           "--quality", "high", "-o", out_rel, "--quiet"]
    if "--start" in flags and "--end" in flags:
        cmd += ["--start", in_t, "--end", out_t]
    elif "--range" in flags:
        cmd += ["--range", f"{in_t}-{out_t}"]
    elif "--frame-window" in flags:
        cmd += ["--frame-window", f"{in_t}-{out_t}"]
    proc = run(cmd, cwd=graphics_dir_abs)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        die("range render failed")
    print(out_rel)


def main():
    ap = argparse.ArgumentParser(
        description="Rebuild one HyperFrames graphic and put it back on the storyboard.")
    ap.add_argument("storyboard")
    ap.add_argument("selector", help="row number or a substring of the composition name")
    ap.add_argument("--crf", help="override the encoder CRF (lower = cleaner). Fine detail held "
                                  "under a slow camera move shimmers at the default quantiser; 16 "
                                  "settles it. Recorded on the row so re-renders keep the setting.")
    ap.add_argument("--no-xlsx", action="store_true", help="skip rebuilding the xlsx")
    ap.add_argument("--fast-capture", action="store_true",
                    help="allow HyperFrames' experimental fast capture (faster, but can flicker "
                         "per render worker — run scripts/check_flicker.py on the result)")
    ap.add_argument("--no-layers", action="store_true",
                    help="render flat even if the composition declares a background layer "
                         "(one pass instead of two — for quick iteration while authoring)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, do nothing")
    ap.add_argument("--no-check", action="store_true",
                    help="skip the craft check (check_row.py) that runs at every poster time after the render")
    ap.add_argument("--range", nargs=2, metavar=("IN", "OUT"),
                     help="render only this time window for fast iteration")
    args = ap.parse_args()

    sb_path = os.path.abspath(args.storyboard)
    if not os.path.isfile(sb_path):
        die(f"storyboard not found: {sb_path}")
    project_dir = os.path.dirname(sb_path)
    doc = load(sb_path)

    graphics_dir_rel, added = ensure_graphics_dir(sb_path, doc, args.dry_run)
    graphics_dir_abs = os.path.join(project_dir, graphics_dir_rel)
    if added:
        verb = "would add" if args.dry_run else "added"
        print(f"storyboard.json: {verb} graphics_dir = {graphics_dir_rel!r}")

    comp_path = resolve_composition(graphics_dir_abs, args.selector)
    name = os.path.splitext(os.path.basename(comp_path))[0]
    print(f"-> {name}")

    if args.range:
        do_range(graphics_dir_abs, name, args.range[0], args.range[1], args.dry_run)
        return

    asset_file_rel = f"assets/{name}.mp4"
    entry = load_plan(graphics_dir_abs).get(name)
    if entry:
        import copy
        preview = copy.deepcopy(doc)          # what the board will look like after registering
        planned_rows(preview, entry, asset_file_rel)
        print(f"  plan.json: rows {entry['rows'][0]}-{entry['rows'][1]}")
    else:
        preview = doc
    referencing = [(row, asset) for row in doc["rows"] for asset in row.get("assets", [])
                   if asset.get("file") == asset_file_rel]
    poster_plan = poster_plan_for(preview, asset_file_rel)

    # A composition that marks its background (data-sb-layer="bg") is delivered as layers: the
    # graphic on alpha, the background on its own, and a composited preview — see layers.py.
    # A background marked data-sb-preview-only (the presenter frame behind an overlay) is used for
    # the board preview and never delivered: the editor has the real footage.
    layered = layers.declares_bg_layer(comp_path) and not args.no_layers
    bg_delivered = layered and not layers.bg_is_preview_only(comp_path)

    if args.dry_run:
        print("[dry-run] would lint the project")
        if layered:
            print(f"[dry-run] layered delivery: would also write assets/{name}.graphic.mov (alpha)"
                  + (f" and assets/{name}.bg.mp4" if bg_delivered else " (bg is preview-only)")
                  + f"; assets/{name}.mp4 becomes their composite")
        print(f"[dry-run] would render compositions/{name}.html -> "
              f"{graphics_dir_rel}/renders/{name}.mp4 (quality high)")
        print(f"[dry-run] would copy renders/{name}.mp4 -> {asset_file_rel}")
        if poster_plan:
            for n, poster, t, how in poster_plan:
                print(f"[dry-run] would cut poster {poster} @ {t:.3f}s (row {n}, {how})")
        else:
            print(f"[dry-run] no row references {asset_file_rel} — no posters would be cut")
        if not args.no_xlsx:
            print(f"[dry-run] would rebuild {find_xlsx(project_dir, doc)}")
        return

    # ---- lint (whole project, same as rebuild-row.sh) ----
    lint = run(["npx", "--yes", HF_PKG, "lint"], cwd=graphics_dir_abs)
    if lint.returncode != 0:
        print("lint failed — full output:")
        print(lint.stdout)
        print(lint.stderr)
        die("lint failed", code=1)
    print("  lint ok")

    # ---- sound effects (opt-in per composition) ----
    # A row has sound only if it has a cue sheet at sfx/<name>.json. The track is rebuilt from the
    # composition's live timeline before every render, so a retimed animation carries its sounds
    # with it; rows without a cue sheet render silent exactly as before.
    if os.path.exists(os.path.join(graphics_dir_abs, "sfx", name + ".json")):
        sp = run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfx_track.py"),
                  graphics_dir_abs, name, "--write-audio-tag"], cwd=graphics_dir_abs)
        if sp.returncode != 0:
            print(sp.stdout); print(sp.stderr)
            die("sfx track failed", code=1)
        print("  sfx track rebuilt from the timeline")

    # ---- render ----
    render_rel = f"renders/{name}.mp4"
    render_cmd = ["npx", "--yes", HF_PKG, "render", "--composition", f"compositions/{name}.html",
                  "--quality", "high", "-o", render_rel, "--quiet"]
    # Screenshot capture, not HyperFrames' experimental fast capture (drawElementImage), unless
    # asked. Fast capture splits frames across workers and can draw a transformed layer a
    # sub-pixel differently on one of them — measured 1.75px on every 3rd frame of a camera-rail
    # clip, which reads as a steady flicker during holds. Screenshot capture of the same
    # composition: zero flicker frames. Correct frames beat a faster render.
    if not args.fast_capture:
        render_cmd += ["--experimental-fast-capture=false"]
    # a row can pin its own CRF (stored on its asset) so later rebuilds do not lose it
    crf = args.crf or next((asset.get("crf") for _row, asset in referencing if asset.get("crf")), None)
    if crf:
        render_cmd += ["--crf", str(crf)]
        print(f"  encoding at crf {crf}")
    if args.crf:
        with editing(sb_path) as live:        # pinned, so a later plain rebuild encodes the same
            for row in live["rows"]:
                for asset in row.get("assets", []):
                    if asset.get("file") == asset_file_rel:
                        asset["crf"] = str(args.crf)
    layer_files = None
    if layered:
        # two passes (graphic on alpha, background alone) and an ffmpeg composite for the preview;
        # the composite lands at render_rel, so posters, checks and the board see no difference
        try:
            layer_files = layers.render_layers(graphics_dir_abs, name,
                                               fast_capture=args.fast_capture, crf=crf,
                                               hf_pkg=HF_PKG)
        except RuntimeError as e:
            print(e)
            die("layered render failed")
    else:
        proc = run(render_cmd, cwd=graphics_dir_abs)
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr)
            die("render failed")
        print(f"  rendered {render_rel}")

    # ---- copy into the project's assets/ ----
    src = os.path.join(graphics_dir_abs, render_rel)
    dst = os.path.join(project_dir, asset_file_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  copied -> {asset_file_rel}")
    delivered = {}
    if layer_files:
        for key, ext in (("graphic", "graphic.mov"), ("bg", "bg.mp4")):
            rel = f"assets/{name}.{ext}"
            if key == "bg" and not bg_delivered:
                stale = os.path.join(project_dir, rel)
                if os.path.exists(stale):       # an older render delivered it; the editor must not get it
                    os.remove(stale)
                    print(f"  removed {rel} (preview-only background)")
                continue
            shutil.copy2(os.path.join(graphics_dir_abs, layer_files[key]), os.path.join(project_dir, rel))
            delivered[key] = rel
            print(f"  copied -> {rel}")

    # ---- register: patch the CURRENT board (re-read under a lock), never the copy loaded before
    # the render — anything edited while the render ran is kept ----
    with editing(sb_path) as live:
        if entry:
            planned_rows(live, entry, asset_file_rel)
        for row in live["rows"]:
            for asset in row.get("assets", []):
                if asset.get("file") != asset_file_rel:
                    continue
                if delivered:       # `file` stays the composited preview; deliverables listed beside it
                    asset["layers"] = dict(delivered)
                else:               # composition no longer layered: drop the stale pointers
                    asset.pop("layers", None)
        poster_plan = poster_plan_for(live, asset_file_rel)

    # ---- posters, cut straight from the board ----
    if not poster_plan:
        print(f"  no row references {asset_file_rel} — render left in place, no posters cut")
    for n, poster, t, how in poster_plan:
        poster_abs = os.path.join(project_dir, poster)
        os.makedirs(os.path.dirname(poster_abs), exist_ok=True)
        ff = subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", dst, "-frames:v", "1",
                              poster_abs], capture_output=True, text=True)
        if ff.returncode != 0:
            last = ff.stderr.strip().splitlines()[-1] if ff.stderr.strip() else "unknown error"
            print(f"  ! row {n}: poster cut failed ({poster}) — {last}")
            continue
        print(f"  poster {poster} @ {t:.2f}s (row {n}, {how})")

    # ---- craft check at every poster time (the frames stakeholders will actually see) ----
    check_failed = False
    if poster_plan and not args.no_check:
        times = ",".join(f"{t:.3f}" for _, _, t, _ in poster_plan)
        chk = run(["python3", CHECK_ROW, sb_path, name, "--at", times, "--strict"], cwd=project_dir)
        tail = [l for l in chk.stdout.splitlines() if l.strip()][-14:]
        print("  check:")
        for l in tail:
            print("    " + l)
        if chk.returncode != 0:
            check_failed = True
            print("  ! CHECK FAILED at a poster time — render and posters are kept so you can look;"
                  " fix the composition and rebuild (or --no-check to accept)")

    # ---- xlsx ----
    if not args.no_xlsx:
        xlsx_name = find_xlsx(project_dir, doc)
        kept = archive_if_commented(project_dir, xlsx_name)
        if kept:
            print(f"  ! {xlsx_name} carries reviewer comments — archived to {kept} before overwrite")
            print(f"    read them in with: python3 {INGEST_SHEET_COMMENTS} storyboard.json \"{kept}\" --apply")
        proc = run(["python3", SB_TO_XLSX, "storyboard.json", xlsx_name], cwd=project_dir)
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr)
            die("xlsx rebuild failed")
        print(f"  board rebuilt ({xlsx_name})")

    print(f"done. {asset_file_rel}")
    if check_failed:
        sys.exit(3)


if __name__ == "__main__":
    main()
