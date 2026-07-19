#!/usr/bin/env python3
"""Regenerate the Spanish page (publish/es/index.html) from the English source
(publish/index.html). Bakes the data-es / data-es-html / data-es-ph values in as
static Spanish content, sets the ES head (lang, title, description, canonical,
og:locale, social), localizes the JSON-LD blocks (org + FAQPage) and flips the
language-toggle links.

EN (publish/index.html) is the source of truth. After editing it, run:  python3 build-es.py
Requires: beautifulsoup4  (pip install beautifulsoup4)
"""
import json
import os
from bs4 import BeautifulSoup, NavigableString

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "publish", "index.html")
OUT_DIR = os.path.join(ROOT, "publish", "es")
OUT = os.path.join(OUT_DIR, "index.html")

ES_TITLE = "Ciberseguridad para Pymes y Empresas — Red Team, GRC y Zero Trust | SlapSec"
ES_DESC = ("Consultoría de ciberseguridad senior para pymes y gran empresa. Red team y threat intel, "
           "Zero Trust, GRC y compliance (ENS, ISO 27001), vCISO, dato y automatización. "
           "El criterio de las Big Four, sin el overhead.")
ES_OG_TITLE = "SlapSec — Ciberseguridad senior. Democratizada."
ES_OG_DESC = ("Mismo rigor que las firmas tier-1, sin el overhead. Red team y threat intel, "
              "Zero Trust, GRC y compliance, dato y automatización. Para pymes y gran empresa.")
ES_TW_DESC = "Mismo rigor que las firmas tier-1, sin el overhead. Consultoría de ciberseguridad senior."
ES_SCHEMA_DESC = ("Consultoría de ciberseguridad senior independiente. Red team y threat intel, "
                  "arquitectura Zero Trust, GRC y compliance, seguridad del dato y automatización. "
                  "Mismo rigor que las firmas tier-1, sin el overhead.")
ES_SLOGAN = "Ciberseguridad senior. Democratizada."

# ---- Step 0: bake ENGLISH statically into the source page itself ----
# (data-en / data-en-html / data-en-ph attrs stay as the i18n source of truth;
#  the visible static text is derived from them, so crawlers and no-JS visitors
#  always see the FULL English content, not fallback stubs.)
en = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")
for el in en.select("[data-en]"):
    el.clear(); el.append(NavigableString(el.get("data-en")))
for el in en.select("[data-en-html]"):
    el.clear()
    for c in list(BeautifulSoup(el.get("data-en-html"), "html.parser").contents):
        el.append(c)
for el in en.select("[data-en-ph]"):
    el["placeholder"] = el.get("data-en-ph")
# keep EN FAQPage schema in sync with the baked EN DOM
_faq = en.find("script", id="faq-schema")
if _faq is not None:
    _items = []
    for item in en.select(".faq-item"):
        _q = item.select_one(".faq-q-text").get_text(" ", strip=True)
        _a = item.select_one(".faq-a-inner").get_text(" ", strip=True)
        _items.append({"@type": "Question", "name": _q,
                       "acceptedAnswer": {"@type": "Answer", "text": _a}})
    _faq.string = "\n" + json.dumps(
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": _items},
        ensure_ascii=False, indent=1) + "\n"
_out = str(en)
if not _out.lstrip().lower().startswith("<!doctype"):
    _out = "<!DOCTYPE html>\n" + _out
open(SRC, "w", encoding="utf-8").write(_out)
print("Baked EN statics into", SRC)

# ---- Spanish page ----
soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")

# 1) html lang
soup.find("html")["lang"] = "es"

# 2) bake Spanish content (mirrors the former setLang('es'))
for el in soup.select("[data-es]"):
    el.clear(); el.append(NavigableString(el.get("data-es")))
for el in soup.select("[data-es-html]"):
    el.clear()
    for c in list(BeautifulSoup(el.get("data-es-html"), "html.parser").contents):
        el.append(c)
for el in soup.select("[data-es-ph]"):
    el["placeholder"] = el.get("data-es-ph")

# 3) ES head
soup.title.string = ES_TITLE
def setmeta(attr, key, val):
    m = soup.find("meta", attrs={attr: key})
    if m:
        m["content"] = val
setmeta("name", "description", ES_DESC)
setmeta("property", "og:title", ES_OG_TITLE)
setmeta("property", "og:description", ES_OG_DESC)
setmeta("name", "twitter:title", ES_OG_TITLE)
setmeta("name", "twitter:description", ES_TW_DESC)
setmeta("property", "og:url", "https://slapsec.com/es/")
setmeta("property", "og:locale", "es_ES")
setmeta("property", "og:locale:alternate", "en_US")
setmeta("property", "og:image:alt", "SlapSec — consultoría de ciberseguridad senior")
soup.find("link", attrs={"rel": "canonical"})["href"] = "https://slapsec.com/es/"

# 4) localize org JSON-LD (first ld+json script, no id)
for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
    if sc.get("id"):
        continue
    d = json.loads(sc.string)
    d["description"] = ES_SCHEMA_DESC
    d["slogan"] = ES_SLOGAN
    d["inLanguage"] = "es"
    sc.string = "\n" + json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    break

# 5) regenerate FAQPage JSON-LD in Spanish from the baked DOM
faq_schema = soup.find("script", id="faq-schema")
if faq_schema is not None:
    faqs = []
    for item in soup.select(".faq-item"):
        q = item.select_one(".faq-q-text").get_text(" ", strip=True)
        a = item.select_one(".faq-a-inner").get_text(" ", strip=True)
        faqs.append({"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}})
    faq_schema.string = "\n" + json.dumps(
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqs},
        ensure_ascii=False, indent=1) + "\n"

# 6) language toggle links: ES active
for b in soup.select(".lang-btn"):
    if b.get("data-lang") == "es":
        b["class"] = ["lang-btn", "active"]; b["aria-current"] = "page"
    else:
        b["class"] = ["lang-btn"]
        if b.has_attr("aria-current"):
            del b["aria-current"]
        # explicit EN choice must bypass the Spain geo-redirect at the edge
        if b.get("data-lang") == "en":
            b["href"] = "/?lang=en"

os.makedirs(OUT_DIR, exist_ok=True)
out = str(soup)
if not out.lstrip().lower().startswith("<!doctype"):
    out = "<!DOCTYPE html>\n" + out
open(OUT, "w", encoding="utf-8").write(out)
print("Wrote", OUT, "(%d bytes)" % os.path.getsize(OUT))
