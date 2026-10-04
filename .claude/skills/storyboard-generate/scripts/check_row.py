#!/usr/bin/env python3
"""check_row.py — automated frame verification for a HyperFrames composition.

Seeks a composition's registered GSAP timeline to a set of times (by default: every row's
poster_t plus the transition frames around each internal segment boundary), screenshots each
frame, and checks the DOM + pixels against the storyboard-generate "Craft standards":

  OFF_FRAME  — a text/img/svg element whose bbox runs past the 0..1920 x 0..1080 frame
  OVERLAP    — two text/img/svg leaf elements whose boxes intersect (neither is an ancestor)
  LINES      — headline-style elements (class disp/ph/h or h1-h4) wrapping past 2 lines
  SOFT_EDGE  — a linear-gradient box with no border or radius whose ends stop inside the frame:
               the gradient fades along one axis but the two edges across it are hard crop
               lines (the shelf-shadow bug). Element-based, so it fires even when the step is
               too faint or too short for the pixel scan.
  HARD_EDGE  — a luminance step across a long contiguous run, i.e. a visible crop line

Usage:
  check_row.py <storyboard.json> <row-number|name-fragment> [--at t1,t2,...] [--out DIR]
               [--ignore sel1,sel2] [--strict]

Renders one PNG per time, a report.json, a labelled contact sheet (sheet.png), and a printed
summary. Exits 1 with --strict if any finding was recorded on any frame.
"""
import argparse, glob, http.server, json, os, socket, subprocess, sys, threading, time
from functools import partial

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROBE_JS = os.path.join(SCRIPT_DIR, "_probe.mjs")

DEFAULT_GRAPHICS_DIR = "videos/vsl-graphics"
HEADLINE_CLASSES = {"disp", "ph", "h"}
HEADLINE_TAGS = {"h1", "h2", "h3", "h4"}
MARGIN_OFF_FRAME = 2
OVERLAP_MIN = 6
HARD_EDGE_DIFF_THRESH = 18
HARD_EDGE_MIN_RUN = 60
HARD_EDGE_STEP = 1
HARD_EDGE_ELEMENT_MARGIN = 3
HARD_EDGE_FRAME_MARGIN = 3


# ---------------------------------------------------------------------------
# Storyboard / composition resolution (mirrors rebuild-row.sh's logic)
# ---------------------------------------------------------------------------

def load_storyboard(path):
    with open(path) as f:
        return json.load(f)


def resolve_composition(project_dir, graphics_dir, query):
    comp_dir = os.path.join(project_dir, graphics_dir, "compositions")
    q = str(query).strip()
    if q.isdigit():
        q = f"{int(q):03d}"
    all_html = sorted(glob.glob(os.path.join(comp_dir, "*.html")))
    matches = [p for p in all_html if q.lower() in os.path.basename(p).lower()]
    if not matches:
        raise SystemExit(f"no composition matches '{query}' in {comp_dir}\n"
                          f"available: {[os.path.basename(p) for p in all_html]}")
    if len(matches) > 1:
        raise SystemExit(f"'{query}' is ambiguous:\n" + "\n".join(matches))
    return matches[0]


def read_composition_meta(html_path):
    with open(html_path, encoding="utf-8") as f:
        text = f.read()
    import re
    m_id = re.search(r'data-composition-id="([^"]+)"', text)
    m_dur = re.search(r'data-duration="([^"]+)"', text)
    if not m_id or not m_dur:
        raise SystemExit(f"{html_path}: missing data-composition-id or data-duration on #root")
    return m_id.group(1), float(m_dur.group(1))


def rows_referencing(storyboard, basename):
    """Rows whose assets[] point at this composition's rendered file (<basename>.mp4/.png/...)."""
    hits = []
    for row in storyboard.get("rows", []):
        for asset in row.get("assets", []) or []:
            f = asset.get("file") or ""
            if os.path.splitext(os.path.basename(f))[0] == basename:
                hits.append((row, asset))
    return hits


