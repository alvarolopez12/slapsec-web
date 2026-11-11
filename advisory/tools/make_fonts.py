#!/usr/bin/env python3
"""Derive the site's font files from the Google Fonts latin files in fonts/source/.

    python3 advisory/tools/make_fonts.py

  newsreader-300-italic-hero.woff2      the italic, cut to the hero's clause (ES and EN)
  schibsted-grotesk-italic-loans.woff2  the italic, cut to the loanwords
  schibsted-grotesk-400.woff2           running text, a static instance of the variable file
  schibsted-grotesk-800-wordmark.woff2  the wordmark, static and cut to its letters
  newsreader-300-print.woff2            print only: static instances at optical size 18,
  newsreader-300-italic-print.woff2     because a PDF cannot carry variable fonts as text

The cut files record their characters in fonts/subsets.json, which the build checks: if the
hero clause, a loanword or the name changes, the build stops and asks for this to be run again.
Requires fontTools with brotli (pip install fonttools brotli).
"""
import json
import os
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "fonts")
sys.path.insert(0, ROOT)
import build_advisory as b  # noqa: E402  the clause and the loanwords live in the build


def cut(font, text):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    return font


def save(font, name):
    font.flavor = "woff2"
    path = os.path.join(FONTS, name)
    font.save(path)
    print(f"  {name}: {os.path.getsize(path):,} bytes")


def source(name):
    return TTFont(os.path.join(FONTS, "source", name))


record = {}
spaces = " " + b.NBSP

hero = b.EMPHASIS["es"] + b.EMPHASIS["en"] + spaces
save(cut(source("newsreader-300-italic.woff2"), hero), "newsreader-300-italic-hero.woff2")
record["newsreader-300-italic-hero.woff2"] = "".join(sorted(set(hero)))

loans = "".join(b.LOANS) + spaces
save(cut(source("schibsted-grotesk-italic.woff2"), loans), "schibsted-grotesk-italic-loans.woff2")
record["schibsted-grotesk-italic-loans.woff2"] = "".join(sorted(set(loans)))

save(instancer.instantiateVariableFont(source("schibsted-grotesk.woff2"), {"wght": 400}), "schibsted-grotesk-400.woff2")
mark = b.BRAND
save(cut(instancer.instantiateVariableFont(source("schibsted-grotesk.woff2"), {"wght": 800}), mark), "schibsted-grotesk-800-wordmark.woff2")
record["schibsted-grotesk-800-wordmark.woff2"] = "".join(sorted(set(mark)))

save(instancer.instantiateVariableFont(TTFont(os.path.join(FONTS, "newsreader-300.woff2")), {"opsz": 18}), "newsreader-300-print.woff2")
save(instancer.instantiateVariableFont(cut(source("newsreader-300-italic.woff2"), hero), {"opsz": 18}), "newsreader-300-italic-print.woff2")

json.dump(record, open(os.path.join(FONTS, "subsets.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
