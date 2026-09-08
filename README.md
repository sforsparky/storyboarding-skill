# Storyboarding pipeline

Turn a video script into a collaborative, mostly auto-generated storyboard — with **no server and
no database to manage**. This repo + Claude Code on your Mac is the "app"; Google Sheets is the
collaboration surface and the only shared state; Google Drive stores assets; HyperFrames renders
custom graphics locally (no Adobe); Higgsfield generates silent B-roll.

## Setup
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```
Node 22+ and FFmpeg are needed for graphic rendering (`npx hyperframes …`).
For Sheets sync, drop a Google Desktop-OAuth client at `.secrets/credentials.json` (one-time).

## Workflow (Claude Code skills in `.claude/skills/`)
0. `mkdir my-video && cd my-video` then `/storyboard-new` — scaffold the project in that folder.
1. `/storyboard-build` — `script.md` → `storyboard.json` (rows, sections, visual types, briefs, reuse).
2. `/storyboard-sheet` — push to a Google Sheet the team reviews in; `/storyboard-sheet (pull)` reads notes/status back.
3. `/storyboard-generate 7` · `/storyboard-generate span 43-46` · `/storyboard-generate series 50-56` — briefs → graphics/B-roll, named by row.
3b. `/storyboard-motion` — animate approved infographic stills into clips (builds an HTML motion sheet for approval first).
4. `/storyboard-handoff` — approved assets → `handoff/` named by row + `manifest.csv`, mirrored to Drive.

See [CLAUDE.md](CLAUDE.md) for the full layout and conventions.

## Layout
- A **project folder** (anywhere): `script.md`, `storyboard.json` (source of truth), `assets/`, `handoff/`, `brands/<brand>/` (its own brand).
- This **repo**: the six `.claude/skills/storyboard-*` skills + `brands/_template/`.
- `.claude/skills/{storyboard-build,storyboard-sheet,storyboard-generate,storyboard-handoff}/` — the four workflow skills + scripts.