def default_times(refs, duration):
    times = set()
    boundaries = set()
    for row, asset in refs:
        pt = asset.get("poster_t")
        if pt is not None:
            times.add(float(pt))
        seg = asset.get("segment")
        if seg and len(seg) == 2:
            boundaries.add(float(seg[0]))
            boundaries.add(float(seg[1]))
    internal = {b for b in boundaries if 0 < b < duration}
    for b in internal:
        times.add(round(b - 0.4, 3))
        times.add(round(b + 0.4, 3))
    times = {round(max(0.0, min(duration, t)), 3) for t in times}
    return sorted(times)


# ---------------------------------------------------------------------------
# Static file server for GRAPHICS (relative asset paths must resolve from its root)
# ---------------------------------------------------------------------------

def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def serve_dir(root, port):
    handler = partial(_QuietHandler, directory=root)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


# ---------------------------------------------------------------------------
# Node probe invocation
# ---------------------------------------------------------------------------

def run_probe(url, comp_id, out_dir, times, ignore_selectors):
    times_csv = ",".join(str(t) for t in times)
    ignore_csv = ",".join(ignore_selectors)
    cmd = ["node", PROBE_JS, url, comp_id, out_dir, times_csv, ignore_csv]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"probe failed (exit {proc.returncode})")
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        sys.stderr.write(proc.stdout + "\n" + proc.stderr)
        raise SystemExit(f"could not parse probe output: {e}")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def label(el):
    bits = [el["tag"]]
    if el.get("id"):
        bits.append("#" + el["id"])
    if el.get("classes"):
        bits.append("." + ".".join(el["classes"]))
    return "".join(bits)


def is_ancestor(path_a, path_b):
    return len(path_a) <= len(path_b) and path_b[: len(path_a)] == path_a


def effective_bbox(el):
    """Tight text-glyph bbox when the element carries direct text (a block-level label is
    often much wider than the text it holds), else its full box (img/svg content is its box)."""
    if el["hasText"] and el.get("textBbox"):
        return el["textBbox"]
    return el["bbox"]


CANVAS_AREA_FRACTION = 0.40


def is_content(el, width, height):
    """Text, images and glyph-sized SVGs are content. An <svg> covering most of the frame is a
    drawing canvas (a path layer over the scene) — its box says nothing about what is drawn,
    so it is neither off-frame nor an overlap partner."""
    if el.get("ignored"):
        return False
    if el["hasText"] or el["tag"] == "img":
        return True
    if el["tag"] == "svg":
        # A route/gauge svg that fills its own container is a drawing layer even when it is
        # small against the frame: the markers and labels pinned onto the path it draws are
        # SUPPOSED to sit on top of it, and scoring that as an overlap buries the real ones.
        if el.get("fillsParent"):
            return False
        b = el["bbox"]
        return (b["r"] - b["l"]) * (b["b"] - b["t"]) < CANVAS_AREA_FRACTION * width * height
    return False


def check_off_frame(elements, width, height):
    findings = []
    for el in elements:
        if not is_content(el, width, height):
            continue
        if el.get("overlapOk"):
            continue                     # a camera move is supposed to take these off-frame
        b = effective_bbox(el)
        sides = [
            ("left", -MARGIN_OFF_FRAME - b["l"]),
            ("top", -MARGIN_OFF_FRAME - b["t"]),
            ("right", b["r"] - (width + MARGIN_OFF_FRAME)),
            ("bottom", b["b"] - (height + MARGIN_OFF_FRAME)),
        ]
        for side, overshoot in sides:
            if overshoot > 0:
                findings.append({
                    "element": label(el), "id": el.get("id"), "side": side,
                    "overshoot_px": round(overshoot, 1), "bbox": b,
                })
    return findings


def check_overlap(elements, width, height):
    findings = []
    candidates = [el for el in elements if is_content(el, width, height)]
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            if is_ancestor(a["path"], b["path"]) or is_ancestor(b["path"], a["path"]):
                continue
            if a.get("overlapOk") and b.get("overlapOk"):
                continue                 # both inside a group that overlaps by design

            ba, bb = effective_bbox(a), effective_bbox(b)
            ow = min(ba["r"], bb["r"]) - max(ba["l"], bb["l"])
            oh = min(ba["b"], bb["b"]) - max(ba["t"], bb["t"])
            if ow > OVERLAP_MIN and oh > OVERLAP_MIN:
                findings.append({
                    "a": label(a), "b": label(b),
                    "intersection": {"w": round(ow, 1), "h": round(oh, 1)},
                })
    return findings


