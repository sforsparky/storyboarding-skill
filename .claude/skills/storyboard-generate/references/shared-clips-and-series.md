# Shared clips and series of stills

**Contents**
- Clip across rows (`clip A-B`) — one Higgsfield clip covering a range
- Per-beat posters and re-rendering shared clips
- Series of stills (`series A-B`) — one image per row

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
   `t0 t1 t2 ...` seconds. Each row gets
   `assets:[{file, poster, poster_t, segment:[in,out], clip_group}]` — its own poster, not a
   shared one (see "Per-beat posters").
4. The single clip is shared once and each row carries its in/out, so the editor knows where each
   script beat falls inside it.

### Per-beat posters (shared clips)
One clip covering N rows must NOT leave all N rows showing the same screenshot. The board is what
stakeholders review copy on — if six rows repeat one frame, nobody can check the bullets for the
beat they're actually reading. `register_clip` therefore cuts **one poster per row**, from inside
that row's own segment, named `<NNN>_<that row's slug>.png`, and records `poster_t` on the asset so
the frame can be re-cut identically later.

- **Default** — `BEAT_POSTER_AT` (0.78) of the way through each segment. A beat builds, holds, then
  its panel exits right at the boundary, so late-but-not-at-the-end is the widest-open window.
- **Better — `--poster-times 4.2,9.6,15.8,...`** one absolute second per row. Prefer this: you wrote
  the timeline, so you know when each beat's last element lands and when its panel starts leaving.
  A midpoint or a blind fraction can catch a beat mid-transition. Use `-` to let a row fall back to
  the fraction. A time outside its segment still cuts, with a warning.
- **`--poster-at 0.6`** to move the default fraction for one call.
- **`--no-beat-posters`** for the old shared-poster behaviour.
- If the video isn't on disk or ffmpeg fails, the rows keep the shared poster and it says so —
  registration never breaks over a poster.

**Re-rendering:** `scripts/rebuild.py <storyboard.json> <row|name-fragment>` (wired to a project's
`rebuild-row.sh`) cuts every referencing row's poster straight from the board — no side file. It
finds every row whose `assets[].file` points at the re-rendered mp4 and re-cuts each one's poster
at its own `poster_t` (falling back to `segment-in + (out-in)*0.78`, or 3.0s with no segment), so a
shared clip's per-beat posters and a single-row graphic's poster both come from storyboard.json
itself and never go stale independently of it. Pass `--range IN OUT` to render just a time window
for fast iteration while authoring (only where hyperframes supports it — see the script's `--help`).

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
