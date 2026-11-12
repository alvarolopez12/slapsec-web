"""The practice as one track (Pista): the five drawings and the section's markup.

The drawings are plain SVG in their finished state, so a reader without scripts, a reader who
asked for less motion and the printer all get the composed figure. Their choreography is
declared beside the geometry, in data attributes that pista.js reads (progress is the panel's
own 0..1):

    data-d="a b"         the stroke draws itself between a and b      (needs pathLength="1")
    data-m="a b dx dy r" the element arrives from an offset (dx, dy in figure units, r in degrees)
    data-o="t:o t:o ..." opacity keyframes; the last value is also written as the static opacity

The figure space is 1000 x 500 with the thread on y = 250, entering at x = 0 and leaving at
x = 1000, so the five drawings join into one line when the panels sit side by side. Drawings
are chosen by each area's key; an unknown key gets a plain line, and any number of areas works.
The words come only from copy.json, through the build's own typography and language helpers.
"""
import math
import random

# ---------- drawing helpers ----------
CY = 250


def f3(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


class Fig:
    def __init__(self):
        self.parts = []

    def add(self, d, cls, draw=None, move=None, op=None, extra="", tag="path"):
        a = [f'class="{cls}"']
        if tag == "path":
            a.insert(0, f'd="{d}"')
        if draw:
            a.append('pathLength="1"')
            a.append(f'data-d="{f3(draw[0])} {f3(draw[1])}"')
        if move:
            a.append('data-m="' + " ".join(f3(v) for v in move) + '"')
        if op:
            a.append('data-o="' + " ".join(f"{f3(k)}:{f3(v)}" for k, v in op) + '"')
            if op[-1][1] != 1:
                a.append(f'opacity="{f3(op[-1][1])}"')
        if extra:
            a.append(extra)
        self.parts.append(f"<{tag} " + " ".join(a) + "/>")
        return self

    def group(self, inner, move=None, op=None):
        a = []
        if move:
            a.append('data-m="' + " ".join(f3(v) for v in move) + '"')
        if op:
            a.append('data-o="' + " ".join(f"{f3(k)}:{f3(v)}" for k, v in op) + '"')
            if op[-1][1] != 1:
                a.append(f'opacity="{f3(op[-1][1])}"')
        self.parts.append("<g " + " ".join(a) + ">" + "".join(inner.parts) + "</g>")
        return self

    def svg(self, key):
        lead = ('<path class="k lead lead-in" d="M-400,250H0" pathLength="1" data-d="0 0.07"/>'
                '<path class="k lead lead-out" d="M1000,250H1400" pathLength="1" data-d="0.93 1"/>')
        return (f'<svg class="pista-svg" data-fig="{key}" viewBox="0 0 1000 500" preserveAspectRatio="xMidYMid meet" '
                f'focusable="false">{lead}{"".join(self.parts)}</svg>')


def sq(cx, cy, s):
    h = s / 2
    return f"M{f3(cx - h)},{f3(cy - h)}H{f3(cx + h)}V{f3(cy + h)}H{f3(cx - h)}Z"


def scope(fig, x0, y0, x1, y1, arm, win, cls="b", off=9):
    """The page's scope: two corner brackets that close on what matters, as on the wordmark."""
    a, b = win
    fig.add(f"M{f3(x0)},{f3(y0 + arm)}V{f3(y0)}H{f3(x0 + arm)}", cls, move=(a, b, -off, -off, 0), op=((a, 0), (b, 1)))
    fig.add(f"M{f3(x1)},{f3(y1 - arm)}V{f3(y1)}H{f3(x1 - arm)}", cls, move=(a, b, off, off, 0), op=((a, 0), (b, 1)))


def plen(pts):
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))


def poly(pts):
    return "M" + "L".join(f"{f3(x)},{f3(y)}" for x, y in pts)


def ortho(pts):
    """Orthogonal polyline written with H and V, so it stays crisp and readable."""
    d = f"M{f3(pts[0][0])},{f3(pts[0][1])}"
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d += f"H{f3(x1)}" if y0 == y1 else f"V{f3(y1)}"
    return d