def check_lines(elements):
    """Headline-style elements: class token containing 'disp', 'ph', or 'h'."""
    all_headlines = []
    violations = []
    for el in elements:
        if el.get("ignored") or not el["hasText"]:
            continue
        classes = set(el.get("classes") or [])
        # exact class tokens (substring matching flagged span.chip because "chip" contains "h")
        if not (classes & HEADLINE_CLASSES or el.get("tag") in HEADLINE_TAGS):
            continue
        b = el["bbox"]
        height = b["b"] - b["t"]
        lh = el["lineHeight"] or (el["fontSize"] * 1.2)
        lines = round(height / lh) if lh else 0
        entry = {"element": label(el), "id": el.get("id"), "lines": lines}
        all_headlines.append(entry)
        if lines > 2:
            violations.append(entry)
    return all_headlines, violations


def _gradient_axis(bg):
    """'v' if the linear gradient runs top<->bottom (so its LEFT/RIGHT ends are hard), 'h' if it
    runs left<->right (TOP/BOTTOM ends hard), None for anything else (radial, diagonal, none)."""
    if "linear-gradient" not in bg:
        return None
    head = bg.split("linear-gradient(", 1)[1][:40].strip().lower()
    if head.startswith(("0deg", "180deg", "to bottom", "to top")) or head.startswith("rgb") or head.startswith("#"):
        return "v"                       # default direction is "to bottom"
    if head.startswith(("90deg", "270deg", "to right", "to left")):
        return "h"
    return None


def check_soft_edges(elements, width, height):
    findings = []
    for el in elements:
        if el.get("selfIgnored") or el.get("hasText"):
            continue
        if el.get("borderWidth", 0) > 0 or el.get("borderRadius", 0) > 0:
            continue                     # a bordered/rounded box is a card, its edges are meant
        axis = _gradient_axis(el.get("bgImage", "none"))
        if not axis:
            continue
        b = el["bbox"]
        edges = [("left", b["l"]), ("right", b["r"])] if axis == "v" else [("top", b["t"]), ("bottom", b["b"])]
        limit = width if axis == "v" else height
        for side, pos in edges:
            if HARD_EDGE_FRAME_MARGIN < pos < limit - HARD_EDGE_FRAME_MARGIN:
                findings.append({"element": label(el), "id": el.get("id"), "edge": side,
                                 "at": round(pos, 1), "why": "linear-gradient box ends inside the frame"})
    return findings


def find_runs_1d(boolarr, min_run):
    n = len(boolarr)
    if n == 0:
        return []
    padded = np.concatenate(([False], boolarr, [False])).astype(np.int8)
    d = np.diff(padded)
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]
    return [(int(s), int(e)) for s, e in zip(starts, ends) if (e - s) >= min_run]


