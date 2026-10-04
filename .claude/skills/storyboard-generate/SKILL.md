---
name: storyboard-generate
description: >
  Generate the asset(s) for storyboard rows from their brief + brand kit. Custom graphics render
  locally via HyperFrames (replacing hand Adobe work); B-roll via Higgsfield (silent, no audio);
  talking-head/cutaway reuse a still; screencast gets a capture placeholder. Handles single rows,
  lists, a whole visual type, a continuous Higgsfield clip spanning a row range, and a style-linked
  series of stills. Consecutive custom-graphic rows are auto-grouped into one continuous graphic
  when context says they're beats of the same visual.
---

# /storyboard-generate — rows → asset(s)

Selection syntax:
- `/storyboard-generate` — NO selector: whole-board default. Generate every free/local asset across
  the board (HyperFrames graphics, still reuses, placeholders) and STOP before any paid Higgsfield
  B-roll. See "Whole-board default" below.
- `/storyboard-generate 7` — one row.
- `/storyboard-generate 7 "make the bars taller, lean into the lime accent"` — regenerate row 7
  with added guidance (see "Editing a generated row").
  Quotes are optional — everything after the row is read as guidance; quote only to disambiguate
  guidance that starts with a selector keyword (`clip`, `series`, `custom-graphic`, `b-roll`).
- `/storyboard-generate 5,7,45` — several independent rows.
- `/storyboard-generate 43-46` — a range, each row generated independently.
- `/storyboard-generate clip 43-46` — ONE Higgsfield video clip covering the range (see "Clip across rows").
- `/storyboard-generate series 50-56` — a still IMAGE per row across the range, storyboard/previz frames that
  share a look and can later seed clips (see "Series of stills").
- `/storyboard-generate b-roll` — every Higgsfield B-roll/testimonial row (the paid rows), after cost preflight.
- `/storyboard-generate custom-graphic` — every row of that visual type; consecutive graphic rows
  that read as one continuous graphic are auto-grouped (see the CUSTOM GRAPHIC route).

Route by `visual_type` (see `../storyboard-build/scripts/lib_types.py` GENERATED_BY_TYPE).

## Whole-board default (no selector)
`/storyboard-generate` with no argument does NOT blindly render everything — it protects credits:
0. **Style gate first.** Until the board carries a `style_signoff`, the plan leads with the style
   samples: one pending row per visual type the free route renders, and one per overlay placement
   (`generate_row.py plan storyboard.json --samples` lists only these). Render ONLY those, show them,
   and settle every project-wide call before the full pass — ground (light/dark), overlay style
   (cards or type over footage), quote marks, number formats, and every figure a graphic asserts
   (record unconfirmed ones with `assume`, below). Then `generate_row.py signoff storyboard.json
   "<who>" "<what was agreed>"`. A look corrected after 40 rows costs 40 re-renders; corrected
   after 5 it costs 5.
1. Print the plan: `generate_row.py plan storyboard.json`. It buckets pending rows into free/local
   (route `hyperframes` / `still` / `placeholder`, honoring any per-row `motion_engine: hyperframes`
   override) versus paid Higgsfield (route `video`), and skips rows already `Generated`/`Approved`.
   - The plan ends with an "Open feedback" section: rows whose feedback is newer than what was
     last generated for them (see "Editing a generated row" below) — check these before generating.
   - Then "Open assumptions": facts the board asserts that a named person must still confirm.
2. Generate the free/local rows now — this is the "render all the infographics" pass, and it spends
   nothing. Apply the custom-graphic grouping rules (consecutive graphic beats → one graphic).
   Put each composition's rows in `<graphics_dir>/plan.json` and render them all with
   `render_plan.py` (see "Rendering: plan.json" below).
3. STOP before the paid rows. Show the user the Higgsfield B-roll list and the estimated credits,
   and ask before generating them (or tell them to run `/storyboard-generate b-roll`). Only proceed
   on an explicit yes, and preflight exact cost with `get_cost:true` at that point.

