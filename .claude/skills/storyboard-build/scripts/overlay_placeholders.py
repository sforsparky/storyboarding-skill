#!/usr/bin/env python3
"""overlay_placeholders.py — give every TALKING HEAD + OVERLAY row a board placeholder.

Composites the waist-up presenter silhouette (storyboard-generate/assets/silhouette/) with a dashed
c-green zone where the overlay will sit, writes assets/_placeholders/overlay-{right|left|lower-third}.jpg
in the project, and sets each overlay row's assets to one `kind: "placeholder"` asset. Placement is read
from the row's visual_direction ("lower third" / "overlay left" / default right). Rows that already have a
non-placeholder asset are left alone, so re-running after /storyboard-generate is safe.

Usage: overlay_placeholders.py <storyboard.json>
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_types import OVERLAY_TYPES, normalize_type

SIL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                   "storyboard-generate", "assets", "silhouette"))
# overlay side -> (silhouette with presenter on the opposite side, overlay zone box at 1920x1080)
ZONES = {
    "right": ("presenter-left.png", (1010, 140, 1820, 940)),
    "left": ("presenter-right.png", (100, 140, 910, 940)),
    "lower third": ("presenter-center.png", (140, 790, 1780, 1010)),
}
GREEN, DARK = "#1DA877", "#0E6E4D"


def placement(row):
    d = (row.get("visual_direction") or "").lower()
    if "lower third" in d:
        return "lower third"
    if "overlay left" in d or d.startswith("left"):
        return "left"
    return "right"


def font(size):
    for cand in ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial Unicode.ttf"):
        try:
            return ImageFont.truetype(cand, size, index=1 if cand.endswith(".ttc") else 0)
        except Exception:
            continue
    return ImageFont.load_default()


def render(kind, out):
    sil, (x0, y0, x1, y1) = ZONES[kind]
    im = Image.open(os.path.join(SIL, sil)).convert("RGBA")
    wash = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(wash).rounded_rectangle((x0, y0, x1, y1), radius=24, fill=(29, 168, 119, 40))
    im = Image.alpha_composite(im, wash).convert("RGB")
    d = ImageDraw.Draw(im)
    for x in range(x0, x1, 28):
        d.line([(x, y0), (min(x + 14, x1), y0)], fill=GREEN, width=4)
        d.line([(x, y1), (min(x + 14, x1), y1)], fill=GREEN, width=4)
    for y in range(y0, y1, 28):
        d.line([(x0, y), (x0, min(y + 14, y1))], fill=GREEN, width=4)
        d.line([(x1, y), (x1, min(y + 14, y1))], fill=GREEN, width=4)
    f = font(34)
    t = f"OVERLAY ({kind.upper()})"
    d.text(((x0 + x1 - d.textlength(t, font=f)) / 2, (y0 + y1) / 2 - 20), t, font=f, fill=DARK)
    im.save(out, quality=88)


def main(sb_path):
    root = os.path.dirname(os.path.abspath(sb_path))
    doc = json.load(open(sb_path))
    os.makedirs(os.path.join(root, "assets", "_placeholders"), exist_ok=True)
    made, n = set(), 0
    for r in doc["rows"]:
        if normalize_type(r["visual_type"]) not in OVERLAY_TYPES:
            continue
        if any(a.get("kind") != "placeholder" for a in r.get("assets") or []):
            continue  # already generated
        kind = placement(r)
        rel = f"assets/_placeholders/overlay-{kind.replace(' ', '-')}.jpg"
        if kind not in made:
            render(kind, os.path.join(root, rel)); made.add(kind)
        r["assets"] = [{"file": rel, "poster": rel, "kind": "placeholder",
                        "source": "silhouette", "duration": None}]
        n += 1
    json.dump(doc, open(sb_path, "w"), indent=2, ensure_ascii=False)
    print(f"{n} overlay row(s) given a silhouette placeholder")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
