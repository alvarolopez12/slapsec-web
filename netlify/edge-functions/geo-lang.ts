// Audience routing for the two sister sites.
//
//   slapsec.com  SlapSec LLC        international, English
//   thalma.es    Thalma Computing   Spain, Spanish (with /en/)
//
// A visitor from Spain landing on slapsec.com is almost certainly looking for the
// Spanish entity, so we send them there. It is a 302 marked no-store, because a
// browser keeps a bare 302 and replays it on Back and on restored tabs, and it is
// escapable: "?stay=1" sets a cookie and we never bounce that visitor again, which
// keeps the door open for a Spanish-based multinational that genuinely wants the
// LLC. Crawlers from non-ES IPs see slapsec.com normally, and hreflang plus the
// canonical on each site keep the two from competing.

// Phase 2 flips this to "https://thalma.es/" once that domain resolves.
const SISTER = "/es/";

export default async (request: Request, context: any) => {
  const url = new URL(request.url);

  // Both sites deploy from the same repo, so this function also loads on thalma.es.
  // Without this guard it would redirect thalma.es to itself, forever.
  if (!url.hostname.endsWith("slapsec.com")) {
    return context.next();
  }

  // Explicit "I want English" -> remember it. The language toggle on the Spanish
  // page links to /?lang=en, so that parameter is the one that has to work; ?stay=1
  // is the phase-2 spelling and is accepted too. Getting this wrong bounces a
  // Spanish visitor straight back to /es/ and they cannot reach the English site.
  // With script, the page's own language switch sets this same cookie, and clears it
  // when the reader chooses Spanish again.
  const asked = url.searchParams.get("lang") === "en" || url.searchParams.get("stay") === "1";
  if (asked) {
    const response = await context.next();
    const headers = new Headers(response.headers);
    headers.append("Set-Cookie", "nf_stay=1; Path=/; Max-Age=31536000; SameSite=Lax; Secure");
    return new Response(response.body, { status: response.status, headers });
  }

  const cookies = request.headers.get("cookie") || "";
  if (/(?:^|;\s*)nf_stay=1(?:;|$)/.test(cookies)) {
    return context.next();
  }

  // Route arrivals only. A reader already on the site who follows a link to "/" (the logo of
  // an English legal page, or of the 404) is reading English and is served it, and no cookie
  // is set. Typed, bookmarked and outside visits carry "none" or "cross-site" and go on below,
  // and so do browsers that do not send the header on such a link (Safari before 18).
  if (request.headers.get("sec-fetch-site") === "same-origin") {
    return context.next();
  }

  if (context.geo?.country?.code === "ES") {
    // Netlify does not apply publish/_headers to a response built here and would add its own,
    // weaker HSTS. This is the value advisory/build_advisory.py writes into _headers, and the
    // build checks that the two agree. no-store: without it Chrome answers a later Back to "/"
    // with this redirect, from its own cache, even for a reader who has since chosen English.
    return new Response(null, {
      status: 302,
      headers: {
        Location: new URL(SISTER, request.url).href,
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "Cache-Control": "no-store",
      },
    });
  }

  return context.next();
};

// onError "bypass": if this function ever fails, the home page is served as it is, in English.
export const config = { path: "/", onError: "bypass" };
