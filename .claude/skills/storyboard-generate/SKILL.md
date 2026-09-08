---
name: storyboard-generate
description: >
  Generate the asset(s) for storyboard rows from their brief + brand kit. Custom graphics render
  locally via HyperFrames (replacing hand Adobe work); B-roll via Higgsfield (silent, no audio);
  talking-head/cutaway reuse a still; screencast gets a capture placeholder. Handles single rows,
  lists, a whole visual type, a continuous Higgsfield clip spanning a row range, and a style-linked series of stills.
---

# /storyboard-generate — rows → asset(s)

Selection syntax:
- `/storyboard-generate 7` — one row.
- `/storyboard-generate 5,7,45` — several independent rows.
- `/storyboard-generate 43-46` — a range, each row generated independently.
- `/storyboard-generate clip 43-46` — ONE Higgsfield video clip covering the range (see "Clip across rows").
- `/storyboard-generate series 50-56` — a still IMAGE per row across the range, storyboard/previz frames that
  share a look and can later seed clips (see "Series of stills").
- `/storyboard-generate custom-graphic` — every row of that visual type.

Route by `visual_type` (see `scripts/lib_types.py` GENERATED_BY_TYPE).

## Video is silent by default
Every generated video is delivered with **no audio** — the video editor sets all sound and music.
- Prefer silent models (`seedance_2_5`). Do not pick audio/lip-sync models (e.g. `kling3_0`'s audio
  mode) unless the user explicitly asks for sound on that row.
- Never add music/voice/SFX terms to a prompt. Briefs already say "No audio (editor handles sound)".
- After download, strip any audio track defensively: `generate_row.py silence <file>` (runs
  `ffmpeg -i in -c:v copy -an out`). Do this before registering the asset.

## CUSTOM GRAPHIC / GRAPHIC-SCREENCAST → HyperFrames (local, no Adobe)
1. Pick or author a composition under `templates/<name>/index.html`. Start from a template (e.g.
   `portfolio-bar-drop`) or `npx hyperframes catalog --query "..."` then `npx hyperframes add`.
   Follow `/hyperframes-core` + `/hyperframes-animation`.
2. Feed the row `brief` and brand tokens (colors, type, motif) into the composition.
3. **Honor the contract or it renders blank:** register the timeline as
   `window.__timelines["<data-composition-id>"] = tl` (create it `paused:true`); animate
   **transforms** (x/y/scale/opacity), never layout props. `npx hyperframes lint` until clean.
4. `npx hyperframes render --quality high --output <NNN_slug>.mp4`; poster:
   `ffmpeg -y -ss <hold-time> -i <NNN_slug>.mp4 -frames:v 1 <NNN_slug>.png`. Graphics have no
   audio track already, so no stripping needed.

## B-ROLL / B-ROLL-GRAPHIC / TESTIMONIAL → Higgsfield (silent)
1. Build a prompt from the row `brief` + brand `broll_style` so clips share one look project-wide.
   Preflight with `get_cost:true`. One row → `generate_video`; several → `generate_video_batch`
   then `jobs_wait`. Model `seedance_2_5`. Keep prompts descriptive, not emotional (distress
   wording can trip the content filter — reword neutrally and retry if a job returns `nsfw`).
2. Download to `assets/<NNN_slug>.mp4`, strip audio (`silence`), extract a poster PNG.
3. Stock-first rows: write a shortlist of search terms to the row notes and drop a placeholder.

## Clip across rows — one Higgsfield clip covering a range (`clip A-B`)
Use when consecutive rows are beats of a SINGLE continuous shot the editor will cut into. Generate
ONE Higgsfield video clip long enough to cover the beats, then point every row in the range at it
with its own in/out time:
1. Build one prompt from the combined briefs of rows A-B + brand `broll_style`; generate a single
   clip with `generate_video` (`seedance_2_5`, silent). Preflight cost with `get_cost:true`.
2. Download, strip audio (`generate_row.py silence`), name it by the FIRST row:
   `<AAA>_<slug>.mp4` (e.g. `043_market-cycle-build.mp4`), extract a poster.
3. Register the clip so each row references the shared file plus its segment:
   `generate_row.py register_clip <sb.json> <A> <B> <file_rel> <poster_rel> b_roll higgsfield <total_dur>`
   splits the duration evenly across the rows, or pass explicit cut points as trailing
   `t0 t1 t2 ...` seconds. Each row gets `assets:[{file, poster, segment:[in,out], clip_group}]`.
4. `/storyboard-handoff` ships the single clip once and lists each row's in/out in the manifest, so the editor
   knows where each script beat falls inside it.

## Series of stills — one image per row (`series A-B`)
Use to storyboard a run of rows as STILL frames that share a look — previz you can approve fast and,
later, feed into image-to-video to make clips. Each row gets its own still image, not a video:
1. Write per-row image prompts that share a fixed style preamble from the brand kit (and, for
   people, a reference image / character sheet so the subject stays consistent across the frames).
2. Submit as one `generate_image_batch`, `jobs_wait`, then one `show_generation_by_ids`.
3. Download each to `assets/<NNN_slug>.png`, and register with kind `still` and a shared `series_id`:
   `generate_row.py register <sb.json> <n> <png_rel> <png_rel> still higgsfield "" <series_id>`
   (the still is its own poster). Rows read as a set; regenerating one keeps the shared preamble.
4. To turn an approved still into motion later, run `/storyboard-generate clip` on that row (or range) using
   the still as the start frame.

## TALKING HEAD / + LOWER THIRD / CUTAWAY → still (no generation)
Copy the `reuse_of` row's still, or a labelled placeholder card if none yet.

## SCREENCAST → placeholder
A card naming the URL/screen to capture; the human records it.

## After generating
- Name outputs `NNN_slug.ext` (three-digit row number) so `/storyboard-handoff` is a copy.
- Write the asset into the row's `assets[]`, set `status` to `Generated`, re-run `/storyboard-sheet`.
- `scripts/generate_row.py` holds download / silence / register / register_span helpers.
