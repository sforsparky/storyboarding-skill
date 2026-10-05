#!/usr/bin/env python3
"""Write TALKING HEAD + OVERLAY compositions from a project spec table, and their plan.json entries.

  make_overlays.py <storyboard.json> <specs.py> [--only NAME_FRAGMENT] [--dry-run]

The project keeps only what is its own — the copy and layout of each overlay — in a specs module
(conventionally <graphics_dir>/tools/overlay_specs.py):

  SPECS = {"005_still-early-boom": (5, 5, "right", lambda b: '<div class="card" data-in="0.30">…</div>'), …}
            name (NNN_slug)          rows  placement  builder(beat_starts) -> inner html  [, bg image]
            placements: right | left | lower | center-lower | sides (see kit/overlay/sb-overlay.css);
            an optional 5th item names a different preview frame in assets/presenter/ (e.g. a
            screencast stand-in when the overlay sits on screen footage, not the presenter)
  PRESENTER = {"right": "andy-left-dim.jpg", "left": "andy-right-dim.jpg", "lower": "andy-center-dim.jpg"}
            preview frame per placement, in <graphics_dir>/assets/presenter/ (presenter_frames.py)
  HEAD = '<link href="assets/fonts/fonts.css" rel="stylesheet"><link href="shared/brand.css" rel="stylesheet">'
            the brand's own stylesheet links (the kit's sb-overlay.css/js are added after them)
  WPS, PAD, MIN_BEAT   optional VO pace overrides (words/sec, air after a beat, shortest beat)
  POSTER_TIMES = {"018_explode-vs-over": [14.2]}   optional: a beat's poster second when the default
            (82% through the beat) would land on an element still entering

This engine does everything else, identically on every project:
  - beat lengths from the rows' VO word count, so each row's segment and poster time follow the read
  - the presenter frame as the background layer, marked data-sb-layer="bg" data-sb-preview-only
    data-check-ignore: the board shows the overlay over the presenter, the editor receives
    <name>.graphic.mov alone (no .bg.mp4), and the craft check ignores the frame
  - the kit (kit/overlay/sb-overlay.css + sb-overlay.js) copied into <graphics_dir>/shared/
  - a plan.json entry per composition, so render_plan.py / rebuild.py register the rows in one pass

Builders get beat_starts (seconds, one per row) and place elements with data-in="<sec>".
"""
import argparse, importlib.util, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "..", "kit", "overlay")
WPS, PAD, MIN_BEAT = 2.6, 0.9, 2.4     # VO pace (words/sec), air after a beat's last word, floor
POSTER_AT = 0.82                       # poster late in each beat, after the last element settles


def beat_len(script, wps=WPS, pad=PAD, floor=MIN_BEAT):
    words = len(re.findall(r"[\w$’'%,.-]+", script or ""))
    return max(floor, round(words / wps + pad, 2))


def page(cid, place, inner, dur, presenter_img, head):
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1920, height=1080">
{head}
<link href="shared/sb-overlay.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script src="shared/sb-overlay.js"></script>
</head>
<body>
<!-- TALKING HEAD + OVERLAY, written by storyboard-generate/scripts/make_overlays.py from the project's
     overlay specs — edit the spec, not this file. The presenter frame is a preview-only background:
     the board shows the overlay over it, the editor receives the overlay alone on alpha. -->
<div id="root" data-composition-id="{cid}" data-start="0" data-duration="{dur}" data-width="1920" data-height="1080" data-fps="30">
  <img class="bg-sil" data-sb-layer="bg" data-sb-preview-only data-check-ignore src="assets/presenter/{presenter_img}" alt="">
  <div class="zone {place}">{inner}
  </div>
</div>
<script>
  const tl = SB_OV.build({dur});
  window.__timelines = window.__timelines || {{}};
  window.__timelines["{cid}"] = tl;
</script>
</body>
</html>
'''


def load_specs(path):
    spec = importlib.util.spec_from_file_location("overlay_specs", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec.loader.exec_module(mod)
    return mod


def install_kit(graphics_dir):
    shared = os.path.join(graphics_dir, "shared")
    os.makedirs(shared, exist_ok=True)
    for f in ("sb-overlay.css", "sb-overlay.js"):
        shutil.copy2(os.path.join(KIT, f), os.path.join(shared, f))


def main():
    ap = argparse.ArgumentParser(description="Write overlay compositions + plan.json entries from specs.")
    ap.add_argument("storyboard")
    ap.add_argument("specs")
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sb_path = os.path.abspath(args.storyboard)
    sb = json.load(open(sb_path))
    gdir = os.path.join(os.path.dirname(sb_path), sb.get("graphics_dir", "videos/vsl-graphics"))
    mod = load_specs(args.specs)
    wps, pad, floor = (getattr(mod, k, d) for k, d in (("WPS", WPS), ("PAD", PAD), ("MIN_BEAT", MIN_BEAT)))
    head = getattr(mod, "HEAD", "")
    rows = {r["n"]: r for r in sb["rows"]}

    entries = {}
    for name, spec in mod.SPECS.items():
        a, b, place, build = spec[:4]
        bg = spec[4] if len(spec) > 4 else mod.PRESENTER.get(place)
        if args.only and args.only not in name:
            continue
        if not bg:
            sys.exit(f"error: {name}: placement {place!r} has no PRESENTER frame")
        lens = [beat_len(rows[n].get("script", ""), wps, pad, floor) for n in range(a, b + 1)]
        starts, t = [], 0.0
        for L in lens:
            starts.append(round(t, 2)); t += L
        dur = round(t, 2)
        posters = getattr(mod, "POSTER_TIMES", {}).get(name) or \
            [round(min(s + L * POSTER_AT, dur - 0.5), 2) for s, L in zip(starts, lens)]
        entries[name] = {"rows": [a, b], "duration": dur, "cuts": starts + [dur],
                         "poster_times": posters, "kind": "custom_graphic"}
        print(f"{name}: rows {a}-{b}  {dur:.2f}s  cuts {starts + [dur]}")
        if not args.dry_run:
            html = page("r" + name[:3], place, build(starts), dur, bg, head)
            with open(os.path.join(gdir, "compositions", name + ".html"), "w") as f:
                f.write(html)

    if args.dry_run:
        return
    install_kit(gdir)
    plan_path = os.path.join(gdir, "plan.json")
    plan = json.load(open(plan_path)) if os.path.exists(plan_path) else {}
    plan.update(entries)
    with open(plan_path, "w") as f:
        json.dump(dict(sorted(plan.items())), f, indent=1)
    print(f"{len(entries)} overlay(s) written; plan.json updated. Render: render_plan.py "
          f"{os.path.relpath(sb_path)} {args.only or ''}".rstrip())


if __name__ == "__main__":
    main()
