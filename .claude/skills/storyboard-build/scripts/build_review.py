#!/usr/bin/env python3
"""build_review.py — generate a self-contained stakeholder review page for a video storyboard.

Usage:
    build_review.py <storyboard.json> -o <outdir> [--title T] [--max-total-mb 60]

Produces <outdir>/index.html plus <outdir>/media/... (transcoded preview video/poster files).
The page has no server, no accounts, and no download links — it is meant to be viewed either
directly in a browser (file://) or through a sandboxed artifact viewer. All CSS/JS is inline;
the only external network reference is the Google Fonts stylesheet (explicitly allowed).

Review state (reviewer name, per-row verdict/note) lives in the viewer's own localStorage.
Reviewers export a JSON payload (shown in a textarea + copied to the clipboard) that a
producer later feeds to ingest_review.py to merge back into storyboard.json.
"""
import argparse, json, os, re, shutil, subprocess, sys, html, uuid
from datetime import datetime, timezone
from string import Template

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# Fallback brand colors (used if brands/<brand>/brand.json can't be found/parsed) — match
# PROJECT/brands/futures-mastery-main-vsl/brand.json.
DEFAULT_COLORS = {
    "primary": "#2F7666",
    "primary_bright": "#39CFAB",
    "ink": "#2B4547",
    "paper": "#FFFFFF",
    "surface": "#EBECEC",
    "muted": "#8FA9A2",
    "up": "#26A69A",
    "down": "#EF5350",
    "cta": "#cf7146",
}

INCLUDE_INTERNAL = False
MEDIA_DIR = None

VISUAL_TYPE_COLORS = {
    # brand-derived, not spreadsheet defaults: talking head = ink, graphics = primary,
    # screen captures = muted teal-grey, B-roll = deep ink-green, overlays = up-green
    "TALKING HEAD": "#2B4547",
    "TALKING HEAD + LOWER THIRD": "#08483B",
    "TALKING HEAD + OVERLAY": "#08483B",
    "CUSTOM GRAPHIC": "#2F7666",
    "GRAPHIC / SCREENCAST": "#2F7666",
    "SCREENCAST": "#6F8F88",
    "B-ROLL": "#4A6B64",
    "B-ROLL / GRAPHIC": "#4A6B64",
    "TESTIMONIAL": "#4A6B64",
    "CUTAWAY": "#6F8F88",
}


def log(*a):
    print(*a, file=sys.stderr)


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return False, r.stderr.decode("utf-8", "replace")
    return True, ""


def ffmpeg_video(src, dst, width, crf):
    vf = f"scale={width}:-2:flags=lanczos"
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast",
        "-an", "-movflags", "+faststart",
        dst,
    ]
    return run(cmd)


def ffmpeg_poster(src, dst, width=960, quality=82):
    # Map a 0-100 "quality" (PIL-style) to ffmpeg mjpeg qscale (2=best .. 31=worst).
    q = max(2, min(31, round(31 - (quality / 100.0) * 29)))
    vf = f"scale={width}:-2:flags=lanczos"
    cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf, "-q:v", str(q), "-frames:v", "1", dst]
    return run(cmd)


def dir_size_mb(d):
    total = 0
    for root, _, files in os.walk(d):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / (1024 * 1024)


def out_basename(src_path, new_ext):
    base = os.path.splitext(os.path.basename(src_path))[0]
    return base + new_ext


def clip_label_from_basename(basename):
    m = re.match(r"^0*(\d+)_", basename)
    return m.group(1) if m else basename


def load_brand_colors(project_dir, brand_id):
    colors = dict(DEFAULT_COLORS)
    if not brand_id:
        return colors
    path = os.path.join(project_dir, "brands", brand_id, "brand.json")
    try:
        with open(path) as f:
            data = json.load(f)
        colors.update({k: v for k, v in (data.get("colors") or {}).items() if v})
    except Exception as e:
        log(f"note: could not load brand colors from {path}: {e}")
    return colors


