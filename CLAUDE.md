# Storyboarding pipeline

Turns a video script into a collaborative, mostly-auto-generated storyboard. No server, no
database, nothing hosted: this repo + Claude Code on the Mac is the "app", the rendered .xlsx (opened in Google
Sheets) is the board, `storyboard.json` is the source of truth, HyperFrames renders custom graphics
locally, and Higgsfield generates B-roll. Clips are shared with the editor straight from `assets/`.

## Source of truth
Each project is a **self-contained folder** (created in place by `/storyboard-new`). Its
`storyboard.json` is authoritative — the xlsx and every asset derive from it. Edit the JSON, then
re-render the xlsx; never treat the xlsx as the master.

## Layout
- A **project folder** (anywhere) holds: `script.md`, `storyboard.json`, `assets/` (NNN_slug.mp4 + .png; also the rendered board `.xlsx`), and `brands/<brand>/` (its own brand: `refs/`, `brand.json` + `brand.md`, `logos/`).
- This **skills repo** holds the seven skills and `brands/_template/` (the brand template new projects copy).
- `.claude/skills/{storyboard-new,storyboard-brand,storyboard-build,storyboard-generate,storyboard-motion}/` — the workflow skills + scripts.
- `.claude/skills/storyboard-generate/templates/` — reusable HyperFrames compositions (e.g. portfolio-bar-drop).
- `.venv/` — Python deps (openpyxl for the xlsx, Pillow for palette extraction).

## Workflow
0. `mkdir <name> && cd <name>`, then `/storyboard-new [--brand <brand>]` — scaffolds the project in that folder (with its own brand from the template).
0b. `/storyboard-brand` — drop reference assets in `brands/<brand>/refs/`; extracts palette + writes brand.json/brand.md.
1. `/storyboard-build` — script.md → storyboard.json (rows, sections, types, briefs, talking-head reuse).
3. `/storyboard-generate 7,45` — row brief + brand → HyperFrames graphic (local) or Higgsfield B-roll, named by row.
   With NO selector it renders every free/local asset across the board and stops before paid Higgsfield rows (asks first).
3b. `/storyboard-motion` — HyperFrames stills → HTML motion design sheet (approval gate) → animated Higgsfield clips.
4. Open the rendered `.xlsx` in Google Sheets to review; share the `assets/` clips with your editor.

## Conventions
- Assets are named `NNN_slug.ext` (three-digit row number) so `assets/` reads in order and is easy to share.
- Visual-type vocabulary + colors live once in `.claude/skills/storyboard-build/scripts/lib_types.py`; import it.
- HyperFrames contract: register the timeline in `window.__timelines`, animate transforms not layout
  props, `npx hyperframes lint` until clean, then render high + extract a poster with ffmpeg.
- Activate the venv before running scripts: `. .venv/bin/activate`.
- Generated video is always silent (the editor sets sound): prefer silent models, keep audio
  terms out of prompts, and strip any track with `generate_row.py silence <file>`.
- `/storyboard-generate clip A-B` makes ONE Higgsfield clip covering a row range (each row gets an in/out segment);
  `/storyboard-generate series A-B` makes one still image per row (previz frames that can later seed clips).
- Every row carries a `motion_engine` (`hyperframes` | `higgsfield` | `none`), set at build time
  by `default_motion_engine()` in `lib_types.py`: information graphics → `hyperframes` (pixel-exact
  text/data), atmospheric footage-from-still → `higgsfield` (image-to-video), captured footage
  (talking head, screencast) → `none`. Never route text/number/chart rows through Higgsfield — i2v
  warps fine text. It shows as an **Engine** column in the xlsx and drives `/storyboard-motion`;
  a user override on a row is preserved on re-runs.
- `/storyboard-generate custom-graphic` is context-aware: consecutive graphic rows that read as beats of
  the same visual are auto-grouped into ONE continuous HyperFrames graphic (registered like a clip, with
  per-row in/out segments); unrelated graphic rows render separately. It states the grouping it chose.

