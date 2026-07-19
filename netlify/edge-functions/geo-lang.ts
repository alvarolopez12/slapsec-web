// Geo language routing for slapsec.com
// - Visitors from Spain hitting "/" get the Spanish version at /es/ (302).
// - Clicking "EN" on the Spanish page links to /?lang=en → we remember the
//   choice in a cookie and never bounce that visitor again.
// - Everyone else (and all crawlers from non-ES IPs) gets English at "/".
// hreflang tags on both pages keep SEO correct; the redirect is 302 (never cached).

export default async (request: Request, context: any) => {
  const url = new URL(request.url);

  // Explicit English choice → set cookie, serve EN.
  if (url.searchParams.get("lang") === "en") {
    const response = await context.next();
    const headers = new Headers(response.headers);
    headers.append(
      "Set-Cookie",
      "nf_lang=en; Path=/; Max-Age=31536000; SameSite=Lax",
    );
    return new Response(response.body, { status: response.status, headers });
  }

  // Previously chose English → respect it.
  const cookies = request.headers.get("cookie") || "";
  if (/(?:^|;\s*)nf_lang=en(?:;|$)/.test(cookies)) {
    return context.next();
  }

  // From Spain → Spanish version.
  if (context.geo?.country?.code === "ES") {
    return Response.redirect(new URL("/es/", request.url), 302);
  }

  return context.next();
};

export const config = { path: "/" };
