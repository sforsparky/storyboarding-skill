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
1. Print the plan: `generate_row.py plan storyboard.json`. It buckets pending rows into free/local
   (route `hyperframes` / `still` / `placeholder`, honoring any per-row `motion_engine: hyperframes`
   override) versus paid Higgsfield (route `video`), and skips rows already `Generated`/`Approved`.
   - The plan ends with an "Open feedback" section: rows whose feedback is newer than what was
     last generated for them (see "Editing a generated row" below) — check these before generating.
2. Generate the free/local rows now — this is the "render all the infographics" pass, and it spends
   nothing. Apply the custom-graphic grouping rules (consecutive graphic beats → one graphic).
3. STOP before the paid rows. Show the user the Higgsfield B-roll list and the estimated credits,
   and ask before generating them (or tell them to run `/storyboard-generate b-roll`). Only proceed
   on an explicit yes, and preflight exact cost with `get_cost:true` at that point.

## Video is silent by default
Every generated video is delivered with **no audio** — the video editor sets all sound and music.
- Prefer silent models (`seedance_2_5`). Do not pick audio/lip-sync models (e.g. `kling3_0`'s audio
  mode) unless the user explicitly asks for sound on that row.
- Never add music/voice/SFX terms to a prompt. Briefs already say "No audio (editor handles sound)".
- After download, strip any audio track defensively: `generate_row.py silence <file>` (runs
  `ffmpeg -i in -c:v copy -an out`). Do this before registering the asset.

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
3. `register`/`register_clip` overwrite the row's `assets[]` (stamping `registered_at`), so the
   new asset replaces the old and status returns to `Generated` — this also clears the row from
   `plan`'s "Open feedback" section, since the regenerate is now newer than the feedback that
   prompted it. An explicit row selector regenerates even a `Generated`/`Approved` row (unlike
   the no-arg whole-board default, which skips them).
Re-render the board xlsx afterward so the new thumbnail shows.

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
  frame — the shelf-shadow bug, caught from the DOM even when the pixel step is faint) per frame,
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
     render once named by the FIRST row (`<AAA>_slug.mp4`); register with the shared-clip helper
     so each row carries its in/out segment:
     `generate_row.py register_clip <sb.json> <A> <B> <file_rel> <poster_rel> custom_graphic hyperframes <total_dur> [t0 t1 …]`
     (pass the beat boundaries as the trailing cut points when you know them). The one graphic is shared
     once and each row carries its in/out — same as a Higgsfield `clip`.
     **Each row also gets its OWN poster**, cut from inside its segment — see "Per-beat posters" below.
     You authored the timeline, so you know when each beat settles: pass `--poster-times` rather
     than letting the fraction guess.
   - **Standalone rows →** render each individually per the steps below.
1. Pick or author a composition under `templates/<name>/index.html`. Start from a template (e.g.
   `portfolio-bar-drop`) or `npx hyperframes catalog --query "..."` then `npx hyperframes add`.
   Follow `/hyperframes-core` + `/hyperframes-animation`.
2. Feed the row `brief` and brand tokens (colors, type, motif) into the composition.
3. **Honor the contract or it renders blank:** register the timeline as
   `window.__timelines["<data-composition-id>"] = tl` (create it `paused:true`); animate
   **transforms** (x/y/scale/opacity), never layout props. `npx hyperframes lint` until clean.
4. `npx hyperframes render --quality high --output <NNN_slug>.mp4`; poster:
   `ffmpeg -y -ss <hold-time> -i <NNN_slug>.mp4 -frames:v 1 <NNN_slug>.png`. Graphics have no
   audio track already, so no stripping needed. Normally use `scripts/rebuild.py` for this instead
   of running render + ffmpeg by hand — it also copies into the project's `assets/`, re-cuts every
   referencing row's poster from the board, and refreshes the xlsx in one step.

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

## TALKING HEAD / + LOWER THIRD / CUTAWAY → still (no generation)
Copy the `reuse_of` row's still, or a labelled placeholder card if none yet.

## SCREENCAST → placeholder
A card naming the URL/screen to capture; the human records it.

## After generating
- Name outputs `NNN_slug.ext` (three-digit row number) so `assets/` is easy to share with the editor.
- Write the asset into the row's `assets[]`, set `status` to `Generated`, and re-render the board xlsx
  (`/storyboard-build`, or `sb_to_xlsx.py storyboard.json <out>.xlsx`) so the new thumbnail shows.
- `scripts/generate_row.py` holds plan / add_feedback / feedback / download / silence / register / register_clip helpers.
