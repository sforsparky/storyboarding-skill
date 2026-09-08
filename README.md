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
1. `/storyboard` — `script.md` → `storyboard.json` (rows, sections, visual types, briefs, reuse).
2. `/push-sheet` — push to a Google Sheet the team reviews in; `/pull-feedback` reads notes/status back.
3. `/generate 7` · `/generate span 43-46` · `/generate series 50-56` — briefs → graphics/B-roll, named by row.
4. `/handoff` — approved assets → `handoff/` named by row + `manifest.csv`, mirrored to Drive.

See [CLAUDE.md](CLAUDE.md) for the full layout and conventions.

## Layout
- `brands/<brand>/` — brand kit (`brand.json` + `logos/`); `_template/` to start a new one.
- `projects/<name>/` — `script.md`, `storyboard.json` (source of truth), `assets/`, `handoff/`.
- `.claude/skills/{storyboard,push-sheet,generate,handoff}/` — the four workflow skills + scripts.