## Assumptions — facts that need a named person to confirm
A graphic often asserts something you inferred: a scaled figure, a reworded quote, a button label,
rights to a logo or a testimonial. Record it on the row instead of leaving it in chat:
`generate_row.py assume storyboard.json <selector> "<what was assumed, and what to confirm>" --owner <name>`.
It shows in amber on the board's Feedback column and as a "Needs confirmation" callout on the review
page, and `plan` lists it until it is closed: `generate_row.py resolve storyboard.json <selector>
--assumptions` (or `--id <id>` for one). Mention open ones whenever you hand the board over.

## Rendering: plan.json (one pass per composition)
`<graphics_dir>/plan.json` says which rows each composition covers:
`{"<NNN_slug>": {"rows": [first, last], "cuts": [0, t1, …, dur], "poster_times": [t, …], "kind": "custom_graphic"}}`
(one `cuts` boundary per row plus the end; one poster time per row, at the moment its beat has
settled). With an entry there, `rebuild.py` renders, then registers those rows itself — segment,
`poster_t`, `layers`, kind — re-reading the board under a lock so nothing edited meanwhile is lost,
and cuts each row's poster. No register → render → register dance, no fix-ups afterwards.
- `render_plan.py storyboard.json [name-fragment …] [--stale] [--rows A-B] [--dry-run]` renders the
  plan and rebuilds the xlsx once. `--stale` renders only compositions older than their HTML or
  anything in `shared/`/`assets/` — after a style change, that is exactly what it touched.
- `make_overlays.py` writes plan entries for overlays; add entries by hand for authored graphics.
- `register_clip` remains for Higgsfield clips and anything rendered outside the plan.

## Video is silent by default
Every generated video is delivered with **no audio** — the video editor sets all sound and music — except HyperFrames graphics a row explicitly opts into sound effects for (see "Sound effects on graphics"), and even then never music or voice.
- Prefer silent models (`seedance_2_5`). Do not pick audio/lip-sync models (e.g. `kling3_0`'s audio
  mode) unless the user explicitly asks for sound on that row.
- Never add music/voice/SFX terms to a prompt. Briefs already say "No audio (editor handles sound)".
- After download, strip any audio track defensively: `generate_row.py silence <file>` (runs
  `ffmpeg -i in -c:v copy -an out`). Do this before registering the asset.

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
- Overlays that were always alpha (lower thirds, captions over footage) are unchanged: they have no
  background layer and render straight to `.mov`.

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

## Craft standards (every graphic, before it is shown)
Learned from review passes on real projects. The user reads a frame like a designer — for
layering, edges, overlap and derived values — so these are checked, not eyeballed. Also read
the project's `brand.json` (`typography.headline_case`, `motifs`, `graphic_style`) and the row's
`feedback[]`; later feedback wins.

**Layout**
- **Nothing overlaps or runs into a neighbour.** Connectors never travel under a card (route
  them orthogonally, 90° with rounded corners, from edge to edge). Lists must clear whatever sits
  below them. If two things must share a frame, spread them — two rows beat one crowded row.
- **Every member of a set is fully visible when the set is the point.** An overlapping fan that
  hides the narrow items is wrong even when it is more cinematic; a bookcase / grid where each
  cover is whole is right. Then give each item its own spotlight when the VO names it, keeping the
  family on screen; items that have had their moment can leave rather than dim.
- **No visible edges on soft things.** Shadows, glows, fades and washes must reach zero inside
  their own box (elliptical/radial gradients, oversized bleed) so nothing crops at the frame or
  at a container edge, at any point of a camera move.
- **Let art leave the frame.** A curve, a route or a spread that stops inside its container reads
  as a diagram; enlarged past the container and cropped by it, the same art reads as graphic. Pair
  that with `overflow:hidden` on the container and keep the readable part of the animation inside.
- **Get content out of card containers when the card is not doing work.** A frosted panel around a
  number or a definition usually adds nothing the field does not already give you.
- **Centre by the content's real extents**, including the transparent margin baked into a supplied
  PNG — element boxes lie. Measure both, then shift.
- **Anything that marks a feature sits ON it**: centred on the peak/valley it names, on the path
  point, standing on the line rather than straddling it. Derive those positions from the geometry
  (`getScreenCTM`/`getPointAtLength`), never from hand-computed percentages — a stretched viewBox
  is exactly where hand arithmetic goes wrong.
