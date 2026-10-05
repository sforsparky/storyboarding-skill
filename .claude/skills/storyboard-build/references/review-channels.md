# Review channels — sheet comments, the review page, layered rows

**Contents**
- Comments made in the sheet (download the xlsx, ingest the threads)
- Stakeholder review page (no sign-in; export → ingest)
- Layered graphics on the board (what `file`/`poster` must point at)

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
only — never as cell notes: Google Sheets shows a cell note as a comment, so reviewers resolve them,
every rebuild writes them back, and the notes trip rebuild.py's archive guard. Any comment you see in
the sheet is a person's. To close a note for good, resolve it in the data:
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
A graphic delivered as layers (see `../../storyboard-generate/references/delivery-layers-and-sfx.md`) has three files, but the
board shows ONE thing: the row's `assets[].file`/`poster` stay the composited preview — graphic over
its own background — so the thumbnail always shows the frame as designed. The editor's deliverables
are listed on the asset as `layers: {graphic: "….graphic.mov", bg: "….bg.mp4"}`; never point `file`
or `poster` at a layer, or the board shows a graphic on black.
