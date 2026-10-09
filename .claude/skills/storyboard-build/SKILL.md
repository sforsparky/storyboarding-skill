---
name: storyboard-build
description: >
  Turn a finished VSL/video script into a project storyboard.json — the single source of
  truth for a board (rows with visual type, section, script, direction, notes, per-row
  generation brief, talking-head reuse, status, assets, feedback). Use when a new script
  arrives or a script changes. Also renders the board as an .xlsx you open in Google Sheets.
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
`id` (r003), `n` (int), `section`, `visual_type`, `script`, `visual_direction`, `notes`,
`reuse_of` (id|null), `slug` (words only — never the `NNN_` row prefix; asset names add it), `brief`, `motion_engine` (hyperframes|higgsfield|none),
`status` (Draft|Generating|Generated|Approved|Reshoot),
`assets` [{file, poster, kind, source, duration}], `feedback` [ {who, when, text} ],
`assumptions` [ {id, text, owner, when, resolved_at?} ].
Top level: `project`, `brand`, `presenter`, `sheet_id`, `drive_folder_id`, `sections_order`, `rows`,
and once the style samples are agreed, `style_signoff` {when, by, note, samples}.

## Reproduce or bulk-convert
`scripts/build_storyboard_json.py <extracted.json> <brand.json> <out storyboard.json>` builds
the JSON deterministically from already-parsed rows (used for the example board and for
re-imports). `scripts/lib_types.py` is the shared type vocabulary — import it, don't restate it.

## Offline xlsx
`scripts/sb_to_xlsx.py <storyboard.json> <out.xlsx>` renders a formatted workbook (section rows,
Status column, embedded posters, legend) for anyone without Google access. The live Sheet from
The rendered `.xlsx` (opened in Google Sheets) is the collaboration surface — it embeds thumbnails in the Visual cell.

## Comments made in the sheet (the other review channel)
Reviewers who live in Google Sheets comment on the row's cell instead of using the review page.
Those threads travel inside the workbook, so download it (File > Download > .xlsx) and read them back:

    scripts/ingest_sheet_comments.py <storyboard.json> <downloaded.xlsx>          # dry run
    scripts/ingest_sheet_comments.py <storyboard.json> <downloaded.xlsx> --apply

Each thread becomes one `feedback` entry on its row — `who` "<Name> (sheet)", `when` the comment's
own date (not today, so `plan` judges it against the asset it was written about), `source`
"sheet-comment", and `comment_id` so re-running only adds what is new. Replies are appended to the
entry's text. Rows are matched through the workbook's "Line #" column, not cell position, so the
section banner rows do not throw the mapping off; a comment on a cell with no line number is
reported and skipped. Status is never changed — regenerating the row is what settles a comment.
Both Google-exported threads and Excel's own threaded comments are read.

**Comments do not survive a replaced sheet.** They are anchored to cells in that one spreadsheet:
re-uploading a fresh xlsx over it (File > Import > Replace) drops every thread. Publish each new
round as a NEW sheet and leave the commented one as that round's record. Locally, `sb_to_xlsx.py`
overwrites the workbook in place, so `rebuild.py` now archives any workbook that carries comments
into `<project>/feedback/` before overwriting it, and prints the ingest command.

**The board writes no comments of its own.** Feedback renders into the **Feedback** column (G)
only. Earlier versions also mirrored it as a cell note on column A; Google Sheets shows a cell note
as a comment, so reviewers resolved them and every rebuild wrote them all back — and the notes
tripped rebuild.py's archive guard, copying the whole board to `feedback/` on every rebuild. Any
comment you see in the sheet is now a person's. To close a note for good, resolve it in the data:
`generate_row.py resolve <sb.json> <selector|all> [--id ID]`, then re-render the xlsx.

## Stakeholder review page (no sign-in needed)
The xlsx is the editor's handoff; stakeholders review on a web page instead:
1. `scripts/build_review.py <storyboard.json> -o review --title "<Project> Review"` — one card per row
   (VO script, direction, media that plays only that row's segment of a shared clip, prior notes),
   two verdicts per row (Approve by default / Needs changes; silence = approved) plus a note, state kept in the viewer's browser,
   and an "Export my review" button that copies a JSON payload (downloads are inert in the artifact
   viewer, so it is clipboard + textarea). `[generated]` implementation notes are hidden unless
   `--internal`. Media is transcoded to 960px previews under `review/media/` (budget `--max-total-mb`).
2. Publish `review/index.html` as an artifact with `review/media/*` as supporting files (map form:
   published path → source path, `root: review`). Label each publish with the round.
3. Reviewers paste their exported payload back; `scripts/ingest_review.py <storyboard.json>
   payload.json --apply` appends each note as feedback (who = "<name> (review page)") and promotes
   Generated → Approved on approve verdicts. Idempotent; never lowers a status.

## Layered graphics on the board
A graphic delivered as layers (see storyboard-generate → "Delivery layers") has three files, but the
board shows ONE thing: the row's `assets[].file`/`poster` stay the composited preview — graphic over
its own background — so the thumbnail always shows the frame as designed. The editor's deliverables
are listed on the asset as `layers: {graphic: "….graphic.mov", bg: "….bg.mp4"}`; never point `file`
or `poster` at a layer, or the board shows a graphic on black.

## Reviewing a script before boarding it (optional)
`references/script-review-lens.md` is a checklist for reading an incoming script — hook, where proof
sits, objection order, CTA count and specificity. It yields notes for the script's owner; it never
changes the script (wording is preserved verbatim, always). The same file's three per-beat questions
— narrative purpose, viewer psychology, sales element — sharpen a row's `brief` even when the copy
is fixed.