- **Anchor a derived position to the thing it marks, not to the container.** Storing a measured
  point as a percentage of its parent silently goes stale whenever the parent resizes — and a
  flex-sized box DOES resize, by ~20px, the moment the display font swaps in under a headline.
  Worse, an `<svg>` is a replaced element: with left+right insets its width comes from those and
  its height then follows the viewBox aspect, so a `bottom` inset does nothing and the drawing
  does not resize with its box. Express the position the same way the drawing's own insets are
  written (`calc(-26% + <px inside the drawing>)`) so the marker and the artwork move together.
  The tell is a drift that grows along the feature instead of a constant offset.
- **Never scale raster art past its own pixels.** Past ~80% of native it softens, and under a slow
  camera move it shimmers. Cap the zoom or ask for a bigger render.
- **Prefer one camera move to two cards.** Two beats that share a subject can live on one rail and
  pan between mirrored layouts, with the editor's cut landing mid-move (see "Clip across rows").
- **Supplied product art is the hero and sits on the top layer.** Boxes, covers, badges, coins:
  full opacity, no colour wash, no glow across them, real files not look-alikes. Ask for the
  master rather than fake it; keep masters in `brands/<brand>/refs/` and a working copy in the
  graphics `assets/`. Scale raster art DOWN only (size the element at its largest use).
- **Headlines and the corner logo are optional chrome.** Drop them when the content needs the
  room, especially where the art already carries the mark. No corner lockup before the product
  is introduced.
- **Display headlines follow the brand's `headline_case`** (Title Case unless the kit says
  otherwise); kickers/labels stay tracked-out caps. Break two-line headlines by hand so no line is
  an orphan word.
- **Lucide icons** (what shadcn/ui ships — shadcn has no icon set of its own), not hand-drawn
  glyphs and not typographic characters. A `✓ → ⇄ ●` sitting in a `<span>` is the most common
  offender: it renders in the body font, so its weight and baseline never match anything around
  it. Replace those first — that is where Lucide wins outright.
  - **Vendor, don't hotlink.** Pull the SVGs into the graphics kit
    (`kit/icons/<name>.svg`, from `lucide-static` on a jsdelivr CDN — ISC licensed) and inline the
    path data. A render that fetches an icon at runtime is not deterministic.
  - **Match the stroke weight to the artwork, not to Lucide's default.** Lucide ships
    `stroke-width="2"` on a 24-unit viewBox. Normalise any bespoke line art the same way
    (`stroke-width ÷ viewBox × 24`) before swapping: thin technical line work often sits at
    0.25–0.5, so dropping in an as-shipped Lucide icon lands 4–8× heavier and reads as a UI
    control blown up to hero size. At small sizes (≤48px) use Lucide's native weight untouched —
    that is what it is drawn for.
  - **Check the icon actually depicts the thing.** Lucide names are not always literal (`vault`
    is a rounded square with an X — no door, no dial). When the bespoke drawing carries meaning
    the icon does not, keep the drawing and say why.
  - Keep supplied brand/product art bespoke — never substitute an icon for art the client sent.

**Typography**
- **Go bigger than feels safe on the one thing the frame is about.** A hero figure or headline that
  dominates beats a balanced frame; reviewers ask for +100% far more often than for less.
- **One bold per block.** Headline bold; eyebrow and supporting line at regular weight. Three bold
  weights stacked reads as shouting.
- **Break every display line by hand and leave no widow** — not in headlines, not in supporting
  lines. Aim for the last line at least half the longest. Then CHECK THE RENDER: a hand-break
  wider than its column re-wraps silently, turning two chosen lines into four arbitrary ones. Read
  the line widths off the rendered poster rather than trusting the markup.
- **A display line box is much taller than its ink.** Past ~100px leave 80-90px of air above and
  below; box collisions the eye cannot see are still real and still fail the frame check.
- A label that is really a title takes the display face, not the tracked-caps label style.

