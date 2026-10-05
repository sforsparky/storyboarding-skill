---
name: storyboard-generate
description: >
  Generates the asset(s) for storyboard rows from their brief + brand kit. Custom graphics render
  locally via HyperFrames (replacing hand Adobe work); B-roll via Higgsfield (silent, no audio);
  talking-head/cutaway reuse a still; screencast gets a capture placeholder. Handles single rows,
  lists, a whole visual type, a continuous Higgsfield clip spanning a row range, and a style-linked
  series of stills. Consecutive custom-graphic rows are auto-grouped into one continuous graphic
  when context says they're beats of the same visual. Use for /storyboard-generate or when asked to
  render, generate or regenerate storyboard rows.
---

# /storyboard-generate — rows → asset(s)

**Contents:** Requirements · Selection syntax · Routing · Whole-board default (checklist) ·
Render → check loop · Rendering: plan.json · Video is silent · CUSTOM GRAPHIC · B-ROLL ·
Talking head / screencast · After generating · Reference files

## Requirements
Activate the repo venv (`. .venv/bin/activate`; built from `requirements.txt`: openpyxl, Pillow,
numpy, scipy). Also needed: `ffmpeg`/`ffprobe` on PATH, Node with `npx hyperframes` (pinned in
`scripts/rebuild.py`) and `puppeteer-core` for the probe scripts, and the Higgsfield MCP connector
for B-roll/series rows. If one is missing, say which and how to install it rather than working around it.

## Selection syntax
Selection syntax:
- `/storyboard-generate` — NO selector: whole-board default. Generate every free/local asset across
  the board (HyperFrames graphics, still reuses, placeholders) and STOP before any paid Higgsfield
  B-roll. See "Whole-board default" below.
- `/storyboard-generate 7` — one row.
- `/storyboard-generate 7 "make the bars taller, lean into the lime accent"` — regenerate row 7
  with added guidance (see `references/feedback-and-assumptions.md`).
  Quotes are optional — everything after the row is read as guidance; quote only to disambiguate
  guidance that starts with a selector keyword (`clip`, `series`, `custom-graphic`, `b-roll`).
- `/storyboard-generate 5,7,45` — several independent rows.
- `/storyboard-generate 43-46` — a range, each row generated independently.
- `/storyboard-generate clip 43-46` — ONE Higgsfield video clip covering the range (see `references/shared-clips-and-series.md`).
- `/storyboard-generate series 50-56` — a still IMAGE per row across the range, storyboard/previz frames that
  share a look and can later seed clips (see `references/shared-clips-and-series.md`).
- `/storyboard-generate b-roll` — every Higgsfield B-roll/testimonial row (the paid rows), after cost preflight.
- `/storyboard-generate custom-graphic` — every row of that visual type; consecutive graphic rows
  that read as one continuous graphic are auto-grouped (see the CUSTOM GRAPHIC route).

## Routing — by `visual_type`
Source of truth: `GENERATED_BY_TYPE` in `../storyboard-build/scripts/lib_types.py`.

| visual_type | route | where |
|---|---|---|
| CUSTOM GRAPHIC, GRAPHIC / SCREENCAST | HyperFrames (local, free) | CUSTOM GRAPHIC below |
| TALKING HEAD + OVERLAY | HyperFrames alpha overlay | `references/talking-head-overlay.md` |
| B-ROLL, B-ROLL / GRAPHIC, TESTIMONIAL | Higgsfield video (paid) | B-ROLL below |
| TALKING HEAD, TALKING HEAD + LOWER THIRD | still reuse | Talking head below |
| SCREENCAST | placeholder | Screencast below |
| `clip A-B` / `series A-B` selectors | one shared clip / one still per row | `references/shared-clips-and-series.md` |

## Whole-board default (no selector)
`/storyboard-generate` with no argument does NOT blindly render everything — it protects credits.
Copy this checklist into your reply and tick it off:

```
- [ ] 0. Style gate: board has `style_signoff`? If not, render only `plan --samples`, settle the calls, `signoff`
- [ ] 1. `generate_row.py plan storyboard.json` — read Open feedback + Open assumptions first
- [ ] 2. Group consecutive graphic rows; write plan.json entries
- [ ] 3. Render the free/local rows (`render_plan.py`)
- [ ] 4. Render → check loop clean on every poster frame
- [ ] 5. STOP: list paid Higgsfield rows + estimated credits; wait for an explicit yes
```
If step 4 finds a problem that comes from a project-wide choice (ground, overlay style, number
format), go back to step 0 rather than fixing it row by row.

`/storyboard-generate` with no argument does NOT blindly render everything — it protects credits:
0. **Style gate first.** Until the board carries a `style_signoff`, the plan leads with the style
   samples: one pending row per visual type the free route renders, and one per overlay placement
   (`generate_row.py plan storyboard.json --samples` lists only these). Render ONLY those, show them,
   and settle every project-wide call before the full pass — ground (light/dark), overlay style
   (cards or type over footage), quote marks, number formats, and every figure a graphic asserts
   (record unconfirmed ones with `assume` — see `references/feedback-and-assumptions.md`). Then `generate_row.py signoff storyboard.json
   "<who>" "<what was agreed>"`. A look corrected after 40 rows costs 40 re-renders; corrected
   after 5 it costs 5.
