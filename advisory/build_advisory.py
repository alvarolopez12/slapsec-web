#!/usr/bin/env python3
"""Build slapsec.com from advisory/copy.json and advisory/legal.json.

    python3 advisory/build_advisory.py                     # the site, in publish/
    python3 advisory/build_advisory.py --artifact <file>   # also a claude.ai artifact body

copy.json and legal.json are the only places the words live. The home page is written once per
language, English at / and Spanish at /es/, each with its own language in the markup, so a
reader, a crawler and a browser without script all get a whole page in one language. Both keep
the other language beside it: plain strings as data-es / data-en attributes, strings that carry
markup as a pair of inert <template> elements. The language switch swaps them in place, with no
HTML ever parsed from a string, so the page runs under Trusted Types, and moves the address to
the other page. The legal pages are written once per language and carry no script at all.

The site build is self-contained: fonts, icons and every script are served from the site's
own origin, and the security headers are written here, with the Content-Security-Policy hashes
computed from the exact inline code that ships. The artifact build embeds the same fonts as
data: URIs, because its frame only allows those, and still makes no request to anyone.
"""
import base64
import hashlib
import html
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.parse
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pista  # noqa: E402  the practice as one track: its five drawings and its markup
COPY = json.load(open(os.path.join(HERE, "copy.json"), encoding="utf-8"))
LEGAL = json.load(open(os.path.join(HERE, "legal.json"), encoding="utf-8"))
FONTS_DIR = os.path.join(HERE, "fonts")
STATIC_DIR = os.path.join(HERE, "static")
OUT = os.path.join(ROOT, "publish")   # the directory Netlify publishes for slapsec.com

BRAND, ENTITY = COPY["brand"], COPY["entity"]
ORIGIN = COPY.get("origin", "").rstrip("/")
DOMAIN = re.sub(r"^https://", "", ORIGIN)
EMAIL = COPY.get("contact_email", "").strip()
LINKEDIN = COPY.get("linkedin", "").strip()   # the firm's page there; empty leaves the footer without the link
PRIMARY = COPY.get("primary_lang", "es")
LANGS = ("en", "es")
HTML_LANG = {"es": "es-ES", "en": "en-GB"}
OG_LOCALE = {"es": "es_ES", "en": "en_GB"}
TODAY = date.today()
YEAR = TODAY.year


def read(name):
    return open(os.path.join(HERE, name), encoding="utf-8").read()


# The closing clause of the hero headline, set in italic. It lives with the words, in copy.json,
# and the italic font is cut to exactly its letters (tools/make_fonts.py).
EMPHASIS = {code: COPY["sections"][0][f"emphasis_{code}"] for code in ("es", "en")}

# The default address Netlify gives this site. It serves the same deploy, so it is sent to ORIGIN.
NETLIFY_HOST = "slapsec.netlify.app"

UI = {
    "menu": ("Menú", "Menu"),
    "close": ("Cerrar", "Close"),
    "home": (f"{BRAND}, inicio", f"{BRAND}, home"),
    "nav": ("Secciones", "Sections"),
    "lang": ("Idioma", "Language"),
    "pause": ("Pausar animación", "Pause animation"),
    "resume": ("Reanudar animación", "Resume animation"),
    "skip": ("Saltar al contenido", "Skip to content"),
    "legal_nav": ("Información legal", "Legal information"),
    "linkedin": (f"{BRAND} en LinkedIn, se abre en otra pestaña", f"{BRAND} on LinkedIn, opens in a new tab"),
    "updated": ("Última actualización", "Last updated"),
    "contents": ("En esta página", "On this page"),
    "legal_kicker": ("Legal", "Legal"),
}

# The language switch names each language in itself.
LANG_NAMES = {"es": "ES, español", "en": "EN, English"}

# Typography the browser cannot do on its own. NBSP keeps short words with the word they
# introduce in display type, and the last two words of a block together, so no line ends on
# "a la" or "que" and no block ends on a single word. It is baked into both languages because
# the language switch rewrites the text.
NBSP = "\u00a0"   # written as an escape, so no editor can turn it into a plain space
SHORT = r"a|al|de|del|el|en|la|las|lo|los|no|o|que|qué|se|su|un|una|y|e|u|ni|sin|con|por|the|an|of|to|in|on|and|or|is|it|we|by"
ONE = r"a|y|o|e|u"


def _glue(s, words):
    return re.sub(rf"(?<![^\s«“‘(¿])({words}) (?=\S)", r"\1" + NBSP, s, flags=re.I)


def widont(s):
    return re.sub(r" (\S+)\s*$", NBSP + r"\1", s)


# Names the reader takes in as one word: never split across a line, in any kind of text.
TERMS = ("ISO 27001", "PCI DSS")


def _bind(s):
    for term in TERMS:
        s = s.replace(term, term.replace(" ", NBSP))
    return s


def display(s):
    """Headlines, the Criterio continuation, the list of moments, the descriptor."""
    return widont(_glue(_bind(s), SHORT))


def balanced(s):
    """Headlines and titles the browser balances (text-wrap: balance): the same binding, without
    the last-two-words glue. Balancing already keeps a last line from being one word, and Chrome
    takes the glued pair for a word it may not leave alone, so it drags the word before it down."""
    return _glue(_bind(s), SHORT)


def running(s, lang):
    """Paragraphs: Spanish binds its one-letter words, as Spanish typesetting does; both
    languages keep "no" with its verb, because the page's commitments are built on negations.
    English does not bind its articles."""
    return widont(_glue(_bind(s), ONE + "|no" if lang == "es" else "no"))


# Loanwords Spanish keeps in their original form: italic in Spanish, marked as English for
# screen readers, and never split across a line in either language.
LOANS = ("due diligence", "red team", "dark web")


def esc(s):
    return html.escape(s, quote=True)


BRAND_RE = re.compile(rf"\b{re.escape(BRAND)}\b")


