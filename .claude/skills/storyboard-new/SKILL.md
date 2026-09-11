---
name: storyboard-new
description: >
  Scaffold a self-contained storyboard project IN THE CURRENT FOLDER — a script.md starter, an empty
  storyboard.json wired to a brand, assets/, and a brands/<brand>/ copied from the template.
  Run it inside a folder named for the project. Use when starting a new video before /storyboard-build.
---

# /storyboard-new — scaffold a project

Run it **from inside the project folder** (a folder you've named for the project):
`scripts/scaffold.py [--brand <brand>] [--title "Human Title"] [--name <slug>]`

It creates:
- `assets/` in the current folder
- `script.md` — a starter with a `## Hook` heading and a note on how beats/sections parse
- `storyboard.json` — an empty skeleton with `project` + `brand` set
- `brands/<brand>/` — the project's own brand, copied from the skills' `_template`
- `brands/<brand>/` from `brands/_template` **if the brand doesn't exist yet** (with `refs/` and `logos/`)

Defaults: the project name is the current folder's name; the brand is created inside the project
(named after it) from the skills' `_template`. Pass `--brand acme` to name the brand, `--title` for a
display title. To reuse a brand across projects, copy an existing `brands/<brand>/` folder in. Names
are slugified. It refuses to overwrite an existing `storyboard.json`, or to run in `$HOME` or the skills repo.

## After scaffolding
- New brand → drop assets into `brands/<brand>/refs/` and run `/storyboard-brand <brand>` to build the design system.
- Existing brand → skip straight ahead.
- Paste the script into `script.md`, then run `/storyboard-build` from this folder.

This is step 0 of the pipeline; `/storyboard-brand` → `/storyboard-build` → `/storyboard-generate` → `/storyboard-motion` follow. Open the rendered `.xlsx` in Google Sheets to review; share `assets/` clips with the editor.