1. Print the plan: `generate_row.py plan storyboard.json`. It buckets pending rows into free/local
   (route `hyperframes` / `still` / `placeholder`, honoring any per-row `motion_engine: hyperframes`
   override) versus paid Higgsfield (route `video`), and skips rows already `Generated`/`Approved`.
   - The plan ends with an "Open feedback" section: rows whose feedback is newer than what was
     last generated for them (see `references/feedback-and-assumptions.md`) — check these before generating.
   - Then "Open assumptions": facts the board asserts that a named person must still confirm.
2. Generate the free/local rows now — this is the "render all the infographics" pass, and it spends
   nothing. Apply the custom-graphic grouping rules (consecutive graphic beats → one graphic).
   Put each composition's rows in `<graphics_dir>/plan.json` and render them all with
   `render_plan.py` (see "Rendering: plan.json" below).
3. STOP before the paid rows. Show the user the Higgsfield B-roll list and the estimated credits,
   and ask before generating them (or tell them to run `/storyboard-generate b-roll`). Only proceed
   on an explicit yes, and preflight exact cost with `get_cost:true` at that point.

## Render → check loop (every graphic, before it is shown)
1. Render (`render_plan.py` / `rebuild.py`). `rebuild.py` runs `check_row.py` at every poster time
   and exits 3 on a finding.
2. On a finding, fix the composition against `references/craft-standards.md` and render again.
3. Repeat until poster frames are clean. Transition frames may report OVERLAP mid-move — judge
   those by eye. Only then show the frame. `--no-check` is for accepting a finding the user has
   seen, not for skipping the loop.

## Rendering: plan.json (one pass per composition)
`<graphics_dir>/plan.json` says which rows each composition covers:
`{"<NNN_slug>": {"rows": [first, last], "cuts": [0, t1, …, dur], "poster_times": [t, …], "kind": "custom_graphic"}}`
(one `cuts` boundary per row plus the end; one poster time per row, at the moment its beat has
settled). With an entry there, `rebuild.py` renders, then registers those rows itself — segment,
`poster_t`, `layers`, kind — re-reading the board under a lock so nothing edited meanwhile is lost,
and cuts each row's poster. No register → render → register dance, no fix-ups afterwards.
- `render_plan.py storyboard.json [name-fragment …] [--stale] [--rows A-B] [--dry-run]` renders the
  plan and rebuilds the xlsx once. `--stale` renders only compositions older than their HTML or
  anything in `shared/`/`assets/` — after a style change, that is exactly what it touched.
- `make_overlays.py` writes plan entries for overlays; add entries by hand for authored graphics.
- `register_clip` remains for Higgsfield clips and anything rendered outside the plan.

## Placeholder voiceover (free, local)
`placeholder_vo.py storyboard.json [--voice am_michael] [--speed 1.0] [--rows A-B]` speaks every row's
script with HyperFrames' local Kokoro TTS into `audio/placeholder-vo/` — one clip per row, the whole
read joined with short gaps (`placeholder-vo.wav`), and `timings.csv` — then lists graphics shorter
than their read. A stand-in for timing and first watches, never the final VO. Needs `kokoro-onnx` and
`soundfile` in the skills repo `.venv` (`HYPERFRAMES_PYTHON` points HyperFrames at it). Spot-check
numbers by transcribing a clip back (`npx hyperframes transcribe <wav>`).

## Video is silent by default
Every generated video is delivered with **no audio** — the video editor sets all sound and music — except HyperFrames graphics a row explicitly opts into sound effects for (see "Sound effects on graphics"), and even then never music or voice.
- Prefer silent models (`seedance_2_5`). Do not pick audio/lip-sync models (e.g. `kling3_0`'s audio
  mode) unless the user explicitly asks for sound on that row.
- Never add music/voice/SFX terms to a prompt. Briefs already say "No audio (editor handles sound)".
- After download, strip any audio track defensively: `generate_row.py silence <file>` (runs
  `ffmpeg -i in -c:v copy -an out`). Do this before registering the asset.
Layered delivery (graphic on alpha, background separate) and opt-in sound effects:
`references/delivery-layers-and-sfx.md`.

