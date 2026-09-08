---
name: brand
description: >
  Build or refine a brand's design system from reference assets the user drops in — no hand-editing
  JSON. Read logos, frames, screenshots, style tiles, and existing graphics from brands/<brand>/refs/,
  extract an accurate color palette programmatically, and synthesize brands/<brand>/brand.json plus a
  human-readable brand.md. Use when starting a new brand or updating one from new references.
---

# /brand — reference assets → design system

The user develops a brand by **pasting assets**, not writing JSON. They drop files into
`brands/<brand>/refs/`; this skill turns them into `brand.json` (consumed by /storyboard and
/generate) and `brand.md` (a readable summary for humans).

Good refs: logo files (svg/png), brand frames or thumbnails, a website/deck screenshot, a style
tile or one-pager, existing custom graphics, a palette swatch. More is better; 3–8 is plenty.

## Steps
1. **Extract colors (accurate math, not eyeballing):**
   `scripts/extract_palette.py brands/<brand>/refs --swatch /tmp/<brand>-swatch.png`
   Returns a deduped palette: hex, RGB, coverage %, saturation, luminance, and a role guess
   (paper / ink / accent / brand / neutral). Pull hexes from here, not from a screenshot.
2. **Read the images yourself** (Read each ref). Judge what the palette math can't:
   - which extracted colors are the **brand** vs **incidental scenery** (e.g. a wood-panel set or
     a stock photo background is not a brand color — drop it).
   - the **logo** (mark vs wordmark), and copy the files into `brands/<brand>/logos/`.
   - the **type feel** (geometric vs humanist sans, weight, tracking) → a real font stack.
   - recurring **motifs** (a mascot, a chart style, a lower-third shape, a texture).
   - the **broll_style** and **graphic_style** sentences that make later prompts feel native.
3. **Write `brand.json`** using the `_template` shape: `colors` (primary, primary_bright, ink,
   paper, up, down, muted — mapped from the extracted roles), `type`, `logos`, `products`,
   `presenters`, `tone`, `motifs`, `broll_style`, `graphic_style`. Record the source hexes so a
   later /brand run can refine rather than restart.
4. **Write `brand.md`** — the same system in prose plus the swatch, so a human can eyeball it.
5. **Confirm with the user**, showing the swatch and the 2–3 judgment calls you made (which colors
   you treated as brand vs scenery, the font guess). They correct in one message; you don't ask
   them to touch JSON.

## Notes
- `extract_palette.py` also scrapes `#RRGGBB` fills out of any SVG in refs/ (logo colors are strong
  signals). It downsamples images, so it's fast and safe on large frames.
- refs/ is committed so the brand is reproducible; large raw frames can be .gitignored per project.
- To refine an existing brand, add new refs and re-run — keep the user's confirmed overrides.