def pick_display_asset(assets):
    """Choose which asset represents a row's media. Returns (mode, asset) where
    mode is 'video', 'image', or 'none'. .mov overlays are never chosen as video —
    only their poster is used (per spec)."""
    video = None
    still = None
    for a in assets or []:
        file = a.get("file") or ""
        ext = os.path.splitext(file)[1].lower()
        if a.get("kind") == "overlay" or ext == ".mov":
            continue
        if ext == ".mp4" and video is None:
            video = a
        elif ext in IMAGE_EXTS and still is None:
            still = a
    if video:
        return "video", video
    if still:
        return "image", still
    # fall back to a poster-only presentation (e.g. only an overlay asset exists)
    for a in assets or []:
        if a.get("poster"):
            return "image", a
    return "none", None


def esc(s):
    return html.escape(s or "", quote=True)


def build_media(rows, project_dir, media_dir, max_total_mb):
    """Transcode every unique referenced video/poster into media_dir. Returns:
       media_map: src_path -> relative media filename (or None if missing on disk)
       missing: list of (row_n, src_path) that couldn't be found
    """
    os.makedirs(media_dir, exist_ok=True)

    # collect unique source files we need previews for
    video_srcs = {}   # src -> planned out filename
    poster_srcs = {}  # src -> planned out filename
    missing = []

    for row in rows:
        mode, asset = pick_display_asset(row.get("assets"))
        if mode == "none":
            continue
        if mode == "video":
            src = os.path.join(project_dir, asset["file"])
            if os.path.exists(src):
                video_srcs.setdefault(asset["file"], out_basename(asset["file"], ".mp4"))
            else:
                missing.append((row["n"], asset["file"]))
        poster_file = asset.get("poster") if asset else None
        if poster_file:
            src = os.path.join(project_dir, poster_file)
            if os.path.exists(src):
                poster_srcs.setdefault(poster_file, out_basename(poster_file, ".jpg"))
            else:
                missing.append((row["n"], poster_file))

    # posters: transcode once, fixed settings (cheap, small)
    for src_rel, out_name in poster_srcs.items():
        src_abs = os.path.join(project_dir, src_rel)
        dst_abs = os.path.join(media_dir, out_name)
        ok, err = ffmpeg_poster(src_abs, dst_abs)
        if not ok:
            log(f"warning: poster transcode failed for {src_rel}: {err[-400:]}")

    # videos: iterate width/crf attempts until under the (video-only share of the) budget
    attempts = [
        (960, 27), (960, 30), (960, 33),
        (854, 30), (854, 33),
        (640, 30), (640, 33),
        (480, 32),
    ]
    poster_total_mb = dir_size_mb(media_dir)
    chosen = None
    for width, crf in attempts:
        for src_rel, out_name in video_srcs.items():
            src_abs = os.path.join(project_dir, src_rel)
            dst_abs = os.path.join(media_dir, out_name)
            ok, err = ffmpeg_video(src_abs, dst_abs, width, crf)
            if not ok:
                log(f"warning: video transcode failed for {src_rel} @ {width}w crf{crf}: {err[-400:]}")
        total_mb = dir_size_mb(media_dir)
        log(f"  media pass: width={width} crf={crf} -> total {total_mb:.1f} MB")
        chosen = (width, crf, total_mb)
        if total_mb <= max_total_mb:
            break
    if chosen and chosen[2] > max_total_mb:
        log(f"warning: could not fit media under {max_total_mb} MB budget "
            f"(best: {chosen[2]:.1f} MB at width={chosen[0]} crf={chosen[1]})")

    media_map = {}
    for src_rel, out_name in video_srcs.items():
        if os.path.exists(os.path.join(media_dir, out_name)):
            media_map[src_rel] = out_name
    for src_rel, out_name in poster_srcs.items():
        if os.path.exists(os.path.join(media_dir, out_name)):
            media_map[src_rel] = out_name

    return media_map, missing


