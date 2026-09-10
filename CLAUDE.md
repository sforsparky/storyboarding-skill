# Storyboarding pipeline

Turns a video script into a collaborative, mostly-auto-generated storyboard. No server, no
database, nothing hosted: this repo + Claude Code on the Mac is the "app", Google Sheets is the
collaboration surface and the only shared state, Google Drive stores assets, HyperFrames renders
custom graphics locally, and Higgsfield generates B-roll.

## Source of truth
Each project is a **self-contained folder** (created in place by `/storyboard-new`). Its
`storyboard.json` is authoritative. The Sheet, the xlsx, and every asset derive
from it. Edit the JSON (or the Sheet, then `/storyboard-sheet (pull)`), never treat the Sheet as the master.

## Layout
- A **project folder** (anywhere) holds: `script.md`, `storyboard.json`, `assets/` (NNN_slug.mp4 + .png), `handoff/`, and `brands/<brand>/` (its own brand: `refs/`, `brand.json` + `brand.md`, `logos/`).
- This **skills repo** holds the seven skills and `brands/_template/` (the brand template new projects copy).
- `.claude/skills/{storyboard-new,storyboard-brand,storyboard-build,storyboard-sheet,storyboard-generate,storyboard-handoff}/` — the workflow skills + scripts.
- `.claude/skills/storyboard-generate/templates/` — reusable HyperFrames compositions (e.g. portfolio-bar-drop).
- `.venv/` — Python deps (openpyxl, google-api-python-client). `.secrets/` — Google OAuth (gitignored).

## Workflow
0. `mkdir <name> && cd <name>`, then `/storyboard-new [--brand <brand>]` — scaffolds the project in that folder (with its own brand from the template).
0b. `/storyboard-brand` — drop reference assets in `brands/<brand>/refs/`; extracts palette + writes brand.json/brand.md.
1. `/storyboard-build` — script.md → storyboard.json (rows, sections, types, briefs, talking-head reuse).
2. `/storyboard-sheet` — storyboard.json → Google Sheet the team reviews in; `/storyboard-sheet (pull)` reads notes/status back.
3. `/storyboard-generate 7,45` — row brief + brand → HyperFrames graphic (local) or Higgsfield B-roll, named by row.
3b. `/storyboard-motion` — HyperFrames stills → HTML motion design sheet (approval gate) → animated Higgsfield clips.
4. `/storyboard-handoff` — approved assets → `handoff/` named by row + manifest.csv, mirrored to Drive.

## Conventions
- Assets are named `NNN_slug.ext` (three-digit row number) so the producer folder is a plain copy.
- Visual-type vocabulary + colors live once in `.claude/skills/storyboard-build/scripts/lib_types.py`; import it.
- HyperFrames contract: register the timeline in `window.__timelines`, animate transforms not layout
  props, `npx hyperframes lint` until clean, then render high + extract a poster with ffmpeg.
- Activate the venv before running scripts: `. .venv/bin/activate`.
- Generated video is always silent (the editor sets sound): prefer silent models, keep audio
  terms out of prompts, and strip any track with `generate_row.py silence <file>`.
- `/storyboard-generate clip A-B` makes ONE Higgsfield clip covering a row range (each row gets an in/out segment);
  `/storyboard-generate series A-B` makes one still image per row (previz frames that can later seed clips).
- `/storyboard-generate custom-graphic` is context-aware: consecutive graphic rows that read as beats of
  the same visual are auto-grouped into ONE continuous HyperFrames graphic (registered like a clip, with
  per-row in/out segments); unrelated graphic rows render separately. It states the grouping it chose.

