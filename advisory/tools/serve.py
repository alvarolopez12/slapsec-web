#!/usr/bin/env python3
"""Serve publish/ on this machine the way Netlify serves it, closely enough to test it.

    python3 advisory/tools/serve.py [port] [--geo ES] [--dir <directory>]

  http://127.0.0.1:8765/   by default, as a visitor from outside Spain
  --geo ES                 as a visitor browsing from Spain

What it reproduces:
- the headers in _headers (the /* block, exact paths and /prefix/* blocks), so the page runs
  under the same Content-Security-Policy and Trusted Types as in production
- clean addresses: /legal serves legal.html, /es/ serves es/index.html, /es goes to /es/ and
  /legal/ to /legal, both with a 301
- the path rules in _redirects (rules that name a host are Netlify's business and are skipped)
- 404.html, with status 404, for anything else
- netlify/edge-functions/geo-lang.ts on "/": ?lang=en (or ?stay=1) sets the nf_stay cookie; a
  request carrying it, or one that comes from a page of the site itself, is served; with
  --geo ES every other request is sent to /es/ with a 302

It is a test server: one process, no TLS, no caching, no compression.
"""
import http.server
import os
import re
import sys
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]


def option(name, default=""):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


ROOT = os.path.abspath(option("--dir", os.path.join(HERE, "..", "..", "publish")))
GEO = option("--geo")
PORT = next((int(a) for a in ARGS if a.isdigit()), 8765)
STAY = re.compile(r"(?:^|;\s*)nf_stay=1(?:;|$)")
COOKIE = "nf_stay=1; Path=/; Max-Age=31536000; SameSite=Lax; Secure"
TYPES = {".html": "text/html; charset=UTF-8", ".css": "text/css", ".js": "application/javascript",
         ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml", ".txt": "text/plain; charset=UTF-8",
         ".xml": "application/xml", ".json": "application/json"}


def header_rules():
    rules, block = [], None
    for line in open(os.path.join(ROOT, "_headers"), encoding="utf-8"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            block = (line.strip(), [])
            rules.append(block)
        else:
            key, value = line.strip().split(":", 1)
            block[1].append((key.strip(), value.strip()))
    return rules


def moved():
    rules = {}
    path = os.path.join(ROOT, "_redirects")
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            parts = line.split("#")[0].split()
            if len(parts) >= 2 and parts[0].startswith("/"):
                rules[parts[0]] = (parts[1], int(parts[2].rstrip("!")) if len(parts) > 2 else 301)
    return rules


def matches(pattern, path):
    return path.startswith(pattern[:-1]) if pattern.endswith("*") else path == pattern


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, body=b"", ctype=None, extra=(), path=None):
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        merged = {}
        if path is not None:   # files and the 404 get _headers; redirects, as on Netlify, do not
            for pattern, pairs in header_rules():
                if matches(pattern, path):
                    for key, value in pairs:
                        merged[key.lower()] = (key, value)
        for key, value in list(merged.values()) + list(extra):
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)
        extra = []
        if path == "/":   # the edge function, in the order geo-lang.ts decides
            if query.get("lang") == ["en"] or query.get("stay") == ["1"]:
                extra.append(("Set-Cookie", COOKIE))
            elif STAY.search(self.headers.get("Cookie", "")):
                pass
            elif self.headers.get("Sec-Fetch-Site") == "same-origin":
                pass
            elif GEO == "ES":
                hsts = next((value for pattern, pairs in header_rules() if pattern == "/*"
                             for key, value in pairs if key == "Strict-Transport-Security"), "")
                return self.send(302, extra=[("Location", "/es/"), ("Strict-Transport-Security", hsts),
                                             ("Cache-Control", "no-store")])
        file = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
        if not file.startswith(ROOT):
            return self.send(403)
        target = None
        if path.endswith("/"):
            if os.path.isfile(os.path.join(file, "index.html")):
                target = os.path.join(file, "index.html")
            elif path != "/" and os.path.isfile(file.rstrip("/") + ".html"):
                return self.send(301, extra=[("Location", path.rstrip("/"))])
        elif os.path.isdir(file) and os.path.isfile(os.path.join(file, "index.html")):
            return self.send(301, extra=[("Location", path + "/" + ("?" + url.query if url.query else ""))])
        elif os.path.isfile(file) and os.path.basename(file) not in ("_headers", "_redirects"):
            target = file
        elif os.path.isfile(file + ".html"):
            target = file + ".html"
        if not target:
            rule = moved().get(path)
            if rule:
                return self.send(rule[1], extra=[("Location", rule[0])])
            body = open(os.path.join(ROOT, "404.html"), "rb").read()
            return self.send(404, body, TYPES[".html"], path=path)
        body = open(target, "rb").read()
        return self.send(200, body, TYPES.get(os.path.splitext(target)[1], "application/octet-stream"), extra, path=path)


if __name__ == "__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    print(f"serving {ROOT} on http://127.0.0.1:{PORT}/ as a visitor from {GEO or 'outside Spain'}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
