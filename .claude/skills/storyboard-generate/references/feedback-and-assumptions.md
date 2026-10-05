# Feedback and assumptions on rows

**Contents**
- Assumptions — facts that need a named person to confirm
- Editing a generated row (add guidance & regenerate)

## Assumptions — facts that need a named person to confirm
A graphic often asserts something you inferred: a scaled figure, a reworded quote, a button label,
rights to a logo or a testimonial. Record it on the row instead of leaving it in chat:
`generate_row.py assume storyboard.json <selector> "<what was assumed, and what to confirm>" --owner <name>`.
It shows in amber on the board's Feedback column and as a "Needs confirmation" callout on the review
page, and `plan` lists it until it is closed: `generate_row.py resolve storyboard.json <selector>
--assumptions` (or `--id <id>` for one). Mention open ones whenever you hand the board over.

## Editing a generated row (add guidance & regenerate)
Trailing text after a single row (or short list) is refinement guidance for an already-
generated row:
1. Append it to the row so it persists and compounds across passes:
   `generate_row.py add_feedback storyboard.json <n> "<guidance>"` — `<n>` is a row selector: a
   single number, a comma list (`5,7,45`), or an `A-B` range (`30-35`, e.g. for a shared clip).
   Every targeted row gets the same entry (shared `id`, `when` stamped today) so a group note is
   recognisable across rows even though it shows on each row's board cell.
2. Regenerate that row, folding its `brief` PLUS every entry in `feedback[]` into the work —
   the HyperFrames composition for a graphic row, or the Higgsfield prompt for a video row.
   Later feedback supersedes earlier where they conflict; treat the newest as authoritative.
   Run `generate_row.py feedback storyboard.json <n>` to review a row's pending notes first.
3. `rebuild.py` (via plan.json) / `register` / `register_clip` overwrite the row's `assets[]` (stamping `registered_at`), so the
   new asset replaces the old and status returns to `Generated` — this also clears the row from
   `plan`'s "Open feedback" section, since the regenerate is now newer than the feedback that
   prompted it. An explicit row selector regenerates even a `Generated`/`Approved` row (unlike
   the no-arg whole-board default, which skips them).
Re-render the board xlsx afterward so the new thumbnail shows.
4. Close notes explicitly: `generate_row.py resolve <sb.json> <selector|all> [--id ID]` stamps
   `resolved_at` (nothing is deleted; the board shows ✔). A regenerate only *implies* a note is
   done, and never for an undated note. Resolving a comment in Google Sheets does not reach
   storyboard.json — the board is regenerated from the JSON — so `resolve` is the only close.
