---
name: storyboard-build
description: >
  Turns a finished VSL/video script into a project storyboard.json — the single source of
  truth for a board (rows with visual type, section, script, direction, notes, per-row
  generation brief, talking-head reuse, status, assets, feedback). Use when a new script
  arrives or a script changes, or for /storyboard-build. Also renders the board as an .xlsx
  opened in Google Sheets, and ingests reviewer comments back into the board.
---

# /storyboard-build — script → storyboard.json

`storyboard.json` is the source of truth. The Google Sheet, the xlsx, and every generated
asset are derived from it. Never hand-edit the Sheet as the primary copy; edit the JSON and
re-push. Scripts need the repo venv (`. .venv/bin/activate`, from `requirements.txt`).

Copy this checklist into your reply and tick it off:
```
- [ ] 1-2. Rows parsed by beat, wording verbatim, sections set
- [ ] 3.   visual_type per row; overlay placement + overlay_placeholders.py; overlay style recorded
- [ ] 4.   reuse_of on repeated talking-head setups
- [ ] 5.   brief on every non-talking-head row
- [ ] 6.   motion_engine per row (user overrides kept)
- [ ] 7.   assumptions recorded with an owner
- [ ] 8.   storyboard.json written with stable ids; xlsx rendered
```
Before step 8: if any non-talking-head row has an empty `brief`, go back to step 5; if any row's
`script` differs from `script.md`, go back to step 2 — wording is never changed.

## Steps
## Steps
1. Read `script.md` in the project folder and its brand at `brands/<brand>/brand.json`.
2. Parse the script into rows using the vsl-storyboard rules: one row per **beat** (how an
   editor would cut), not per sentence. Keep short punchy standalone lines as their own rows;
   fold several short lines that share one visual into one row's `script` with `\n`. Preserve
   wording verbatim. Detect section headers (Hook, Hell, Authority, Heaven, Program,
   Disqualification, Close, etc.) and set each row's `section`.
3. Assign one `visual_type` per row from the types in `scripts/lib_types.py`. Section defaults:
   hook/open → talking head + dramatic custom graphics; pain → b-roll/charts; mechanism →
   custom graphic or screencast; offer → talking head + lower third; proof → testimonial;
   CTA → talking head + lower third; price → clean $ graphic; urgency → animated cost-of-waiting.
   **Prefer `TALKING HEAD + OVERLAY` over a cutaway whenever a beat's supporting text is short
   enough to sit beside the presenter or as a lower third.** That covers a quote, a stat, a name/title, a
   short list, a price, or a CTA. The talking head is shot in 4K waist-up and reframed to make room. Put the
   placement (`lower third` | `left` | `right`, meaning the side the overlay sits on) at the start of
   `visual_direction` and in the brief. Write the brief for a transparent-background overlay: exact
   on-screen text, layout, brand styling, and motion in and out. These rows keep brief, direction
   and notes. They are not in `TALKING_HEAD_TYPES`, and their motion engine is `hyperframes`. Keep full-frame
   `CUSTOM GRAPHIC` for visuals that need the whole screen (charts, montages).
   After writing the board, run `scripts/overlay_placeholders.py storyboard.json`. It gives every overlay
   row a silhouette poster with the overlay zone marked, so the sheet shows the framing before generation.
   If the brand's `components_for_video.talking_head_overlay.style` is not set (`light-type` = type
   straight over the footage, the editor darkens that side; `cards` = solid cards), ask the user once
   now and record it in brand.json — it decides how every overlay row renders.
4. Mark reuse: when a talking-head beat returns to an identical earlier setup, set `reuse_of`
   to that row's id so the sheet duplicates the still instead of asking for a new one.
5. Write a `brief` for every non-talking-head row: a generation-ready prompt naming subject,
   framing, motion, duration, and the brand's colors/motif/broll_style. Talking-head rows get
   an empty brief and empty direction/notes (the one exception is `cut_back`).
6. Set each row's `motion_engine` — how its still gets animated into a clip later (the
   `/storyboard-motion` step). Default it from `visual_type` via `default_motion_engine()` in
   `scripts/lib_types.py`: information graphics (`CUSTOM GRAPHIC`, `GRAPHIC / SCREENCAST`,
   `B-ROLL / GRAPHIC`) → `hyperframes` (deterministic HTML/GSAP render, pixel-exact text/data);
   atmospheric footage-from-still (`B-ROLL`, `TESTIMONIAL`) → `higgsfield` (image-to-video);
   captured footage (`TALKING HEAD`, `TALKING HEAD + LOWER THIRD`, `SCREENCAST`) → `none`;
   `TALKING HEAD + OVERLAY` → `hyperframes` (its overlay is a graphic, the footage is captured). Never
   route text/number/chart graphics through `higgsfield` — i2v warps fine text and data. A user
   can override any row's engine; preserve the override on re-runs.
