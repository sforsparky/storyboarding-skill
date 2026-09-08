#!/usr/bin/env python3
"""Extract a representative color palette from every reference image in a brand's refs/ folder.

Input: brands/<brand>/refs/  (png/jpg/jpeg/webp/gif raster; hex fills are also scraped from svg).
Output: JSON to stdout — a merged, deduped palette with hex, RGB, coverage %, saturation, and a
rough role guess (background / accent / neutral). This gives Claude accurate hexes to build
brand.json from, instead of eyeballing colors. Claude still reads the images itself for type,
logo, and motif — this script only does the color math.

Usage: extract_palette.py brands/<brand>/refs [--swatch out.png]
"""
import os, sys, json, glob, colorsys, re

def load_images(folder):
    from PIL import Image
    exts = ("*.png","*.jpg","*.jpeg","*.webp","*.gif","*.PNG","*.JPG","*.JPEG")
    paths = []
    for e in exts: paths += glob.glob(os.path.join(folder, e))
    imgs = []
    for p in sorted(set(paths)):
        try:
            im = Image.open(p).convert("RGB"); im.thumbnail((240,240)); imgs.append((p, im))
        except Exception as ex:
            print(f"skip {p}: {ex}", file=sys.stderr)
    return imgs

def svg_hexes(folder):
    out = []
    for p in glob.glob(os.path.join(folder, "*.svg")) + glob.glob(os.path.join(folder, "*.SVG")):
        try:
            txt = open(p, encoding="utf-8", errors="ignore").read()
            out += re.findall(r'#[0-9a-fA-F]{6}', txt)
        except Exception: pass
    return out

def quantize_counts(im, n=8):
    from PIL import Image
    q = im.quantize(colors=n, method=Image.FASTOCTREE)
    pal = q.getpalette()
    counts = q.getcolors() or []
    total = sum(c for c,_ in counts) or 1
    res = []
    for cnt, idx in counts:
        r,g,b = pal[idx*3:idx*3+3]
        res.append(((r,g,b), cnt/total))
    return res

def hexof(rgb): return "#%02X%02X%02X" % rgb
def sat(rgb):
    r,g,b = [x/255 for x in rgb]; return colorsys.rgb_to_hls(r,g,b)[2]
def lum(rgb):
    r,g,b = [x/255 for x in rgb]; return 0.2126*r+0.7152*g+0.0722*b
def dist(a,b): return sum((x-y)**2 for x,y in zip(a,b))**0.5

def merge(colors, thresh=34):
    """colors: list of (rgb, weight). Merge near-duplicates, keep weighted."""
    buckets = []
    for rgb, w in sorted(colors, key=lambda t:-t[1]):
        for bk in buckets:
            if dist(bk["rgb"], rgb) < thresh:
                bk["w"] += w; break
        else:
            buckets.append({"rgb": rgb, "w": w})
    return buckets

def role(rgb):
    s, l = sat(rgb), lum(rgb)
    if s > 0.45 and 0.15 < l < 0.85: return "accent"
    if l > 0.85: return "paper"
    if l < 0.12: return "ink"
    if s < 0.18: return "neutral"
    return "brand"

def main():
    folder = sys.argv[1]
    swatch = None
    if "--swatch" in sys.argv: swatch = sys.argv[sys.argv.index("--swatch")+1]
    imgs = load_images(folder)
    all_colors = []
    for _, im in imgs:
        all_colors += quantize_counts(im, 8)
    # svg fills count as strong signals (logo colors)
    for h in svg_hexes(folder):
        rgb = tuple(int(h[i:i+2],16) for i in (1,3,5)); all_colors.append((rgb, 0.05))
    merged = merge(all_colors)
    tw = sum(b["w"] for b in merged) or 1
    palette = []
    for b in sorted(merged, key=lambda x:-x["w"])[:10]:
        rgb = b["rgb"]
        palette.append({"hex": hexof(rgb), "rgb": list(rgb),
                        "coverage": round(b["w"]/tw, 3),
                        "saturation": round(sat(rgb),2), "luminance": round(lum(rgb),2),
                        "role_guess": role(rgb)})
    result = {"folder": folder, "image_count": len(imgs), "palette": palette}
    if swatch and palette:
        from PIL import Image, ImageDraw
        w=120; sw=Image.new("RGB",(w*len(palette),160),"white"); d=ImageDraw.Draw(sw)
        for i,c in enumerate(palette):
            d.rectangle([i*w,0,(i+1)*w,120], fill=tuple(c["rgb"]))
            d.text((i*w+6,126), c["hex"], fill="black")
        sw.save(swatch); result["swatch"]=swatch
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