def brand(markup):
    """The firm's name is never machine translated."""
    return BRAND_RE.sub(f'<span translate="no">{BRAND}</span>', markup)


def loans(markup, lang):
    for w in LOANS:
        tight = w.replace(" ", NBSP)
        markup = markup.replace(w, tight)
        if lang == "es":
            markup = markup.replace(tight, f'<i lang="en">{tight}</i>')
    return markup


# ---------- the language being written ----------
# Every helper below bakes this language into the markup and keeps the other beside it.
LANG = "es"


def pick(es, en):
    return en if LANG == "en" else es


def ui(key):
    return pick(*UI[key])


def home_path(lang):
    return "/" if lang == PRIMARY else f"/{lang}/"


def switch_href(lang):
    """Where the language switch leads without script. The primary language asks for itself
    by name, because the edge function sends visitors browsing from Spain to /es/ and only an
    explicit ?lang=en keeps a reader who chose English on the English page."""
    return home_path(lang) + (f"?lang={lang}" if lang == PRIMARY else "")


# ---------- translatable elements ----------
TEMPLATES = []


def rich(es, en, tag, cls=None, extra=""):
    """An element whose content carries markup: the page's language baked in, both kept as inert templates."""
    key = f"t{len(TEMPLATES) // 2 + 1}"
    TEMPLATES.append(f'<template id="{key}-es">{es}</template>')
    TEMPLATES.append(f'<template id="{key}-en">{en}</template>')
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} data-i18n="{key}"{extra}>{pick(es, en)}</{tag}>'


def t(es, en, tag="span", cls=None, extra=""):
    """A translatable element. Plain text travels in attributes; anything naming the firm goes
    through rich(), so the name can carry translate="no"."""
    if BRAND_RE.search(es) or BRAND_RE.search(en):
        return rich(brand(esc(es)), brand(esc(en)), tag, cls, extra)
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} data-es="{esc(es)}" data-en="{esc(en)}"{extra}>{esc(pick(es, en))}</{tag}>'


def paragraphs(body):
    return [p.strip() for p in body.split("\n\n") if p.strip()]


def list_items(body):
    return [line[2:].strip() for line in body.split("\n") if line.strip().startswith("- ")]


def emphasise(text, lang):
    clause = EMPHASIS[lang]
    assert text.endswith(clause) and text != clause, f"hero {lang}: the headline must end with its emphasis clause"
    head = text[: -len(clause)].rstrip()
    # English binds only articles and prepositions here, so «decisions» is never left alone
    head = _glue(head, SHORT if lang == "es" else r"a|an|the|of|on|to|in")
    return f"{brand(esc(head))} <em>{esc(display(clause))}</em>"


def section(s):
    sid, role = s["id"], s["role"]
    kicker = t(s["kicker_es"], s["kicker_en"], "p", "kicker") if s.get("kicker_es") else ""
    pes = [running(p, "es") for p in paragraphs(s.get("body_es", ""))]
    pen = [running(p, "en") for p in paragraphs(s.get("body_en", ""))]
    # the approach headline runs on into its paragraph; every other h2 is balanced by the browser
    head = display if role == "approach" else balanced
    hes, hen = head(s["headline_es"]), head(s["headline_en"])

    if role == "decisions":
        items = zip(list_items(s["body_es"]), list_items(s["body_en"]))
        lis = "\n".join(f"        {t(display(es), display(en), 'li')}" for es, en in items)
        body = f'      <ul class="moments">\n{lis}\n      </ul>'
        return (f'  <section id="{sid}" class="band light">\n    <div class="wrap grid">\n'
                f'      <div class="head">{kicker}\n        {t(hes, hen, "h2")}\n      </div>\n'
                f'{body}\n    </div>\n  </section>')

    if role == "approach":
        # The first paragraph continues the headline in grey, at headline size, so the
        # question and its diagnosis read as one thought. Semantics stay h2 + p.
        first_es, first_en = display(paragraphs(s["body_es"])[0]), display(paragraphs(s["body_en"])[0])
        lead = (f'      <div class="cont">{t(hes, hen, "h2")} '
                f'{t(first_es, first_en, "p")}</div>')
        rest = "\n".join(f"        {t(es, en, 'p')}" for es, en in zip(pes[1:], pen[1:]))
        return (f'  <section id="{sid}" class="band light">\n    <div class="wrap">\n'
                f'      {kicker}\n{lead}\n      <div class="grid"><div class="body span-right">\n{rest}\n'
                f'      </div></div>\n    </div>\n  </section>')

    if role == "practice":
        # The five areas as one track: a hairline that takes the shape of each area's work,
        # carried sideways by the reader's scroll where there is room, a list everywhere else.
        return pista.module(s, {"t": t, "rich": rich, "balanced": balanced, "running": running,
                                "loans": loans, "esc": esc})

    if role == "feature":
        rest = "\n".join(f"        {t(es, en, 'p')}" for es, en in zip(pes, pen))
        return (f'  <section id="{sid}" class="band light feature">\n    <div class="wrap">\n'
                f'      {kicker}\n      {t(hes, hen, "h2", "feature-h")}\n'
                f'      <div class="grid"><div class="body span-right">\n{rest}\n      </div></div>\n'
                f'    </div>\n  </section>')

    if role == "contact":
        rest = "\n".join(f"        {t(es, en, 'p')}" for es, en in zip(pes, pen))
        # The link is the address itself, so it can be read and copied as it is.
        cta = f'\n        <a class="cta" href="mailto:{esc(EMAIL)}">{esc(EMAIL)}</a>' if EMAIL else ""
        return (f'  <section id="{sid}" class="band dark close">\n    <div class="wrap grid">\n'
                f'      <div class="head">{kicker}\n        {t(hes, hen, "h2")}\n      </div>\n'
                f'      <div class="body">\n{rest}{cta}\n      </div>\n    </div>\n  </section>')

    # point of view, and anything else: kicker + headline left, argument right
    first = t(pes[0], pen[0], "p", "lead")
    rest = "\n".join(f"        {t(es, en, 'p')}" for es, en in zip(pes[1:], pen[1:]))
    return (f'  <section id="{sid}" class="band light">\n    <div class="wrap grid">\n'
            f'      <div class="head">{kicker}\n        {t(hes, hen, "h2")}\n      </div>\n'
            f'      <div class="body">\n        {first}\n{rest}\n      </div>\n    </div>\n  </section>')


