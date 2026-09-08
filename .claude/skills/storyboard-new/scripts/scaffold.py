#!/usr/bin/env python3
"""Scaffold a new storyboard project (and, if needed, its brand) in one step.

Creates projects/<name>/ with assets/, handoff/, a script.md starter, and a storyboard.json
skeleton wired to a brand. If the brand folder does not exist yet, it is created from
brands/_template so you can drop reference assets in and run /storyboard-brand. Safe: refuses to clobber an
existing project.

Usage:
  scaffold.py <project-name> [--brand <brand>] [--title "Human Title"]
"""
import os, sys, json, shutil, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "project"

def main():
    args = sys.argv[1:]
    if not args:
        print("usage: scaffold.py <project-name> [--brand <brand>] [--title \"Title\"]"); sys.exit(1)
    name = slugify(args[0])
    brand = None; title = None
    if "--brand" in args: brand = slugify(args[args.index("--brand")+1])
    if "--title" in args: title = args[args.index("--title")+1]
    title = title or args[0]
    brand = brand or name  # default: a brand named after the project

    proj = os.path.join(ROOT, "projects", name)
    if os.path.exists(proj):
        print(f"refusing to overwrite existing project: projects/{name}"); sys.exit(1)

    # project folders
    for sub in ("assets", "handoff"):
        os.makedirs(os.path.join(proj, sub), exist_ok=True)

    # brand: create from template if missing
    brand_dir = os.path.join(ROOT, "brands", brand)
    brand_created = False
    if not os.path.exists(brand_dir):
        tmpl = os.path.join(ROOT, "brands", "_template")
        shutil.copytree(tmpl, brand_dir)
        os.makedirs(os.path.join(brand_dir, "logos"), exist_ok=True)
        bj_path = os.path.join(brand_dir, "brand.json")
        bj = json.load(open(bj_path)); bj["brand_id"] = brand; bj["name"] = title
        json.dump(bj, open(bj_path, "w"), indent=2)
        brand_created = True

    # script.md starter
    open(os.path.join(proj, "script.md"), "w").write(
        f"# {title} — script\n\n"
        "<!-- Paste the finished script below. Use '## Hook', '## Close', etc. for sections; \n"
        "     Claude will infer them if omitted. One blank line between beats helps the split. -->\n\n"
        "## Hook\n\n\n")

    # storyboard.json skeleton
    doc = {"project": name, "brand": brand, "presenter": None,
           "sheet_id": None, "drive_folder_id": None, "sections_order": [], "rows": []}
    json.dump(doc, open(os.path.join(proj, "storyboard.json"), "w"), indent=2)

    print(f"created projects/{name}/  (assets/, handoff/, script.md, storyboard.json)")
    print(f"brand: brands/{brand}/" + ("  [new — from _template]" if brand_created else "  [existing]"))
    print("\nnext:")
    if brand_created:
        print(f"  1. drop brand assets into brands/{brand}/refs/  then run:  /storyboard-brand {brand}")
        print(f"  2. paste the script into projects/{name}/script.md")
        print(f"  3. /storyboard-build for projects/{name} using brand {brand}")
    else:
        print(f"  1. paste the script into projects/{name}/script.md")
        print(f"  2. /storyboard-build for projects/{name} using brand {brand}")

if __name__ == "__main__":
    main()
