---
name: storyboard-sheet
description: >
  Sync storyboard.json to a Google Sheet the team reviews in, and pull comments/notes back.
  No server, no database — a local script talks to Google Sheets + Drive with a one-time OAuth
  consent. Use to create/update a board's Sheet, or to collect feedback before regenerating.
---

# /storyboard-sheet — push & pull the Google Sheet

Google Sheets is the collaboration surface and the only "database". The script writes the Sheet
from `storyboard.json` and reads feedback back into it. Nothing is hosted.

## One-time setup (per machine)
1. In Google Cloud console, enable the Sheets API and Drive API and download an OAuth **Desktop**
   client secret to `.secrets/credentials.json` (gitignored).
2. First run opens a browser for consent and caches `.secrets/token.json`. No further prompts.

## Push
`scripts/sheets_sync.py push storyboard.json`  (run from the project folder)
- Creates the Sheet on first run and stores `sheet_id` + `drive_folder_id` back into the JSON.
- Columns: Line #, Visual, Script, Visual Direction, Notes, Status, Thumbnail, plus a hidden
  Row-ID column so re-pushes update in place (comments stay attached, no renumbering).
- Writes `▶ SECTION` header rows, applies the legend colors to the Visual column, sets Status
  data-validation (Draft/Generating/Generated/Approved/Reshoot) and Engine data-validation
  (hyperframes/higgsfield/none — the `/storyboard-motion` engine per row, defaulted from the
  visual type but editable in-sheet).
- Thumbnails use `=IMAGE("<drive url>")` pointing at posters uploaded to the project's Drive
  folder (the API cannot place in-cell images any other way). Reused talking-head rows point at
  the `reuse_of` row's poster automatically.

## Pull feedback
`scripts/sheets_sync.py pull storyboard.json`  (run from the project folder)
- Reads the Notes column and the Drive comments API, appends new items to each row's `feedback[]`
  keyed by Row-ID, so the next `/storyboard-generate` includes reviewer feedback in the prompt.
- Also reads the Status and Engine columns back: a valid in-sheet edit to Engine
  (hyperframes/higgsfield/none) overwrites the row's `motion_engine`, so a reviewer can redirect a
  shot's motion route without touching the JSON.

## Notes
- Client stays a Desktop OAuth app; no service account, no shared secret to rotate.
- A later convenience (optional): a bound Apps Script menu ("Refresh thumbnails", "Mark approved")
  for teammates who never open Claude Code.