# ---------- 01 governance: loose risks settle into an order of who answers ----------
def gobierno():
    f = Fig()
    r = random.Random(11)
    f.add("M0,250H184", "k", draw=(0.07, 0.15))
    f.add(sq(190, 250, 12), "k", draw=(0.15, 0.19))
    f.add("M196,250H300", "k", draw=(0.19, 0.24))
    f.add("M300,250V130", "k", draw=(0.24, 0.3))
    f.add("M300,250V370", "k", draw=(0.24, 0.3))
    owners = (130, 250, 370)
    for y in owners:
        f.add(f"M300,{y}H410", "k", draw=(0.3, 0.35))
        f.add(f"M416,{y - 9}V{y + 9}", "k", draw=(0.35, 0.39))
        f.add(f"M416,{y}H486", "s", draw=(0.39, 0.43))
        f.add(f"M486,{y}V{y - 42}", "s", draw=(0.43, 0.47))
        f.add(f"M486,{y}V{y + 42}", "s", draw=(0.43, 0.47))
    # the risks: loose at first, each lands on the bar of whoever answers for it
    lens = (196, 132, 228, 118, 176, 150, 210, 124, 164)
    rows = [y + d for y in owners for d in (-42, 0, 42)]
    order = (4, 0, 7, 2, 5, 8, 1, 6, 3)
    for j, (y, ln) in enumerate(zip(rows, lens)):
        dx, dy, rot = r.uniform(-60, 150), r.uniform(-100, 100), r.uniform(-34, 34)
        a = 0.36 + 0.034 * order[j]
        f.add(f"M486,{y}H{486 + ln}", "s", move=(a, a + 0.22, dx, dy, rot), op=((0.0, 0), (0.1, 0.42), (a, 0.42), (a + 0.2, 1)))
    f.add("M760,250V80H736", "k", draw=(0.72, 0.8))
    f.add("M760,250V420H736", "k", draw=(0.72, 0.8))
    f.add("M760,250H1000", "k", draw=(0.8, 0.92))
    scope(f, 172, 232, 208, 268, 10, (0.84, 0.98))
    return f


# ---------- 02 transactions: two structures meet, and what was not in the book comes too ----------
def operaciones():
    f = Fig()
    f.add("M0,250H90", "k", draw=(0.07, 0.12))
    left = Fig()
    left.add("M90,140H410V360H90Z", "g")
    left.add("M90,250H410", "k", draw=(0.12, 0.3))
    left.add("M170,241V259", "s")
    left.add(sq(330, 250, 12), "s")
    left.add("M170,244V196H330V244", "s")
    left.add("M250,250V310", "s")
    left.add("M241,310H259", "s")
    f.group(left, move=(0.06, 0.5, -110, 0, 0), op=((0, 0), (0.12, 0.5), (0.5, 1)))
    right = Fig()
    right.add("M590,120H910V380H590Z", "g")
    right.add(sq(670, 250, 12), "s")
    right.add("M830,241V259", "s")
    right.add("M670,244V184H830V244", "s")
    right.add("M741,184H759", "s")
    right.add("M750,250V318H670", "s")
    right.add("M670,309V327", "s")
    f.group(right, move=(0.06, 0.5, 110, 0, 0), op=((0, 0), (0.12, 0.5), (0.5, 1)))
    # the joins made at closing: the thread itself, and the two systems stitched either side of it
    f.add("M410,250H590", "k", draw=(0.5, 0.58))
    f.add("M410,196H590", "s", draw=(0.54, 0.62))
    f.add("M410,304H590", "s", draw=(0.56, 0.64))
    f.add("M590,250H910", "k", draw=(0.58, 0.72))
    f.add("M910,250H1000", "k", draw=(0.72, 0.8))
    # what the information memorandum left out: tied to the target, outside its outline, and
    # visible only once the target has changed hands
    f.add("M830,256V432H788", "s dash", op=((0.7, 0), (0.82, 1)))
    f.add(sq(780, 432, 16), "s dash", op=((0.74, 0), (0.86, 1)))
    scope(f, 762, 414, 798, 450, 10, (0.84, 0.98))
    return f