## CUSTOM GRAPHIC / GRAPHIC-SCREENCAST → HyperFrames (local, no Adobe)
0. **Decide grouping from context first** (applies to `custom-graphic`, ranges, and lists).
   Scan the selected rows and merge a run of CONSECUTIVE custom-graphic rows into ONE continuous
   graphic when context says they are beats of the same visual — e.g. the same chart/object
   building or animating across the beats, a `visual_direction` that references the prior row
   ("same graph, now…", "continues"), one sentence split across rows, or a mechanism explainer
   where a single diagram evolves. Keep rows SEPARATE when the subject/data changes, a non-graphic
   row (talking head / B-roll) interrupts the run, or a new section header begins. State the
   grouping you chose (which rows became one graphic, and why) so the user can correct it.
   - **Merged run →** author ONE composition whose single `paused` timeline sequences the beats;
     render once named by the FIRST row (`<AAA>_slug.mp4`); add a plan.json entry with the rows,
     the beat boundaries as `cuts` and each beat's settle time as `poster_times`, then render with
     `rebuild.py`/`render_plan.py` — each row gets its in/out segment and its OWN poster (see
     "Rendering: plan.json" above and "Per-beat posters" in `references/shared-clips-and-series.md`). You authored the timeline, so you know when
     each beat settles: give explicit poster times rather than letting a fraction guess.
   - **Standalone rows →** render each individually per the steps below.
1. Pick or author a composition under `templates/<name>/index.html`. Start from a template (e.g.
   `portfolio-bar-drop`) or `npx hyperframes catalog --query "..."` then `npx hyperframes add`.
   Follow `/hyperframes-core` + `/hyperframes-animation`.
2. Feed the row `brief` and brand tokens (colors, type, motif) into the composition.
3. **Seek-safety, and the one exception.** Every leg is a `fromTo` with explicit start values —
   the renderer SEEKS, it does not play, so a `to` leg resolves its start from whatever the last
   seek left behind and pops. But `immediateRender:false` belongs on an element's SECOND and later
   legs only: on a first entrance the from-state has to apply at load, or the element sits fully
   visible until its tween starts (a panel's copy was on screen through an entire camera move that
   way). Check a frame BEFORE each entrance, not just the poster times.
4. **Honor the contract or it renders blank:** register the timeline as
   `window.__timelines["<data-composition-id>"] = tl` (create it `paused:true`); animate
   **transforms** (x/y/scale/opacity), never layout props. `npx hyperframes lint` until clean.
5. `npx hyperframes render --quality high --output <NNN_slug>.mp4`; poster:
   `ffmpeg -y -ss <hold-time> -i <NNN_slug>.mp4 -frames:v 1 <NNN_slug>.png`. Graphics have no
   audio track already, so no stripping needed. Normally use `scripts/rebuild.py` for this instead
   of running render + ffmpeg by hand — it also copies into the project's `assets/`, registers the
   plan.json rows, cuts every row's poster from the board, and refreshes the xlsx in one step.

## B-ROLL / B-ROLL-GRAPHIC / TESTIMONIAL → Higgsfield (silent)
1. Build a prompt from the row `brief` + brand `broll_style` so clips share one look project-wide.
   Preflight with `get_cost:true`. One row → `generate_video`; several → `generate_video_batch`
   then `jobs_wait`. Model `seedance_2_5`. Keep prompts descriptive, not emotional (distress
   wording can trip the content filter — reword neutrally and retry if a job returns `nsfw`).
2. Download to `assets/<NNN_slug>.mp4`, strip audio (`silence`), extract a poster PNG.
3. Stock-first rows: write a shortlist of search terms to the row notes and drop a placeholder.

## TALKING HEAD / + LOWER THIRD / CUTAWAY → still (no generation)
Copy the `reuse_of` row's still, or a labelled placeholder card if none yet.

## SCREENCAST → placeholder
A card naming the URL/screen to capture; the human records it.

## After generating
- Name outputs `NNN_slug.ext` (three-digit row number) so `assets/` is easy to share with the editor.
- Write the asset into the row's `assets[]`, set `status` to `Generated`, and re-render the board xlsx
  (`/storyboard-build`, or `sb_to_xlsx.py storyboard.json <out>.xlsx`) so the new thumbnail shows.
- `scripts/generate_row.py` holds plan [--samples] / signoff / assume / add_feedback / feedback / resolve /
  download / silence / register / register_clip helpers. Every write to storyboard.json is atomic and
  locked; never hold a loaded board across a long render and save it afterwards.
- `name_for()` adds the `NNN_` row prefix — a row's `slug` never carries it.

## Reference files (open the one the current step needs)
- `references/craft-standards.md` — the review bar for every graphic: layout, typography, timing,
  mechanism, and the verify-before-showing checks.
- `references/feedback-and-assumptions.md` — `assume` / `resolve`, and regenerating a row with
  added guidance (`/storyboard-generate 7 "…"`).
- `references/delivery-layers-and-sfx.md` — `data-sb-layer="bg"`, `.graphic.mov` / `.bg.mp4`,
  `data-sb-preview-only`, sfx cue sheets.
- `references/shared-clips-and-series.md` — `clip A-B`, per-beat posters, re-rendering shared
  clips, `series A-B`.
- `references/talking-head-overlay.md` — overlay placement, style, the overlay kit and specs.
