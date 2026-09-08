#!/usr/bin/env python3
"""Render storyboard.json -> a formatted .xlsx (offline fallback for non-Sheets teams).

Extends the vendored vsl-storyboard styling with: section header rows, a Status
column, a row-number column tied to storyboard.json ids, and an embedded thumbnail
when a row already has a local poster in assets[]. The live Google Sheet (push-sheet)
is the primary surface; this is for handing someone a file with no Google access.
"""
import json, os, sys
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from lib_types import VISUAL_TYPES, TALKING_HEAD_TYPES, normalize_type, STATUSES

WRAP = Alignment(wrap_text=True, vertical="top", horizontal="left")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")
COLS = {"A":"Line #","B":"Visual","C":"Script","D":"Visual Direction","E":"Notes","F":"Status","G":"Thumbnail"}
WIDTHS = {"A":7,"B":26,"C":46,"D":40,"E":28,"F":13,"G":34}
ROW_H = 96

def cell(ws,r,c,v,font=None,fill=None,align=WRAP):
    x=ws[f"{c}{r}"]; x.value=v; x.alignment=align
    if font:x.font=font
    if fill:x.fill=fill
    return x

def main():
    sb_path, out_path = sys.argv[1], sys.argv[2]
    doc = json.load(open(sb_path))
    proj_dir = os.path.dirname(os.path.abspath(sb_path))
    wb = Workbook(); ws = wb.active; ws.title = doc.get("project","Storyboard")[:31]

    # header
    for c,label in COLS.items():
        cell(ws,1,c,label,font=Font(bold=True,color="FFFFFF"),
             fill=PatternFill("solid",fgColor="1F2937"),align=CENTER)
    ws.row_dimensions[1].height=22
    for c,w in WIDTHS.items(): ws.column_dimensions[c].width=w
    ws.freeze_panes="A2"; ws.sheet_view.showGridLines=False

    dv = DataValidation(type="list",formula1='"'+",".join(STATUSES)+'"',allow_blank=True)
    ws.add_data_validation(dv)

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
        cell(ws,r,"A",row["n"],align=CENTER,fill=zebra)
        label=vtype+(f"\n↩ reuse {row['reuse_of']}" if row.get("reuse_of") else "")
        cell(ws,r,"B",label,font=Font(bold=True,color="FFFFFF"),
             fill=PatternFill("solid",fgColor=color),align=CENTER)
        cell(ws,r,"C",row.get("script",""),fill=zebra)
        cell(ws,r,"D",row.get("visual_direction","") if vtype not in TALKING_HEAD_TYPES else "",
             font=Font(color=color),fill=zebra)
        cell(ws,r,"E","" if vtype in TALKING_HEAD_TYPES else row.get("notes",""),fill=zebra)
        cell(ws,r,"F",row.get("status","Draft"),align=CENTER,fill=zebra); dv.add(ws[f"F{r}"])
        # thumbnail: poster from assets or reused row's poster
        poster=None
        for a in row.get("assets",[]):
            if a.get("poster"): poster=os.path.join(proj_dir,a["poster"])
        if poster and os.path.exists(poster):
            try:
                img=XLImage(poster); img.width=int(ROW_H*16/9*1.0); img.height=ROW_H-8
                ws.add_image(img,f"G{r}")
            except Exception: pass
        ws.row_dimensions[r].height=ROW_H; r+=1; i+=1

    # legend sheet
    lg=wb.create_sheet("Legend")
    cell(lg,1,"A","Visual Type",font=Font(bold=True,color="FFFFFF"),fill=PatternFill("solid",fgColor="1F2937"),align=CENTER)
    cell(lg,1,"B","Color",font=Font(bold=True,color="FFFFFF"),fill=PatternFill("solid",fgColor="1F2937"),align=CENTER)
    for idx,(vt,cl) in enumerate(VISUAL_TYPES.items(),start=2):
        cell(lg,idx,"A",vt,font=Font(bold=True,color="FFFFFF"),fill=PatternFill("solid",fgColor=cl))
        cell(lg,idx,"B",f"#{cl}",align=CENTER)
    lg.column_dimensions["A"].width=28; lg.column_dimensions["B"].width=12
    lg.sheet_view.showGridLines=False
    wb.save(out_path); print("Saved",out_path)

if __name__=="__main__":
    main()
