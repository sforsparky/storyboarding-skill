# Delivery layers and sound effects

**Contents**
- Delivery layers — graphic on alpha, background separate
- Sound effects on graphics (opt-in per row)

## Delivery layers — graphic on alpha, background separate (the default for graphics)
Editors composite. They want the motion graphic floating on a transparent layer over a background
of THEIR choosing, and the designed background (usually a subtle motion bed) as a separate asset
they can keep, swap or drop. The board still has to show the frame as designed.

- **Declare the background in the composition**: put `data-sb-layer="bg"` on every background
  element (brand field, vignette, ambient mesh — the templates already do). They must be **direct
  children of the composition root**. (The name is `data-sb-layer`, not `data-layer`: HyperFrames'
  linter rejects `data-layer` as a deprecated alias of its own `data-track-index`.) Everything unmarked is the graphic. A composition with no
  marked element renders flat, as before.
- `rebuild.py` then makes two passes and a composite (`scripts/layers.py`), never touching the source:
  - `assets/<name>.graphic.mov` — ProRes 4444 with alpha, page transparent, **carries the sfx**
  - `assets/<name>.bg.mp4` — the background alone, opaque and silent, same length and motion
  - `assets/<name>.mp4` — the graphic over its background, composited by ffmpeg (not a third
    render). **Posters, the board thumbnail, the review page and every checker use this one**, so
    the storyboard always shows the background even though the editor receives it separately.
  The row's asset keeps `file` → the composite and gains `layers: {graphic, bg}` — hand the editor
  the two layer files, not the composite. `--no-layers` renders flat for quick authoring passes.
- **Design the graphic to survive a different background.** Anything translucent — frosted cards,
  glows, soft shadows, low-opacity washes — composites correctly on alpha but was tuned against
  YOUR background; over the editor's it will look different. Keep type and data on solid or
  near-solid surfaces, check the graphic layer over both a dark and a light plate before sending,
  and say so in the handoff when a frame leans on translucency.
- **The background is per composition**, not one file: each composition gives its background its
  own drift, so each gets its own `.bg.mp4`. If the editor wants one reusable bed instead, render
  a single long background composition for them rather than reusing a row's.
- Light that belongs to the subject (a glow under a product, a spotlight) is graphic, not
  background — leave it unmarked. Mark only what the editor could replace wholesale.
- Budget for size: full-frame ProRes 4444 runs roughly 50 MB per second (a 10s graphic ≈ 500 MB).
- Verify a layered render the first time on a project: a corner pixel of an extracted RGBA frame
  has alpha 0 (`pix_fmt` alone proves nothing), the `.mov` has an audio stream when the row has
  sfx, and the composite matches a `--no-layers` render at the poster time.
- A background that only stands in for footage the editor already has (the presenter behind a
  talking-head overlay) is marked `data-sb-preview-only`: it composites the board preview but is never
  delivered — the row's `layers` holds `graphic` alone.

## Sound effects on graphics (opt-in per row)
Graphics render silent unless the row has a cue sheet at `<graphics>/sfx/<composition>.json`. With
one, `rebuild.py` runs `scripts/sfx_track.py` before rendering: it reads cue times from the
composition's LIVE timeline (`at: "startOf('.card', i)"`, `len: "durOf('#line')"`, the composition's
own constants like `WAVE_T`, `pan: "xOf('.card', i)"`), mixes one track to `assets/sfx/<name>.wav`,
and writes a single `<audio id="sfx">` into the composition, so the MP4 carries the sound and a
retimed animation carries its sounds with it.
- Keep them out of the producer's music: **no pitched sounds** (chimes, dings, pops with a note),
  **nothing under 150 Hz** (the mixer high-passes every cue), **short**, quiet (cues ~-19..-31 dBFS,
  track capped at -16). Sound the moments that matter, not every element — a sweep across 141
  candles is ONE whoosh, not 141 clicks.
- Measure a sound before choosing it (low-end %, energy on one pitch). Library names lie: bundled
  "whoosh"/"whoosh-short" are one pitched file; HeyGen "airy" whooshes are 90% sub-bass.
- The built-in `air` sound is synthesized noise (no pitch, no licence question), shaped per cue:
  `swell` / `rise` / `fall` / `puff`, a band sweep, and a `[from, to]` pan that can follow motion.
- Only use library sounds whose licence covers paid ads; record each in `assets/sfx/src/SOURCES.md`.