# The wordmark as the brand kit draws it (01-logo/png, measured in em of the word): the box is
# 1.4 em tall, the brackets' arms 0.405 em long and 0.085 em thick (never under 2px, so they stay
# crisp), and the letters' ink 0.39 em in from the left and 0.38 em from the right; the padding
# allows for the S's and the c's own side bearings. All of it is in em of the word, so the scope
# scales as one piece.
LOGO_CSS = (
    ".logo-mark{position:relative;display:inline-block;font-size:1.3125rem;padding:.2em .385em .2em .366em}\n"
    ".logo-word{font-family:var(--sans);font-weight:800;font-size:1em;letter-spacing:-.025em;line-height:1;"
    "display:block;color:var(--on-dark)}\n"
    '.logo-mark::before,.logo-mark::after{content:"";position:absolute;width:.405em;height:.405em;'
    "border:0 solid var(--green)}\n"
    ".logo-mark::before{top:0;left:0;border-width:max(2px,.085em) 0 0 max(2px,.085em)}\n"
    ".logo-mark::after{bottom:0;right:0;border-width:0 max(2px,.085em) max(2px,.085em) 0}")


def wordmark():
    return f'<span class="logo-mark"><span class="logo-word" translate="no">{BRAND}</span></span>'


def logo(href="#inicio", swap=True):
    """The scope wordmark and, beside it, what the firm does. On the home page the link label
    follows the language switch; on a legal page there is no switch to follow."""
    aria = (f'data-es-aria="{esc(UI["home"][0])}" data-en-aria="{esc(UI["home"][1])}" ' if swap else "")
    desc = (t(display(COPY["descriptor_es"]), display(COPY["descriptor_en"])) if swap
            else esc(display(pick(COPY["descriptor_es"], COPY["descriptor_en"]))))
    return (f'<a class="logo" href="{href}" {aria}aria-label="{esc(ui("home"))}">{wordmark()}</a>'
            f'<span class="desc">{desc}</span>')


def lang_switch(target, counterpart=None):
    """ES / EN. Links, so the switch works without script; on the home page the script swaps
    the words in place instead and moves the address (data-path) to the other language's page.
    counterpart maps each language to the page a legal page switches to."""
    items = []
    for code in ("es", "en"):
        current = ' aria-current="true"' if code == LANG else ""
        if counterpart:
            href, path = counterpart[code], ""
        elif target == "site":
            href, path = switch_href(code), f' data-path="{home_path(code)}"'
        else:
            href, path = "#inicio", ""
        items.append(f'<a href="{esc(href)}" hreflang="{code}" lang="{HTML_LANG[code]}" data-lang="{code}"{path} '
                     f'aria-label="{esc(LANG_NAMES[code])}"{current}>{code.upper()}</a>')
    swap = "" if counterpart else f' data-es-aria="{esc(UI["lang"][0])}" data-en-aria="{esc(UI["lang"][1])}"'
    return (f'<div class="lang" role="group" aria-label="{esc(ui("lang"))}"{swap}>'
            + '<span aria-hidden="true">/</span>'.join(items) + "</div>")


# ---------- the legal pages ----------
PAGES = {p["key"]: p for p in LEGAL["pages"]}


def legal_url(key, lang):
    return PAGES[key]["path"][lang]


def legal_file(key, lang):
    return legal_url(key, lang).lstrip("/") + ".html"


def footer_links(swap, current=None):
    """The footer's legal links. On the home page each carries both addresses, so the language
    switch can move them too; a legal page marks itself as the current one."""
    lis = []
    for key in PAGES:
        es, en = PAGES[key]["label"]["es"], PAGES[key]["label"]["en"]
        href = legal_url(key, LANG)
        cur = ' aria-current="page"' if key == current else ""
        if swap:
            extra = (f' href="{esc(href)}" data-es-href="{esc(legal_url(key, "es"))}" '
                     f'data-en-href="{esc(legal_url(key, "en"))}"{cur}')
            lis.append(f"        <li>{t(es, en, 'a', None, extra)}</li>")
        else:
            lis.append(f'        <li><a href="{esc(href)}"{cur}>{esc(pick(es, en))}</a></li>')
    label = (f' aria-label="{esc(ui("legal_nav"))}" data-es-aria="{esc(UI["legal_nav"][0])}" '
             f'data-en-aria="{esc(UI["legal_nav"][1])}"' if swap else f' aria-label="{esc(ui("legal_nav"))}"')
    return f"      <ul{label}>\n" + "\n".join(lis) + "\n      </ul>"


def social(swap):
    """The firm's page on LinkedIn, in the footer across from the wordmark. It opens in its own
    tab, so the reader keeps the page; on the home page its label follows the language switch."""
    if not LINKEDIN:
        return ""
    aria = f' aria-label="{esc(ui("linkedin"))}"'
    if swap:
        aria += f' data-es-aria="{esc(UI["linkedin"][0])}" data-en-aria="{esc(UI["linkedin"][1])}"'
    return (f'      <a class="social" href="{esc(LINKEDIN)}" target="_blank" rel="noopener"{aria}>'
            f'<span translate="no">LinkedIn</span></a>')


