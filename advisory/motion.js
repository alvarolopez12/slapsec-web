/*
  Motion: the layer between the film and the reader.
  A scope that follows the pointer and locks onto what can be pressed; headlines that rise line
  by line; the Criterio diagnosis lighting up word by word as it is read; blocks that arrive in
  the order they enter; a compact header that comes back when the reader scrolls up and marks
  the section being read; the hero drifting away under the paper. Nothing here hides content
  without being able to show it, and none of it runs under reduced motion.
*/
(function () {
  "use strict";

  var root = document.documentElement;
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || !root.classList.contains("motion")) return;

  var hero = document.querySelector(".hero"), top = document.querySelector(".top");
  var vh = window.innerHeight;
  function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  // The words always come from the language's own copy, never from a previous split.
  function source(el) {
    return el.getAttribute("data-" + (root.lang.slice(0, 2) === "en" ? "en" : "es")) || el.textContent;
  }
  // what a screen reader hears while the words are split for the eye: the sentence, whole
  function whole(text) {
    var s = document.createElement("span");
    s.className = "sr"; s.textContent = text;
    return s;
  }

  /* ---------- headlines: split into lines that rise out of their own masks ---------- */
  var lined = [].slice.call(document.querySelectorAll(".light h2:not(.cont h2), .close h2"));
  function splitLines(el) {
    if (el.hasAttribute("data-settled")) return;
    var text = source(el);
    el.classList.remove("split");
    el.textContent = "";
    var words = text.split(" "), spans = [];
    words.forEach(function (w, i) {
      var s = document.createElement("span");
      s.textContent = w + (i < words.length - 1 ? " " : "");
      el.appendChild(s); spans.push(s);
    });
    var lines = [], last = null;
    spans.forEach(function (s) {
      var t = s.offsetTop;
      if (t !== last) { lines.push(""); last = t; }
      lines[lines.length - 1] += s.textContent;
    });
    el.textContent = "";
    el.classList.add("split");
    el.appendChild(whole(text));
    lines.forEach(function (line, i) {
      var o = document.createElement("span"), inner = document.createElement("span");
      o.className = "ln"; o.setAttribute("aria-hidden", "true"); inner.textContent = line;
      inner.style.setProperty("--i", i);
      o.appendChild(inner); el.appendChild(o);
    });
  }
  // Once risen, a headline goes back to plain text, so find in page and copy see one sentence.
  function settle(el) {
    el.setAttribute("data-settled", "");
    el.classList.remove("split");
    el.textContent = source(el);
  }

  /* ---------- Criterio: the diagnosis lights up as it is read, once, and never left half lit ---------- */
  var scrub = document.querySelector(".cont p"), scrubWords = [], scrubMax = 0, scrubIdle = 0, scrubDone = 0;
  function splitWords() {
    if (!scrub) return;
    var text = source(scrub);
    scrubWords = [];
    if (scrubMax >= 1) { scrub.textContent = text; return; }
    scrub.textContent = "";
    scrub.appendChild(whole(text));
    var box = document.createElement("span");
    box.setAttribute("aria-hidden", "true");
    scrub.appendChild(box);
    scrubWords = text.split(" ").map(function (w, i, all) {
      var s = document.createElement("span");
      s.className = "sw";
      s.textContent = w + (i < all.length - 1 ? " " : "");
      box.appendChild(s);
      return s;
    });
    paintScrub();
  }
  function paintScrub() {
    if (!scrub || !scrubWords.length) return;
    var r = scrub.getBoundingClientRect();
    scrubMax = Math.max(scrubMax, clamp01((vh * 0.92 - r.top) / (vh * 0.42 + r.height * 0.6)));
    var lit = Math.round(scrubMax * scrubWords.length);
    for (var i = 0; i < scrubWords.length; i++) scrubWords[i].classList.toggle("on", i < lit);
    // a reader who stops with it on screen gets the rest without having to scroll for it
    clearTimeout(scrubIdle);
    if (lit > 0 && lit < scrubWords.length) scrubIdle = setTimeout(function () { scrubMax = 1; paintScrub(); }, 900);
    // once every word is lit, the paragraph goes back to plain text
    if (lit >= scrubWords.length && !scrubDone) {
      scrubDone = setTimeout(function () { scrubWords = []; scrub.textContent = source(scrub); }, 600);
    }
  }

  /* ---------- reveals: hidden only if below the fold now, shown in the order they enter ---------- */
  var io = new IntersectionObserver(function (es) {
    var n = 0;
    es.filter(function (e) { return e.isIntersecting; })
      .sort(function (a, b) {
        return (a.boundingClientRect.top - b.boundingClientRect.top) || (a.boundingClientRect.left - b.boundingClientRect.left);
      })
      .forEach(function (e) {
        var el = e.target;
        el.style.setProperty("--d", Math.min(n++, 4));
        el.classList.add("in");
        io.unobserve(el);
        if (el.classList.contains("split")) setTimeout(settle, 1300 + 90 * el.querySelectorAll(".ln").length, el);
      });
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0 });

  function arm(el) {
    if (el.getBoundingClientRect().top < vh * 0.92) return false;   // already on screen: leave it be
    el.classList.add("rv");
    io.observe(el);
    return true;
  }
  document.querySelectorAll(".band .kicker, .body > p, .body > a, .moments li, .cont").forEach(arm);
  lined.forEach(function (el) { splitLines(el); if (!arm(el)) settle(el); });
  var close = document.querySelector(".close");
  if (close) arm(close);
  splitWords();

  // The language switch rewrites every string: split again what still has to rise.
  document.addEventListener("slap:lang", function () {
    lined.forEach(function (el) { if (el.hasAttribute("data-settled")) el.textContent = source(el); else splitLines(el); });
    splitWords();
  });
  var rt = 0, lastW = window.innerWidth;
  window.addEventListener("resize", function () {
    vh = window.innerHeight;
    if (window.innerWidth === lastW) { paintScrub(); return; }   // a toolbar folding away is not a new layout
    lastW = window.innerWidth;
    clearTimeout(rt); rt = setTimeout(function () { lined.forEach(splitLines); paintScrub(); }, 160);
  });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { lined.forEach(splitLines); });

  /* ---------- the compact header marks the section being read ---------- */
  var links = [].slice.call(document.querySelectorAll('.nav a[href^="#"]'));
  // a section without its own link (Cuándo llamarnos) keeps the chapter before it marked
  var owner = {}, lastLink = null;
  document.querySelectorAll("main > section").forEach(function (s) {
    var a = links.filter(function (l) { return l.getAttribute("href") === "#" + s.id; })[0];
    if (a) lastLink = a;
    owner[s.id] = a || lastLink;
  });
  var spied = null;
  function applySpy() {
    var atEnd = window.scrollY + vh >= root.scrollHeight - 2;
    var mark = atEnd ? links[links.length - 1] : spied;
    links.forEach(function (a) {
      if (a === mark) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
  }
  var spy = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) spied = owner[e.target.id] || null; });
    applySpy();
  }, { rootMargin: "-40% 0px -55% 0px" });
  document.querySelectorAll("main > section").forEach(function (s) { spy.observe(s); });

  /* ---------- scroll: the hero drifts away, the header comes back on the way up ---------- */
  var lastY = window.scrollY, ticking = false, acc = 0;
  var heroWords = hero && hero.querySelector(".wrap"), heroSub = hero && hero.querySelector(".standfirst");
  // where the hero's words end, in layout space, so the drift itself never changes the answer
  function wordsEnd() {
    return heroSub ? hero.offsetTop + heroWords.offsetTop + heroSub.offsetTop + heroSub.offsetHeight : 0;
  }
  function onScroll() {
    ticking = false;
    var y = window.scrollY, hh = hero ? hero.offsetHeight : vh;
    // on a short screen (a phone held sideways, a page zoomed to 400 percent) the words are still
    // being read while they scroll: they neither fade nor drift there
    if (hero && y < hh && wordsEnd() > vh) {
      hero.style.setProperty("--hero-shift", "0px");
      hero.style.setProperty("--hero-fade", "1");
    } else if (hero && y < hh) {
      // the film and the words move together, so the shade stays under the type;
      // the words are gone by the time the paper reaches them
      var f = clamp01((y - hh * 0.06) / (hh * 0.5));
      hero.style.setProperty("--hero-shift", (y * 0.32).toFixed(1) + "px");
      hero.style.setProperty("--hero-fade", (1 - f * f * (3 - 2 * f)).toFixed(3));
    }
    if (top && !root.classList.contains("menu-open")) {
      var d = y - lastY;
      if (d && (d > 0) !== (acc > 0)) acc = 0;   // distance since the scroll last changed direction
      acc += d;
      // a bar holding keyboard focus stays where the focus can be seen
      var stuck = top.classList.contains("stuck"), held = !!top.querySelector(":focus-visible");
      if (y > hh * 0.92) {
        if (!stuck) {
          // park it above the screen without animating there
          top.style.transition = "none";
          top.classList.add("stuck"); top.classList.remove("shown");
          void top.offsetHeight;
          top.style.transition = "";
          acc = 0;
        } else if (acc < -24) top.classList.add("shown");
        else if (acc > 24 && !held) top.classList.remove("shown");
      } else if (stuck) {
        // over the film the bar slides away; it hands over once the header in place is back
        if (y < 120) top.classList.remove("stuck", "shown");
        else if (y < hh * 0.6 && !held) top.classList.remove("shown");
      }
    }
    paintScrub();
    applySpy();
    lastY = y;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  // keyboard users who tab into a hidden bar get it back
  if (top) top.addEventListener("focusin", function () { if (top.classList.contains("stuck")) top.classList.add("shown"); });
  onScroll();
  // the entrance runs once; a later language switch rebuilds the headline without replaying it
  setTimeout(function () { root.classList.add("entered"); }, 2000);

  /* ---------- the scope: two corner brackets that follow the mouse and lock onto what can be pressed ---------- */
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)");
  if (!fine.matches) return;
  var scope = document.createElement("div");
  scope.className = "scope"; scope.setAttribute("aria-hidden", "true");
  var tl = document.createElement("i"), br = document.createElement("i");
  tl.className = "tl"; br.className = "br";
  scope.appendChild(tl); scope.appendChild(br);
  document.body.appendChild(scope);

  var px = -100, py = -100, target = null, R = 16, ARM = 9, OX = 3, OY = 5;
  var dpr = window.devicePixelRatio || 1;
  function sn(v) { return (Math.round(v * dpr) / dpr).toFixed(2); }   // whole device pixels, crisp arms
  var cur = { x0: -100, y0: -100, x1: -100, y1: -100 }, goal = { x0: 0, y0: 0, x1: 0, y1: 0 };
  var running = false, lastT = 0;
  var LOCK = "a:not(.logo), button", DARK = ".hero, .dark, .foot, .top, .nav.open";
  function hit(el) {
    el = el && el.closest ? el : null;
    target = el ? el.closest(LOCK) : null;
    scope.classList.toggle("lock", !!target);
    scope.classList.toggle("on-dark", !!(el && el.closest(DARK)));
    scope.classList.toggle("off", !!(el && el.closest(".logo")));   // the wordmark answers by itself
  }
  function aim() {
    if (target && document.contains(target)) {
      var r = target.getBoundingClientRect();
      goal.x0 = r.left - 7; goal.y0 = r.top - 5; goal.x1 = r.right + 7; goal.y1 = r.bottom + 5;
    } else {
      // framed a little down and right of the hotspot, clear of the arrow and the I-beam
      goal.x0 = px + OX - R; goal.y0 = py + OY - R; goal.x1 = px + OX + R; goal.y1 = py + OY + R;
    }
  }
  function frame(t) {
    var dt = lastT ? Math.min(0.05, (t - lastT) / 1000) : 0.016; lastT = t;
    aim();
    // close behind the pointer when free; the weight is in the lock
    var e = 1 - Math.exp(-dt / (target ? 0.09 : 0.016)), moving = false;
    for (var k in cur) {
      var d = goal[k] - cur[k];
      if (Math.abs(d) > 0.2) moving = true;
      cur[k] += d * e;
    }
    tl.style.transform = "translate3d(" + sn(cur.x0) + "px," + sn(cur.y0) + "px,0)";
    br.style.transform = "translate3d(" + sn(cur.x1 - ARM) + "px," + sn(cur.y1 - ARM) + "px,0)";
    if (moving) requestAnimationFrame(frame); else { running = false; lastT = 0; }
  }
  function kick() { if (!running) { running = true; requestAnimationFrame(frame); } }

  document.addEventListener("pointermove", function (e) {
    if (e.pointerType && e.pointerType !== "mouse") { scope.classList.remove("on"); return; }
    px = e.clientX; py = e.clientY;
    if (cur.x0 < -50) { cur.x0 = px + OX - R; cur.y0 = py + OY - R; cur.x1 = px + OX + R; cur.y1 = py + OY + R; }
    hit(e.target);
    scope.classList.add("on");
    kick();
  }, { passive: true });
  document.addEventListener("pointerdown", function (e) {
    if (e.pointerType && e.pointerType !== "mouse") { scope.classList.remove("on"); return; }
    scope.classList.add("press");
  }, { passive: true });
  document.addEventListener("pointerup", function () { scope.classList.remove("press"); }, { passive: true });
  document.addEventListener("mouseout", function (e) { if (!e.relatedTarget) scope.classList.remove("on"); });
  window.addEventListener("blur", function () { scope.classList.remove("on"); });
  // the page moves under a still mouse: look again at what is under it now
  if (top) top.addEventListener("transitionend", function (e) {
    if (e.propertyName === "top" && scope.classList.contains("on")) { hit(document.elementFromPoint(px, py)); kick(); }
  });
  var rehit = false;
  window.addEventListener("scroll", function () {
    if (rehit || !scope.classList.contains("on")) return;
    rehit = true;
    requestAnimationFrame(function () { rehit = false; hit(document.elementFromPoint(px, py)); kick(); });
  }, { passive: true });
})();