**Timing** (seconds on the timeline — never frame counts)
- **Give things time to be read.** Nothing that carries meaning is on screen for less than ~0.3s;
  a small UI-scale move (a pop, a tick, a chip) lands best around 0.5s; a transition between
  states takes 1-2s; a frame carrying complex information holds 3-5s once it has settled. If a
  beat cannot hold its content that long, the beat has too much in it.
- **Nothing sits unchanged for more than ~8-12s.** A long hold needs a slow camera move, a drift,
  or the next element arriving.
- **One easing vocabulary per video.** Pick the entrance, exit and emphasis eases once and reuse
  them; easing chosen per element reads as noise.
- **Stagger a group by ~0.15-0.35s per item** so it reads as one gesture; tighter looks like a
  glitch, looser like a list being read out.
- **Exits are quicker than entrances** — about two-thirds the duration. The viewer has already read
  what is leaving.
- **Name the focus point of every beat** — the one thing the eye should land on — and make the
  motion lead there. If two things move at once, one of them is the focus and the other is slower,
  smaller or later.

**Mechanism**
- **One idea, one mechanism, one source of truth.** Prefer one diagram that evolves over two
  cards side by side; one shared axis over two; one derived scalar driving every readout. A value
  that labels data (a %, a delta, a colour) must be computed from that data — never hardcoded
  markup beside a number that moves.
- **Simplify toward the sentence.** If the script says "the number goes up and down", the graphic
  is the number going up and down; extra machinery competes with it.
- **Colour is semantic.** Market up/down colours only for market data; the CTA colour only on the
  CTA; the brand accent everywhere else. Warm/neutral light behind gold or orange art, not the
  brand accent (it muddies).