def copyright_line():
    return f'© {YEAR} <span translate="no">{ENTITY}</span>'


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def legal_text(s, lang):
    """A legal string: set as running text, escaped, then its few placeholders become markup."""
    out = esc(running(s, lang))
    out = re.sub(r"`([^`]+)`", r'<code translate="no">\1</code>', out)
    refs = {
        "{email}": f'<a href="mailto:{esc(EMAIL)}">{esc(EMAIL)}</a>',
        "{entity}": f'<span translate="no">{esc(ENTITY)}</span>',
        "{brand}": f'<span translate="no">{esc(BRAND)}</span>',
        "{domain}": f'<span translate="no">{esc(DOMAIN)}</span>',
    }
    for key in PAGES:
        refs["{" + key + "}"] = f'<a href="{esc(legal_url(key, lang))}">{esc(PAGES[key]["ref"][lang])}</a>'
    for k, v in refs.items():
        out = out.replace(k, v)
    left = re.findall(r"\{[a-z]+\}", out)
    assert not left, f"unknown placeholder in legal.json: {left}"
    return out


def legal_block(b, lang):
    if "p" in b:
        return f"<p>{legal_text(b['p'][lang], lang)}</p>"
    if "intro" in b:
        return f'<p class="intro">{legal_text(b["intro"][lang], lang)}</p>'
    if "h3" in b:
        return f"<h3>{esc(b['h3'][lang])}</h3>"
    if "ul" in b:
        return "<ul>\n" + "\n".join(f"  <li>{legal_text(li, lang)}</li>" for li in b["ul"][lang]) + "\n</ul>"
    if "dl" in b:
        rows = "\n".join(f'  <div><dt>{esc(r["dt"][lang])}</dt><dd>{legal_text(r["dd"][lang], lang)}</dd></div>'
                         for r in b["dl"])
        return f"<dl>\n{rows}\n</dl>"
    if "note" in b:
        return (f'<div class="note"><p class="note-label">{esc(b["note"]["label"][lang])}</p>'
                f'<p>{legal_text(b["note"]["text"][lang], lang)}</p></div>')
    raise SystemExit(f"legal.json: unknown block {list(b)}")


def legal_page(key, lang):
    global LANG
    LANG = lang
    page = PAGES[key]
    toc, body = [], []
    for b in page.get("lead", []):
        body.append(legal_block(b, lang))
    for i, s in enumerate(page["sections"], 1):
        head = s["h"][lang]
        sid = slug(head)
        toc.append(f'<li><a href="#{sid}"><span class="n" aria-hidden="true">{i:02d}</span>{esc(head)}</a></li>')
        body.append(f'<h2 id="{sid}"><span class="n">{i:02d}</span> {esc(display(head))}</h2>')
        body.extend(legal_block(b, lang) for b in s["blocks"])
    counterpart = {code: legal_url(key, code) for code in LANGS}
    title = f'{page["title"][lang]} | {BRAND}'
    fills = {
        "HTML_LANG": HTML_LANG[lang],
        "TITLE": esc(title),
        "DESC": esc(page["desc"][lang]),
        "LINKS": head_links({code: ORIGIN + legal_url(key, code) for code in LANGS}),
        "ICONS": icons("site"),
        "FONT_PRELOADS": font_preloads("site", only=("newsreader-300.woff2",)),
        "FONT_FACES": font_faces("site"),
        "LOGO_CSS": LOGO_CSS,
        "SKIP": esc(ui("skip")),
        "LOGO_HEAD": logo(home_path(lang), swap=False),
        "LOGO_FOOT": logo(home_path(lang), swap=False),
        "LANG_SWITCH": lang_switch("site", counterpart),
        "KICKER": esc(ui("legal_kicker")),
        "H1": esc(display(page["title"][lang])),
        "UPDATED": (f'{esc(ui("updated"))}: <time datetime="{LEGAL["updated"]["iso"]}">'
                    f'{esc(LEGAL["updated"][lang]).replace(" ", NBSP)}</time>'),   # the date never breaks
        "CONTENTS": esc(ui("contents")),
        "TOC": "\n".join(f"          {li}" for li in toc),
        "BODY": "\n".join(body),
        "COPYRIGHT": copyright_line(),
        "FOOT_SOCIAL": social(False),
        "FOOT_NOTE": footer_links(False, key),
    }
    return finish(fill(read("legal.template.html"), fills), "site")


# ---------- fonts, icons, head ----------
# family, style, weight, file, preloaded (the hero's two faces, which set the first screen).
# Newsreader stays variable on screen for its optical sizes; print gets static instances,
# because a PDF can only carry variable fonts as pictures of letters, not as text.
FACES = (
    ("Newsreader", "normal", "300", "newsreader-300.woff2", True),
    ("Newsreader", "italic", "300", "newsreader-300-italic-hero.woff2", True),
    ("Schibsted Grotesk", "normal", "400", "schibsted-grotesk-400.woff2", False),
    ("Schibsted Grotesk", "normal", "800", "schibsted-grotesk-800-wordmark.woff2", False),
    ("Schibsted Grotesk", "italic", "400", "schibsted-grotesk-italic-loans.woff2", False),
    ("JetBrains Mono", "normal", "400", "jetbrains-mono-400.woff2", False),
)
PRINT_FACES = (
    ("Newsreader Print", "normal", "300", "newsreader-300-print.woff2", False),
    ("Newsreader Print", "italic", "300", "newsreader-300-italic-print.woff2", False),
)


def font_bytes(name):
    return open(os.path.join(FONTS_DIR, name), "rb").read()


def hashed(name):
    """fonts/<name>.<sha8>.woff2: a new file name whenever the file changes, so it can be cached for a year."""
    stem, ext = os.path.splitext(name)
    return f"{stem}.{hashlib.sha256(font_bytes(name)).hexdigest()[:8]}{ext}"


def check_subsets():
    """The italics and the wordmark are cut to the words they set: refuse to build if those words changed."""
    sets = json.load(open(os.path.join(FONTS_DIR, "subsets.json"), encoding="utf-8"))
    need = {"newsreader-300-italic-hero.woff2": EMPHASIS["es"] + EMPHASIS["en"] + NBSP,
            "schibsted-grotesk-italic-loans.woff2": "".join(LOANS) + NBSP,
            "schibsted-grotesk-800-wordmark.woff2": BRAND}
    for f, text in need.items():
        missing = set(text) - set(sets[f])
        assert not missing, f"{f} lacks {sorted(missing)}: run advisory/tools/make_fonts.py"


