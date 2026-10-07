#!/usr/bin/env python3
"""Render storyboard.json -> a formatted .xlsx — the board you open directly in Google Sheets.

Layout mirrors the working storyboard: section header rows, a row-number column tied to
storyboard.json ids, an Engine column (the /storyboard-motion route), and the thumbnail embedded
IN the Visual cell once a row has a local poster (the type label shows until then). No Status
column. This .xlsx is the collaboration surface — open it in Google Sheets, comment, and share.

The Feedback column re-attaches every note to its row: a Google Sheets comment is anchored to a
cell in that one spreadsheet and comes loose (or vanishes) when the file is replaced, so each
round's notes are read back into storyboard.json with ingest_sheet_comments.py and RENDERED here.
A note shows ✔ once resolved (generate_row.py resolve) or when the row's art was made after it was
written, ● while it is still open. Resolving a comment in Google Sheets does NOT close a note —
the board is regenerated from storyboard.json, so close notes with `resolve`.

Reviewers' own comments are CARRIED across a rebuild. Before overwriting, the existing workbook's
comments are read and re-placed on the row with the same Line # (so they follow their row even when
rows are added or removed), with Google's thread data (xl/commentsmeta0) copied across, so Google
Sheets re-anchors the original threads instead of leaving them unmapped:

  sb_to_xlsx.py <storyboard.json> <out.xlsx> [--carry-comments-from <commented.xlsx>] [--no-carry]

The default source is <out.xlsx> itself. Pass --carry-comments-from to restore comments from an
archived copy (rebuild.py keeps one in <project>/feedback/) after a rebuild that lost them.
"""
import datetime as dt
import hashlib, json, os, re, shutil, sys, tempfile, zipfile
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from lib_types import VISUAL_TYPES, TALKING_HEAD_TYPES, normalize_type, default_motion_engine

WRAP = Alignment(wrap_text=True, vertical="top", horizontal="left")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")
COLS = {"A":"Line #","B":"Visual","C":"Script","D":"Visual Direction","E":"Notes","F":"Engine",
        "G":"Feedback"}
WIDTHS = {"A":7,"B":32,"C":46,"D":40,"E":28,"F":14,"G":44}
ROW_H = 97   # points; sized so the Visual cell is ~16:9 and a thumbnail fills it
IMG_W = int(WIDTHS["B"]*7) + 5      # Visual cell, px
IMG_H = int(ROW_H*4/3)
THUMB_W = IMG_W*2                    # embedded thumbnail: 2x the displayed width, so it stays sharp when zoomed
THUMB_QUALITY = 82

def cell(ws,r,c,v,font=None,fill=None,align=WRAP):
    x=ws[f"{c}{r}"]; x.value=v; x.alignment=align
    if font:x.font=font
    if fill:x.fill=fill
    return x


_warned_pil = False

