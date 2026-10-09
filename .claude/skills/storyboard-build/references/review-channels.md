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

**Comments are carried across rebuilds.** `sb_to_xlsx.py` reads the reviewers' comments out of the
workbook it is about to overwrite and re-places each on the row with the same Line # (so a comment
follows its row when rows are added or removed), keeping Google's thread ID in the comment text and
copying Google's thread data (`xl/commentsmeta0`) across. A comment whose Line # no longer exists is
reported, not placed. (Before this, every rebuild dropped them, and Sheets listed them as unmapped.)
Observed on the ACM board (2026-10-07): after a restore, Sheets showed the comments on their cells
again, but as NEW threads (new IDs; original author, time and text kept in the body), not the old
threads re-attached. Anything resolved in Sheets is gone from the file, so it is not carried.
- Lost them anyway? Restore from an archived copy:
  `sb_to_xlsx.py storyboard.json "<Board>.xlsx" --carry-comments-from "feedback/<date>_<Board>.xlsx"`
- `rebuild.py` still archives a commented workbook into `<project>/feedback/` (once a day) as that
  round's record; `--no-carry` writes a clean board with no comments.
- Uploading a brand-new file over the sheet (File > Import > Replace) still drops threads — that
  bypasses the board entirely. Let the synced xlsx update in place instead.
- Excel's own threaded comments (`xl/threadedComments/`) are not carried yet; Google's format is.

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