def font_faces(target):
    out = []
    # the print faces are declared on the site only: a browser fetches them when printing
    for fam, style, weight, name, _ in FACES + (PRINT_FACES if target == "site" else ()):
        if target == "artifact":
            src = "data:font/woff2;base64," + base64.b64encode(font_bytes(name)).decode()
        else:
            src = f"/fonts/{hashed(name)}"
        out.append(f'@font-face{{font-family:"{fam}";font-style:{style};font-weight:{weight};font-display:swap;'
                   f'src:url({src}) format("woff2")}}')
    return "\n".join(out)


def font_preloads(target, only=None):
    if target == "artifact":
        return ""
    return "\n".join(f'<link rel="preload" href="/fonts/{hashed(name)}" as="font" type="font/woff2" crossorigin>'
                     for _, _, _, name, pre in FACES if (name in only if only else pre))


FAVICON_SVG = open(os.path.join(STATIC_DIR, "favicon.svg"), encoding="utf-8").read().strip()
ICON_FILES = ("favicon.svg", "favicon-32.png", "apple-touch-icon.png", "icon-512.png")


def icon_version(name):
    """A tab icon's address carries a hash of the picture, as the share image's does: browsers keep
    an icon by its address for a long time, and would otherwise go on showing the old one."""
    return "?v=" + hashlib.sha256(open(os.path.join(STATIC_DIR, name), "rb").read()).hexdigest()[:8]


def icons(target):
    """The tab icons (tools/make_icons.py draws them). The vector one has no size and the bitmap
    exactly one, which is what makes Chrome and Firefox take the first and Safari the second."""
    if target == "artifact":
        return f'<link rel="icon" href="data:image/svg+xml,{urllib.parse.quote(FAVICON_SVG)}">'
    return (f'<link rel="icon" href="/favicon.svg{icon_version("favicon.svg")}" type="image/svg+xml">\n'
            f'<link rel="icon" href="/favicon-32.png{icon_version("favicon-32.png")}" sizes="32x32" type="image/png">\n'
            '<link rel="apple-touch-icon" href="/apple-touch-icon.png">')


def robots_meta():
    return '<meta name="robots" content="noindex, nofollow">' if COPY.get("private", True) else ""


def verification_meta(target):
    """Search Console's proof of ownership for the home pages. It is a line of text: nothing loads."""
    token = COPY.get("google_site_verification", "")
    assert re.fullmatch(r"[A-Za-z0-9_-]*", token), "google_site_verification"
    return f'<meta name="google-site-verification" content="{token}">' if token and target == "site" else ""


def head_links(urls, swap=False):
    """canonical and the language alternates: urls maps each language to its absolute address.
    On the home pages the canonical follows the language switch, as the address bar does, so a
    link shared from the page after switching is the page the reader is looking at."""
    if not ORIGIN:
        return ""
    both = "".join(f' data-{code}-href="{esc(urls[code])}"' for code in ("es", "en")) if swap else ""
    out = [f'<link rel="canonical" href="{esc(urls[LANG])}"{both}>']
    out += [f'<link rel="alternate" hreflang="{code}" href="{esc(urls[code])}">' for code in LANGS]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{esc(urls[PRIMARY])}">')
    return "\n".join(out)


OG_SIZE = (1200, 630)


def share_image(lang):
    """The share image's address carries a hash of the picture: sites that show link previews keep
    an image by its address, and would otherwise go on showing an old headline."""
    path = os.path.join(STATIC_DIR, f"og-{lang}.png")
    version = "?v=" + hashlib.sha256(open(path, "rb").read()).hexdigest()[:8] if os.path.isfile(path) else ""
    return f"{ORIGIN}/og-{lang}.png{version}"


def open_graph(target):
    """What a shared link shows. A value that depends on the language is an (es, en) pair and, on
    the site, carries both, so it follows the language switch with the title and the canonical."""
    meta = COPY["meta"]
    site = bool(ORIGIN) and target == "site"
    tags = [("og:type", "website"), ("og:site_name", BRAND),
            ("og:title", (meta["title_es"], meta["title_en"])),
            ("og:description", (meta["desc_es"], meta["desc_en"])),
            ("og:locale", (OG_LOCALE["es"], OG_LOCALE["en"])),
            ("og:locale:alternate", (OG_LOCALE["en"], OG_LOCALE["es"]))]
    if site:
        tags += [("og:url", (ORIGIN + home_path("es"), ORIGIN + home_path("en"))),
                 ("og:image", (share_image("es"), share_image("en"))),
                 ("og:image:width", str(OG_SIZE[0])), ("og:image:height", str(OG_SIZE[1])),
                 ("og:image:alt", (meta["og_alt_es"], meta["og_alt_en"]))]
    out = []
    for k, v in tags:
        if isinstance(v, tuple):
            both = f' data-es-content="{esc(v[0])}" data-en-content="{esc(v[1])}"' if site else ""
            out.append(f'<meta property="{k}" content="{esc(pick(*v))}"{both}>')
        else:
            out.append(f'<meta property="{k}" content="{esc(v)}">')
    if site:
        out.append('<meta name="twitter:card" content="summary_large_image">')
    return "\n".join(out)


def json_ld(target):
    """Who the site belongs to, for search engines: the name, the address of the site, a square
    logo and the contact address. A data block, never executed, so it needs no CSP hash."""
    if not ORIGIN or target != "site":
        return ""
    data = {"@context": "https://schema.org", "@type": "Organization", "@id": f"{ORIGIN}/#organization",
            "name": BRAND, "legalName": ENTITY, "url": f"{ORIGIN}/", "logo": f"{ORIGIN}/icon-512.png",
            "description": pick(COPY["positioning_es"], COPY["positioning_en"])}
    if EMAIL:
        data["email"] = EMAIL
    if LINKEDIN:
        data["sameAs"] = [LINKEDIN]
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


