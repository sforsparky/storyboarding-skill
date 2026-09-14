# shelf-spotlight

N items standing on a shelf/ledge with a soft elliptical floor shadow; one at a time lifts into
a spotlight at left with a detail panel at right, then returns to its slot. Generalized from the
family-shelf + lift-to-spotlight mechanic in `030_bonus-stack-sequence.html`, which sequenced
eleven bonus-guide cover renders across six beats of a 34s continuous graphic.

## Files

- `index.html` — the composition. `data-composition-id="shelf-spotlight"`, 9s, 5 demo items
  (one lift-and-return cycle; extend the timeline to cycle through more).
- `base.css` — brand tokens and the `.stage`/`.world` 3D-parallax scaffold (copied verbatim
  from `shared/base.css`).

## Parameters

Edit the `ITEMS` array at the top of the `<script>`:

```js
{ label:'Quick\nStart', aspect:0.75, color:'#2AB78E', title:'Quick Start Guide', desc:'…' }
```

- `aspect` — width/height of the item's natural box (height is fixed at `H = 600`). Get this
  from the real asset's pixel dimensions, not a guess (Trap #7 below).
- `src` (optional) — a real image path. Omit it to get a colored placeholder cover (using
  `label` and `color`) instead — this template ships with **no bundled images**, so every demo
  item is a placeholder by default; set `src` once you have real art.
- `title` / `desc` — the spotlight-panel copy shown for `HERO_IDX`.
- `HERO_IDX` and the two timing blocks (`2.0s` lift, `6.5s` return) — which item is featured
  and when; duplicate the "lift / return" block per additional item to cycle through more than
  one, same as `030`'s six beats.

## Traps this avoids (full writeups in `hyperframes-core/TRAPS.md`)

- **#7 — raster art only ever scales DOWN.** Every item's box is authored at its largest used
  size (the 1x spotlight slot, `H=600`); the shelf slot is a smaller `scale`, never the other
  way around. If you add real images, size the source art to at least 600px tall or the
  spotlight close-up will look soft.
- **#8 — floor shadow is an ellipse, not a bar.** `.ledge i` is a radial gradient that tapers
  to transparent well inside its own box; a rectangular shadow crops with a hard edge at the
  shelf's ends, worst on the widest shelf.
- **#6 — every leg is an explicit `fromTo` with `immediateRender:false`.** The `leg()` helper
  enforces this for every item move (assemble / lift / dim / return), so a cold seek to any
  timeline frame reproduces exactly what linear playback would show — never a value read from
  whatever the element happened to hold from an earlier, unrelated tween.
- The spotlight (`#spot`) is a sibling of `.world`, not nested inside it, so it always paints
  under everything on the 3D stage regardless of the stage's own depth motion.
