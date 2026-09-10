---
name: storyboard-build
description: >
  Turn a finished VSL/video script into a project storyboard.json — the single source of
  truth for a board (rows with visual type, section, script, direction, notes, per-row
  generation brief, talking-head reuse, status, assets, feedback). Use when a new script
  arrives or a script changes. Also renders an offline .xlsx fallback.
---

# /storyboard-build — script → storyboard.json

`storyboard.json` is the source of truth. The Google Sheet, the xlsx, and every generated
asset are derived from it. Never hand-edit the Sheet as the primary copy; edit the JSON and
re-push.

## Steps
1. Read `script.md` in the project folder and its brand at `brands/<brand>/brand.json`.
2. Parse the script into rows using the vsl-storyboard rules: one row per **beat** (how an
   editor would cut), not per sentence. Keep short punchy standalone lines as their own rows;
   fold several short lines that share one visual into one row's `script` with `\n`. Preserve
   wording verbatim. Detect section headers (Hook, Hell, Authority, Heaven, Program,
   Disqualification, Close, etc.) and set each row's `section`.
3. Assign one `visual_type` per row from the eight in `scripts/lib_types.py`. Section defaults:
   hook/open → talking head + dramatic custom graphics; pain → b-roll/charts; mechanism →
   custom graphic or screencast; offer → talking head + lower third; proof → testimonial;
   CTA → talking head + lower third; price → clean $ graphic; urgency → animated cost-of-waiting.
4. Mark reuse: when a talking-head beat returns to an identical earlier setup, set `reuse_of`
   to that row's id so the sheet duplicates the still instead of asking for a new one.
5. Write a `brief` for every non-talking-head row: a generation-ready prompt naming subject,
   framing, motion, duration, and the brand's colors/motif/broll_style. Talking-head rows get
   an empty brief and empty direction/notes (the one exception is `cut_back`).
6. Set each row's `motion_engine` — how its still gets animated into a clip later (the
   `/storyboard-motion` handoff). Default it from `visual_type` via `default_motion_engine()` in
   `scripts/lib_types.py`: information graphics (`CUSTOM GRAPHIC`, `GRAPHIC / SCREENCAST`,
   `B-ROLL / GRAPHIC`) → `hyperframes` (deterministic HTML/GSAP render, pixel-exact text/data);
   atmospheric footage-from-still (`B-ROLL`, `TESTIMONIAL`) → `higgsfield` (image-to-video);
   captured footage (`TALKING HEAD`, `TALKING HEAD + LOWER THIRD`, `SCREENCAST`) → `none`. Never
   route text/number/chart graphics through `higgsfield` — i2v warps fine text and data. A user
   can override any row's engine; preserve the override on re-runs.
7. Emit `storyboard.json` in the project folder with the schema below. Keep row `id` stable across
   re-runs so the Sheet updates in place and comments stay attached.

## Schema (per row)
`id` (r003), `n` (int), `section`, `visual_type`, `script`, `visual_direction`, `notes`,
`reuse_of` (id|null), `slug`, `brief`, `motion_engine` (hyperframes|higgsfield|none),
`status` (Draft|Generating|Generated|Approved|Reshoot),
`assets` [{file, poster, kind, source, duration}], `feedback` [ {who, when, text} ].
Top level: `project`, `brand`, `presenter`, `sheet_id`, `drive_folder_id`, `sections_order`, `rows`.

## Reproduce or bulk-convert
`scripts/build_storyboard_json.py <extracted.json> <brand.json> <out storyboard.json>` builds
the JSON deterministically from already-parsed rows (used for the example board and for
re-imports). `scripts/lib_types.py` is the shared type vocabulary — import it, don't restate it.

## Offline xlsx
`scripts/sb_to_xlsx.py <storyboard.json> <out.xlsx>` renders a formatted workbook (section rows,
Status column, embedded posters, legend) for anyone without Google access. The live Sheet from
`/storyboard-sheet` is the primary collaboration surface.
