# Craft standards (every graphic, before it is shown)

**Contents**
- Layout — overlap, visible sets, soft edges, centring, derived positions, raster scale, supplied art, chrome, case, icons
- Typography — hero size, one bold, hand breaks and widows, line-box air
- Timing — read times, holds, easing, stagger, exits, focus point
- Mechanism — one source of truth, simplify toward the sentence, semantic colour
- Verify before showing — `check_row.py`, `check_briefs.py`, flicker, render contact sheet, shared-clip posters
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
  pan between mirrored layouts, with the editor's cut landing mid-move (see "Clip across rows" in `shared-clips-and-series.md`).
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

---
Timing floors, stagger and exit/entrance guidance adapted from `motion-designer` in
ncklrs/startup-os-skills (MIT per its README), restated in seconds for a HyperFrames/GSAP timeline.
Its audio model (always-on layers, pitched emphasis sounds, 2-3 SFX per action) and its Remotion
specifics were deliberately NOT adopted — they contradict "Sound effects on graphics" above.