7. Record assumptions as you go: any figure you scaled or derived, wording the VO and an on-screen
   quote disagree on, a label you guessed, rights to a logo or testimonial. Each becomes an entry in
   the row's `assumptions` with an `owner` (or later: `generate_row.py assume <sb> <rows> "<text>"
   --owner <name>`). They show on the board and the review page until someone confirms them.
8. Emit `storyboard.json` in the project folder with the schema below. Keep row `id` stable across
   re-runs so the Sheet updates in place and comments stay attached.

## Schema (per row)
## Schema (per row)
`id` (r003), `n` (int), `section`, `visual_type`, `script`, `visual_direction`, `notes`,
`reuse_of` (id|null), `slug` (words only — never the `NNN_` row prefix; asset names add it), `brief`, `motion_engine` (hyperframes|higgsfield|none),
`status` (Draft|Generating|Generated|Approved|Reshoot),
`assets` [{file, poster, kind, source, duration}], `feedback` [ {who, when, text} ],
`assumptions` [ {id, text, owner, when, resolved_at?} ].
Top level: `project`, `brand`, `presenter`, `sheet_id`, `drive_folder_id`, `sections_order`, `rows`,
and once the style samples are agreed, `style_signoff` {when, by, note, samples}.

Example — two beats of `script.md` and the rows they become (keys per the Schema above):
```json
{"id": "r012", "n": 12, "section": "Hell", "visual_type": "CUSTOM GRAPHIC",
 "script": "Most portfolios lost 40% in the last drawdown.",
 "visual_direction": "A portfolio bar drops 40%, red fill, number counts down to -40%.",
 "notes": "", "reuse_of": null, "slug": "portfolio-drop",
 "brief": "Full-frame bar on the brand field drops from 100% to 60%; the figure counts down to -40% and locks in the `down` colour. Brand motif, flat graphic_style. 16:9, ~4s, hold on the final frame. No audio (editor handles sound).",
 "motion_engine": "hyperframes", "status": "Draft", "assets": [], "feedback": [], "assumptions": []}
{"id": "r013", "n": 13, "section": "Hell", "visual_type": "TALKING HEAD",
 "script": "And most people never saw it coming.", "visual_direction": "", "notes": "",
 "reuse_of": null, "slug": "talking-head", "brief": "", "motion_engine": "none",
 "status": "Draft", "assets": [], "feedback": [], "assumptions": []}
```
If the "40%" was derived rather than read off the script, it also gets an `assumptions` entry (step 7).

## Reproduce or bulk-convert
## Reproduce or bulk-convert
`scripts/build_storyboard_json.py <extracted.json> <brand.json> <out storyboard.json>` builds
the JSON deterministically from already-parsed rows (used for the example board and for
re-imports). `scripts/lib_types.py` is the shared type vocabulary — import it, don't restate it.

## Offline xlsx
`scripts/sb_to_xlsx.py <storyboard.json> <out.xlsx>` renders a formatted workbook (section rows,
Status column, embedded posters, legend). Opened in Google Sheets, the rendered `.xlsx` is the
collaboration surface — it embeds thumbnails in the Visual cell — and it also serves anyone
without Google access.

## Review channels
Open `references/review-channels.md` when reviewers have commented in the sheet, when publishing
the stakeholder review page (`scripts/build_review.py`) or ingesting its payload
(`scripts/ingest_review.py`), or when a row carries layered assets. Two rules hold everywhere:
rebuilding the board carries reviewers' comments onto their rows (by Line #) so Google re-anchors
them, and ingestion never lowers a row's status.

## Reviewing a script before boarding it (optional)
`references/script-review-lens.md` is a checklist for reading an incoming script — hook, where proof
sits, objection order, CTA count and specificity. It yields notes for the script's owner; it never
changes the script (wording is preserved verbatim, always). The same file's three per-beat questions
— narrative purpose, viewer psychology, sales element — sharpen a row's `brief` even when the copy
is fixed.