**Verify before showing** (measure, don't look)
- Automate the measuring: `scripts/check_row.py <storyboard.json> <row|name-fragment>` seeks the
  composition's real timeline to every referencing row's poster_t plus each segment boundary
  ±0.4s, then reports OFF_FRAME, OVERLAP, headline LINES>2, HARD_EDGE (a luminance step along a
  long run) and SOFT_EDGE (a linear-gradient box with no border/radius whose ends stop inside the
  frame — the shelf-shadow bug, caught from the DOM even when the pixel step is faint), WIDOW (a
  wrapped or hand-broken text block whose last line is under half its longest; opt out with
  `data-check-widow="off"`), LABEL_ON_PATH (a text box crossed by the drawn part of a stroked SVG
  path — the label sitting on the chart line) and SEE_THROUGH (a translucent element in front of
  other content — dim with `filter:brightness`, not opacity) per frame,
  plus a labelled contact sheet and `report.json`; `--at t1,t2` checks specific times, `--strict`
  exits 1 on any finding. `scripts/rebuild.py` runs it at every poster time after each render and
  exits 3 on a failure (render and posters are kept so you can look; `--no-check` to accept).
  Transition frames may legitimately report OVERLAP mid-move — judge those by eye; poster frames
  must be clean.
- Names: `scripts/check_briefs.py <storyboard.json> [--rows A-B]` diffs product names in script,
  briefs and notes against the supplied art in `brands/<brand>/refs/` and flags DRIFT (a changed
  or dropped distinguishing word) vs NEAR (a safe elision). Run it when new art lands and before
  a stakeholder round; the decision on which side moves (art or VO) goes on the row as feedback.
- Seek to each beat's poster time and check bounding boxes: nothing off-frame, nothing under the
  next element, lists clear the thing below, headline line count as intended.
- Scan for hard edges (luminance step across an overlay's boundary) and for stray dots on
  undrawn strokes (round caps on `dasharray` paths).
- Check the render for FLICKER: `scripts/check_flicker.py <mp4> --windows "t0-t1,…"` (camera
  holds, where nothing should change) flags frames that differ from both neighbours while the
  neighbours agree. If they all land on one `frame % workers` residue, one render worker drew the
  page differently — a renderer problem, not the art. HyperFrames' experimental fast capture did
  exactly this (a transformed layer 1.75px off on every 3rd frame), so `rebuild.py` renders with
  `--experimental-fast-capture=false` unless given `--fast-capture`.
- Check the RENDER, not only the browser probe: extract frames at the poster times and one or two
  mid-transition times and eyeball a contact sheet.
- Shared clips: one poster per row (see Per-beat posters), and the rebuild script must cut them
  all or they go stale silently.
- When a graphic reuses art or copy from the script, cross-check names against the supplied
  art and flag mismatches to the user rather than papering over them.

## CUSTOM GRAPHIC / GRAPHIC-SCREENCAST → HyperFrames (local, no Adobe)
0. **Decide grouping from context first** (applies to `custom-graphic`, ranges, and lists).
   Scan the selected rows and merge a run of CONSECUTIVE custom-graphic rows into ONE continuous
   graphic when context says they are beats of the same visual — e.g. the same chart/object
   building or animating across the beats, a `visual_direction` that references the prior row
   ("same graph, now…", "continues"), one sentence split across rows, or a mechanism explainer
   where a single diagram evolves. Keep rows SEPARATE when the subject/data changes, a non-graphic
   row (talking head / B-roll) interrupts the run, or a new section header begins. State the
   grouping you chose (which rows became one graphic, and why) so the user can correct it.
   - **Merged run →** author ONE composition whose single `paused` timeline sequences the beats;
     render once named by the FIRST row (`<AAA>_slug.mp4`); add a plan.json entry with the rows,
     the beat boundaries as `cuts` and each beat's settle time as `poster_times`, then render with
     `rebuild.py`/`render_plan.py` — each row gets its in/out segment and its OWN poster (see
     "Rendering: plan.json" and "Per-beat posters"). You authored the timeline, so you know when
     each beat settles: give explicit poster times rather than letting a fraction guess.
   - **Standalone rows →** render each individually per the steps below.
1. Pick or author a composition under `templates/<name>/index.html`. Start from a template (e.g.
   `portfolio-bar-drop`) or `npx hyperframes catalog --query "..."` then `npx hyperframes add`.
   Follow `/hyperframes-core` + `/hyperframes-animation`.
2. Feed the row `brief` and brand tokens (colors, type, motif) into the composition.
3. **Seek-safety, and the one exception.** Every leg is a `fromTo` with explicit start values —
   the renderer SEEKS, it does not play, so a `to` leg resolves its start from whatever the last
   seek left behind and pops. But `immediateRender:false` belongs on an element's SECOND and later
   legs only: on a first entrance the from-state has to apply at load, or the element sits fully
   visible until its tween starts (a panel's copy was on screen through an entire camera move that
   way). Check a frame BEFORE each entrance, not just the poster times.
4. **Honor the contract or it renders blank:** register the timeline as
   `window.__timelines["<data-composition-id>"] = tl` (create it `paused:true`); animate
   **transforms** (x/y/scale/opacity), never layout props. `npx hyperframes lint` until clean.
5. `npx hyperframes render --quality high --output <NNN_slug>.mp4`; poster:
   `ffmpeg -y -ss <hold-time> -i <NNN_slug>.mp4 -frames:v 1 <NNN_slug>.png`. Graphics have no
   audio track already, so no stripping needed. Normally use `scripts/rebuild.py` for this instead
   of running render + ffmpeg by hand — it also copies into the project's `assets/`, registers the
   plan.json rows, cuts every row's poster from the board, and refreshes the xlsx in one step.

## B-ROLL / B-ROLL-GRAPHIC / TESTIMONIAL → Higgsfield (silent)
1. Build a prompt from the row `brief` + brand `broll_style` so clips share one look project-wide.
   Preflight with `get_cost:true`. One row → `generate_video`; several → `generate_video_batch`
   then `jobs_wait`. Model `seedance_2_5`. Keep prompts descriptive, not emotional (distress
   wording can trip the content filter — reword neutrally and retry if a job returns `nsfw`).
2. Download to `assets/<NNN_slug>.mp4`, strip audio (`silence`), extract a poster PNG.
3. Stock-first rows: write a shortlist of search terms to the row notes and drop a placeholder.

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

## TALKING HEAD + OVERLAY → transparent overlay, presenter on the board
The talking head is shot in 4K, waist up, so the editor can reframe it and make room for a graphic.
These rows ask for the **overlay only**. The footage is captured, and the overlay is never baked into it.
- **Placement** comes from `visual_direction`/`brief`. With `lower third`, the presenter stays centred. With `right`,
  the overlay fills roughly the right 45% and the presenter is reframed left. `left` is the mirror image. Keep the overlay
  clear of the presenter's half, and keep it within title-safe margins (5%).
- **Style** comes from the brand: `components_for_video.talking_head_overlay.style` is `light-type`
  (type straight over the footage, the editor darkens that side) or `cards` (solid cards, safe over
  anything). If the brand does not say, ask once at the style gate — do not guess and re-render.
- **Use the kit, don't hand-write compositions.** The project keeps only copy and layout, in
  `<graphics_dir>/tools/overlay_specs.py` (`SPECS`, `PRESENTER`, `HEAD`; see the docstring of
  `scripts/make_overlays.py`). Then:
  1. `presenter_frames.py <presenter still> <graphics_dir>/assets/presenter --name <who>` — the
     centre / left / right reframes and their `-dim` previews (a stand-in for the editor's grade).
     Without a presenter still, use the silhouettes in `assets/silhouette/`.
  2. `make_overlays.py storyboard.json <specs.py> [--only NAME]` — writes each composition (beat
     lengths from the VO word count), copies the kit (`kit/overlay/sb-overlay.css` + `.js`: zones,
     light-type rules, hanging quotes, the entrance/exit timing) into `shared/`, and adds plan.json
     entries.
  3. `render_plan.py storyboard.json [NAME]`.
  The presenter frame is the background layer, marked `data-sb-layer="bg" data-sb-preview-only
  data-check-ignore`: the board shows the overlay over the presenter, the editor receives
  `<name>.graphic.mov` alone (ProRes 4444 alpha), no `.bg.mp4` is delivered, and the craft check
  ignores the frame. The row's asset is kind `custom_graphic` with `layers.graphic` only.
- The brand CSS defines the type classes (`.kicker .h-xl .h-lg .h-md .body .attr .card .pill .icon
  .rule .num .grad .strike .check .stack .cta`) and `--accent`; the kit only places and recolours
  them. Secondary lines take class `muted`, never an inline colour.
- Consecutive overlay rows with the same placement whose notes say "Continues the previous overlay"
  are ONE spec spanning those rows, for example a checklist adding an item per beat; the builder gets
  each beat's start time.
- Before generation, /storyboard-build (`overlay_placeholders.py`) attaches a `kind: "placeholder"` asset (the silhouette with a dashed
  overlay zone, `assets/_placeholders/overlay-{right|left|lower-third}.jpg`). Registering the render replaces it.
- Verify the first one on each project: a corner pixel of an RGBA frame from `.graphic.mov` has alpha 0.

## TALKING HEAD / + LOWER THIRD / CUTAWAY → still (no generation)
Copy the `reuse_of` row's still, or a labelled placeholder card if none yet.

## SCREENCAST → placeholder
A card naming the URL/screen to capture; the human records it.

## After generating
- Name outputs `NNN_slug.ext` (three-digit row number) so `assets/` is easy to share with the editor.
- Write the asset into the row's `assets[]`, set `status` to `Generated`, and re-render the board xlsx
  (`/storyboard-build`, or `sb_to_xlsx.py storyboard.json <out>.xlsx`) so the new thumbnail shows.
- `scripts/generate_row.py` holds plan [--samples] / signoff / assume / add_feedback / feedback / resolve /
  download / silence / register / register_clip helpers. Every write to storyboard.json is atomic and
  locked; never hold a loaded board across a long render and save it afterwards.
- `name_for()` adds the `NNN_` row prefix — a row's `slug` never carries it.

---
Timing floors, stagger and exit/entrance guidance adapted from `motion-designer` in
ncklrs/startup-os-skills (MIT per its README), restated in seconds for a HyperFrames/GSAP timeline.
Its audio model (always-on layers, pitched emphasis sounds, 2-3 SFX per action) and its Remotion
specifics were deliberately NOT adopted — they contradict "Sound effects on graphics" above.
