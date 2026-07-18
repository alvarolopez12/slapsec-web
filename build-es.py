#!/usr/bin/env python3
"""Regenerate the Spanish page (publish/es/index.html) from the English source
(publish/index.html). Bakes the data-es / data-es-html / data-es-ph values in as
static Spanish content (mirrors the old JS setLang('es')), and sets the ES head
(lang, title, description, canonical, og:locale, social) + hreflang.

EN (publish/index.html) is the source of truth. After editing it, run:  python3 build-es.py
Requires: beautifulsoup4  (pip install beautifulsoup4)
"""
import os
from bs4 import BeautifulSoup, NavigableString

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "publish", "index.html")
OUT_DIR = os.path.join(ROOT, "publish", "es")
OUT = os.path.join(OUT_DIR, "index.html")

ES_TITLE = "Consultoría de Ciberseguridad — Pentest y Red Team | SlapSec"
ES_DESC = ("Consultoría de ciberseguridad senior independiente. Red team, pentest, "
           "Digital Risk Radar, Zero Trust, seguridad del dato (DLP/DSPM) y automatización "
           "con IA. El criterio de las Big Four, sin el overhead.")
ES_OG_TITLE = "SlapSec — Ciberseguridad senior. Democratizada."
ES_OG_DESC = ("Mismo rigor que las firmas tier-1, sin el overhead. Red team, pentest, "
              "Digital Risk Radar, Zero Trust, seguridad del dato y automatización con IA.")
ES_TW_DESC = "Mismo rigor que las firmas tier-1, sin el overhead. Consultoría de ciberseguridad senior."

soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")

# 1) html lang
soup.find("html")["lang"] = "es"

# 2) bake Spanish content (same order as the former setLang('es'))
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
soup.find("link", attrs={"rel": "canonical"})["href"] = "https://slapsec.com/es/"

# 4) language toggle: ES button active (pre-JS static state)
for b in soup.select(".lang-btn"):
    if b.get("data-lang") == "es":
        b["class"] = ["lang-btn", "active"]; b["aria-pressed"] = "true"
    else:
        b["class"] = ["lang-btn"]; b["aria-pressed"] = "false"

os.makedirs(OUT_DIR, exist_ok=True)
out = str(soup)
if not out.lstrip().lower().startswith("<!doctype"):
    out = "<!DOCTYPE html>\n" + out
open(OUT, "w", encoding="utf-8").write(out)
print("Wrote", OUT, "(%d bytes)" % os.path.getsize(OUT))
