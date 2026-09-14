/* Futures Mastery — deterministic BTC weekly candle series.
   ONE source of truth so rows 002 / 006 / 007 render pixel-identical candle geometry;
   the r007 red->green transform only lands if the frame is literally the same chart. */
(function (global) {
  var UP = '#26A69A', DOWN = '#EF5350';

  // Seeded LCG — no Math.random, renders must be frame-deterministic.
  function rng(seed) {
    var s = seed >>> 0;
    return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }

  function gauss(r){ var u = 1 - r(), v = r(); return Math.sqrt(-2*Math.log(u)) * Math.cos(2*Math.PI*v); }

  /* Macro shape anchored to a real BTC arc: 2021 run-up, blow-off top, 2022 bear,
     2023 base, 2024-25 new highs. Smoothstep-interpolated in log price. */
  var ANCHORS = [[0,10500],[0.10,48000],[0.20,62000],[0.30,40000],[0.42,20000],
                 [0.52,16500],[0.64,27000],[0.74,31000],[0.86,62000],[1,98000]];
  function macro(t) {
    for (var i = 1; i < ANCHORS.length; i++) {
      if (t <= ANCHORS[i][0]) {
        var a = ANCHORS[i-1], b = ANCHORS[i], u = (t - a[0]) / (b[0] - a[0]);
        u = u * u * (3 - 2 * u);
        return Math.exp(Math.log(a[1]) + (Math.log(b[1]) - Math.log(a[1])) * u);
      }
    }
    return ANCHORS[ANCHORS.length-1][1];
  }

  /* Weekly OHLC. An AR(1) residual around the macro curve keeps the walk BTC-like
     while landing the close/open split at ~52% green — "about half and half", which is
     the entire premise of the hook. seed 7771 is the checked-in split; do not change it
     without re-checking the ratio. */
  function series(n, seed) {
    var r = rng(seed), w = 0, closes = [];
    for (var i = 0; i < n; i++) {
      w = 0.6 * w + 0.09 * gauss(r);
      closes.push(macro(i / (n - 1)) * Math.exp(w));
    }
    var out = [];
    for (var j = 0; j < n; j++) {
      var open = j === 0 ? closes[0] * 0.985 : closes[j-1], close = closes[j];
      var span = Math.abs(close - open);
      var hi = Math.max(open, close) + span * (0.3 + r() * 0.85) + open * 0.005;
      var lo = Math.min(open, close) - span * (0.3 + r() * 0.85) - open * 0.005;
      out.push({ o: open, c: close, h: hi, l: lo, up: close >= open });
    }
    return out;
  }

  /* Render into an <svg> using a plain viewBox of w x h.
     Returns { bars, wicks, data, x, y, closePts } — bars[i] is the body <rect>,
     already transform-boxed so scaleY/rotateX animate about its own centre. */
  function build(svg, opts) {
    opts = opts || {};
    var w = opts.w || 1560, h = opts.h || 620,
        n = opts.n || 232, seed = opts.seed || 7771,
        padL = opts.padL || 0, padR = opts.padR || 96,
        padT = opts.padT || 28, padB = opts.padB || 54;

    var d = series(n, seed);
    var lo = Infinity, hi = -Infinity;
    d.forEach(function (k) { if (k.l < lo) lo = k.l; if (k.h > hi) hi = k.h; });
    var pad = (hi - lo) * 0.06; lo -= pad; hi += pad;

    var plotW = w - padL - padR, plotH = h - padT - padB;
    var step = plotW / n, bodyW = Math.max(3, step * 0.62);
    var x = function (i) { return padL + step * (i + 0.5); };
    var y = function (v) { return padT + plotH * (1 - (v - lo) / (hi - lo)); };

    var gWick = mk('g'), gBody = mk('g'), frag = [];
    var bars = [], wicks = [], closePts = [];

    d.forEach(function (k, i) {
      var col = k.up ? UP : DOWN, cx = x(i);
      var wk = mk('line');
      wk.setAttribute('x1', cx.toFixed(2)); wk.setAttribute('x2', cx.toFixed(2));
      wk.setAttribute('y1', y(k.h).toFixed(2)); wk.setAttribute('y2', y(k.l).toFixed(2));
      wk.setAttribute('stroke', col); wk.setAttribute('stroke-width', '1.6');
      wk.setAttribute('class', 'wk ' + (k.up ? 'wk-up' : 'wk-dn'));
      gWick.appendChild(wk); wicks.push(wk);

      var top = Math.min(y(k.o), y(k.c));
      var bh = Math.max(2, Math.abs(y(k.o) - y(k.c)));
      var rc = mk('rect');
      rc.setAttribute('x', (cx - bodyW / 2).toFixed(2)); rc.setAttribute('y', top.toFixed(2));
      rc.setAttribute('width', bodyW.toFixed(2)); rc.setAttribute('height', bh.toFixed(2));
      rc.setAttribute('rx', '1'); rc.setAttribute('fill', col);
      rc.setAttribute('class', 'cnd ' + (k.up ? 'cnd-up' : 'cnd-dn'));
      rc.style.transformBox = 'fill-box';
      rc.style.transformOrigin = 'center center';
      gBody.appendChild(rc); bars.push(rc);
      closePts.push([cx, y(k.c)]);
    });

    // price gridlines + right-hand axis labels (subtle, uncluttered)
    var gGrid = mk('g'), gAxis = mk('g');
    for (var i = 0; i <= 4; i++) {
      var v = lo + (hi - lo) * (i / 4), gy = y(v);
      var ln = mk('line');
      ln.setAttribute('x1', padL); ln.setAttribute('x2', padL + plotW);
      ln.setAttribute('y1', gy.toFixed(1)); ln.setAttribute('y2', gy.toFixed(1));
      ln.setAttribute('stroke', 'rgba(20,48,42,.09)'); ln.setAttribute('stroke-width', '1');
      gGrid.appendChild(ln);
      var tx = mk('text');
      tx.setAttribute('x', padL + plotW + 14); tx.setAttribute('y', (gy + 6).toFixed(1));
      tx.setAttribute('fill', '#7d908c'); tx.setAttribute('font-size', '20');
      tx.setAttribute('font-family', 'Poppins, system-ui, sans-serif');
      tx.setAttribute('font-weight', '500');
      tx.textContent = '$' + Math.round(v / 1000) + 'k';
      gAxis.appendChild(tx);
    }
    // year ticks along the bottom
    var years = opts.years || ['2021', '2022', '2023', '2024', '2025'];
    years.forEach(function (yr, k) {
      var px = padL + plotW * ((k + 0.5) / years.length);
      var tx = mk('text');
      tx.setAttribute('x', px.toFixed(1)); tx.setAttribute('y', h - 16);
      tx.setAttribute('fill', '#7d908c'); tx.setAttribute('font-size', '20');
      tx.setAttribute('text-anchor', 'middle');
      tx.setAttribute('font-family', 'Poppins, system-ui, sans-serif');
      tx.setAttribute('font-weight', '500');
      tx.textContent = yr;
      gAxis.appendChild(tx);
    });

    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    svg.appendChild(gGrid); svg.appendChild(gAxis);
    svg.appendChild(gWick); svg.appendChild(gBody);

    var greens = d.filter(function (k) { return k.up; }).length;
    return { bars: bars, wicks: wicks, data: d, x: x, y: y, w: w, h: h,
             closePts: closePts, greens: greens, reds: n - greens, step: step };
  }

  function mk(tag) { return document.createElementNS('http://www.w3.org/2000/svg', tag); }

  global.FM_CHART = { build: build, UP: UP, DOWN: DOWN };
})(window);