def check_hard_edges(png_path, elements, width, height):
    img = Image.open(png_path).convert("RGB")
    arr = np.asarray(img).astype(np.float64)
    L = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    # Real UI content (headline glyphs, icons, checklist ticks, badges, book-cover art) is
    # SUPPOSED to look crisp — a hard edge there isn't the "soft overlay with a crop line"
    # defect this check hunts for. So mask out every such element's own box (tight text bbox
    # for a text node, full box otherwise); a real crop-line lives in the bare background/
    # overlay area left over. The default-ignore list (.ledge/#spot) mixes two different
    # things and needs to be told apart here: `.ledge` itself is a deliberately crisp rule
    # line (a wrapper, trusted like any other real content) — but `#spot` IS a soft glow
    # directly (no wrapper/child split), and `.ledge i` is `.ledge`'s soft shadow child. Only
    # a direct, by-name match on the ledge-bar's own class counts as "trusted crisp"; anything
    # ignored via an ancestor (the shadow) or by matching `#spot` itself stays unmasked and
    # un-trusted, because THAT is exactly the kind of element this check exists to examine.
    def trusted_crisp(el):
        return not el.get("ignored") or (el.get("selfIgnored") and "ledge" in (el.get("classes") or []))

    content_mask = np.zeros((height, width), dtype=bool)
    for el in elements:
        if not trusted_crisp(el):
            continue
        b = effective_bbox(el)
        l = max(0, int(np.floor(b["l"])))
        t = max(0, int(np.floor(b["t"])))
        r = min(width, int(np.ceil(b["r"])))
        bo = min(height, int(np.ceil(b["b"])))
        if r > l and bo > t:
            content_mask[t:bo, l:r] = True

    # Elements usable as "this coincides with a real border, not a defect" references — same
    # trusted set as the mask (see above): a real border, or the ledge bar's own deliberate line.
    border_refs = [el for el in elements if trusted_crisp(el)]

    findings = []

    def overlaps_element_edge_h(y, x0, x1):
        for el in border_refs:
            b = el["bbox"]
            if abs(b["t"] - y) <= HARD_EDGE_ELEMENT_MARGIN or abs(b["b"] - y) <= HARD_EDGE_ELEMENT_MARGIN:
                ov = min(x1, b["r"]) - max(x0, b["l"])
                if ov > 0:
                    return True
        return False

    def overlaps_element_edge_v(x, y0, y1):
        for el in border_refs:
            b = el["bbox"]
            if abs(b["l"] - x) <= HARD_EDGE_ELEMENT_MARGIN or abs(b["r"] - x) <= HARD_EDGE_ELEMENT_MARGIN:
                ov = min(y1, b["b"]) - max(y0, b["t"])
                if ov > 0:
                    return True
        return False

    # horizontal edges: luminance jump across a small (STEP-row) stencil, contiguous across x.
    # A single-row derivative misses a real hard edge whenever Chrome anti-aliases it across
    # 2px (the per-row step then splits below threshold on both sides); a wider stencil still
    # reads a genuinely soft/gradual gradient (spanning tens-to-hundreds of px, by design) as a
    # tiny fractional change, so it doesn't blur the soft/hard distinction this check is for.
    s = HARD_EDGE_STEP
    dY = np.abs(L[s:, :] - L[:-s, :]) > HARD_EDGE_DIFF_THRESH
    # a jump can't count where either side of the stencil falls inside a masked content region
    dY &= ~(content_mask[s:, :] | content_mask[:-s, :])
    for y in range(dY.shape[0]):
        y_mid = y + s // 2
        if y_mid <= HARD_EDGE_FRAME_MARGIN or y_mid >= height - 1 - HARD_EDGE_FRAME_MARGIN:
            continue
        for (x0, x1) in find_runs_1d(dY[y], HARD_EDGE_MIN_RUN):
            if overlaps_element_edge_h(y_mid, x0, x1):
                continue
            findings.append({"type": "horizontal", "y": y_mid, "x0": x0, "x1": x1, "len": x1 - x0})

    # vertical edges: column-to-column luminance jump (same widened stencil), contiguous across y
    dX = np.abs(L[:, s:] - L[:, :-s]) > HARD_EDGE_DIFF_THRESH
    dX &= ~(content_mask[:, s:] | content_mask[:, :-s])
    for x in range(dX.shape[1]):
        x_mid = x + s // 2
        if x_mid <= HARD_EDGE_FRAME_MARGIN or x_mid >= width - 1 - HARD_EDGE_FRAME_MARGIN:
            continue
        col = dX[:, x]
        for (y0, y1) in find_runs_1d(col, HARD_EDGE_MIN_RUN):
            if overlaps_element_edge_v(x_mid, y0, y1):
                continue
            findings.append({"type": "vertical", "x": x_mid, "y0": y0, "y1": y1, "len": y1 - y0})

    return findings


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------