# ---------- 03 architecture: the decision travels through every layer and turns plan into build ----------
def arquitectura():
    f = Fig()
    frames = ((200, 40, 800, 460), (270, 96, 730, 404), (340, 152, 660, 348), (410, 206, 590, 294))
    tone = ("g", "g", "s", "s")
    g = 13
    t0, t1, xin = 0.07, 0.47, 490
    def at(x):                      # when the thread, moving at one speed, reaches x
        return t0 + (t1 - t0) * x / xin
    for x0, y0, x1, y1 in frames:   # the plan, on paper
        plan = f"M{x0},{250 - g}V{y0}H{x1}V{250 - g}M{x0},{250 + g}V{y1}H{x1}V{250 + g}"
        f.add(plan, "g dash", op=((0.0, 0), (0.1, 1), (0.82, 1), (0.96, 0)))
    f.add(f"M0,250H{xin}", "k", draw=(t0, t1))
    for n, (x0, y0, x1, y1) in enumerate(frames):
        a = at(x0)
        b = a + 0.26 - 0.03 * n
        f.add(f"M{x0},{250 - g}V{y0}H{x1}V{250 - g}", tone[n], draw=(a, b))
        f.add(f"M{x0},{250 + g}V{y1}H{x1}V{250 + g}", tone[n], draw=(a, b))
        for x in (x0, x1):          # the control at each crossing
            ta = a if x == x0 else 0.52 + 0.34 * (x - 510) / 490
            f.add(f"M{x - 7},{250 - g}H{x + 7}M{x - 7},{250 + g}H{x + 7}", "s", op=((ta, 0), (ta + 0.05, 1)))
    f.add(sq(500, 250, 20), "k", draw=(0.47, 0.52))
    f.add("M510,250H1000", "k", draw=(0.52, 0.86))
    scope(f, 478, 228, 522, 272, 10, (0.84, 0.98))
    return f


# ---------- 04 offensive: inside an agreed scope, a path feels along each defence for its way through ----------
def ofensiva():
    f = Fig()
    scope(f, 236, 78, 808, 422, 28, (0.02, 0.14), cls="g", off=16)
    walls = ((340, 300), (440, 200), (540, 320), (640, 180))
    gap, near = 19, 9
    for n, (x, gy) in enumerate(walls):
        a = 0.05 + 0.025 * n
        f.add(f"M{x},104V{gy - gap}", "s", draw=(a, a + 0.12))
        f.add(f"M{x},396V{gy + gap}", "s", draw=(a, a + 0.12))
    # the route: to each defence, along it (first the wrong way, then the right one), through
    pts = [(0, 250)]
    y = 250
    for x, gy in walls:
        pts += [(x - near, y), (x - near, gy)]
        y = gy
    pts += [(720, y), (720, 250), (762, 250)]
    total = plen(pts) + 4 * 44
    t, speed = 0.12, 0.64 / total
    i0 = 0
    for n, (x, gy) in enumerate(walls):
        m = 1 + 2 * n               # where the route meets wall n
        seg = pts[i0:m + 1]
        dur = plen(seg) * speed
        f.add(ortho(seg), "k", draw=(t, t + dur))
        t += dur
        cx, cy = pts[m]
        wrong = cy - 44 if gy > cy else cy + 44
        pd = 44 * speed
        f.add(f"M{cx},{cy}V{wrong}", "s", draw=(t, t + pd), op=((t + pd, 1), (t + pd * 4, 0.6)))
        t += pd
        i0 = m
    seg = pts[i0:]
    dur = plen(seg) * speed
    f.add(ortho(seg), "k", draw=(t, t + dur))
    t += dur
    f.add(sq(770, 250, 16), "k", draw=(t, t + 0.035))
    f.add(sq(770, 250, 6), "fill", op=((t + 0.03, 0), (t + 0.06, 1)))
    f.add("M778,250H1000", "k", draw=(t + 0.04, t + 0.14))
    scope(f, 752, 232, 788, 268, 10, (0.86, 0.98))
    return f


def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