CSS = """
:root{
  --paper:$paper; --ink:$ink; --primary:$primary; --bright:$primary_bright;
  --surface:$surface; --muted:$muted; --up:$up; --down:$down; --cta:$cta;
  --card:#FFFFFF; --border:#DDE3E1;
  color-scheme: light;
}
*{box-sizing:border-box;}
body{background:var(--paper);}
.sbr{
  font-family:'Poppins', system-ui, -apple-system, sans-serif;
  color:var(--ink); background:var(--paper); max-width:920px; margin:0 auto;
  padding:24px 20px 140px; line-height:1.45;
}
.sbr h1{
  font-family:'Poppins', system-ui, sans-serif; font-weight:800; font-size:26px;
  margin:0 0 4px; letter-spacing:-0.01em;
}
.sbr .subtitle{color:var(--muted); font-size:14px; margin-bottom:18px;}
.reviewer-bar{
  background:var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:14px 16px; display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center;
  margin-bottom:22px;
}
.reviewer-bar label{font-weight:600; font-size:13px;}
.reviewer-bar input[type=text]{
  font:inherit; font-size:14px; padding:8px 10px; border:1px solid var(--border);
  border-radius:8px; min-width:220px; background:#fff; color:var(--ink);
}
.section-header{
  font-family:'Barlow Semi Condensed', 'Poppins', sans-serif; font-weight:600;
  text-transform:uppercase; letter-spacing:0.14em; font-size:13px; color:#fff;
  background:var(--primary); border-radius:8px; padding:8px 14px; margin:26px 0 12px;
}
.section-header:first-child{margin-top:0;}
.card{
  border:1px solid var(--border); border-radius:16px; background:var(--card);
  padding:16px; margin-bottom:16px; position:relative;
}
.card-head{display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:8px;}
.row-num{
  font-weight:800; font-size:14px; color:#fff; background:var(--ink);
  border-radius:999px; min-width:28px; height:28px; display:inline-flex;
  align-items:center; justify-content:center; padding:0 8px;
}
.type-pill{
  font-family:'Barlow Semi Condensed', sans-serif; font-weight:600; font-size:11px;
  text-transform:uppercase; letter-spacing:0.08em; color:#fff; border-radius:999px;
  padding:4px 10px;
}
.status-pill{
  font-size:11px; font-weight:600; border-radius:999px; padding:4px 10px;
  border:1px solid var(--border); color:var(--ink); background:var(--surface);
}
.status-Approved{background:var(--up); color:#fff; border-color:var(--up);}
.status-Generated{background:var(--bright); color:var(--ink); border-color:var(--bright);}
.status-Draft{background:var(--surface);}
.vo{font-size:17px; font-weight:600; margin:0 0 10px; color:var(--ink); line-height:1.4;}
.toggle{
  font-size:12.5px; color:var(--primary); cursor:pointer; user-select:none;
  font-weight:600; display:inline-block; margin-bottom:6px;
}
.toggle:hover{color:var(--bright);}
.collapsible{display:none; font-size:13.5px; color:var(--ink); background:var(--surface);
  border-radius:10px; padding:10px 12px; margin-bottom:10px;}
.collapsible.open{display:block;}
.collapsible .field{margin-bottom:6px;}
.collapsible .field b{color:var(--primary);}
.card-body{display:flex; gap:18px; align-items:flex-start; margin-top:6px;}
.media-wrap{flex:0 0 400px; min-width:0;}
.vo-col{flex:1; min-width:0;}
.media-wrap video, .media-wrap img{
  width:100%; border-radius:12px; background:#000; display:block; aspect-ratio:16/9; object-fit:cover;
}
.media-wrap img.placeholder{background:var(--surface);}
@media (max-width:680px){ .card-body{flex-direction:column;} .media-wrap{flex:none; width:100%;} }
.media-note{font-size:11.5px; color:var(--muted); margin-top:4px;}
.no-media{
  font-size:13px; color:var(--muted); background:var(--surface); border-radius:10px;
  padding:10px 12px;
}
.needs-confirm{
  margin:10px 0; font-size:13px; background:#FFF7E0; border:1px solid #F0C36D;
  border-left:4px solid #D98E04; border-radius:8px; padding:9px 12px; color:#5C3B00;
}
.needs-confirm .nc-title{font-weight:700; font-size:12px; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;}
.needs-confirm ul{margin:0; padding-left:18px;}
.needs-confirm li{margin:2px 0;}
.needs-confirm .nc-owner{font-weight:700;}
.confirm-pill{
  font-size:11px; font-weight:700; border-radius:999px; padding:4px 10px;
  background:#FFF7E0; color:#8A5A00; border:1px solid #F0C36D;
}
.prior-feedback{margin:10px 0; font-size:13px;}
.prior-feedback .fb{
  background:var(--surface); border-left:3px solid var(--primary); border-radius:6px;
  padding:8px 10px; margin-bottom:6px;
}
.prior-feedback .fb .who{font-weight:700; margin-right:6px;}
.prior-feedback .fb .when{color:var(--muted); font-size:11.5px;}
.controls{border-top:1px dashed var(--border); margin-top:12px; padding-top:12px;}
.verdicts{display:flex; gap:14px; flex-wrap:wrap; margin-bottom:8px; font-size:13.5px;}
.verdicts label{display:flex; align-items:center; gap:5px; cursor:pointer; font-weight:500;}
textarea.note{
  width:100%; min-height:56px; font:inherit; font-size:13.5px; border:1px solid var(--border);
  border-radius:8px; padding:8px 10px; resize:vertical; color:var(--ink); background:#fff;
}
.footer{
  position:fixed; left:0; right:0; bottom:0; background:var(--ink); color:#fff;
  padding:12px 20px; display:flex; gap:18px; align-items:center; flex-wrap:wrap;
  font-size:13.5px; z-index:50; box-shadow:0 -2px 10px rgba(0,0,0,.15);
}
.footer .counts{display:flex; gap:16px; flex-wrap:wrap;}
.footer .count b{font-size:15px;}
.footer button{
  font:inherit; font-weight:700; font-size:13px; padding:9px 16px; border-radius:999px;
  border:none; cursor:pointer;
}
.btn-export{background:var(--bright); color:var(--ink);}
.btn-export:hover{opacity:.9;}
.export-panel, .import-panel{
  margin-top:20px; border:1px solid var(--border); border-radius:14px; padding:14px 16px;
  background:var(--surface);
}
.export-panel h3, .import-panel h3{margin:0 0 8px; font-size:14px;}
.export-panel textarea, .import-panel textarea{
  width:100%; min-height:110px; font-family:ui-monospace, monospace; font-size:11.5px;
  border:1px solid var(--border); border-radius:8px; padding:8px; background:#fff; color:var(--ink);
}
.export-panel .row, .import-panel .row{display:flex; gap:10px; align-items:center; margin-top:8px; flex-wrap:wrap;}
.copy-fallback{font-size:12px; color:var(--muted);}
.pill-btn{
  font:inherit; font-weight:700; font-size:12.5px; padding:8px 14px; border-radius:999px;
  border:1px solid var(--primary); background:#fff; color:var(--primary); cursor:pointer;
}
.pill-btn.primary{background:var(--primary); color:#fff;}
.msg{font-size:12px; color:var(--primary); font-weight:600;}
"""


