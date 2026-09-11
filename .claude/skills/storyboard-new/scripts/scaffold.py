#!/usr/bin/env python3
"""Scaffold a storyboard project *in place* — inside the current folder.

Run it from a folder you've already named for the project. It creates, in the CURRENT directory:
  script.md, storyboard.json, assets/, and brands/<brand>/ (from the template).
Each project is self-contained: its brand lives inside it. The project name defaults to the
folder name. Safe: refuses to clobber an existing storyboard.json, and refuses to run in $HOME
or the skills repo itself.

The brand template ships with the skills, so this works from any folder (the skill scripts live
in the storyboarding-app repo and are found via their real path even when run through a symlink).

Usage (from inside the project folder):
  scaffold.py [--brand <brand>] [--title "Human Title"] [--name <slug>]
"""
import os, sys, json, shutil, re

# repo that ships the skills (for the brand template) — resolved through any symlink
SKILLS_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                           "..", "..", "..", ".."))
TEMPLATE = os.path.join(SKILLS_REPO, "brands", "_template")

def slugify(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "project"

def main():
    args = sys.argv[1:]
    def opt(flag):
        return args[args.index(flag)+1] if flag in args else None
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    if os.path.realpath(cwd) in (os.path.realpath(home), os.path.realpath(SKILLS_REPO)):
        print(f"refusing to scaffold in {cwd!r}. cd into an empty project folder first."); sys.exit(1)
    if os.path.exists(os.path.join(cwd, "storyboard.json")):
        print("refusing to overwrite: storyboard.json already exists here."); sys.exit(1)

    name = slugify(opt("--name") or os.path.basename(cwd.rstrip("/")))
    title = opt("--title") or os.path.basename(cwd.rstrip("/"))
    brand = slugify(opt("--brand") or name)

    for sub in ("assets",):
        os.makedirs(os.path.join(cwd, sub), exist_ok=True)

    # brand lives inside the project (per-project brands)
    brand_dir = os.path.join(cwd, "brands", brand)
    brand_created = False
    if not os.path.exists(brand_dir):
        shutil.copytree(TEMPLATE, brand_dir)
        os.makedirs(os.path.join(brand_dir, "logos"), exist_ok=True)
        bj = os.path.join(brand_dir, "brand.json")
        d = json.load(open(bj)); d["brand_id"] = brand; d["name"] = title
        json.dump(d, open(bj, "w"), indent=2)
        brand_created = True

    open(os.path.join(cwd, "script.md"), "w").write(
        f"# {title} — script\n\n"
        "<!-- Paste the finished script below. Use '## Hook', '## Close', etc. for sections;\n"
        "     Claude infers them if omitted. One blank line between beats helps the split. -->\n\n"
        "## Hook\n\n\n")

    json.dump({"project": name, "brand": brand, "presenter": None,
               "sheet_id": None, "drive_folder_id": None,
               "sections_order": [], "rows": []},
              open(os.path.join(cwd, "storyboard.json"), "w"), indent=2)

    print(f"scaffolded project '{name}' in {cwd}")
    print("  created: script.md, storyboard.json, assets/, "
          f"brands/{brand}/" + (" [new from template]" if brand_created else " [existing]"))
    print("\nnext (run these from this folder):")
    if brand_created:
        print(f"  1. drop brand assets into brands/{brand}/refs/  then run:  /storyboard-brand {brand}")
        print("  2. paste the script into script.md")
        print("  3. /storyboard-build")
    else:
        print("  1. paste the script into script.md")
        print("  2. /storyboard-build")

if __name__ == "__main__":
    main()
