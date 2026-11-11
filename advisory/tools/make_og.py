#!/usr/bin/env python3
"""Draw the share images, one per language, from the site's own words, fonts and wordmark.

    python3 advisory/tools/make_og.py

  static/og-en.png, static/og-es.png   1200 x 630, what a link to / or /es/ shows when shared

The card is the hero without the film: black ground, the scope wordmark, the headline in the
serif with its last clause in italic, and the descriptor in mono over a hairline. Chrome renders
it (headless, from a file with the fonts inlined), so the type is exactly the site's. Set CHROME
to use a browser somewhere other than the default macOS location.
"""
import base64
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build_advisory as b  # noqa: E402  the words, the typography and the wordmark live in the build

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
W, H = b.OG_SIZE


def face(family, style, weight, name):
    data = base64.b64encode(b.font_bytes(name)).decode()
    return (f'@font-face{{font-family:"{family}";font-style:{style};font-weight:{weight};font-display:block;'
            f'src:url(data:font/woff2;base64,{data}) format("woff2")}}')


def card(lang):
    b.LANG = lang
    hero = b.COPY["sections"][0]
    headline = b.emphasise(hero[f"headline_{lang}"], lang)
    desc = b.esc(b.COPY[f"descriptor_{lang}"])
    faces = "\n".join(face(f, s, w, n) for f, s, w, n, _ in b.FACES)
    return f"""<!DOCTYPE html>
<html lang="{b.HTML_LANG[lang]}"><head><meta charset="utf-8"><style>
{faces}
:root{{--black:#050505;--on-dark:#f4f4f2;--on-dark-2:#9a9a97;--line-dark:#232326;--green:#67e18f;
  --sans:"Schibsted Grotesk",Arial,sans-serif}}
html,body{{margin:0;width:{W}px;height:{H}px;background:var(--black);overflow:hidden}}
body{{box-sizing:border-box;padding:60px 72px 56px;display:flex;flex-direction:column;justify-content:space-between;
  color:var(--on-dark);-webkit-font-smoothing:antialiased}}
.logo{{display:flex}}
{b.LOGO_CSS.replace("font-size:1.3125rem", "font-size:36px")}
h1{{margin:0;font-family:"Newsreader",Georgia,serif;font-weight:300;font-size:60px;line-height:1.06;letter-spacing:-.022em;
  max-width:15.2em;text-wrap:balance}}
h1 em{{display:block;font-style:italic}}
.base{{margin-top:34px;padding-top:22px;border-top:1px solid var(--line-dark);display:flex;justify-content:space-between;gap:24px;
  font-family:"JetBrains Mono",monospace;font-size:15px;letter-spacing:.16em;text-transform:uppercase;color:var(--on-dark-2)}}
</style></head><body>
<div class="logo">{b.wordmark()}</div>
<div><h1>{headline}</h1><div class="base"><span>{desc}</span><span>{b.DOMAIN}</span></div></div>
</body></html>"""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for lang in b.LANGS:
            src = os.path.join(tmp, f"og-{lang}.html")
            open(src, "w", encoding="utf-8").write(card(lang))
            out = os.path.join(b.STATIC_DIR, f"og-{lang}.png")
            subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                            f"--user-data-dir={os.path.join(tmp, 'profile')}", "--no-first-run",
                            f"--window-size={W},{H}", "--virtual-time-budget=4000", f"--screenshot={out}",
                            "file://" + src], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  {os.path.relpath(out, ROOT)}: {os.path.getsize(out):,} bytes")


if __name__ == "__main__":
    main()