def make_placeholder(n, vtype, hint):
    """A branded 960x540 stand-in for a row with no media yet: surface grey with the diagonal
    hatch used on the landing-page mockups, the visual type, and what is still owed."""
    from PIL import Image, ImageDraw, ImageFont
    out_name = f"placeholder_{n:03d}.jpg"
    if MEDIA_DIR is None:
        return None
    path = os.path.join(MEDIA_DIR, out_name)
    W, H = 960, 540
    im = Image.new("RGB", (W, H), "#EBECEC")
    d = ImageDraw.Draw(im)
    for x in range(-H, W + H, 34):                      # 45-degree hatch, one tone darker than the ground
        d.line([(x, 0), (x + H, H)], fill="#E1E4E3", width=12)
    d.rectangle([0, 0, W - 1, H - 1], outline="#D6DBD9", width=2)
    def font(size, bold=True):
        for cand in ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial Unicode.ttf"):
            try:
                return ImageFont.truetype(cand, size, index=1 if (bold and cand.endswith(".ttc")) else 0)
            except Exception:
                continue
        return ImageFont.load_default()
    label = (vtype or "MEDIA").upper()
    f1, f2, f3 = font(30), font(22, bold=False), font(18, bold=False)
    def centred(text, y, f, fill):
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill=fill)
    centred(" ".join(label), 212, f1, "#2B4547")        # tracked-out caps
    centred(hint, 268, f2, "#2F7666")
    centred(f"Row {n}", 310, f3, "#8FA9A2")
    im.save(path, "JPEG", quality=82, optimize=True)
    return out_name


