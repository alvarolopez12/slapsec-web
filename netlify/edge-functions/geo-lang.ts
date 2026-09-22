// Audience routing for the two sister sites.
//
//   slapsec.com  SlapSec LLC        international, English
//   thalma.es    Thalma Computing   Spain, Spanish (with /en/)
//
// A visitor from Spain landing on slapsec.com is almost certainly looking for the
// Spanish entity, so we send them there. It is a 302 (never cached) and it is
// escapable: "?stay=1" sets a cookie and we never bounce that visitor again, which
// keeps the door open for a Spanish-based multinational that genuinely wants the
// LLC. Crawlers from non-ES IPs see slapsec.com normally, and hreflang plus the
// canonical on each site keep the two from competing.

const SISTER = "https://thalma.es/";

export default async (request: Request, context: any) => {
  const url = new URL(request.url);

  // Both sites deploy from the same repo, so this function also loads on thalma.es.
  // Without this guard it would redirect thalma.es to itself, forever.
  if (!url.hostname.endsWith("slapsec.com")) {
    return context.next();
  }

  // explicit "keep me here" -> remember it
  if (url.searchParams.get("stay") === "1") {
    const response = await context.next();
    const headers = new Headers(response.headers);
    headers.append("Set-Cookie", "nf_stay=1; Path=/; Max-Age=31536000; SameSite=Lax");
    return new Response(response.body, { status: response.status, headers });
  }

  const cookies = request.headers.get("cookie") || "";
  if (/(?:^|;\s*)nf_stay=1(?:;|$)/.test(cookies)) {
    return context.next();
  }

  if (context.geo?.country?.code === "ES") {
    return Response.redirect(SISTER, 302);
  }

  return context.next();
};

export const config = { path: "/" };
