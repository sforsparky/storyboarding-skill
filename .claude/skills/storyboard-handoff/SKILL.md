---
name: storyboard-handoff
description: >
  Package approved row assets into a producer folder named by row number, with a manifest, and
  mirror it to Drive. Use when a board (or a section) is approved and ready for the editor.
---

# /storyboard-handoff — approved rows → producer folder

The producer wants a flat folder of files named by row number. This copies only rows whose
`status` is `Approved` (override with `--all` to include `Generated`).

`scripts/storyboard-handoff.py projects/<name>/storyboard-build.json [--all]`
- Copies each asset to `handoff/<NNN_slug>.<ext>` (three-digit row number first, so the folder
  sorts in script order).
- Writes `handoff/manifest.csv`: row, section, visual_type, script line, file, duration, status.
- Mirrors the folder to the project's Drive folder when `drive_folder_id` is set.
- Prints a summary of what shipped and which approved rows are still missing an asset.

Premiere XML / EDL export is a later addition if the producer asks for a pre-built timeline.