# ---------- the page ----------
# Words that must never reach a published page. They live in an untracked file, advisory/.leakwords
# (one per line), so the guard does not itself publish them in the source.
LEAK_FILE = os.path.join(HERE, ".leakwords")
LEAK = [w.strip().lower() for w in open(LEAK_FILE, encoding="utf-8")] if os.path.exists(LEAK_FILE) else []
LEAK = [w for w in LEAK if w]
# A name the firm no longer goes by: the brand is matched whole, so «SlapSec» never trips it.
OLD_NAMES = re.compile(r"\bSlap\b")


def strip_js(block):
    """Notes in the scripts are for whoever edits them, not for whoever opens DevTools."""
    block = re.sub(r"(?s)/\*.*?\*/\s*", "", block)
    block = re.sub(r"(?m)^[ \t]*//[^\n]*\n", "", block)
    return re.sub(r"(?m)[ \t]{2,}//[^\n]*$", "", block)


def fill(template, fills):
    """One pass over the template: a copy string can never expand into another placeholder."""
    return re.sub(r"\{\{([A-Z_0-9]+)\}\}", lambda m: fills[m.group(1)], template)


def finish(page, target):
    leftover = re.findall(r"\{\{[A-Z_0-9]+\}\}", page)
    assert not leftover, f"unfilled placeholders: {leftover}"
    # Notes are for whoever edits the source, not for whoever reads View Source.
    page = re.sub(r"(?s)<!--.*?-->\s*", "", page)
    page = re.sub(r"(?s)<style>.*?</style>", lambda m: re.sub(r"(?s)/\*.*?\*/\s*", "", m.group(0)), page)
    page = re.sub(r"(?s)<script>.*?</script>", lambda m: strip_js(m.group(0)), page)
    assert "—" not in page and "–" not in page, "em or en dash in output"
    low = page.lower()
    leaked = [w for w in LEAK if w in low]
    assert not leaked, f"internal context leaked into the page: {leaked}"
    assert not OLD_NAMES.search(page), f"a former name in the page: {OLD_NAMES.findall(page)}"
    assert "innerHTML" not in page and "insertAdjacentHTML" not in page and "outerHTML" not in page, "HTML from strings"
    if target == "site":
        assert "googleapis" not in page and "gstatic" not in page, "a third party in the site build"
    return page


def check_launch():
    """A public build needs what the law and a careful reader expect to find."""
    if ORIGIN:
        assert re.fullmatch(r"https://[a-z0-9.-]+\.[a-z]{2,}", ORIGIN), "origin must be https://<domain>"
    if not COPY.get("private", True):
        assert ORIGIN, "a public site needs origin"
        assert EMAIL, "a public site needs contact_email: the contact band and security.txt"
        assert {"legal", "privacy", "cookies"} <= set(PAGES), "a public site needs its legal pages (LSSI-CE art. 10)"
    if EMAIL:
        assert re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", EMAIL), "contact_email"
    for p in PAGES.values():
        for code in LANGS:
            assert re.fullmatch(r"/(?:[a-z]{2}/)?[a-z0-9-]+", p["path"][code]), f"legal path {p['path'][code]}"


def build(target="site", lang=None):
    global LANG
    LANG = lang or ("es" if target == "artifact" else PRIMARY)
    TEMPLATES.clear()
    hero = COPY["sections"][0]
    meta = COPY["meta"]
    nav = "\n".join(
        f'          <li><a href="#{n["anchor"]}" data-es="{esc(n["es"])}" data-en="{esc(n["en"])}">{esc(pick(n["es"], n["en"]))}</a></li>'
        for n in COPY["nav"])
    sections = "\n\n".join(section(s) for s in COPY["sections"][1:])

    fills = {
        "HTML_LANG": HTML_LANG[LANG],
        "TITLE": esc(pick(meta["title_es"], meta["title_en"])),
        "TITLE_ES": esc(meta["title_es"]), "TITLE_EN": esc(meta["title_en"]),
        "DESC": esc(pick(meta["desc_es"], meta["desc_en"])),
        "DESC_ES": esc(meta["desc_es"]), "DESC_EN": esc(meta["desc_en"]),
        "ROBOTS": robots_meta(),
        "VERIFY": verification_meta(target),
        "LINKS": head_links({code: ORIGIN + home_path(code) for code in LANGS}, swap=True) if target == "site" else "",
        "OG": open_graph(target),
        "JSONLD": json_ld(target),
        "ICONS": icons(target),
        "FONT_PRELOADS": font_preloads(target),
        "FONT_FACES": font_faces(target),
        "LOGO_CSS": LOGO_CSS,
        "SKIP": t(*UI["skip"], "a", "skip", ' href="#contenido"'),
        "LOGO_HEAD": logo(),
        "LOGO_FOOT": logo(),
        "NAV": nav,
        "LANG_SWITCH": lang_switch(target),
        "H1": rich(emphasise(hero["headline_es"], "es"), emphasise(hero["headline_en"], "en"), "h1"),
        "STANDFIRST": t(running(hero["body_es"], "es"), running(hero["body_en"], "en"), "p", "standfirst"),
        "FILM_CTL": (f'<button class="film-ctl" type="button" hidden '
                     f'data-pause-es="{esc(UI["pause"][0])}" data-pause-en="{esc(UI["pause"][1])}" '
                     f'data-resume-es="{esc(UI["resume"][0])}" data-resume-en="{esc(UI["resume"][1])}">{esc(ui("pause"))}</button>'),
        "SECTIONS": sections,
        "MENU_NOW": esc(ui("menu")),
        "MENU": esc(UI["menu"][0]), "MENU_EN": esc(UI["menu"][1]),
        "CLOSE": esc(UI["close"][0]), "CLOSE_EN": esc(UI["close"][1]),
        "NAV_LABEL_NOW": esc(ui("nav")),
        "NAV_LABEL": esc(UI["nav"][0]), "NAV_LABEL_EN": esc(UI["nav"][1]),
        "COPYRIGHT": copyright_line(),
        "FOOT_SOCIAL": social(True) if target == "site" else "",
        "FOOT_NOTE": footer_links(True) if (PAGES and target == "site") else "",
        "FILM": read("film.js"),
        "MOTION": read("motion.js"),
        "PISTA_CSS": read("pista.css"),
        "PISTA_JS": read("pista.js"),
    }
    fills["TEMPLATES"] = "\n".join(TEMPLATES)   # last: every rich() call above has registered by now
    page = finish(fill(TEMPLATE, fills), target)

    if target == "artifact":
        # The artifact frame wraps the page in its own document: keep the title, styles, fonts and
        # body, drop the shell. Its gallery name is the firm's name alone.
        body = re.sub(r"(?s)^.*?<head>", "", page)
        body = re.sub(r"(?s)</head>\s*<body[^>]*>", "", body)
        body = re.sub(r"(?s)</body>\s*</html>\s*$", "", body)
        body = re.sub(r'<meta charset="utf-8">\s*', "", body)
        body = re.sub(r'<meta name="viewport"[^>]*>\s*', "", body)
        body = re.sub(r"<title[^>]*>.*?</title>", f"<title>{BRAND}</title>", body, count=1)
        return body.strip() + "\n"
    return page


