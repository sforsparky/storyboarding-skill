#!/usr/bin/env python3
"""Convert extracted board rows -> canonical storyboard.json.

Input: the _extracted.json produced from a source board (or, in normal use, the
rows Claude parses from a raw script). Output: storyboard.json, the single source
of truth for a project. Each row carries an id, section, visual_type, script,
visual_direction, notes, reuse_of (row id whose still to duplicate), a generation
brief, status, assets[], feedback[].

This script exists so the example board can be reproduced deterministically for the
dry run. In normal use Claude writes storyboard.json directly from a script using
the same schema and the rules in SKILL.md; the brief-writing here is the fallback.
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from lib_types import infer_type, TALKING_HEAD_TYPES, GENERATED_BY_TYPE, default_motion_engine

def slug(text, n=4):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    skip = {"the","a","an","of","to","and","or","on","in","with","for","your","you"}
    words = [w for w in words if w not in skip] or ["shot"]
    return "-".join(words[:n])

def make_brief(vtype, script, direction, brand):
    """A generation-ready brief string. Concrete; names brand cues for non-TH rows."""
    if vtype in TALKING_HEAD_TYPES:
        return ""
    bg = brand.get("graphic_style", "")
    bb = brand.get("broll_style", "")
    colors = brand.get("colors", {})
    palette = f"{colors.get('primary_bright','')} on {colors.get('primary','')}".strip(" on")
    route = GENERATED_BY_TYPE.get(vtype, "video")
    if route == "hyperframes":
        return (f"CUSTOM GRAPHIC. {direction.strip()} "
                f"Brand look: {bg} Palette: {palette}. 16:9, 1920x1080, ~4s, hold on final frame.")
    if route == "video":
        return (f"B-ROLL. {direction.strip()} "
                f"Consistent project look: {bb} 16:9, ~5s, subtle motion, no on-screen text. "
                f"No audio (editor handles sound).")
    if route == "placeholder":
        return f"SCREENCAST placeholder. Capture: {direction.strip()}"
    return direction.strip()

def main():
    extracted, brand_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    rows_in = json.load(open(extracted))
    brand = json.load(open(brand_path))
    presenter = (brand.get("presenters") or [{}])[0]

    out_rows = []
    still_first_seen = {}   # image filename -> row id where it first appeared
    current_section = None
    for item in rows_in:
        if item["kind"] == "section":
            current_section = item["title"]
            continue
        if item["kind"] != "row":
            continue
        n = item["n"]
        rid = f"r{n:03d}"
        direction = item.get("direction", "")
        vtype = infer_type(direction)
        # lower-third promotion for offer/CTA talking heads
        if vtype == "TALKING HEAD" and re.search(r"apply now|lower third|cta", direction.lower()):
            vtype = "TALKING HEAD + LOWER THIRD"

        reuse_of = None
        img = item.get("img")
        if vtype in TALKING_HEAD_TYPES and img:
            if img in still_first_seen:
                reuse_of = still_first_seen[img]
            else:
                still_first_seen[img] = rid

        script = item.get("script", "")
        row = {
            "id": rid,
            "n": n,
            "section": current_section,
            "visual_type": vtype,
            "script": script,
            "visual_direction": "" if vtype in TALKING_HEAD_TYPES else direction,
            "notes": item.get("notes", ""),
            "reuse_of": reuse_of,
            "slug": slug(direction or script),
            "brief": make_brief(vtype, script, direction, brand),
            "motion_engine": default_motion_engine(vtype),
            "status": "Draft",
            "assets": [],
            "feedback": [],
            "source_still": img,
        }
        out_rows.append(row)

    doc = {
        "project": os.path.basename(os.path.dirname(out_path)),
        "brand": brand.get("brand_id"),
        "presenter": presenter.get("name"),
        "sheet_id": None,
        "drive_folder_id": None,
        "sections_order": [],
        "rows": out_rows,
    }
    seen = []
    for r in out_rows:
        if r["section"] and r["section"] not in seen:
            seen.append(r["section"])
    doc["sections_order"] = seen
    json.dump(doc, open(out_path, "w"), indent=2)

    from collections import Counter
    c = Counter(r["visual_type"] for r in out_rows)
    reused = sum(1 for r in out_rows if r["reuse_of"])
    print(f"Wrote {out_path}: {len(out_rows)} rows, {len(seen)} sections, {reused} reused stills")
    for k, v in c.most_common():
        print(f"  {v:3d}  {k}")

if __name__ == "__main__":
    main()
