/*
  Pista: the practice areas as one track, carried by the reader's scroll.
  The section pins; vertical scroll moves a row of panels sideways, one area at a time, and each
  drawing finishes itself as its panel arrives. One hairline runs through all of them: it comes in
  from the left edge, takes the shape of each area's work and leaves for the next.

  Every drawing is already in the markup in its finished state, with its choreography declared in
  data attributes (data-d draws a stroke, data-m brings an element in from an offset, data-o
  keys its opacity); this script only interpolates between where an element starts and where the
  markup has it. Without the script, under reduced motion and in print, nothing here runs and the
  finished drawings are what is shown. Scroll work is batched into one animation frame, positions
  are measured on layout only, and nothing is done while the section is off screen.
*/
(function () {
  "use strict";

  var sec = document.querySelector(".pista");
  var root = document.documentElement;
  if (!sec || !window.requestAnimationFrame || !window.matchMedia) return;
  var reduceMQ = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!root.classList.contains("motion") || reduceMQ.matches) return;

  var run = sec.querySelector(".pista-run"), stage = sec.querySelector(".pista-stage");
  var view = sec.querySelector(".pista-view"), track = sec.querySelector(".pista-track");
  var panels = [].slice.call(sec.querySelectorAll(".pista-panel"));
  var texts = panels.map(function (p) { return p.querySelector(".pista-text"); });
  var boxes = panels.map(function (p) { return p.querySelector(".pista-fig"); });
  var now = sec.querySelector(".pista-now"), done = sec.querySelector(".pista-done");
  var ticks = [].slice.call(sec.querySelectorAll(".pista-tick"));
  var idx = [].slice.call(sec.querySelectorAll(".pista-idx")), mark = sec.querySelector(".pista-mark");
  var N = panels.length;
  if (!run || !stage || !track || !N) return;

  // Pinned only where a sideways track has room: a laptop or larger, held in landscape, so the
  // panels fit and an upright tablet gets the list instead of a stage full of air.
  var pinMQ = window.matchMedia("(min-width: 861px) and (min-height: 560px) and (min-aspect-ratio: 1/1)");

  // The pinned timeline, in stage heights of scroll: a dwell on the first area, then for each
  // next area a move (the track slides and the drawing builds) and a dwell (the reader reads).
  var PRE = 0.22, MOVE = 0.46, DWELL = 0.18, END = 0.1, LEG = MOVE + DWELL;
  var SPAN = PRE + (N - 1) * LEG + END;
  // The figure space: the thread on y = 250, the part that must always show inside this box.
  var BOX = [70, 36, 930, 464], CY = 250;

  /* ---------- small maths ---------- */
  function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function sstep(v) { v = clamp01(v); return v * v * (3 - 2 * v); }
  function outCubic(v) { v = 1 - clamp01(v); return 1 - v * v * v; }
  // the track glides: a little linear motion keeps it moving under the hand, the rest settles
  function glide(v) { return 0.3 * v + 0.7 * sstep(v); }
  function pad(n) { return (n < 10 ? "0" : "") + n; }

  /* ---------- a drawing: its declared choreography, played at any progress ---------- */
  function Figure(svg) {
    var self = this;
    this.svg = svg; this.p = -1; this.k = 1;
    this.draws = []; this.moves = []; this.fades = [];
    this.leadIn = svg.querySelector(".lead-in"); this.leadOut = svg.querySelector(".lead-out");
    [].forEach.call(svg.querySelectorAll("[data-d]"), function (el) {
      var w = el.getAttribute("data-d").split(" ").map(Number);
      self.draws.push({ el: el, a: w[0], b: w[1], v: -1 });
    });
    [].forEach.call(svg.querySelectorAll("[data-m]"), function (el) {
      var w = el.getAttribute("data-m").split(" ").map(Number);
      self.moves.push({ el: el, a: w[0], b: w[1], dx: w[2], dy: w[3], r: w[4], v: -1 });
    });
    [].forEach.call(svg.querySelectorAll("[data-o]"), function (el) {
      var keys = el.getAttribute("data-o").split(" ").map(function (s) { return s.split(":").map(Number); });
      self.fades.push({ el: el, keys: keys, v: -1 });
    });
    this.leadInDraw = this.draws.filter(function (d) { return d.el === self.leadIn; })[0];
  }
  Figure.prototype.arm = function () {
    this.draws.forEach(function (d) { d.el.style.strokeDasharray = "1 2"; d.v = -1; });
    this.p = -1;
  };
  Figure.prototype.disarm = function () {
    this.draws.forEach(function (d) { d.el.style.strokeDasharray = ""; d.el.style.strokeDashoffset = ""; });
    this.moves.forEach(function (m) { m.el.style.transform = ""; });
    this.fades.forEach(function (f) { f.el.style.opacity = ""; });
    this.svg.style.removeProperty("--sw");
    this.svg.setAttribute("viewBox", "0 0 1000 500");
  };
  Figure.prototype.set = function (p) {
    if (p === this.p) return;
    this.p = p;
    var i, d, m, f, v;
    for (i = 0; i < this.draws.length; i++) {
      d = this.draws[i];
      v = sstep((p - d.a) / (d.b - d.a));
      v = Math.round(v * 2000) / 2000;
      if (v !== d.v) { d.v = v; d.el.style.strokeDashoffset = String(1 - v); }
    }
    for (i = 0; i < this.moves.length; i++) {
      m = this.moves[i];
      v = Math.round(outCubic((p - m.a) / (m.b - m.a)) * 2000) / 2000;
      if (v !== m.v) {
        m.v = v;
        var q = 1 - v;
        m.el.style.transform = q ? "translate(" + (m.dx * q).toFixed(2) + "px," + (m.dy * q).toFixed(2) + "px) rotate(" + (m.r * q).toFixed(2) + "deg)" : "";
      }
    }
    for (i = 0; i < this.fades.length; i++) {
      f = this.fades[i];
      v = keyed(f.keys, p);
      v = Math.round(v * 500) / 500;
      if (v !== f.v) { f.v = v; f.el.style.opacity = String(v); }
    }
  };
  function keyed(keys, p) {
    if (p <= keys[0][0]) return keys[0][1];
    for (var i = 1; i < keys.length; i++) {
      if (p <= keys[i][0]) {
        var a = keys[i - 1], b = keys[i];
        return a[1] + (b[1] - a[1]) * sstep((p - a[0]) / (b[0] - a[0] || 1));
      }
    }
    return keys[keys.length - 1][1];
  }
  // The figure fills its box: the box's own aspect decides how much of the figure space shows,
  // always the whole of BOX, centred on the thread. On the track (`whole`) the figure is also
  // never cropped sideways, so each one's line ends exactly where the next one's begins. The
  // line may run on past the box, by `left` and `right` screen pixels, to the edge of the screen.
  Figure.prototype.fit = function (w, h, left, right, whole) {
    if (w < 2 || h < 2) return;
    var bx0 = whole ? 0 : BOX[0], bx1 = whole ? 1000 : BOX[2];
    var bw = bx1 - bx0, bh = BOX[3] - BOX[1], a = w / h, vw, vh;
    if (a > bw / bh) { vh = bh; vw = bh * a; } else { vw = bw; vh = bw / a; }
    var x0 = (bx0 + bx1) / 2 - vw / 2, y0 = CY - vh / 2, k = w / vw;
    this.k = k;
    this.svg.setAttribute("viewBox", x0.toFixed(2) + " " + y0.toFixed(2) + " " + vw.toFixed(2) + " " + vh.toFixed(2));
    this.svg.style.setProperty("--sw", (1 / k).toFixed(4));
    if (this.leadIn) this.leadIn.setAttribute("d", "M" + Math.min(0, x0 - left / k).toFixed(2) + ",250H0");
    if (this.leadOut) this.leadOut.setAttribute("d", "M1000,250H" + Math.max(1000, x0 + vw + right / k).toFixed(2));
  };

  var figs = panels.map(function (p) { return new Figure(p.querySelector(".pista-svg")); });

  /* ---------- state and layout ---------- */
  var mode = "", active = false, ticking = false, layoutPending = 0, stopped = false;
  var U = window.innerHeight, runTop = 0, step = 0, lastNow = -1, lastW = window.innerWidth;
  var figTop = [], figH = [];
  var idxBox = [];

  function setMode(next) {
    if (next === mode) return;
    mode = next;
    sec.classList.add("pista--js");
    sec.classList.toggle("pista--on", mode === "pin");
    figs.forEach(function (f) { f.arm(); });
    if (mode !== "pin") {
      run.style.height = ""; track.style.transform = "";
      texts.forEach(function (t) { t.style.opacity = ""; t.style.transform = ""; t.style.removeProperty("--hr"); t.style.removeProperty("--f"); });
      boxes.forEach(function (b) { b.style.opacity = ""; });
    }
    // the very first stretch of line is already there when the pinned track arrives
    if (figs[0].leadInDraw) { figs[0].leadInDraw.a = mode === "pin" ? -2 : 0; figs[0].leadInDraw.b = mode === "pin" ? -1 : 0.07; }
  }

  function layout() {
    layoutPending = 0;
    if (stopped) return;
    setMode(pinMQ.matches ? "pin" : "list");
    U = window.innerHeight;
    var vw = root.clientWidth, sy = window.scrollY;
    if (mode === "pin") {
      var h = Math.round(stage.offsetHeight * (1 + SPAN));
      if (run.style.height !== h + "px") run.style.height = h + "px";
      U = stage.offsetHeight;
      runTop = run.getBoundingClientRect().top + sy;
      var vr = view.getBoundingClientRect(), padL = parseFloat(getComputedStyle(view).paddingLeft) || 0;
      var left = vr.left + padL;
      // measure every box first, then write
      var dims = boxes.map(function (b) { var r = b.getBoundingClientRect(); return [r.width, r.height]; });
      step = panels[0].getBoundingClientRect().width;
      figs.forEach(function (f, i) {
        var extraL = i === 0 ? left : 0;
        var extraR = i === N - 1 ? Math.max(0, vw - left - step) : 0;
        f.fit(dims[i][0], dims[i][1], extraL, extraR, true);
        f.p = -1;
      });
      ticks.forEach(function (t, i) { t.style.left = (N > 1 ? (100 * i / (N - 1)) : 0) + "%"; });
      // the index: each name under its tick, the first and last held inside the rule
      idx.forEach(function (el, i) {
        var at = N > 1 ? i / (N - 1) : 0;
        el.style.left = (100 * at) + "%";
        el.style.transform = "translateX(" + (-100 * at) + "%)";
      });
      var ib = idx.length && idx[0].parentNode.getBoundingClientRect();
      idxBox = idx.map(function (el) {
        var r = el.getBoundingClientRect();
        return ib && r.width ? [r.left - ib.left, r.width] : null;
      });
    } else {
      var rects = boxes.map(function (b) { return b.getBoundingClientRect(); });
      var beside = texts.map(function (t) { return t.getBoundingClientRect().left; });
      figs.forEach(function (f, i) {
        var r = rects[i];
        // with the words beside it, the drawing keeps to its own box on that side
        var side = beside[i] >= r.right - 1;
        f.fit(r.width, r.height, r.left, side ? 0 : Math.max(0, vw - r.right), side);
        figTop[i] = r.top + sy; figH[i] = r.height; f.p = -1;
      });
    }
    lastNow = -1;
    frame();
  }
  function scheduleLayout() { if (!layoutPending) layoutPending = requestAnimationFrame(layout); }

  // where the track stands, in panels, for a scroll s measured in stage heights since pinning
  function posAt(s) {
    if (s <= PRE) return 0;
    var t = s - PRE, seg = Math.floor(t / LEG);
    if (seg >= N - 1) return N - 1;
    var r = (t - seg * LEG) / MOVE;
    return seg + (r >= 1 ? 1 : glide(r));
  }
  // how far a panel's drawing has come. The first builds as the section rises into view. Every
  // other one begins while the reader is still on the one before: its line reaches out to the
  // edge of the screen and what it starts from shows faintly (progress up to OPEN). The rest is
  // built while its panel slides in, and is finished early in its own dwell.
  var LEAD = DWELL * 0.55, OPEN = 0.08;
  function drawAt(i, s) {
    if (i === 0) return clamp01((s + 0.74) / (0.74 + PRE * 0.8));
    var a = PRE + (i - 1) * LEG - LEAD;
    if (s < a + LEAD) return OPEN * clamp01((s - a) / LEAD);
    return OPEN + (1 - OPEN) * clamp01((s - a - LEAD) / (MOVE + DWELL * 0.6));
  }

  function frame() {
    ticking = false;
    if (stopped) return;
    var y = window.scrollY, i;
    if (mode === "pin") {
      var s = (y - runTop) / U, pos = posAt(s);
      track.style.transform = "translate3d(" + (-pos * step).toFixed(2) + "px,0,0)";
      for (i = 0; i < N; i++) {
        figs[i].set(drawAt(i, s));
        var d = i - pos, o, hr, fo;
        // The words stay where they are read while the drawings slide beneath them: each area's
        // words are held in place against the track, the arriving ones come in order (label,
        // statement, body) and the ones just read fade where they stood. Nothing is ever cut at
        // an edge, and nothing the reader is reading moves.
        if (d >= 0) { o = 1; fo = sstep(1 - Math.min(1, d) * 2); hr = sstep(1 - d * 2); }
        else { o = sstep(1 + d * 2.2); fo = 1; hr = 1; }
        texts[i].style.opacity = o === 1 ? "" : o.toFixed(3);
        texts[i].style.transform = d ? "translate3d(" + (-d * step).toFixed(1) + "px,0,0)" : "";
        texts[i].style.setProperty("--f", fo.toFixed(3));
        // a drawing already read steps back, its line still there to follow
        boxes[i].style.opacity = d >= 0 ? "" : (0.3 + 0.7 * sstep(1 + d * 1.3)).toFixed(3);
        texts[i].style.setProperty("--hr", hr.toFixed(3));
      }
      if (done) done.style.transform = "scaleX(" + (N > 1 ? pos / (N - 1) : 1).toFixed(4) + ")";
      var at = Math.min(N - 1, Math.round(pos));
      if (at !== lastNow) {
        lastNow = at;
        if (now) now.textContent = pad(at + 1);
        ticks.forEach(function (t, k) { t.classList.toggle("on", k <= at); });
        idx.forEach(function (el, k) { el.classList.toggle("on", k === at); });
      }
      // the small scope glides from one name to the next with the track
      if (mark && idxBox[0]) {
        var lo = Math.floor(pos), hi = Math.min(N - 1, lo + 1), fr = pos - lo, A = idxBox[lo], B = idxBox[hi] || A;
        if (A && B) {
          mark.style.transform = "translateX(" + (A[0] + (B[0] - A[0]) * fr).toFixed(1) + "px)";
          mark.style.width = (A[1] + (B[1] - A[1]) * fr).toFixed(1) + "px";
        }
      }
    } else {
      for (i = 0; i < N; i++) {
        var top = figTop[i] - y;
        figs[i].set(clamp01((U * 0.9 - top) / (U * 0.5 + figH[i] * 0.3)));
      }
    }
  }
  function onScroll() {
    if (!active || ticking) return;
    ticking = true;
    requestAnimationFrame(frame);
  }

  /* ---------- wiring ---------- */
  var io = new IntersectionObserver(function (es) {
    var was = active;
    active = es[es.length - 1].isIntersecting;
    // leaving fast, the last frame is drawn where the reader left it
    if (was !== active) frame();
  }, { rootMargin: "25% 0px 25% 0px", threshold: 0 });
  io.observe(sec);

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", function () {
    // a phone's toolbar folding away is not a new layout
    if (window.innerWidth === lastW && mode === "list") { U = window.innerHeight; onScroll(); return; }
    lastW = window.innerWidth;
    scheduleLayout();
  });
  if (pinMQ.addEventListener) pinMQ.addEventListener("change", scheduleLayout);
  // anything above that changes height (a language, a late font) moves where the track starts
  document.addEventListener("slap:lang", scheduleLayout);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(scheduleLayout);
  window.addEventListener("load", scheduleLayout);
  if (window.ResizeObserver) {
    var main = document.querySelector("main") || document.body, lastMainH = 0;
    new ResizeObserver(function () {
      var h = main.offsetHeight;
      if (Math.abs(h - lastMainH) > 1) { lastMainH = h; scheduleLayout(); }
    }).observe(main);
  }
  // asked for less motion mid-visit: every drawing finished, no track, the list
  var onReduce = function () {
    if (!reduceMQ.matches) return;
    stopped = true;
    if (layoutPending) cancelAnimationFrame(layoutPending);
    window.removeEventListener("scroll", onScroll);
    io.disconnect();
    active = false; mode = "off";
    sec.classList.remove("pista--on", "pista--js");
    run.style.height = ""; track.style.transform = "";
    texts.forEach(function (t) { t.style.opacity = ""; t.style.transform = ""; t.style.removeProperty("--hr"); t.style.removeProperty("--f"); });
    boxes.forEach(function (b) { b.style.opacity = ""; });
    idx.forEach(function (el) { el.classList.remove("on"); el.style.left = ""; el.style.transform = ""; });
    if (mark) { mark.style.transform = ""; mark.style.width = ""; }
    if (done) done.style.transform = "";
    ticks.forEach(function (t) { t.style.left = ""; t.classList.remove("on"); });
    figs.forEach(function (f) { f.disarm(); });
  };
  if (reduceMQ.addEventListener) reduceMQ.addEventListener("change", onReduce);

  layout();
})();