def build_404():
    global LANG
    LANG = PRIMARY
    fills = {"ICONS": icons("site"), "FONT_FACES": font_faces("site"), "ROBOTS": '<meta name="robots" content="noindex">',
             "TITLE": esc(f"This page does not exist | {BRAND}"), "HOME": home_path(PRIMARY), "HOME_ES": home_path("es"), "HOME_EN": switch_href("en"),
             "WORDMARK": wordmark(), "BRAND": BRAND, "COPYRIGHT": copyright_line(), "LOGO_CSS": LOGO_CSS}
    return finish(fill(read("404.template.html"), fills), "site")


# ---------- headers ----------
PERMISSIONS = ("accelerometer", "autoplay", "bluetooth", "browsing-topics", "camera", "captured-surface-control",
               "compute-pressure", "cross-origin-isolated", "display-capture", "encrypted-media", "fullscreen",
               "gamepad", "geolocation", "gyroscope", "hid", "identity-credentials-get", "idle-detection",
               "keyboard-map", "local-fonts", "magnetometer", "microphone", "midi", "otp-credentials", "payment",
               "picture-in-picture", "publickey-credentials-create", "publickey-credentials-get",
               "screen-wake-lock", "serial", "storage-access", "sync-xhr", "unload", "usb", "web-share",
               "window-management", "xr-spatial-tracking", "clipboard-read", "clipboard-write")

DATA_BLOCK = re.compile(r'<script type="application/ld\+json">.*?</script>', re.S)


def csp_hashes(pages, tag):
    blocks = set()
    for page in pages:
        page = DATA_BLOCK.sub("", page)   # data blocks never run, so they need no hash
        found = re.findall(rf"(?s)<{tag}>(.*?)</{tag}>", page)
        assert len(found) == len(re.findall(rf"<{tag}\b", page)), f"<{tag}> with attributes cannot be hashed here"
        blocks.update(found)
    return " ".join(sorted("'sha256-" + base64.b64encode(hashlib.sha256(b.encode("utf-8")).digest()).decode() + "'"
                           for b in blocks))


# The edge function answers visitors from Spain with a redirect it builds itself, which Netlify
# sends without these headers, so it carries this value too and the build keeps the two in step.
HSTS = "max-age=63072000; includeSubDomains; preload"
EDGE_FUNCTION = os.path.join(ROOT, "netlify", "edge-functions", "geo-lang.ts")


def headers(pages):
    assert f'"Strict-Transport-Security": "{HSTS}"' in open(EDGE_FUNCTION, encoding="utf-8").read(), \
        "geo-lang.ts must send the same Strict-Transport-Security as _headers"
    csp = ("default-src 'none'; "
           f"script-src {csp_hashes(pages, 'script')}; "
           f"style-src {csp_hashes(pages + [FAVICON_SVG], 'style')}; "
           "img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; "
           "require-trusted-types-for 'script'; trusted-types 'none'")
    lines = [
        "# Written by advisory/build_advisory.py on every build. Do not edit by hand: the",
        "# Content-Security-Policy hashes are those of the inline code in every page of this directory,",
        "# and of the style inside favicon.svg, which is served under the same policy.",
        "/*",
        f"  Content-Security-Policy: {csp}",
        f"  Strict-Transport-Security: {HSTS}",
        "  Cross-Origin-Opener-Policy: same-origin",
        "  Cross-Origin-Embedder-Policy: require-corp",
        "  Cross-Origin-Resource-Policy: same-origin",
        "  Permissions-Policy: " + ", ".join(f"{p}=()" for p in PERMISSIONS),
        "  Referrer-Policy: no-referrer",
        "  X-Content-Type-Options: nosniff",
        "  X-Frame-Options: DENY",
    ]
    if COPY.get("private", True):
        lines.append("  X-Robots-Tag: noindex, nofollow, noarchive, nosnippet, noimageindex")
    lines.append("")
    # A year only for the faces whose name is a hash of their content. A wildcard would also pin a
    # missing font's 404, and the licence texts, in every browser that asked for them.
    for _, _, _, name, _ in FACES + PRINT_FACES:
        lines += [f"/fonts/{hashed(name)}", "  Cache-Control: public, max-age=31536000, immutable"]
    lines += [
        "/robots.txt", "  Cache-Control: public, max-age=3600",
        "/.well-known/security.txt", "  Content-Type: text/plain; charset=utf-8", "  Cache-Control: public, max-age=86400",
    ]
    return "\n".join(lines) + "\n"


