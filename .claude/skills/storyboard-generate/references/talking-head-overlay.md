# TALKING HEAD + OVERLAY rows

Transparent overlay only; the presenter appears on the board as a preview.
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
