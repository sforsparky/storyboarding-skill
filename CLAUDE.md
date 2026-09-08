# Storyboarding pipeline

Turns a video script into a collaborative, mostly-auto-generated storyboard. No server, no
database, nothing hosted: this repo + Claude Code on the Mac is the "app", Google Sheets is the
collaboration surface and the only shared state, Google Drive stores assets, HyperFrames renders
custom graphics locally, and Higgsfield generates B-roll.

## Source of truth
`projects/<name>/storyboard.json` is authoritative. The Sheet, the xlsx, and every asset derive
from it. Edit the JSON (or the Sheet, then `/pull-feedback`), never treat the Sheet as the master.

## Layout
- `brands/<brand>/` — `refs/` (drop assets here), `brand.json` + `brand.md` (built by /brand), `logos/`. `_template/` to start one.
- `projects/<name>/` — `script.md`, `storyboard.json`, `assets/` (NNN_slug.mp4 + .png), `handoff/`.
- `.claude/skills/{brand,storyboard,push-sheet,generate,handoff}/` — the workflow skills + scripts.
- `.claude/skills/generate/templates/` — reusable HyperFrames compositions (e.g. portfolio-bar-drop).
- `.venv/` — Python deps (openpyxl, google-api-python-client). `.secrets/` — Google OAuth (gitignored).

## Workflow
0. `/brand` — drop reference assets in `brands/<brand>/refs/`; extracts palette + writes brand.json/brand.md.
1. `/storyboard` — script.md → storyboard.json (rows, sections, types, briefs, talking-head reuse).
2. `/push-sheet` — storyboard.json → Google Sheet the team reviews in; `/pull-feedback` reads notes/status back.
3. `/generate 7,45` — row brief + brand → HyperFrames graphic (local) or Higgsfield B-roll, named by row.
4. `/handoff` — approved assets → `handoff/` named by row + manifest.csv, mirrored to Drive.

## Conventions
- Assets are named `NNN_slug.ext` (three-digit row number) so the producer folder is a plain copy.
- Visual-type vocabulary + colors live once in `.claude/skills/storyboard/scripts/lib_types.py`; import it.
- HyperFrames contract: register the timeline in `window.__timelines`, animate transforms not layout
  props, `npx hyperframes lint` until clean, then render high + extract a poster with ffmpeg.
- Activate the venv before running scripts: `. .venv/bin/activate`.
- Generated video is always silent (the editor sets sound): prefer silent models, keep audio
  terms out of prompts, and strip any track with `generate_row.py silence <file>`.
- `/generate clip A-B` makes ONE Higgsfield clip covering a row range (each row gets an in/out segment);
  `/generate series A-B` makes one still image per row (previz frames that can later seed clips).

## Example / test case
`projects/ic-vsl-2026/` is the Inner Circle VSL, extracted from `_example/` and used to validate the
pipeline (102 rows, 8 sections). It is a test fixture, not a template — real projects get their own folder.
