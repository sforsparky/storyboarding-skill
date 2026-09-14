# chart-panel

A white TradingView-style candlestick panel: header (live/tick dot, ticker, timeframe pill,
last-close readout) over a deterministic BTC weekly candle chart that builds in left to right.
Lifted from `002_btc-weekly-chart-red-green.html` / `006` / `007` in the Futures Mastery VSL,
where this exact panel + chart pairing had to stay byte-identical across three rows so a later
row's color transform lands on the chart the viewer actually saw.

## Files

- `index.html` — the composition. `data-composition-id="chart-panel"`, 6s.
- `chart-panel.css` — the panel/header chrome (copied verbatim from `shared/chart-panel.css`).
- `btc-chart.js` — `FM_CHART.build(svg, opts)`: seeded, deterministic OHLC series + SVG
  candle/wick/gridline/axis-label renderer (copied verbatim from `shared/btc-chart.js`).
- `base.css` — brand tokens (`--disp`/`--label` fonts, colors) and the `.stage`/`.world`
  3D-parallax scaffold the panel sits in (copied from `shared/base.css`).

## Parameters (edit in `index.html`'s `<script>`)

- `FM_CHART.build(svg, { w, h, n, seed, padL, padR, padT, padB, years })` — `n` candle count,
  `seed` for the RNG (same seed = same series, so a chart that must reappear identically
  across rows always calls `build` with the same seed), `years` axis tick labels.
- `BUILD` / `BUILD_AT` — how long the candle build-in takes and when it starts.
- `#panel{ top / bottom }` — panel height; a title-carrying row needs more top headroom than
  a title-less one (see the trap below).

## Traps this avoids (full writeups in `hyperframes-core/TRAPS.md`)

- **Flex child clips instead of shrinking** (`chart-panel.css`'s `#plot{ min-height:0 }`): a
  flex item defaults to `min-height:auto` (= its content's height), so without this the plot
  area refuses to shrink below the SVG's intrinsic height and `#panel{ overflow:hidden }`
  crops the chart's bottom band. If you ever copy this chrome without `min-height:0`, a
  shorter panel will silently clip.
- **Stagger `each` must be derived from the real array length, not hand-picked for the
  candle count.** `candles` holds a wick *and* a body per bar (2n elements), so `each` is
  `BUILD / candles.length` — never a constant tuned by eye. Verify by computing
  `BUILD_AT + BUILD + <tween duration>` and confirming nothing else starts before that time.
- Wicks are `<line>` elements with a degenerate bounding box — the build-in animates
  `autoAlpha` only, never `scale`, on the candle array (a fill-box scale on a `<line>` is
  unreliable).
