#!/usr/bin/env python3
"""Generate every brand's site from the single source in src/.

    python3 build.py            # build all brands
    python3 build.py slapsec    # build one

src/ is the only thing anyone edits. It carries the i18n attributes
(data-en / data-es / *-html / *-ph / *-aria / *-title) and {{TOKEN}}
placeholders for everything brand- or entity-specific. Each brand in
brands/*.json supplies the token values, its languages and its publish
directory; both publish directories are generated and committed, because
Netlify runs no build step.

Adding a brand is a JSON file plus a favicon set. Editing copy is one
edit in src/, and every brand picks it up on the next build.
"""
import json
import os
import re
import shutil
import sys
from bs4 import BeautifulSoup, NavigableString

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
BRANDS = os.path.join(ROOT, "brands")

PAGES = ["index.html", "legal.html", "privacy.html", "cookies.html", "404.html"]
PLAIN = ["robots.txt", "sitemap.xml", "site.webmanifest", "_headers"]

# Head copy differs per language and per brand, so it lives here rather than in
# the markup. {brand} is filled from the brand config.
HEAD = {
    "en": {
        "title": "Cybersecurity Consulting: Red Team, Zero Trust | {brand}",
        "desc": ("Senior cybersecurity consulting for enterprises and SMBs: red team, Zero Trust, "
                 "GRC and compliance. Big Four judgment, without the overhead."),
        "og_title": "{brand}: Senior cybersecurity. Democratized.",
        "og_desc": ("Same rigor as tier-1 firms, without the overhead. Red team & threat intel, "
                    "Zero Trust, GRC & compliance, data security and automation. Senior-only team."),
        "tw_desc": "Same rigor as tier-1 firms, without the overhead. Senior-only cybersecurity consulting.",
        "schema_desc": ("Independent senior cybersecurity consulting. Red team & threat intel, "
                        "Zero Trust architecture, GRC & compliance, data security and automation. "
                        "Same rigor as tier-1 firms, without the overhead."),
        "slogan": "Senior cybersecurity. Democratized.",
        "image_alt": "{brand}, senior cybersecurity consulting",
        "locale": "en_US",
    },
    "es": {
        "title": "Ciberseguridad para pymes: Red Team y Zero Trust | {brand}",
        "desc": ("Consultoría de ciberseguridad senior para pymes y gran empresa: red team, Zero Trust, "
                 "GRC y compliance. El criterio de las Big Four, sin el overhead."),
        "og_title": "{brand}: Ciberseguridad senior. Democratizada.",
        "og_desc": ("Mismo rigor que las firmas tier-1, sin el overhead. Red team y threat intel, "
                    "Zero Trust, GRC y compliance, dato y automatización. Para pymes y gran empresa."),
        "tw_desc": "Mismo rigor que las firmas tier-1, sin el overhead. Consultoría de ciberseguridad senior.",
        "schema_desc": ("Consultoría de ciberseguridad senior independiente. Red team y threat intel, "
                        "arquitectura Zero Trust, GRC y compliance, seguridad del dato y automatización. "
                        "Mismo rigor que las firmas tier-1, sin el overhead."),
        "slogan": "Ciberseguridad senior. Democratizada.",
        "image_alt": "{brand}, consultoría de ciberseguridad senior",
        "locale": "es_ES",
    },
}


def clean(t):
    """get_text(" ") inserts a space at every inline-element boundary, which leaves
    artifacts like "2-6 weeks , red team". The JSON-LD must match what a reader sees."""
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:!?%)\]])", r"\1", t)
    t = re.sub(r"([(\[])\s+", r"\1", t)
    return t.strip()


