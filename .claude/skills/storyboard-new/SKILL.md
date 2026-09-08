---
name: storyboard-new
description: >
  Scaffold a whole new storyboard project in one step — projects/<name>/ with assets/, handoff/, a
  script.md starter, and a storyboard.json skeleton wired to a brand (creating the brand folder from
  the template if it doesn't exist yet). Use when starting a new video before /storyboard-build.
---

# /storyboard-new — scaffold a project

Run: `scripts/scaffold.py <project-name> [--brand <brand>] [--title "Human Title"]`

It creates:
- `projects/<name>/assets/` and `handoff/`
- `projects/<name>/script.md` — a starter with a `## Hook` heading and a note on how beats/sections parse
- `projects/<name>/storyboard.json` — an empty skeleton with `project` + `brand` set
- `brands/<brand>/` from `brands/_template` **if the brand doesn't exist yet** (with `refs/` and `logos/`)

Defaults: the brand name defaults to the project name; pass `--brand` to point at an existing brand
(e.g. reuse `inner-circle`). Names are slugified. It refuses to overwrite an existing project.

## After scaffolding
- New brand → drop assets into `brands/<brand>/refs/` and run `/storyboard-brand <brand>` to build the design system.
- Existing brand → skip straight ahead.
- Paste the script into `projects/<name>/script.md`, then run `/storyboard-build` for that project.

This is step 0 of the pipeline; `/storyboard-build` → `/storyboard-sheet` → `/storyboard-generate` → `/storyboard-handoff` follow.
