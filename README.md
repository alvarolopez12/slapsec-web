# slapsec.com

Marketing site for **SlapSec** — senior cybersecurity consulting. Static site: hand-written HTML/CSS/JS, no build step.

## Structure

| Path | What |
|------|------|
| `publish/` | **The site** — this is what gets deployed. Edit here. |
| `publish/_headers` | Security headers (CSP, HSTS, …) |
| `publish/robots.txt`, `publish/sitemap.xml` | SEO |
| `assets/` | Brand source files (logo, etc.) — not deployed |
| `netlify.toml` | Host config (publish dir = `publish`, no build) |

## Deploy

Continuous deployment from this repo:

> **Push to `main` → the site rebuilds and goes live automatically.**

Previous deploys can be rolled back from the hosting dashboard.

## Notes

- **Bilingual EN/ES** via a JS toggle (`data-en` / `data-es` / `data-*-html` attributes). Default language is English.