def fill(text, brand):
    """Replace every {{TOKEN}} with its value for this brand.

    {{#TOKEN}}...{{/TOKEN}} keeps its body only when the brand defines a non-empty
    TOKEN, so a clause that does not apply to an entity is omitted rather than
    shipped with a placeholder in it."""
    def block(m):
        key, body = m.group(1), m.group(2)
        return body if brand.get(key) else ""
    text = re.sub(r"\{\{#([A-Z_]+)\}\}(.*?)\{\{/\1\}\}", block, text, flags=re.S)

    def sub(m):
        key = m.group(1)
        if key not in brand:
            raise KeyError(f"{brand['id']}: no value for token {{{{{key}}}}}")
        return str(brand[key])
    return re.sub(r"\{\{([A-Z_]+)\}\}", sub, text)


def path_for(lang, brand, page="index.html"):
    """Primary language sits at the root; the other one gets a /<lang>/ prefix."""
    if lang == brand["primary_lang"]:
        return page
    return os.path.join(lang, page)


def url_for(lang, brand):
    return brand["ORIGIN"] + "/" if lang == brand["primary_lang"] else f"{brand['ORIGIN']}/{lang}/"


def bake(soup, lang):
    """Turn the i18n attributes into static text for one language, so crawlers and
    no-JS visitors get the full page rather than a fallback stub."""
    for el in soup.select(f"[data-{lang}]"):
        el.clear()
        el.append(NavigableString(el.get(f"data-{lang}")))
    for el in soup.select(f"[data-{lang}-html]"):
        el.clear()
        for c in list(BeautifulSoup(el.get(f"data-{lang}-html"), "html.parser").contents):
            el.append(c)
    for el in soup.select(f"[data-{lang}-ph]"):
        el["placeholder"] = el.get(f"data-{lang}-ph")
    for el in soup.select(f"[data-{lang}-aria]"):
        el["aria-label"] = el.get(f"data-{lang}-aria")
    for el in soup.select(f"[data-{lang}-title]"):
        el["title"] = el.get(f"data-{lang}-title")


def set_head(soup, lang, brand):
    h = {k: (v.format(brand=brand["BRAND"]) if isinstance(v, str) else v)
         for k, v in HEAD[lang].items()}
    other = [l for l in brand["languages"] if l != lang]

    soup.find("html")["lang"] = lang
    if soup.title:
        soup.title.string = h["title"]

    def meta(attr, key, val):
        m = soup.find("meta", attrs={attr: key})
        if m:
            m["content"] = val

    meta("name", "description", h["desc"])
    meta("property", "og:title", h["og_title"])
    meta("property", "og:description", h["og_desc"])
    meta("name", "twitter:title", h["og_title"])
    meta("name", "twitter:description", h["tw_desc"])
    meta("property", "og:url", url_for(lang, brand))
    meta("property", "og:locale", h["locale"])
    meta("property", "og:image:alt", h["image_alt"])
    meta("name", "twitter:image:alt", h["image_alt"])
    if other:
        meta("property", "og:locale:alternate", HEAD[other[0]]["locale"])

    can = soup.find("link", attrs={"rel": "canonical"})
    if can:
        can["href"] = url_for(lang, brand)

    # hreflang: one per language this brand serves, plus x-default on the primary,
    # emitted in a stable order so the generated diff stays readable
    for link in soup.find_all("link", attrs={"rel": "alternate"}):
        link.decompose()
    after = can
    for l in sorted(brand["languages"]) + ["x-default"]:
        href = url_for(brand["primary_lang"] if l == "x-default" else l, brand)
        tag = soup.new_tag("link", rel="alternate", hreflang=l, href=href)
        after.insert_after(tag)
        after = tag


def set_schema(soup, lang, brand):
    h = {k: (v.format(brand=brand["BRAND"]) if isinstance(v, str) else v)
         for k, v in HEAD[lang].items()}
    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if sc.get("id"):
            continue
        d = json.loads(sc.string)
        d["description"] = h["schema_desc"]
        d["slogan"] = h["slogan"]
        d["inLanguage"] = lang
        d["url"] = url_for(lang, brand)
        sc.string = "\n" + json.dumps(d, ensure_ascii=False, indent=2) + "\n"
        break

    faq = soup.find("script", id="faq-schema")
    if faq is not None:
        items = []
        for item in soup.select(".faq-item"):
            items.append({
                "@type": "Question",
                "name": clean(item.select_one(".faq-q-text").get_text(" ", strip=True)),
                "acceptedAnswer": {"@type": "Answer",
                                   "text": clean(item.select_one(".faq-a-inner").get_text(" ", strip=True))},
            })
        faq.string = "\n" + json.dumps(
            {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items},
            ensure_ascii=False, indent=1) + "\n"