# ---------- 05 intelligence: scattered signals outside each draw a line to one point ----------
def inteligencia():
    f = Fig()
    r = random.Random(5)
    P = (452, 250)
    f.add("M0,250H110", "k", draw=(0.07, 0.11))
    f.add("M110,198H270V302H110Z", "s", draw=(0.09, 0.2))
    f.add("M110,250H184", "k", draw=(0.11, 0.135))
    f.add(sq(190, 250, 12), "k", draw=(0.135, 0.15))
    f.add("M196,250H270", "k", draw=(0.15, 0.17))
    f.add(f"M270,250H{P[0]}", "k", draw=(0.17, 0.27))
    noise = ((560, 96, 26, -22), (636, 410, 22, 31), (702, 64, 24, 12), (760, 432, 30, -8), (618, 140, 18, 47),
             (884, 452, 22, -35), (980, 128, 26, 18), (520, 380, 18, 60), (720, 330, 16, -64), (812, 58, 18, 72))
    for n, (x, y, ln, rot) in enumerate(noise):
        a = 0.01 + 0.012 * n
        rad = math.radians(rot)
        dx, dy = math.cos(rad) * ln / 2, math.sin(rad) * ln / 2
        f.add(poly([(x - dx, y - dy), (x + dx, y + dy)]), "g", op=((a, 0), (a + 0.1, 1), (0.6, 1), (0.84, 0.3)))
    # each signal: a short mark somewhere outside that settles, then draws its line to the point
    sources = ((934, 92), (842, 150), (968, 196), (872, 318), (946, 372), (826, 420))
    order = (2, 4, 0, 1, 5, 3)
    for n, (sx, sy) in enumerate(sources):
        a = 0.2 + 0.05 * order[n]
        dx, dy, rot = r.uniform(-60, 60), r.choice((-1, 1)) * r.uniform(40, 110), r.uniform(-60, 60)
        f.add(f"M{sx + 34},{sy}H{sx}", "s", move=(a, a + 0.18, dx, dy, rot), op=((0.02, 0), (0.12, 0.7), (a + 0.18, 1)))
        c1, c2 = (sx - 210, sy), (P[0] + 170, 250)
        d = f"M{sx},{sy}C{c1[0]},{c1[1]} {c2[0]},{c2[1]} {P[0]},{P[1]}"
        f.add(d, "g", draw=(a + 0.16, a + 0.42))
    f.add(f"M{P[0]},250H1000", "k", draw=(0.7, 0.86))
    scope(f, P[0] - 18, 232, P[0] + 18, 268, 10, (0.84, 0.98))
    return f


FIGURES = {"gobierno": gobierno, "operaciones": operaciones, "arquitectura": arquitectura,
           "ofensiva": ofensiva, "inteligencia": inteligencia}


def figure(key):
    if key in FIGURES:
        return FIGURES[key]().svg(key)
    # an area without a drawing of its own still carries the line through
    return Fig().add("M0,250H1000", "k", draw=(0.07, 0.93)).svg(key)


# ---------- the section ----------
def module(s, h):
    """s is the practice section from copy.json; h carries the build's helpers
    (t, rich, balanced, running, loans, esc), so the module follows the page's typography and
    its language switch exactly. The headline and the titles are balanced by the browser."""
    t, rich, balanced, running, loans, esc = h["t"], h["rich"], h["balanced"], h["running"], h["loans"], h["esc"]
    areas = s["items"]
    n = len(areas)
    items, index = [], []
    for i, a in enumerate(areas, 1):
        num = f"{i:02d}"
        body = rich(loans(esc(running(a["body_es"], "es")), "es"), loans(esc(running(a["body_en"], "en")), "en"),
                    "p", "pista-body")
        items.append(
            f'          <li class="pista-panel" data-key="{esc(a["key"])}">\n'
            f'            <div class="pista-fig" aria-hidden="true">{figure(a["key"])}</div>\n'
            f'            <div class="pista-text">\n'
            f'              <h3 class="pista-label"><span class="pista-n" aria-hidden="true">{num}</span>'
            f'{t(a["label_es"], a["label_en"])}</h3>\n'
            f'              {t(balanced(a["title_es"]), balanced(a["title_en"]), "p", "pista-title")}\n'
            f'              {body}\n'
            f'            </div>\n'
            f'          </li>')
        index.append(t(a["label_es"], a["label_en"], "span", "pista-idx"))
    return f'''  <section id="{s["id"]}" class="band light practice pista">
    <div class="wrap">
      <div class="grid">
      <div class="head">{t(s["kicker_es"], s["kicker_en"], "p", "kicker")}
        {t(balanced(s["headline_es"]), balanced(s["headline_en"]), "h2")}
      </div>
      <div class="body">
        {t(running(s["intro_es"], "es"), running(s["intro_en"], "en"), "p", "lead")}
      </div>
      </div>
    </div>
    <div class="pista-run">
      <div class="pista-stage">
        <div class="pista-view">
          <ol class="pista-track">
{chr(10).join(items)}
          </ol>
          <div class="pista-foot" aria-hidden="true">
            {t(s["kicker_es"], s["kicker_en"], "span", "pista-kicker")}
            <span class="pista-count"><span class="pista-now">01</span> / {n:02d}</span>
            <span class="pista-rule"><span class="pista-done"></span>{"".join('<span class="pista-tick"></span>' for _ in range(n))}</span>
            <span class="pista-index">{"".join(index)}<span class="pista-mark"></span></span>
          </div>
        </div>
      </div>
    </div>
  </section>'''
