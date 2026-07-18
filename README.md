# slapsec.com

Marketing site for **SlapSec LLC**. Static — hand-written HTML/CSS/JS, no build step.

## Structure

| Path | What |
|------|------|
| `publish/` | **The live site** — this is the Netlify publish directory. **Edit here.** |
| `publish/_headers` | Security headers (CSP, HSTS, …) applied at the Netlify edge |
| `publish/robots.txt`, `publish/sitemap.xml` | SEO |
| `assets/` | Brand source files (logo, etc.) — not deployed |
| `archive/` | Old versions / backups — gitignored, local only |
| `netlify.toml` | Netlify config (publish dir = `publish`, no build) |

## Deploy

The site is on **Netlify with continuous deployment from this Git repo**:

> **Push to `main` → Netlify builds & deploys to https://slapsec.com automatically.**

Roll back any deploy from the Netlify UI (Deploys → pick a previous one → Publish).

**Manual deploy (fallback, if CD is ever off):**
```bash
npx netlify-cli@latest deploy --prod --dir=publish
```

## Notes

- **Bilingual EN/ES** via a JS toggle (`data-en` / `data-es` / `data-*-html` attributes). Default static language is English. Spanish market SEO would need separate `/es/` URLs + `hreflang`.
- **Email** (Microsoft 365) DNS lives at **Arsys** — only the `A @` and `CNAME www` records point to Netlify. Never touch MX / SPF / DKIM.
- Contact form has no backend yet: it opens a `mailto:` draft. Wire a real endpoint (Formspree / API) before running paid campaigns.
