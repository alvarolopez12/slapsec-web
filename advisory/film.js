/*
  Convergencia, the hero film.
  Faint threads cross the frame above the headline: the options that are still open. Over one
  long take they drift and, one by one, either fall away or lie down onto a neighbour, until a
  single ordinary line remains and slowly takes the accent. Nothing marks the moment of choice;
  the options simply stop being there. The line then dissolves while a freshly seeded set opens
  out of it, so no two takes are the same.

  Canvas 2D, no libraries. A still ground layer is painted once per size; the film layer is
  cleared and redrawn each frame from preallocated buffers. Paused when the tab is hidden, the
  hero is off screen or the visitor presses pause; one composed still under reduced motion.
*/
(function () {
  "use strict";

  var hero = document.querySelector(".hero");
  if (!hero || !window.CanvasRenderingContext2D) return;
  var base = hero.querySelector(".ground"), canvas = hero.querySelector(".film");
  var h1 = hero.querySelector("h1"), sub = hero.querySelector(".standfirst");
  var words = hero.querySelector(".wrap"), top = document.querySelector(".top");
  var ctl = hero.querySelector(".film-ctl");
  var bctx = base.getContext("2d", { alpha: false }), ctx = canvas.getContext("2d");
  if (!bctx || !ctx) return;

  var reduceMQ = window.matchMedia("(prefers-reduced-motion: reduce)");
  var forcedMQ = window.matchMedia("(forced-colors: active)");
  var reduced = reduceMQ.matches, userPaused = false;

  var TAU = Math.PI * 2;
  var MAXN = 40, MAXS = 96, STRIDE = MAXS + 1;
  var FALL = 1, MERGE = 2;

  // Timeline, as fractions of one take.
  var CONVERGE_END = 0.72;                      // the spread finishes narrowing
  var FATE_START = 0.07, FATE_SPAN = 0.40, FATE_LAST = 0.70;
  var ACCENT_A = 0.40, ACCENT_B = 0.68;         // the survivor takes the accent
  var DISSOLVE_A = 0.88;                        // and, after holding alone for a while, starts to go
  var HANDOFF = 0.885;                          // while the next take opens out of it
  // A first visit gets a shorter take that opens already populated, so the line is legible
  // within the time a visitor actually gives a hero. Later takes keep the full arc.
  var FIRST_DUR = 26, FIRST_U = 0.14, INTRO_S = 1.5;
  var GLIDE_S = 0.45;                           // how fast the field follows a change of layout

  // Still frame for reduced motion: the field half gone, the line that will remain fully lit.
  var STILL_SEED = 8, STILL_U = 0.5, STILL_K = 1;

  /* ---------- small maths ---------- */
  function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function sstep(a, b, v) { var t = clamp01((v - a) / (b - a)); return t * t * (3 - 2 * t); }
  function ease(v) { v = clamp01(v); return v * v * v * (v * (v * 6 - 15) + 10); }
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  var master = mulberry32((Math.random() * 4294967296) >>> 0 ^ (Date.now() & 0xffffffff));
  function nextSeed() { return (master() * 4294967296) >>> 0; }

  /* ---------- palette, read from the page's tokens ---------- */
  var probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  probe.canvas.width = probe.canvas.height = 1;
  function toRGBA(str, fallback) {
    probe.clearRect(0, 0, 1, 1);
    probe.fillStyle = fallback; probe.fillStyle = str;
    probe.fillRect(0, 0, 1, 1);
    var d = probe.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  }
  function readColor(name, fallback) {
    return toRGBA(getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback, fallback);
  }
  function rgba(c, a) { return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")"; }
  var BG, LINE, ACC, LINE_A = 0.24;
  function readPalette() {
    BG = readColor("--film-bg", "#050505");
    LINE = readColor("--film-line", "rgba(226,226,222,.24)");
    ACC = readColor("--film-accent", "#67e18f");
    LINE_A = LINE[3] > 0 ? LINE[3] : 0.24;
  }

  /* ---------- geometry ---------- */
  var W = 0, H = 0, CW = 1, CH = 1, dpr = 1, gd = 1, N = 24, S = 60, hair = 1, mobile = false, Lref = 1;
  // Backing pixels: high-density screens are brought down to about 17 MB for the film and 8 MB for
  // the still ground. The film never drops below one pixel per CSS pixel, so its hairlines stay crisp.
  var FILM_PX = 4.2e6, GROUND_PX = 2.1e6;
  // The band and the amplitudes have targets set by layout; the film glides toward them, so a
  // language switch or a late web font never makes the field jump.
  var bandMid = 0, bandHalf = 0, Ha = 0, Hi = 0, tMid = 0, tHalf = 0, tHa = 0, tHi = 0, settled = false;
  var xs = new Float32Array(STRIDE), NX = new Float32Array(STRIDE), DX = new Float32Array(STRIDE);
  var F = new Float32Array(STRIDE), YS = new Float32Array(STRIDE);
  var gradLine = null, SURV_STEPS = 32, gradSurv = new Array(SURV_STEPS + 1);
  // The shade is all soft gradients, so it is kept at a quarter of the film's resolution.
  var VS = 4, veil = document.createElement("canvas"), vctx = veil.getContext("2d"), veilSrc = veil, veilGen = 0;
  var veilRects = new Float32Array(8), veilCount = 0;
  var noiseTile = null;

  function makeNoise() {
    var c = document.createElement("canvas"); c.width = c.height = 128;
    var x = c.getContext("2d"), img = x.createImageData(128, 128), d = img.data, r = mulberry32(7);
    for (var i = 0; i < d.length; i += 4) { var v = r() < 0.5 ? 0 : 255; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
    x.putImageData(img, 0, 0);
    return c;
  }

  // Measured in the hero's own layout, so a transform shared by the film and the words (the hero
  // drifting as the page scrolls) never moves the shade off the type.
  // Layout geometry, not painted geometry: an entrance animation that is still lifting the
  // headline into place does not move the shade either.
  function rectOf(el, pad) {
    var x = 0, y = 0, n = el;
    while (n && n !== hero) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
    return { x: x - pad, y: y - pad, w: el.offsetWidth + pad * 2, h: el.offsetHeight + pad * 2 };
  }

  // Where the header's ink ends, and where its shade can stop, in CSS px from the hero's top.
  // Measured only while the header sits in its place at the top of the page; once it rides
  // along as a compact bar, the last measure in place is kept.
  var lastHeader = null;
  function headerExtent() {
    if (!top) return { ink: H * 0.08, shade: H * 0.12 };
    if (lastHeader && (top.classList.contains("stuck") || window.scrollY > 0)) return lastHeader;
    var hTop = hero.getBoundingClientRect().top;
    var bottom = top.getBoundingClientRect().bottom - hTop, ink = 0;
    top.querySelectorAll(".lockup, .right").forEach(function (el) {
      ink = Math.max(ink, el.getBoundingClientRect().bottom - hTop);
    });
    if (!ink) ink = bottom * 0.7;
    lastHeader = { ink: ink, shade: Math.max(ink + 28, bottom + H * 0.03) };
    return lastHeader;
  }

  function layout() {
    var r = hero.getBoundingClientRect();
    W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
    dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1, Math.sqrt(FILM_PX / (W * H))));
    gd = Math.min(1, Math.sqrt(GROUND_PX / (W * H)));   // the ground is a soft gradient and grain: it needs no more
    var cw = Math.round(W * dpr), ch = Math.round(H * dpr);
    if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
    var gw = Math.max(1, Math.round(W * gd)), gh = Math.max(1, Math.round(H * gd));
    if (base.width !== gw || base.height !== gh) { base.width = gw; base.height = gh; }
    veil.width = Math.ceil(cw / VS); veil.height = Math.ceil(ch / VS);
    CW = cw; CH = ch;

    mobile = W < 720;
    // Never thinner than a device pixel, and a full CSS pixel on ordinary office screens.
    hair = dpr >= 2 ? 0.75 : dpr > 1.2 ? 0.85 : 1;
    N = Math.max(16, Math.min(28, Math.round(14 + W / 80)));
    S = Math.max(32, Math.min(90, Math.round(W / 18)));
    Lref = Math.max(W, 820);

    // The field lives between the header and the headline, measured from the page itself. When
    // that room is short (a laptop with a low screen) the current calms down with it, so the
    // threads never sway into the type.
    var lo = Math.max(headerExtent().shade, H * 0.1);
    var hi = Math.max(lo + 24, rectOf(h1, 0).y - H * 0.07);
    var calm = 0.45 + 0.55 * clamp01((hi - lo) / (H * 0.3));
    tHa = Math.min(H, W * 0.9) * 0.82 * calm;
    tHi = (mobile ? H * 0.8 : Math.min(H, W * 0.9) * 0.82) * calm;
    tMid = (lo + hi) / 2;
    tHalf = (hi - lo) / 2 * 0.92;
    if (!settled || !running) { bandMid = tMid; bandHalf = tHalf; Ha = tHa; Hi = tHi; settled = true; }
    for (var s = 0; s <= S; s++) { xs[s] = -0.06 * W + (1.12 * W) * s / S; NX[s] = xs[s] / Lref; DX[s] = xs[s] / W - 0.5; }

    gradLine = edgeGradient(LINE);
    var mix = [0, 0, 0];
    for (var q = 0; q <= SURV_STEPS; q++) {
      var k = q / SURV_STEPS;
      mix[0] = Math.round(LINE[0] + (ACC[0] - LINE[0]) * k);
      mix[1] = Math.round(LINE[1] + (ACC[1] - LINE[1]) * k);
      mix[2] = Math.round(LINE[2] + (ACC[2] - LINE[2]) * k);
      gradSurv[q] = edgeGradient(mix);
    }
    buildBase(); buildVeil();
  }

  function edgeGradient(c) {
    var g = ctx.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0.00, rgba(c, 0));
    g.addColorStop(0.05, rgba(c, 0.25));
    g.addColorStop(0.16, rgba(c, 1));
    g.addColorStop(0.84, rgba(c, 1));
    g.addColorStop(0.95, rgba(c, 0.25));
    g.addColorStop(1.00, rgba(c, 0));
    return g;
  }

  // The ground: ink with a barely perceptible lift where the threads gather, dithered.
  function buildBase() {
    bctx.setTransform(1, 0, 0, 1, 0, 0);
    bctx.globalAlpha = 1;
    bctx.fillStyle = rgba(BG, 1); bctx.fillRect(0, 0, base.width, base.height);
    var cx = W * (mobile ? 0.5 : 0.62) * gd, cy = tMid * gd;
    var rad = Math.max(W, H) * 0.8 * gd;
    var g = bctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
    g.addColorStop(0, rgba(LINE, 0.04)); g.addColorStop(0.55, rgba(LINE, 0.014)); g.addColorStop(1, rgba(LINE, 0));
    bctx.fillStyle = g; bctx.fillRect(0, 0, base.width, base.height);
    if (!noiseTile) noiseTile = makeNoise();
    bctx.globalAlpha = 0.012;
    bctx.fillStyle = bctx.createPattern(noiseTile, "repeat");
    bctx.fillRect(0, 0, base.width, base.height);
    bctx.globalAlpha = 1;
  }

  // Rectangles are kept in full film pixels; the veil canvas is drawn from at 1 / VS.
  function addVeilRect(x, y, w, h) {
    var x0 = Math.max(0, Math.floor(x)), y0 = Math.max(0, Math.floor(y));
    var x1 = Math.min(CW, Math.ceil(x + w)), y1 = Math.min(CH, Math.ceil(y + h));
    if (x1 <= x0 || y1 <= y0 || veilCount >= 2) return;
    var o = veilCount * 4;
    veilRects[o] = x0; veilRects[o + 1] = y0; veilRects[o + 2] = x1 - x0; veilRects[o + 3] = y1 - y0;
    veilCount++;
  }

  // The shade: solid under the header's ink and fading below it, and a feathered pool under the
  // words that runs to the right edge, so nothing the film does can rise beside or behind the
  // type. It erases film in proportion to its alpha, only inside its rectangles.
  function buildVeil() {
    var hx = headerExtent(), hb = hx.shade * dpr;
    vctx.setTransform(1 / VS, 0, 0, 1 / VS, 0, 0);
    vctx.clearRect(0, 0, CW, CH);
    var g = vctx.createLinearGradient(0, 0, 0, hb);
    g.addColorStop(0, "rgba(0,0,0,1)");
    g.addColorStop(Math.min(0.95, (hx.ink + 6) / hx.shade), "rgba(0,0,0,1)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    vctx.fillStyle = g; vctx.fillRect(0, 0, CW, hb);
    veilCount = 0;
    addVeilRect(0, 0, CW, hb);

    var pad = mobile ? 16 : 30, blur = (mobile ? 40 : 80) * dpr;
    var a = rectOf(h1, pad), b = rectOf(sub, pad);
    var x0 = Math.min(a.x, b.x), y0 = Math.min(a.y, b.y);
    var x1 = W + blur, y1 = Math.max(a.y + a.h, b.y + b.h);
    var off = CW + 4000;
    vctx.save();
    // Shadows ignore the transform, so blur and offset are given in veil pixels.
    vctx.shadowColor = "rgba(0,0,0,0.9)";
    vctx.shadowBlur = blur / VS; vctx.shadowOffsetX = off / VS; vctx.shadowOffsetY = 0;
    vctx.fillStyle = "#000";
    vctx.fillRect(x0 * dpr - off, y0 * dpr, (x1 - x0) * dpr, (y1 - y0) * dpr);
    vctx.restore();
    addVeilRect(x0 * dpr - blur * 1.6, y0 * dpr - blur * 1.6, (x1 - x0) * dpr + blur * 3.2, (y1 - y0) * dpr + blur * 3.2);

    // A bitmap snapshot composites faster than a canvas on machines without GPU raster.
    var gen = ++veilGen;
    if (veilSrc !== veil && veilSrc.close) veilSrc.close();
    veilSrc = veil;
    if (window.createImageBitmap) {
      createImageBitmap(veil).then(function (bm) {
        if (gen !== veilGen) { bm.close(); return; }
        veilSrc = bm;
        if (!running) draw();
      }, function () {});
    }
  }

  /* ---------- takes: one seeded world each ---------- */
  function World() {
    var f = function () { return new Float32Array(MAXN); };
    this.on = false; this.first = false; this.t = 0; this.dur = 32; this.n = 0; this.s = 0; this.toff = 0;
    this.lane = f(); this.z = f(); this.fin = f(); this.tf = f(); this.df = f();
    this.a1 = f(); this.k1 = f(); this.w1 = f(); this.p1 = f();
    this.a2 = f(); this.k2 = f(); this.w2 = f(); this.p2 = f();
    this.wa = f(); this.ww = f(); this.wp = f();
    this.fate = new Uint8Array(MAXN); this.tgt = new Int16Array(MAXN);
    this.own = new Float32Array(MAXN * STRIDE);
    this.yc = 0; this.kHold = -1;
  }
  var worlds = [new World(), new World()], cur = 0;
  var tmpIdx = new Int16Array(MAXN);

  function seedWorld(w, seed, n, dur) {
    var r = mulberry32(seed), i, j, k;
    w.on = true; w.first = !!dur; w.t = 0; w.n = n; w.dur = dur || 30 + r() * 4; w.toff = r() * 400; w.kHold = -1;
    w.A1 = 0.05 + r() * 0.03;  w.K1 = TAU / (1.6 + r() * 0.9);  w.W1 = TAU / (44 + r() * 22); w.P1 = r() * TAU;
    w.A2 = 0.016 + r() * 0.014; w.K2 = TAU / (0.8 + r() * 0.45); w.W2 = TAU / (30 + r() * 18); w.P2 = r() * TAU;
    w.tilt = (r() * 2 - 1) * 0.045; w.bend = (r() * 2 - 1) * 0.09;
    w.rot0 = (r() * 2 - 1) * 0.009; w.rot1 = w.rot0 + (r() * 2 - 1) * 0.009;
    w.zoom = 0.03 + r() * 0.03; w.endJ = (r() * 2 - 1);

    for (i = 0; i < n; i++) {
      var z = r();
      w.lane[i] = -1 + 2 * (i + 0.2 + r() * 0.6) / n;
      // Later takes open slowly out of the line before them; the first opens already populated.
      w.z[i] = z; w.fin[i] = w.first ? r() * 0.07 : 0.01 + r() * 0.2; w.fate[i] = 0; w.tgt[i] = -1;
      var dz = 0.6 + 0.6 * z, pz = 0.7 + 0.6 * z;
      w.a1[i] = (0.012 + r() * 0.02) * dz;  w.k1[i] = TAU / (0.55 + r() * 0.8); w.w1[i] = TAU / (26 + r() * 30) * pz; w.p1[i] = r() * TAU;
      w.a2[i] = (0.005 + r() * 0.011) * dz; w.k2[i] = TAU / (0.3 + r() * 0.4);  w.w2[i] = TAU / (20 + r() * 24) * pz * (r() < 0.5 ? -1 : 1); w.p2[i] = r() * TAU;
      w.wa[i] = 0.025 + r() * 0.045; w.ww[i] = TAU / (28 + r() * 30); w.wp[i] = r() * TAU;
    }
    // The survivor: an ordinary thread from the middle third; nothing marks it yet.
    var lo = Math.floor(n * 0.33), hi = Math.ceil(n * 0.67);
    w.s = lo + Math.floor(r() * (hi - lo));
    w.z[w.s] = 0.62 + r() * 0.18; w.fin[w.s] = 0.015;

    // Everyone else gets a fate and a time; the order of fates is shuffled across the frame.
    var m = 0;
    for (i = 0; i < n; i++) if (i !== w.s) tmpIdx[m++] = i;
    for (i = m - 1; i > 0; i--) { j = Math.floor(r() * (i + 1)); k = tmpIdx[i]; tmpIdx[i] = tmpIdx[j]; tmpIdx[j] = k; }
    for (k = 0; k < m; k++) {
      i = tmpIdx[k];
      var q = (k + 0.2 + 0.6 * r()) / m;
      var tf = FATE_START + FATE_SPAN * Math.pow(q, 0.92);
      var merge = k >= m - 3 || r() < 0.3 + 0.35 * q;
      var df = merge ? 0.2 + r() * 0.08 : 0.16 + r() * 0.08;
      if (tf + df > FATE_LAST) df = Math.max(0.12, FATE_LAST - tf);
      w.tf[i] = tf; w.df[i] = df; w.fate[i] = merge ? MERGE : FALL;
      if (!w.first) w.fin[i] = Math.min(w.fin[i], Math.max(0, tf - 0.12));
    }
    // Merges join the nearest thread that will still be there when they finish.
    for (k = 0; k < m; k++) {
      i = tmpIdx[k];
      if (w.fate[i] !== MERGE) continue;
      if (k >= m - 3) { w.tgt[i] = w.s; continue; }
      var best = w.s, bd = Math.abs(w.lane[w.s] - w.lane[i]) * 1.4, done = w.tf[i] + w.df[i];
      for (j = 0; j < n; j++) {
        if (j === i || j === w.s || w.tf[j] < done) continue;
        var d = Math.abs(w.lane[j] - w.lane[i]);
        if (d < bd) { bd = d; best = j; }
      }
      w.tgt[i] = best;
    }
  }

  // Every thread's own path at the take's current time.
  function computeOwn(w) {
    var u = w.t / w.dur, n = w.n, t = w.t + w.toff, s, i;
    var cv = ease(u / CONVERGE_END);
    var open = w.first ? 1 : 0.3 + 0.7 * ease(u / 0.22);
    var spread = bandHalf * open * (1 - 0.64 * cv);
    var yc = bandMid + w.endJ * H * 0.02 * cv;
    var ind = Hi * (1 - 0.55 * cv);
    // As the options go, the current itself settles: the last line is calmer than the field was.
    var flow = Ha * (1 - 0.42 * cv), shape = Ha * (1 - 0.6 * cv);
    w.yc = yc;
    for (s = 0; s <= S; s++) {
      var nx = NX[s], dx = DX[s];
      F[s] = flow * (w.A1 * Math.sin(w.K1 * nx - w.W1 * t + w.P1) + w.A2 * Math.sin(w.K2 * nx + w.W2 * t + w.P2)) +
             shape * (w.tilt * dx * 2 + w.bend * dx * dx * 4);
    }
    for (i = 0; i < n; i++) {
      var lane = w.lane[i] + w.wa[i] * Math.sin(w.ww[i] * t + w.wp[i]), slack = 1;
      if (i === w.s) lane *= (1 - cv);
      else if (w.fate[i] === FALL) {
        var p = sstep(w.tf[i], w.tf[i] + w.df[i], u);
        lane += (lane < 0 ? -0.26 : 0.26) * p; slack = 1 + 0.8 * p;
      }
      var y0 = yc + spread * lane, a1 = w.a1[i] * ind * slack, a2 = w.a2[i] * ind * slack;
      var k1 = w.k1[i], k2 = w.k2[i], ph1 = w.p1[i] - w.w1[i] * t, ph2 = w.p2[i] + w.w2[i] * t;
      var o = i * STRIDE;
      for (s = 0; s <= S; s++) {
        var x = NX[s];
        w.own[o + s] = y0 + F[s] + a1 * Math.sin(k1 * x + ph1) + a2 * Math.sin(k2 * x + ph2);
      }
    }
  }

  function tracePath(ys) {
    ctx.beginPath();
    ctx.moveTo(xs[0], ys[0]);
    for (var s = 1; s < S; s++) {
      ctx.quadraticCurveTo(xs[s], ys[s], (xs[s] + xs[s + 1]) * 0.5, (ys[s] + ys[s + 1]) * 0.5);
    }
    ctx.lineTo(xs[S], ys[S]);
  }

  var intro = 1;   // global fade on first paint, so the page opens on a faint field, not on black
  function drawWorld(w) {
    computeOwn(w);
    var u = w.t / w.dur, n = w.n, i, s, o, a;
    var rot = w.rot0 + (w.rot1 - w.rot0) * u, sc = 1 + w.zoom * ease(u);
    var cx = W * 0.5, cy = w.yc, c = Math.cos(rot) * sc * dpr, sn = Math.sin(rot) * sc * dpr;
    var ramp = w.first ? 0.06 : 0.1;
    ctx.setTransform(c, sn, -sn, c, dpr * cx - c * cx + sn * cy, dpr * cy - sn * cx - c * cy);
    ctx.strokeStyle = gradLine;

    for (i = 0; i < n; i++) {
      if (i === w.s) continue;
      a = intro * LINE_A * (0.34 + 0.66 * w.z[i]) * sstep(w.fin[i], w.fin[i] + ramp, u);
      var p = (u - w.tf[i]) / w.df[i];
      if (w.fate[i] === FALL) a *= 1 - sstep(0, 1, p);
      else a *= 1 - sstep(0.58, 1, p);
      if (a < 0.002) continue;
      o = i * STRIDE;
      if (w.fate[i] === MERGE && p > 0) {
        // A front travels right to left: downstream of it the thread already lies on its target.
        var L = Lref * 0.32, xf = W * 1.06 + L - (W * 1.12 + 2 * L) * ease(p), to = w.tgt[i] * STRIDE;
        for (s = 0; s <= S; s++) {
          var mm = 1 - sstep(xf - L, xf + L, xs[s]);
          YS[s] = w.own[to + s] + (w.own[o + s] - w.own[to + s]) * mm;
        }
      } else {
        for (s = 0; s <= S; s++) YS[s] = w.own[o + s];
      }
      ctx.globalAlpha = a;
      ctx.lineWidth = hair * (0.85 + 0.5 * w.z[i]);
      tracePath(YS);
      ctx.stroke();
    }

    // The survivor: grey among the others, turning into the accent as they leave. One stroke,
    // its colour and opacity interpolated together, so the change reads as hue and never as a
    // brighter flash that would give the choice away.
    var k = w.kHold >= 0 ? w.kHold : sstep(ACCENT_A, ACCENT_B, u), fade = 1 - sstep(DISSOLVE_A, 1, u);
    var fin = sstep(w.fin[w.s], w.fin[w.s] + 0.06, u);
    var aGrey = LINE_A * (0.34 + 0.66 * w.z[w.s]), aAcc = 0.8;
    a = intro * fin * fade * (aGrey + (aAcc - aGrey) * k * k);
    if (a > 0.002) {
      o = w.s * STRIDE;
      for (s = 0; s <= S; s++) YS[s] = w.own[o + s];
      tracePath(YS);
      ctx.lineWidth = hair * (0.85 + 0.5 * w.z[w.s] + 0.4 * k);
      ctx.strokeStyle = gradSurv[Math.round(k * SURV_STEPS)];
      ctx.globalAlpha = a;
      ctx.stroke();
    }
  }

  function draw() {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.clearRect(0, 0, CW, CH);
    var older = worlds[1 - cur], newer = worlds[cur];
    if (older.on) drawWorld(older);
    if (newer.on) drawWorld(newer);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "destination-out";
    for (var i = 0, o = 0; i < veilCount; i++, o += 4) {
      var rx = veilRects[o], ry = veilRects[o + 1], rw = veilRects[o + 2], rh = veilRects[o + 3];
      ctx.drawImage(veilSrc, rx / VS, ry / VS, rw / VS, rh / VS, rx, ry, rw, rh);
    }
    ctx.globalCompositeOperation = "source-over";
  }

  var elapsed = 0;
  function step(dt) {
    elapsed += dt; intro = sstep(0, INTRO_S, elapsed);
    var e = 1 - Math.exp(-dt / GLIDE_S);
    bandMid += (tMid - bandMid) * e; bandHalf += (tHalf - bandHalf) * e;
    Ha += (tHa - Ha) * e; Hi += (tHi - Hi) * e;
    var a = worlds[cur], b = worlds[1 - cur];
    a.t += dt;
    if (b.on) { b.t += dt; if (b.t >= b.dur) b.on = false; }
    if (a.t / a.dur >= HANDOFF && !b.on) {
      seedWorld(b, nextSeed(), N);
      cur = 1 - cur;
    }
    if (a.t >= a.dur) a.on = false;
  }

  /* ---------- run loop, paused when hidden, scrolled away or paused by the visitor ---------- */
  var running = false, raf = 0, last = 0, onScreen = true;
  // nothing is drawn that nobody can see: not under the open menu, not in forced colours
  function wanted() {
    return !reduced && !userPaused && onScreen && !document.hidden && !forcedMQ.matches &&
      !document.documentElement.classList.contains("menu-open");
  }
  function frame(now) {
    if (!running) return;
    var dt = (now - last) / 1000; last = now;
    if (dt < 0) dt = 0; else if (dt > 0.1) dt = 0.1;
    step(dt); draw();
    raf = requestAnimationFrame(frame);
  }
  function sync() {
    if (wanted()) {
      if (!running) { running = true; last = performance.now(); raf = requestAnimationFrame(frame); }
    } else if (running) { running = false; cancelAnimationFrame(raf); }
  }

  function renderStill() {
    worlds[1 - cur].on = false;
    var w = worlds[cur];
    seedWorld(w, STILL_SEED, N);
    w.t = STILL_U * w.dur; w.kHold = STILL_K; intro = 1;
    draw();
  }
  function firstTake() {
    worlds[1 - cur].on = false;
    var w = worlds[cur];
    seedWorld(w, nextSeed(), N, FIRST_DUR + master() * 2);
    w.t = FIRST_U * w.dur;
    elapsed = 0; intro = 0;
  }

  /* ---------- the pause control: anything that moves for more than 5 s can be stopped ---------- */
  function ctlLabel() {
    if (!ctl) return;
    var l = document.documentElement.lang.slice(0, 2) === "en" ? "en" : "es";
    ctl.textContent = ctl.getAttribute("data-" + (userPaused ? "resume" : "pause") + "-" + l);
  }
  if (ctl) {
    ctl.hidden = reduced;
    ctl.addEventListener("click", function () { userPaused = !userPaused; ctlLabel(); sync(); });
    document.addEventListener("slap:lang", ctlLabel);
    ctlLabel();
  }

  var pending = 0;
  function relayout() {
    pending = 0; layout();
    if (reduced) renderStill(); else if (!running) draw();
  }
  function scheduleLayout() { if (!pending) pending = requestAnimationFrame(relayout); }

  readPalette();
  layout();
  if (reduced) renderStill(); else { firstTake(); draw(); }

  if (window.ResizeObserver) {
    new ResizeObserver(scheduleLayout).observe(hero);
    new ResizeObserver(scheduleLayout).observe(words);
  } else {
    window.addEventListener("resize", scheduleLayout);
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(scheduleLayout);
  if (window.IntersectionObserver) {
    new IntersectionObserver(function (es) { onScreen = es[es.length - 1].isIntersecting; sync(); }, { threshold: 0 }).observe(hero);
  }
  document.addEventListener("visibilitychange", sync);
  document.addEventListener("slap:menu", sync);
  if (forcedMQ.addEventListener) forcedMQ.addEventListener("change", sync);
  // a window moved between a 1x monitor and a 2x laptop screen changes no CSS size: watch the density
  (function watchDensity() {
    if (!window.matchMedia) return;
    var mq = window.matchMedia("(resolution: " + (window.devicePixelRatio || 1) + "dppx)");
    var on = function () { if (mq.removeEventListener) mq.removeEventListener("change", on); scheduleLayout(); watchDensity(); };
    if (mq.addEventListener) mq.addEventListener("change", on);
  })();
  var onReduce = function () {
    reduced = reduceMQ.matches;
    if (ctl) ctl.hidden = reduced;
    if (reduced) { sync(); renderStill(); }
    else { firstTake(); elapsed = INTRO_S; intro = 1; sync(); }
  };
  if (reduceMQ.addEventListener) reduceMQ.addEventListener("change", onReduce);
  sync();
})();