# Addresses the previous site published, which old shares, caches and indexes still ask for,
# and the places a browser or a scanner looks by habit. No file may exist at a "from" path.
MOVED = (
    ("/og.png", "/og-en.png"),
    ("/brand/favicon.svg", "/favicon.svg"),
    ("/brand/favicon-32.png", "/favicon-32.png"),
    ("/brand/apple-touch-icon.png", "/apple-touch-icon.png"),
    ("/brand/icon-512.png", "/icon-512.png"),
    ("/favicon.ico", "/apple-touch-icon.png"),   # asked for by habit: the opaque icon, which holds on any ground
    ("/security.txt", "/.well-known/security.txt"),
)


def redirects():
    lines = ["# Written by advisory/build_advisory.py on every build. Do not edit by hand."]
    if ORIGIN and NETLIFY_HOST:
        # Netlify's own address for this site serves the same deploy: one host for readers and search.
        # The rule names its host, so branch and preview addresses are left alone.
        lines.append(f"https://{NETLIFY_HOST}/*  {ORIGIN}/:splat  301!")
    for old, new in MOVED:
        assert not os.path.exists(os.path.join(OUT, old.lstrip("/"))), f"{old} exists, so its redirect would never fire"
        assert os.path.isfile(os.path.join(OUT, new.lstrip("/"))), f"{old} points at {new}, which the build did not write"
        lines.append(f"{old}  {new}  301")
    return "\n".join(lines) + "\n"


def sitemap():
    def entry(urls, loc):
        alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{code}" href="{urls[code]}"/>' for code in LANGS)
        alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{urls[PRIMARY]}"/>'
        return f"  <url>\n    <loc>{loc}</loc>{alts}\n    <lastmod>{TODAY.isoformat()}</lastmod>\n  </url>"
    groups = [{code: ORIGIN + home_path(code) for code in LANGS}]
    groups += [{code: ORIGIN + legal_url(key, code) for code in LANGS} for key in PAGES]
    urls = [entry(g, g[code]) for g in groups for code in (PRIMARY,) + tuple(c for c in LANGS if c != PRIMARY)]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(urls) + "\n</urlset>\n")


def write_site():
    pages = {}
    for code in LANGS:
        pages[os.path.join(home_path(code).lstrip("/"), "index.html")] = build("site", code)
    for key in PAGES:
        for code in LANGS:
            pages[legal_file(key, code)] = legal_page(key, code)
    pages["404.html"] = build_404()

    # publish/ belongs to this build alone: nothing survives from a build that did not write it
    assert os.path.basename(OUT) == "publish" and os.path.dirname(OUT) == ROOT, OUT
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "fonts"))
    for rel, text in pages.items():
        path = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)
    for _, _, _, name, _ in FACES + PRINT_FACES:
        shutil.copyfile(os.path.join(FONTS_DIR, name), os.path.join(OUT, "fonts", hashed(name)))
    for f in sorted(os.listdir(FONTS_DIR)):
        if f.startswith("OFL"):
            shutil.copyfile(os.path.join(FONTS_DIR, f), os.path.join(OUT, "fonts", f))
    for f in ICON_FILES:
        shutil.copyfile(os.path.join(STATIC_DIR, f), os.path.join(OUT, f))
    for code in LANGS:
        og = os.path.join(STATIC_DIR, f"og-{code}.png")
        if os.path.exists(og):
            shutil.copyfile(og, os.path.join(OUT, f"og-{code}.png"))
        else:
            print(f"  warning: {os.path.relpath(og, ROOT)} is missing: run advisory/tools/make_og.py")
    private = COPY.get("private", True)
    robots = "User-agent: *\n" + ("Disallow: /\n" if private else "Allow: /\n")
    if ORIGIN and not private:
        robots += f"\nSitemap: {ORIGIN}/sitemap.xml\n"
        open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(sitemap())
    open(os.path.join(OUT, "robots.txt"), "w").write(robots)
    if ORIGIN and EMAIL:
        # RFC 9116: a role address, and an expiry under a year, renewed on every build
        os.makedirs(os.path.join(OUT, ".well-known"))
        expires = (datetime.now(timezone.utc) + timedelta(days=360)).strftime("%Y-%m-%dT%H:%M:%SZ")
        langs = ", ".join((PRIMARY,) + tuple(c for c in LANGS if c != PRIMARY))
        open(os.path.join(OUT, ".well-known", "security.txt"), "w").write(
            f"Contact: mailto:{EMAIL}\nExpires: {expires}\nPreferred-Languages: {langs}\n"
            f"Canonical: {ORIGIN}/.well-known/security.txt\n")
    open(os.path.join(OUT, "_headers"), "w").write(headers(list(pages.values())))
    open(os.path.join(OUT, "_redirects"), "w").write(redirects())
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
    print(f"  wrote publish/ ({len(pages)} pages, {size:,} bytes in all)")


def check_copy():
    """Every visible string: typographer's apostrophes and quotes only, no dashes."""
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k not in ("origin", "contact_email", "path", "iso"):
                    yield from walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, f"{path}[{i}]")
        elif isinstance(o, str):
            yield path, o
    for name, doc in (("copy.json", COPY), ("legal.json", LEGAL)):
        for path, v in walk(doc):
            assert "{{" not in v and "}}" not in v, f"placeholder syntax in {name}{path}"
            assert "'" not in v and '"' not in v, f"straight quote in {name}{path}"
            assert "—" not in v and "–" not in v, f"dash in {name}{path}"


TEMPLATE = read("template.html")

if __name__ == "__main__":
    if not LEAK:
        print("  warning: advisory/.leakwords is missing, so the leak guard is off")
    check_copy()
    check_subsets()
    check_launch()
    write_site()
    if "--artifact" in sys.argv:
        path = sys.argv[sys.argv.index("--artifact") + 1]
        body = build("artifact")
        open(path, "w", encoding="utf-8").write(body)
        print(f"  wrote {path} ({len(body):,} bytes)")