def set_lang_toggle(soup, lang, brand):
    """Point each toggle at this brand's own URL for that language, mark the active one,
    and drop any button for a language this brand does not serve. A brand with a single
    language has nothing to toggle, so the whole control goes."""
    if len(brand["languages"]) < 2:
        for w in soup.select(".lang-switch"):
            w.decompose()
        return
    for b in soup.select(".lang-btn"):
        l = b.get("data-lang")
        if l not in brand["languages"]:
            b.decompose()
            continue
        b["href"] = "/" if l == brand["primary_lang"] else f"/{l}/"
        if l == lang:
            b["class"] = ["lang-btn", "active"]
            b["aria-current"] = "page"
        else:
            b["class"] = ["lang-btn"]
            if b.has_attr("aria-current"):
                del b["aria-current"]
            # an explicit choice must survive the geo redirect at the edge
            if l == brand["primary_lang"]:
                b["href"] = f"/?lang={l}"


def tidy(html):
    """bs4 leaves the whitespace text nodes behind when links are decomposed, and puts
    freshly inserted tags back to back. Normalise the head so the generated diff is
    readable and each link sits on its own line."""
    html = re.sub(r'(<link[^>]*rel="alternate"[^>]*/>)(?=<link)', r"\1\n", html)
    html = re.sub(r'(rel="canonical"/>)(?=<link)', r"\1\n", html)
    html = re.sub(r"\n{3,}", "\n", html)
    return html


WRITTEN = []