def thumb_for(proj_dir, poster):
    """Downscaled JPEG of a poster, for embedding. The full 1920x1080 PNGs are ~1MB apiece, which
    made the board tens of MB; a ~2x-cell thumbnail is ~30-60KB. Cached under <project>/.board-cache/
    (NOT assets/ — that folder is handed to the video editor), keyed on poster path + mtime + size so
    a thumbnail only regenerates when its poster changes. Falls back to the original poster."""
    global _warned_pil
    try:
        from PIL import Image
    except ImportError:
        if not _warned_pil:
            print("warning: Pillow not installed - embedding full-size posters (big xlsx)", file=sys.stderr)
            _warned_pil = True
        return poster
    st = os.stat(poster)
    key = hashlib.sha1(f"{os.path.abspath(poster)}|{st.st_mtime_ns}|{st.st_size}|{THUMB_W}|{THUMB_QUALITY}".encode()).hexdigest()[:16]
    cache = os.path.join(proj_dir, ".board-cache", "thumbs")
    out = os.path.join(cache, key + ".jpg")
    if os.path.exists(out):
        return out
    try:
        os.makedirs(cache, exist_ok=True)
        with Image.open(poster) as im:
            if im.mode in ("RGBA", "LA", "P"):         # JPEG has no alpha: flatten onto white
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[3]); im = bg
            else:
                im = im.convert("RGB")
            im.thumbnail((THUMB_W, THUMB_W * 9), Image.LANCZOS)
            im.save(out, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return out
    except Exception as e:
        print(f"warning: thumbnail failed for {poster}: {e}", file=sys.stderr)
        return poster


def _asset_time(proj_dir, row):
    """Newest moment this row's art was produced: the registered_at stamp, else the file mtime."""
    newest = None
    for a in row.get("assets") or []:
        stamp = a.get("registered_at")
        cand = None
        if stamp:
            try:
                cand = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                cand = None
        if cand is None:
            f = a.get("file") or a.get("poster")
            path = os.path.join(proj_dir, f) if f else None
            if path and os.path.exists(path):
                cand = dt.datetime.fromtimestamp(os.path.getmtime(path))
        if cand and (newest is None or cand > newest):
            newest = cand
    return newest


def _fb_time(entry):
    """When the note was written. `when_at` carries the comment's own timestamp; `when` is
    date-only, so fall back to the start of that day."""
    for key, parse in (("when_at", lambda v: dt.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)),
                       ("when", lambda v: dt.datetime.fromisoformat(v))):
        v = entry.get(key)
        if v:
            try:
                return parse(v)
            except ValueError:
                continue
    return None


def feedback_block(proj_dir, row):
    """The row's notes as one block of text, newest last, each marked done or open against the
    art that is currently on the row. Rendering them INTO the workbook is what keeps a comment
    attached to its row: a sheet's own comments are anchored to cells and are lost the moment
    someone replaces the spreadsheet, while these travel with the board."""
    entries = row.get("feedback") or []
    if not entries:
        return "", 0
    made = _asset_time(proj_dir, row)
    lines, open_count = [], 0
    for e in sorted(entries, key=lambda x: (x.get("when") or "", x.get("when_at") or "")):
        at = _fb_time(e)
        if e.get("resolved_at"):              # closed with `generate_row.py resolve`
            mark, done = "✔", True
        elif made is None or at is None:
            mark, done = "•", False
        else:
            done = made > at
            mark = "✔" if done else "●"
        if not done:
            open_count += 1
        who = e.get("who") or "note"
        when = (e.get("when_at") or e.get("when") or "")[:16].replace("T", " ")
        text = " ".join((e.get("text") or "").split())
        lines.append(f"{mark} {who} {when}\n   {text}")
    return "\n\n".join(lines), open_count


def assumption_lines(row):
    """Unresolved assumptions — open questions about data/wording a named person must confirm —
    as one line each. Resolved ones (resolved_at set) are left off to keep the board quiet."""
    return [f"⚠ Confirm ({a.get('owner') or '?'}): {' '.join((a.get('text') or '').split())}"
            for a in row.get("assumptions") or [] if not a.get("resolved_at")]


OUR_AUTHOR = "storyboard"          # notes older versions of this script wrote; never carried
META_REL = "http://customschemas.google.com/relationships/workbookmetadata"


def read_reviewer_comments(xlsx):
    """[(line_no|None, column, old_ref, text, author)] and Google's thread metadata (bytes|None)
    from a board workbook. Only reviewers' comments; the Line # comes from column A of the
    comment's row, which is how it finds its row in the new board."""
    if not xlsx or not os.path.exists(xlsx):
        return [], None
    try:
        wb = load_workbook(xlsx)
    except Exception as e:
        print(f"warning: could not read comments from {xlsx}: {e}", file=sys.stderr)
        return [], None
    ws = wb.worksheets[0]
    found = []
    for row in ws.iter_rows():
        for c in row:
            if c.comment and (c.comment.author or "") != OUR_AUTHOR and c.comment.text.strip():
                line = ws.cell(c.row, 1).value
                line = int(line) if isinstance(line, (int, float)) or (isinstance(line, str) and line.isdigit()) else None
                found.append((line, c.column_letter, c.coordinate, c.comment.text, c.comment.author or ""))
    meta = None
    with zipfile.ZipFile(xlsx) as z:
        for n in z.namelist():
            if re.fullmatch(r"xl/(?:comments/)?commentsmeta\d*", n):
                meta = z.read(n)
    return found, meta