def build_contact_sheet(frames, out_path):
    cols = 4
    thumb_w = 480
    thumb_h = round(thumb_w * 1080 / 1920)
    label_h = 28
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for idx, fr in enumerate(frames):
        r, c = divmod(idx, cols)
        x0, y0 = c * thumb_w, r * (thumb_h + label_h)
        thumb = Image.open(fr["png"]).convert("RGB").resize((thumb_w, thumb_h))
        sheet.paste(thumb, (x0, y0 + label_h))
        status = "PASS" if fr["pass"] else "FAIL"
        draw.rectangle([x0, y0, x0 + thumb_w, y0 + label_h], fill=(0, 0, 0))
        draw.text((x0 + 6, y0 + 7), f"t={fr['t']}s  {status}", fill=(255, 255, 255), font=font)
    sheet.save(out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("row")
    ap.add_argument("--at", default=None, help="comma-separated explicit times, overrides defaults")
    ap.add_argument("--out", default=None)
    ap.add_argument("--ignore", default="", help="comma-separated extra CSS selectors to ignore")
    ap.add_argument("--strict", action="store_true")
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
    row_ns = sorted({row["n"] for row, _ in refs})

    if args.at:
        times = sorted({round(float(x), 3) for x in args.at.split(",") if x.strip() != ""})
    else:
        times = default_times(refs, duration)
        if not times:
            times = [round(duration / 2, 3)]

    out_dir = args.out or os.path.join(project_dir, "renders", "check", basename)
    os.makedirs(out_dir, exist_ok=True)

    ignore_selectors = [s.strip() for s in args.ignore.split(",") if s.strip()]

    # Compositions use asset paths ("assets/...", "shared/...") relative to GRAPHICS ROOT,
    # not to compositions/ where the .html actually lives. Serve a copy at root level so
    # those relative fetches resolve the same way they do for the real hyperframes renderer,
    # instead of injecting a <base> tag (simpler, and matches "resolve from GRAPHICS root").
    tmp_html = os.path.join(graphics_root, f"_check_probe_{basename}.html")
    with open(html_path, encoding="utf-8") as f:
        html_text = f.read()
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_text)

    port = free_port()
    httpd = serve_dir(graphics_root, port)
    try:
        # give the server a beat to be reachable
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/{os.path.basename(tmp_html)}"
        probe_result = run_probe(url, comp_id, out_dir, times, ignore_selectors)
    finally:
        httpd.shutdown()
        try:
            os.remove(tmp_html)
        except OSError:
            pass

    width, height = probe_result["width"], probe_result["height"]
    frame_reports = []
    any_finding = False

    for fr in probe_result["frames"]:
        t = fr["t"]
        elements = fr["elements"]
        off_frame = check_off_frame(elements, width, height)
        overlap = check_overlap(elements, width, height)
        headlines, line_violations = check_lines(elements)
        hard_edge = check_hard_edges(fr["png"], elements, width, height)
        soft_edge = check_soft_edges(elements, width, height)

        findings = {
            "off_frame": off_frame,
            "overlap": overlap,
            "lines": line_violations,
            "hard_edge": hard_edge,
            "soft_edge": soft_edge,
        }
        passed = not any(findings.values())
        any_finding = any_finding or not passed

        frame_reports.append({
            "t": t, "png": fr["png"], "pass": passed,
            "findings": findings, "headline_lines": headlines,
        })

    report = {
        "composition": os.path.basename(html_path),
        "composition_id": comp_id,
        "duration": duration,
        "rows": row_ns,
        "times": times,
        "ignore": ignore_selectors,
        "frames": [
            {k: v for k, v in fr.items()} for fr in frame_reports
        ],
    }
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=2)

    build_contact_sheet(frame_reports, os.path.join(out_dir, "sheet.png"))

    print(f"check_row: {os.path.basename(html_path)}  (rows {row_ns}, id={comp_id}, dur={duration}s)")
    print(f"times probed: {times}")
    for fr in frame_reports:
        if fr["pass"]:
            print(f"  t={fr['t']:>6}  PASS")
        else:
            print(f"  t={fr['t']:>6}  FAIL")
            for cat, items in fr["findings"].items():
                for it in items:
                    print(f"      [{cat}] {it}")
    seen_heads = {}
    for fr in frame_reports:
        for h in fr["headline_lines"]:
            seen_heads[h["element"] + (h["id"] or "")] = h
    if seen_heads:
        print("headline line counts: " +
              ", ".join(f"{h['element']}={h['lines']}" for h in seen_heads.values()))
    print(f"out: {out_dir}")

    if args.strict and any_finding:
        sys.exit(1)


if __name__ == "__main__":
    main()