def open_assumptions(row):
    """Assumptions nobody has confirmed yet (no resolved_at). Shown to stakeholders, not just --internal."""
    return [a for a in row.get("assumptions") or [] if not a.get("resolved_at")]


def render_row_card(row, media_map, project_dir):
    n = row["n"]
    vtype = row.get("visual_type", "")
    status = row.get("status", "Draft")
    color = VISUAL_TYPE_COLORS.get(vtype, "#5B7A99")
    script_txt = esc(row.get("script", ""))
    direction = esc(row.get("visual_direction", ""))
    raw_notes = row.get("notes", "") or ""
    if not INCLUDE_INTERNAL:
        # [generated] lines are implementation notes (file paths, render gotchas) — not review material
        raw_notes = "\n".join(l for l in raw_notes.splitlines() if not l.strip().startswith("[generated]")).strip()
    notes = esc(raw_notes)

    mode, asset = pick_display_asset(row.get("assets"))
    media_html = ""
    if mode == "none" or asset is None:
        hint = "To be recorded" if "SCREENCAST" in vtype.upper() else "Not yet built"
        ph = make_placeholder(n, vtype, hint)
        if ph:
            media_html = (f'<img class="placeholder" src="media/{ph}" alt="Row {n}: no media yet">'
                          f'<div class="media-note">{hint} — no media for this row yet</div>')
        else:
            media_html = '<div class="no-media">No media for this row yet.</div>'
    else:
        poster_rel = asset.get("poster")
        poster_out = media_map.get(poster_rel) if poster_rel else None
        if mode == "video":
            file_rel = asset["file"]
            video_out = media_map.get(file_rel)
            if not video_out:
                media_html = '<div class="no-media">Media file missing on disk — skipped.</div>'
            else:
                seg = asset.get("segment")
                poster_attr = f' poster="media/{esc(poster_out)}"' if poster_out else ""
                note_line = ""
                if seg:
                    clip_label = clip_label_from_basename(os.path.splitext(os.path.basename(file_rel))[0])
                    note_line = (f'<div class="media-note">Plays beat {seg[0]:.1f}–{seg[1]:.1f}s '
                                 f'of shared clip {esc(clip_label)}</div>')
                data_seg = ""
                if seg:
                    data_seg = f' data-in="{seg[0]}" data-out="{seg[1]}"'
                media_html = (
                    f'<video class="row-video" preload="metadata"{poster_attr}{data_seg} '
                    f'playsinline controls src="media/{esc(video_out)}"></video>{note_line}'
                )
        else:  # image
            if poster_out:
                overlay_note = ""
                if asset.get("kind") == "overlay" or os.path.splitext(asset.get("file", ""))[1].lower() == ".mov":
                    overlay_note = '<div class="media-note">Preview frame only (source is an alpha overlay clip)</div>'
                media_html = f'<img src="media/{esc(poster_out)}" alt="Row {n} preview">{overlay_note}'
            else:
                media_html = '<div class="no-media">Media file missing on disk — skipped.</div>'

    feedback = row.get("feedback") or []
    fb_html = ""
    if feedback:
        items = "".join(
            f'<div class="fb"><span class="who">{esc(f.get("who"))}</span>'
            f'<span class="when">{esc(f.get("when"))}</span><div>{esc(f.get("text"))}</div></div>'
            for f in feedback
        )
        fb_html = f'<div class="prior-feedback"><div class="toggle" data-toggle="fb-{n}">Prior notes ({len(feedback)}) ▾</div>' \
                  f'<div class="collapsible" id="fb-{n}">{items}</div></div>'

    asm = open_assumptions(row)
    asm_html = confirm_pill = ""
    if asm:
        items = "".join(
            f'<li><span class="nc-owner">{esc(a.get("owner") or "?")}:</span> {esc(a.get("text"))}</li>'
            for a in asm
        )
        asm_html = f'<div class="needs-confirm"><div class="nc-title">Needs confirmation</div><ul>{items}</ul></div>'
        confirm_pill = '<span class="confirm-pill">Needs confirmation</span>'

    return f"""
<div class="card" data-row="{n}">
  <div class="card-head">
    <span class="row-num">{n}</span>
    <span class="type-pill" style="background:{color}">{esc(vtype)}</span>
    <span class="status-pill status-{esc(status)}">{esc(status)}</span>
    {confirm_pill}
  </div>
  <div class="card-body">
    <div class="media-wrap">{media_html}</div>
    <div class="vo-col">
      <div class="vo">{script_txt}</div>
      <div class="toggle" data-toggle="dir-{n}">Visual direction &amp; notes ▾</div>
      <div class="collapsible" id="dir-{n}">
        <div class="field"><b>Direction:</b> {direction or '&mdash;'}</div>
        <div class="field"><b>Notes:</b> {notes or '&mdash;'}</div>
      </div>
    </div>
  </div>
  {asm_html}
  {fb_html}
  <div class="controls" data-controls="{n}">
    <div class="verdicts">
      <label><input type="radio" name="verdict-{n}" value="approve" checked> Approve</label>
      <label><input type="radio" name="verdict-{n}" value="changes"> Needs changes</label>
    </div>
    <textarea class="note" data-note="{n}" placeholder="Add a note for this row..."></textarea>
  </div>
</div>
"""


