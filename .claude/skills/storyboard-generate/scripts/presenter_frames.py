#!/usr/bin/env python3
"""Board-preview frames for TALKING HEAD + OVERLAY rows, from one still of the presenter.

  presenter_frames.py <presenter.jpg> <out_dir> [--name andy] [--zoom 1.45] [--subject-x 0.5]
                      [--no-dim]

Writes, at 1920x1080:
  <name>-center.jpg   the frame as shot (cover-fit)            -> lower-third overlays
  <name>-left.jpg     reframed in, presenter on the LEFT third  -> overlays placed right
  <name>-right.jpg    reframed in, presenter on the RIGHT third -> overlays placed left
  …-dim.jpg           each with a darkening gradient on the overlay side — a stand-in for the
                      grade the editor adds, so light type reads on the board. Preview only; it
                      is never delivered (the composition marks it data-sb-preview-only).

The reframes mimic cropping a 4K waist-up shot: zoom in (--zoom), then slide so the presenter
(--subject-x, as a fraction of the source width) lands on a third. Needs Pillow.
"""
import argparse, os
from PIL import Image

W, H = 1920, 1080


def cover(im, zoom=1.0, subject_x=0.5, target_x=0.5):
    """Scale im to cover WxH times zoom, then crop so subject_x lands at target_x of the frame."""
    s = max(W / im.width, H / im.height) * zoom
    big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    left = round(subject_x * big.width - target_x * W)
    left = max(0, min(big.width - W, left))
    top = (big.height - H) // 2
    return big.crop((left, top, left + W, top + H))


def darken(im, side, strength=165):
    """Gradient to black on the overlay side ('right' | 'left' | 'bottom')."""
    if side in ("right", "left"):
        col = []
        for x in range(W):
            t = (x - W * 0.42) / (W * 0.58) if side == "right" else (W * 0.58 - x) / (W * 0.58)
            col.append(int(max(0.0, min(1.0, t)) ** 0.8 * strength))
        g = Image.new("L", (W, 1)); g.putdata(col)
    else:
        row = [int(max(0.0, min(1.0, (y - H * 0.6) / (H * 0.4))) ** 0.8 * (strength + 10)) for y in range(H)]
        g = Image.new("L", (1, H)); g.putdata(row)
    return Image.composite(Image.new("RGB", (W, H)), im, g.resize((W, H)))


def main():
    ap = argparse.ArgumentParser(description="Presenter preview frames for overlay rows.")
    ap.add_argument("src"); ap.add_argument("out_dir")
    ap.add_argument("--name", default="presenter")
    ap.add_argument("--zoom", type=float, default=1.45)
    ap.add_argument("--subject-x", type=float, default=0.5)
    ap.add_argument("--no-dim", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    im = Image.open(a.src).convert("RGB")
    frames = {  # file suffix: (zoom, target x of the presenter, side the overlay sits on)
        "center": (1.0, 0.5, "bottom"),
        "left": (a.zoom, 0.27, "right"),
        "right": (a.zoom, 0.73, "left"),
    }
    for suffix, (zoom, tx, side) in frames.items():
        fr = cover(im, zoom, a.subject_x, tx)
        out = os.path.join(a.out_dir, f"{a.name}-{suffix}.jpg")
        fr.save(out, quality=92)
        print(out)
        if not a.no_dim:
            out = os.path.join(a.out_dir, f"{a.name}-{suffix}-dim.jpg")
            darken(fr, side).save(out, quality=92)
            print(out)


if __name__ == "__main__":
    main()
