# glass-cards

Three frosted-glass feature cards, each with an icon tile (Material Symbols), a headline, body
copy, and a small checkmark chip. Lifted from the `.frost` / `.chip` / `svg.ico` patterns in
`shared/base.css`, used throughout the Futures Mastery VSL for feature call-outs and benefit
lists.

## Files

- `index.html` — the composition. `data-composition-id="glass-cards"`, 5s.
- `base.css` — brand tokens, `.frost`/`.glass`/`.chip`/`svg.ico` primitives, `.stage`/`.world`
  3D scaffold (copied verbatim from `shared/base.css`).

## Parameters (edit in `index.html`)

- Card count/content: duplicate a `.card.frost` block; the stagger in the script keys off the
  `.card` class so no JS change is needed for 1-4 cards (beyond adjusting `#cards` layout for
  card count).
- Icon: swap the Material Symbols glyph name inside `<span class="material-symbols-outlined">`
  (any name from the [Material Symbols set](https://fonts.google.com/icons)), or swap the whole
  `.icon-wrap` contents for an inline `svg.ico` (stroke icon) instead of a filled glyph.
- Chip label/checkmark: `.chip` is a generic pill — swap its `<svg class="ico">` path or drop
  the icon for text-only.

## Traps this avoids

- **`.frost`, not `.glass`, inside anything that might sit in a `preserve-3d` stage.**
  `base.css` defines two visually similar treatments on purpose: `.glass` uses
  `backdrop-filter` (flat scenes only), `.frost` uses a plain gradient/border/shadow so it
  is safe inside `transform-style:preserve-3d` and survives the headless render capture path
  (`backdrop-filter` and `mix-blend-mode` do not). This template uses `.frost` throughout;
  if you later nest these cards inside a `.world`/3D stage, do not swap in `.glass`.
- Card entrance is an explicit `fromTo` with `immediateRender:false` and a derived stagger
  (not a plain `to`), so a cold seek to any mid-stagger frame matches what linear playback
  produces at that time (see Trap #6 in `hyperframes-core/TRAPS.md`).
- The Material Symbols webfont is loaded from the allowed `fonts.googleapis.com` /
  `fonts.gstatic.com` hosts; if that request fails (offline render), the `<span>` glyph name
  renders as literal fallback text instead of disappearing, so the frame is never blank.
