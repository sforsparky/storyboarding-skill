# orthogonal-links

A hub-and-spoke diagram connected by bus-routed, 90°-only connectors with rounded corners:
two "core" nodes each send a stub up/down to a shared horizontal bus, which then runs outward
and turns onto each outer node's edge. Every connector draws itself on, one at a time.
Generalized from `023_portable-to-any-exchange.html`, which used this exact routing to show a
skill/feature reaching six exchanges from two already-covered ones.

## Files

- `index.html` — the composition. `data-composition-id="orthogonal-links"`, 7s, 2 core nodes
  + 6 outer nodes (generic "Core 1/2" and "Node A-F" labels).
- `base.css` — brand tokens and the `.stage`/`.world` 3D-parallax scaffold (copied verbatim
  from `shared/base.css`).

## Parameters

- Node labels/positions: edit the `.node`/`.node.core` `<div>`s in `#wall` (`left`/`top` is
  each node's *center*, matched by the `margin` offsets in CSS) and the glyph/name inside.
- Routing geometry: the `<path>` `d` strings in `#links svg` are hand-plotted to the node
  positions above. If you move a node, recompute its path's endpoint to match the node's new
  edge coordinate (see the coordinate table in the composition's own comment) — the paths do
  not follow the nodes automatically.
- Reveal order/timing: the `tgt.forEach(...)` loop controls per-node stagger (`2.25 + i*0.28`)
  and the matching connector draw-on (`1.90 + i*0.28`).
- Node/core count: add more `<path>`s + `.node` divs and extend the `tgt` array; keep the
  "stub → shared bus → turn → outer edge" shape for any new branch so segments never cross
  under a translucent node.

## Traps this avoids (full writeup in `hyperframes-core/TRAPS.md`, #3)

- **Round line caps painting a dot on an undrawn path.** Every connector is prepped with
  `strokeDasharray: L + ' ' + (L+20)`, `strokeDashoffset: L+10` — the hidden dash sits
  entirely *past* the path's visible end, so `stroke-linecap:round` never renders a stray dot
  at the endpoint before the reveal starts. A naive `dasharray:L / offset:L` looks identical
  until you check frame 0 closely: it leaves exactly that dot.
- Every segment starts and ends exactly on a node's rendered edge (not its center) — because
  nodes here are translucent (`.node`'s gradient background lets what's behind it show
  through), a centre-to-centre line would visibly cross underneath the node instead of
  appearing to terminate at it.