def build_html(doc, media_map, project_dir, title, rows_without_media):
    colors = load_brand_colors(project_dir, doc.get("brand"))
    css = Template(CSS).safe_substitute(colors)

    sections_html = []
    last_section = None
    for row in doc["rows"]:
        sec = row.get("section")
        if sec and sec != last_section:
            sections_html.append(f'<div class="section-header">{esc(sec)}</div>')
            last_section = sec
        sections_html.append(render_row_card(row, media_map, project_dir))

    project_name = esc(doc.get("project", title))
    state_key = "sb_review::" + (doc.get("project") or "storyboard")
    row_count = len(doc["rows"])
    n_confirm = sum(len(open_assumptions(r)) for r in doc["rows"])
    confirm_note = f' &middot; <b style="color:#8A5A00">{n_confirm} to confirm</b>' if n_confirm else ""

    body = f"""<meta charset="utf-8">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Barlow+Semi+Condensed:wght@500&display=swap" rel="stylesheet">
<style>{css}</style>
<div class="sbr">
  <h1>{esc(title)}</h1>
  <div class="subtitle">{project_name} &middot; {row_count} rows{confirm_note} &middot; stakeholder review</div>
  <div class="reviewer-bar">
    <label for="reviewerName">Reviewer name</label>
    <input type="text" id="reviewerName" placeholder="Your name">
    <span class="msg" id="reviewerMsg"></span>
  </div>
  {''.join(sections_html)}

  <div class="export-panel">
    <h3>Export my review</h3>
    <div class="row">
      <button class="pill-btn primary" id="exportBtn">Export my review</button>
      <span class="copy-fallback" id="exportStatus">Builds a JSON payload and copies it to your clipboard.</span>
    </div>
    <textarea id="exportOutput" readonly placeholder="Your exported review will appear here..."></textarea>
  </div>

  <div class="import-panel">
    <h3>Import a review</h3>
    <div class="row">
      <span class="copy-fallback">Paste a previously exported payload to restore your review on another machine.</span>
    </div>
    <textarea id="importInput" placeholder="Paste exported JSON here..."></textarea>
    <div class="row">
      <button class="pill-btn" id="importBtn">Import</button>
      <span class="msg" id="importStatus"></span>
    </div>
  </div>
</div>

<div class="footer">
  <div class="counts">
    <span class="count">Approved: <b id="cntApprove">0</b></span>
    <span class="count">Needs changes: <b id="cntChanges">0</b></span>
  </div>
</div>

<script>
(function(){{
  var STATE_KEY = {json.dumps(state_key)};
  var ROW_NUMS = {json.dumps([r["n"] for r in doc["rows"]])};

  function safeGet(){{
    try {{
      var raw = localStorage.getItem(STATE_KEY);
      if (raw) return JSON.parse(raw);
    }} catch(e) {{}}
    return null;
  }}
  function safeSet(state){{
    try {{ localStorage.setItem(STATE_KEY, JSON.stringify(state)); }} catch(e) {{}}
  }}

  var state = safeGet() || {{ reviewer: "", rows: {{}} }};
  if (!state.rows) state.rows = {{}};

  function getRow(n){{
    if (!state.rows[n]) state.rows[n] = {{ verdict: "approve", note: "" }};   // approved unless flagged
    return state.rows[n];
  }}

  function renderState(){{
    document.getElementById('reviewerName').value = state.reviewer || "";
    ROW_NUMS.forEach(function(n){{
      var r = getRow(n);
      var radios = document.getElementsByName('verdict-' + n);
      for (var i=0;i<radios.length;i++) {{
        radios[i].checked = (radios[i].value === (r.verdict || "approve"));
      }}
      var note = document.querySelector('[data-note="' + n + '"]');
      if (note) note.value = r.note || "";
    }});
    updateCounts();
  }}

  function updateCounts(){{
    var approve=0, changes=0;
    ROW_NUMS.forEach(function(n){{
      var r = state.rows[n];
      var v = r && r.verdict;
      if (v === 'approve') approve++;
      else if (v === 'changes') changes++;
      else approve++;   // no selection = approved
    }});
    document.getElementById('cntApprove').textContent = approve;
    document.getElementById('cntChanges').textContent = changes;
  }}

  document.getElementById('reviewerName').addEventListener('input', function(e){{
    state.reviewer = e.target.value;
    safeSet(state);
  }});

  ROW_NUMS.forEach(function(n){{
    var radios = document.getElementsByName('verdict-' + n);
    for (var i=0;i<radios.length;i++) {{
      radios[i].addEventListener('change', function(e){{
        var rn = e.target.name.split('-')[1];
        getRow(rn).verdict = e.target.value;
        safeSet(state);
        updateCounts();
      }});
    }}
    var note = document.querySelector('[data-note="' + n + '"]');
    if (note) {{
      note.addEventListener('input', function(e){{
        var rn = e.target.getAttribute('data-note');
        getRow(rn).note = e.target.value;
        safeSet(state);
      }});
    }}
  }});

  // collapsible toggles (direction/notes, prior feedback)
  document.querySelectorAll('.toggle').forEach(function(t){{
    t.addEventListener('click', function(){{
      var id = t.getAttribute('data-toggle');
      var el = document.getElementById(id);
      if (el) el.classList.toggle('open');
    }});
  }});

  // segment playback: play only [in,out], pause at out
  document.querySelectorAll('.row-video').forEach(function(v){{
    var inT = parseFloat(v.getAttribute('data-in'));
    var outT = parseFloat(v.getAttribute('data-out'));
    if (isNaN(inT) || isNaN(outT)) return;
    v.addEventListener('play', function(){{
      if (v.currentTime < inT - 0.05 || v.currentTime >= outT) {{
        v.currentTime = inT;
      }}
    }});
    v.addEventListener('timeupdate', function(){{
      if (v.currentTime >= outT) {{
        v.pause();
        v.currentTime = outT;
      }}
    }});
  }});

  // export
  document.getElementById('exportBtn').addEventListener('click', function(){{
    var payload = {{
      reviewer: state.reviewer || "",
      exported_at: new Date().toISOString(),
      rows: []
    }};
    ROW_NUMS.forEach(function(n){{
      var r = state.rows[n];
      if (!r) return;
      var hasVerdict = r.verdict === 'approve' || r.verdict === 'changes';
      var hasNote = r.note && r.note.trim().length > 0;
      if (hasVerdict || hasNote) {{
        payload.rows.push({{ n: n, verdict: r.verdict || "", note: r.note || "" }});
      }}
    }});
    var json_str = JSON.stringify(payload, null, 2);
    var out = document.getElementById('exportOutput');
    out.value = json_str;
    var statusEl = document.getElementById('exportStatus');
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(json_str).then(function(){{
        statusEl.textContent = 'Copied to clipboard — paste it to your producer.';
      }}, function(){{
        statusEl.textContent = 'Could not copy automatically — select all text below and copy.';
        out.focus(); out.select();
      }});
    }} else {{
      statusEl.textContent = 'Clipboard unavailable — select all text below and copy.';
      out.focus(); out.select();
    }}
  }});

  // import
  document.getElementById('importBtn').addEventListener('click', function(){{
    var statusEl = document.getElementById('importStatus');
    var raw = document.getElementById('importInput').value;
    try {{
      var payload = JSON.parse(raw);
      if (!payload || !Array.isArray(payload.rows)) throw new Error('missing rows[]');
      state.reviewer = payload.reviewer || state.reviewer || "";
      payload.rows.forEach(function(r){{
        if (r && r.n != null) {{
          state.rows[r.n] = {{ verdict: r.verdict || "approve", note: r.note || "" }};
        }}
      }});
      safeSet(state);
      renderState();
      statusEl.textContent = 'Imported ' + payload.rows.length + ' row(s).';
    }} catch(e) {{
      statusEl.textContent = 'Could not parse that payload: ' + e.message;
    }}
  }});

  renderState();
}})();
</script>
"""
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard_json")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--internal", action="store_true",
                    help="include [generated] implementation notes (default: stakeholder view hides them)")
    ap.add_argument("--max-total-mb", type=float, default=60.0)
    args = ap.parse_args()
    global INCLUDE_INTERNAL
    INCLUDE_INTERNAL = bool(args.internal)

    sb_path = os.path.abspath(args.storyboard_json)
    project_dir = os.path.dirname(sb_path)
    with open(sb_path) as f:
        doc = json.load(f)

    title = args.title or f"{doc.get('project', 'Storyboard')} Review"

    outdir = os.path.abspath(args.outdir)
    media_dir = os.path.join(outdir, "media")
    os.makedirs(outdir, exist_ok=True)

    log(f"Building review page for {len(doc['rows'])} rows -> {outdir}")
    global MEDIA_DIR
    MEDIA_DIR = media_dir
    media_map, missing = build_media(doc["rows"], project_dir, media_dir, args.max_total_mb)

    rows_without_media = []
    for row in doc["rows"]:
        mode, asset = pick_display_asset(row.get("assets"))
        if mode == "none":
            rows_without_media.append(row["n"])
        elif mode == "video" and not media_map.get(asset["file"]):
            rows_without_media.append(row["n"])
        elif mode == "image" and asset.get("poster") and not media_map.get(asset["poster"]):
            rows_without_media.append(row["n"])

    html_body = build_html(doc, media_map, project_dir, title, rows_without_media)

    index_path = os.path.join(outdir, "index.html")
    with open(index_path, "w") as f:
        f.write(html_body)

    total_mb = dir_size_mb(media_dir) if os.path.isdir(media_dir) else 0.0
    html_kb = os.path.getsize(index_path) / 1024

    print(f"outdir: {outdir}")
    print(f"index.html: {html_kb:.1f} KB")
    print(f"media total: {total_mb:.1f} MB (budget {args.max_total_mb} MB)")
    print(f"rows: {len(doc['rows'])}")
    print(f"rows without media: {rows_without_media if rows_without_media else 'none'}")
    if missing:
        print(f"missing source files ({len(missing)}):")
        for n, path in missing:
            print(f"  row {n}: {path}")


if __name__ == "__main__":
    main()