def write(path, text):
    WRITTEN.append(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if text.lstrip().lower().startswith("<!doctype") or not path.endswith(".html"):
        open(path, "w", encoding="utf-8").write(text)
    else:
        open(path, "w", encoding="utf-8").write("<!DOCTYPE html>\n" + text)


def build_index(brand, out):
    raw = fill(open(os.path.join(SRC, "index.html"), encoding="utf-8").read(), brand)
    for lang in brand["languages"]:
        soup = BeautifulSoup(raw, "html.parser")
        bake(soup, lang)
        set_head(soup, lang, brand)
        set_schema(soup, lang, brand)
        set_lang_toggle(soup, lang, brand)
        home = "/" if lang == brand["primary_lang"] else f"/{lang}/"
        for a in soup.select("a.logo"):
            a["href"] = home
        write(os.path.join(out, path_for(lang, brand)), tidy(str(soup)))


def build_secondary(brand, out):
    """The legal pages carry both languages inline and toggle with JS, so they only
    need token substitution plus the language buttons this brand actually serves."""
    for page in PAGES[1:]:
        raw = fill(open(os.path.join(SRC, page), encoding="utf-8").read(), brand)
        served = set(brand["languages"])
        if served >= {"en", "es"}:
            write(os.path.join(out, page), raw)
            continue
        soup = BeautifulSoup(raw, "html.parser")
        for b in soup.select(".lang button"):
            if b.get("data-l") not in served:
                b.decompose()
        if len(brand["languages"]) < 2:
            for w in soup.select(".lang"):
                w.decompose()
            for art in soup.select("article[data-lang]"):
                if art.get("data-lang") != brand["primary_lang"]:
                    art.decompose()
                elif art.has_attr("hidden"):
                    del art["hidden"]
        write(os.path.join(out, page), str(soup))


def build_sitemap(brand, out):
    urls = []
    alts = "".join(
        f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{url_for(l, brand)}"/>'
        for l in brand["languages"]
    ) + f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{url_for(brand["primary_lang"], brand)}"/>'
    for l in brand["languages"]:
        urls.append(f'  <url>\n    <loc>{url_for(l, brand)}</loc>{alts}\n'
                    f'    <lastmod>{brand["lastmod"]}</lastmod>\n'
                    f'    <changefreq>monthly</changefreq>\n    <priority>1.0</priority>\n  </url>')
    for page in ["privacy.html", "legal.html", "cookies.html"]:
        urls.append(f'  <url>\n    <loc>{brand["ORIGIN"]}/{page}</loc>\n'
                    f'    <lastmod>{brand["lastmod"]}</lastmod>\n'
                    f'    <changefreq>yearly</changefreq>\n    <priority>0.3</priority>\n  </url>')
    write(os.path.join(out, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
          '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
          + "\n".join(urls) + "\n</urlset>\n")


def build_assets(brand, out):
    """Per-brand favicons and OG image come from src/brand-<id>/; anything else in
    src/ that is not a template is copied through."""
    brand_dir = os.path.join(SRC, f"brand-{brand['id']}")
    if not os.path.isdir(brand_dir):
        raise SystemExit(f"missing {brand_dir} (favicons, logo, og.png for this brand)")
    dst = os.path.join(out, "brand")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(brand_dir, dst)
    og = os.path.join(dst, "og.png")
    if os.path.exists(og):
        shutil.move(og, os.path.join(out, "og.png"))
        WRITTEN.append(os.path.join(out, "og.png"))
    for f in sorted(os.listdir(dst)):
        WRITTEN.append(os.path.join(dst, f))
    wk = os.path.join(SRC, ".well-known")
    if os.path.isdir(wk):
        for f in sorted(os.listdir(wk)):
            write(os.path.join(out, ".well-known", f),
                  fill(open(os.path.join(wk, f), encoding="utf-8").read(), brand))


def prune(brand, out, written):
    """Delete anything under the output directory this build did not produce.

    Without this, a file the config stops generating survives, gets committed and
    ships: dropping src/_redirects.slapsec once left a stale _redirects live that
    301'd /es/ to a domain that was not ready."""
    keep = {os.path.normpath(p) for p in written}
    for root, dirs, files in os.walk(out, topdown=False):
        for f in files:
            full = os.path.normpath(os.path.join(root, f))
            if full not in keep:
                os.remove(full)
                print(f"  pruned stale {os.path.relpath(full, ROOT)}")
        for d in dirs:
            full = os.path.join(root, d)
            if not os.listdir(full):
                os.rmdir(full)


def build(brand):
    WRITTEN.clear()
    out = os.path.join(ROOT, brand["publish"])
    build_index(brand, out)
    build_secondary(brand, out)
    build_sitemap(brand, out)
    for f in ["robots.txt", "site.webmanifest", "_headers"]:
        write(os.path.join(out, f), fill(open(os.path.join(SRC, f), encoding="utf-8").read(), brand))
    red = os.path.join(SRC, f"_redirects.{brand['id']}")
    if os.path.exists(red):
        write(os.path.join(out, "_redirects"), fill(open(red, encoding="utf-8").read(), brand))
    build_assets(brand, out)
    prune(brand, out, WRITTEN)
    langs = "+".join(brand["languages"])
    print(f"  built {brand['BRAND']:9s} -> {brand['publish']}/  ({langs}, primary {brand['primary_lang']})")


def main():
    wanted = sys.argv[1:]
    files = sorted(f for f in os.listdir(BRANDS) if f.endswith(".json"))
    built = 0
    for f in files:
        brand = json.load(open(os.path.join(BRANDS, f), encoding="utf-8"))
        if wanted and brand["id"] not in wanted:
            continue
        brand.setdefault("lastmod", "2026-09-22")
        build(brand)
        built += 1
    if not built:
        raise SystemExit(f"no brand matched {wanted}; have {[f[:-5] for f in files]}")


if __name__ == "__main__":
    main()
