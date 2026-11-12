#!/usr/bin/env python3
"""The tab icons, from one drawing: the scope's two brackets on a 16-unit grid (a margin of 1, a
stroke of 2, arms of 8), with no tile behind them.

    python3 advisory/tools/make_icons.py

Why no tile: Safari in dark appearance sets any icon it judges too dark on a white plate, and a
near-black square is exactly that. Bare brackets in the bright green are left alone, and on the
16-unit grid their edges land on whole pixels at 16 and at 32.

- favicon.svg     Chrome, Edge and Firefox. The green for light grounds by default, the bright one
                  when the browser is dark. Safari ignores that query inside an icon, so one rule
                  that only WebKit understands keeps the bright green there too.
- favicon-32.png  Safari, which takes the icon that declares a size, and older browsers: the
                  bright green on transparency.

The touch icon and the 512px logo keep their black tile, because a home screen and a search result
want an opaque picture. A file is rewritten only when its bytes change.
"""
import os
import struct
import zlib

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
ON_DARK, ON_LIGHT = "#67e18f", "#00a24f"
# Each bracket as two rectangles (x0, y0, x1, y1) on the 16-unit grid: top-left, then bottom-right.
RECTS = ((1, 1, 9, 3), (1, 1, 3, 9), (7, 13, 15, 15), (13, 7, 15, 15))
PATH = "M1 1h8v2H3v6H1zM15 15H7v-2h6V7h2z"

SVG = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><style>'
       f"@media (prefers-color-scheme:dark){{path{{fill:{ON_DARK}}}}}"
       f"@supports (font:-apple-system-body){{path{{fill:{ON_DARK}}}}}"
       f'</style><path fill="{ON_LIGHT}" d="{PATH}"/></svg>\n')


def png(size, colour):
    """The brackets at `size` pixels (a multiple of 16), in one colour on transparency."""
    k, rgb = size // 16, bytes.fromhex(colour.lstrip("#"))
    assert size == 16 * k
    on = [[any(x0 * k <= x < x1 * k and y0 * k <= y < y1 * k for x0, y0, x1, y1 in RECTS) for x in range(size)]
          for y in range(size)]
    raw = b"".join(b"\x00" + b"".join(rgb + b"\xff" if px else b"\x00\x00\x00\x00" for px in row) for row in on)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def write(name, data):
    path = os.path.join(STATIC, name)
    same = os.path.isfile(path) and open(path, "rb").read() == data
    if not same:
        open(path, "wb").write(data)
    print(f"  {name}: {'unchanged' if same else f'{len(data):,} bytes'}")


if __name__ == "__main__":
    write("favicon.svg", SVG.encode("utf-8"))
    write("favicon-32.png", png(32, ON_DARK))
