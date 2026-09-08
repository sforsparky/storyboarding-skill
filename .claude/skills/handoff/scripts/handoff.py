#!/usr/bin/env python3
"""Copy approved (or --all generated) row assets into handoff/ named by row number,
write manifest.csv, and report gaps. Drive mirroring is delegated to sheets_sync when
a drive_folder_id is present (kept optional so handoff runs offline)."""
import json, os, sys, csv, shutil

def main():
    sb_path = sys.argv[1]
    include_generated = "--all" in sys.argv[2:]
    doc = json.load(open(sb_path))
    proj = os.path.dirname(os.path.abspath(sb_path))
    out = os.path.join(proj, "handoff"); os.makedirs(out, exist_ok=True)
    want = {"Approved"} | ({"Generated"} if include_generated else set())

    shipped, missing, rows, copied = [], [], [], set()
    for r in doc["rows"]:
        if r.get("status") not in want:
            continue
        assets = r.get("assets") or []
        if not assets:
            missing.append(r["n"]); continue
        a = assets[0]
        src = os.path.join(proj, a["file"])
        ext = os.path.splitext(a["file"])[1].lstrip(".")
        if a.get("span_group"):
            dest_name = os.path.basename(a["file"])   # one shared file for the whole span
        else:
            dest_name = f"{r['n']:03d}_{r.get('slug','shot')}.{ext}"
        if os.path.exists(src):
            if a["file"] not in copied:
                shutil.copy2(src, os.path.join(out, dest_name)); shipped.append(dest_name); copied.add(a["file"])
        else:
            missing.append(r["n"]); continue
        seg = a.get("segment") or ["", ""]
        rows.append({"row": r["n"], "section": r.get("section",""),
                     "visual_type": r["visual_type"], "script": (r.get("script","") or "")[:120],
                     "file": dest_name, "in": seg[0], "out": seg[1],
                     "duration": a.get("duration",""), "status": r["status"]})

    with open(os.path.join(out, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["row","section","visual_type","script","file","in","out","duration","status"])
        w.writeheader(); w.writerows(rows)

    print(f"handoff → {out}")
    print(f"  shipped {len(shipped)} file(s); manifest.csv written")
    if missing:
        print(f"  approved rows still missing an asset: {sorted(set(missing))}")

if __name__ == "__main__":
    main()