def attach_google_meta(path, meta):
    """Put Google's thread data back next to the comments part openpyxl wrote, so Sheets can match
    the IDs in each comment ("ID#AAAC…") to its original thread instead of orphaning it."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=os.path.dirname(os.path.abspath(path))).name
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        names = zin.namelist()
        cparts = [n for n in names if re.fullmatch(r"xl/comments/comment\d+\.xml", n)]
        for n in names:
            data = zin.read(n)
            if n == "[Content_Types].xml":
                data = data.replace(b"</Types>", b'<Override PartName="/xl/commentsmeta0" '
                                    b'ContentType="application/binary"/></Types>')
            zout.writestr(n, data)
        zout.writestr("xl/commentsmeta0", meta)
        for cp in cparts:
            d, b = os.path.split(cp)
            zout.writestr(f"{d}/_rels/{b}.rels",
                          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                          f'<Relationship Id="rId1" Type="{META_REL}" Target="../commentsmeta0"/></Relationships>')
    shutil.move(tmp, path)


def main():
    argv = sys.argv[1:]
    carry_from, no_carry = None, "--no-carry" in argv
    if "--carry-comments-from" in argv:
        i = argv.index("--carry-comments-from"); carry_from = argv[i + 1]; del argv[i:i + 2]
    argv = [x for x in argv if x != "--no-carry"]
    sb_path, out_path = argv[0], argv[1]
    carried, meta = ([], None) if no_carry else read_reviewer_comments(carry_from or out_path)
    line_to_row = {}
    doc = json.load(open(sb_path))
    proj_dir = os.path.dirname(os.path.abspath(sb_path))
    wb = Workbook(); ws = wb.active; ws.title = doc.get("project","Storyboard")[:31]

    for c,label in COLS.items():
        cell(ws,1,c,label,font=Font(bold=True,color="FFFFFF"),
             fill=PatternFill("solid",fgColor="1F2937"),align=CENTER)
    ws.row_dimensions[1].height=22
    for c,w in WIDTHS.items(): ws.column_dimensions[c].width=w
    ws.freeze_panes="A2"; ws.sheet_view.showGridLines=False

    r=2; last_section=None; i=0
    for row in doc["rows"]:
        sec=row.get("section")
        if sec and sec!=last_section:
            ws.merge_cells(f"A{r}:G{r}")
            cell(ws,r,"A",f"▶  {sec}",font=Font(bold=True,color="FFFFFF",size=12),
                 fill=PatternFill("solid",fgColor="0F172A"),align=Alignment(vertical="center",horizontal="left"))
            ws.row_dimensions[r].height=26; last_section=sec; r+=1
        vtype=normalize_type(row["visual_type"]); color=VISUAL_TYPES[vtype]
        zebra=PatternFill("solid",fgColor="F2F2F2") if i%2 else None
        cell(ws,r,"A",row["n"],align=CENTER,fill=zebra); line_to_row[row["n"]] = r
        eng = row.get("motion_engine") or default_motion_engine(vtype)
        # Find a poster: the row's OWN asset wins, and the reused row is only a fallback for a
        # row that has none. Reaching for the reused row first was silently overriding rows that
        # had been given a different still on purpose — e.g. plain talking-head rows pointing at
        # a row whose poster carries a lower third, which then showed a lower third on every one
        # of them. reuse_of says where the SHOT comes from, not which frame to show.
        def _poster_of(rw):
            p=None
            for a in rw.get("assets",[]):
                if a.get("poster"): p=os.path.join(proj_dir,a["poster"])
            return p
        poster=_poster_of(row)
        if not (poster and os.path.exists(poster)) and row.get("reuse_of"):
            src=next((x for x in doc["rows"] if x["id"]==row["reuse_of"]), None)
            if src: poster=_poster_of(src)
        # Visual cell: the thumbnail replaces the type label once a poster exists (type color stays as fill)
        label = "" if poster and os.path.exists(poster) else vtype + (f"\n↩ reuse {row['reuse_of']}" if row.get("reuse_of") else "")
        cell(ws,r,"B",label,font=Font(bold=True,color="FFFFFF"),
             fill=PatternFill("solid",fgColor=color),align=CENTER)
        if poster and os.path.exists(poster):
            try:
                img=XLImage(thumb_for(proj_dir, poster))
                img.width  = IMG_W                      # column B width in px (thumbnail is 2x; display size is set here)
                img.height = IMG_H                      # row height (pt) in px
                ws.add_image(img,f"B{r}")               # fills the Visual cell edge-to-edge
            except Exception: pass
        cell(ws,r,"C",row.get("script",""),fill=zebra)
        cell(ws,r,"D",row.get("visual_direction","") if vtype not in TALKING_HEAD_TYPES else "",
             font=Font(color=color),fill=zebra)
        cell(ws,r,"E","" if vtype in TALKING_HEAD_TYPES else row.get("notes",""),fill=zebra)
        cell(ws,r,"F","" if eng=="none" else eng,align=CENTER,fill=zebra)
        # Feedback travels with the board, not with the sheet's own comment anchors
        fb_text, fb_open = feedback_block(proj_dir, row)
        asm = assumption_lines(row)
        if asm:
            # assumptions go first, bold amber, ahead of the feedback they sit above
            from openpyxl.cell.rich_text import CellRichText, TextBlock
            from openpyxl.cell.text import InlineFont
            parts = [TextBlock(InlineFont(b=True, color="B45309"), "\n".join(asm))]
            if fb_text:
                parts.append(TextBlock(InlineFont(b=bool(fb_open), color="9A3412" if fb_open else "000000"), "\n\n" + fb_text))
            fb_cell = cell(ws,r,"G",CellRichText(*parts),fill=zebra)
        else:
            fb_cell = cell(ws,r,"G",fb_text,fill=zebra)
            if fb_open:
                fb_cell.font = Font(color="9A3412", bold=True)
        # No cell notes. They used to mirror this column onto column A, but Google Sheets shows a
        # cell note as a COMMENT: reviewers resolved them, and the next rebuild — which knows
        # nothing about a resolve in Sheets — wrote all of them back. They also tripped the
        # rebuild's "reviewer comments present" guard, archiving a copy of the board on every
        # rebuild. The only comments in the workbook should be the reviewers' own.
        ws.row_dimensions[r].height=ROW_H; r+=1; i+=1

    lg=wb.create_sheet("Legend")
    cell(lg,1,"A","Visual Type",font=Font(bold=True,color="FFFFFF"),fill=PatternFill("solid",fgColor="1F2937"),align=CENTER)
    cell(lg,1,"B","Color",font=Font(bold=True,color="FFFFFF"),fill=PatternFill("solid",fgColor="1F2937"),align=CENTER)
    for idx,(vt,cl) in enumerate(VISUAL_TYPES.items(),start=2):
        cell(lg,idx,"A",vt,font=Font(bold=True,color="FFFFFF"),fill=PatternFill("solid",fgColor=cl))
        cell(lg,idx,"B",f"#{cl}",align=CENTER)
    lg.column_dimensions["A"].width=28; lg.column_dimensions["B"].width=12
    lg.sheet_view.showGridLines=False
    placed, lost = 0, []
    for line, col, old_ref, text, author in carried:
        if line in line_to_row:
            ws[f"{col}{line_to_row[line]}"].comment = Comment(text, author, width=320, height=180)
            placed += 1
        else:
            lost.append((old_ref, text.splitlines()[-1][:60] if text else ""))
    wb.save(out_path)
    if placed and meta:
        attach_google_meta(out_path, meta)
    print("Saved", out_path)
    if carried:
        print(f"  carried {placed} reviewer comment(s) onto their rows"
              + (" with Google thread data" if meta and placed else ""))
    for ref, gist in lost:
        print(f"  ! comment at {ref} has no matching Line # on the board now — not placed: {gist}")

if __name__=="__main__":
    main()
