/**
 * proxy.ts — Auth gate with silent token refresh (Next.js 16 proxy).
 *
 * Redirects unauthenticated users to /login and authenticated users away from
 * /login. Before either decision, it renews an expiring JWT in the background.
 *
 * Why the refresh exists: Better Auth mints short-lived JWTs (minutes). Gating
 * purely on the JWT's `exp` — as this file used to — logged people out minutes
 * after signing in, even though their Better Auth session was still valid for
 * days. The long-lived session cookie is now the source of truth for "are you
 * signed in", and the JWT is just a short-lived credential the proxy re-mints
 * on demand.
 *
 * The proxy runtime is nodejs (not edge), so Buffer and fetch are available.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  AUTH_COOKIE,
  REFRESH_COOKIE,
  cookieOptions,
  isUsable,
  needsRefresh,
} from "@/lib/jwt";
import { exchangeSessionForJwt } from "@/lib/neon-auth";

const PUBLIC_PATHS = ["/login", "/api/auth"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname.startsWith(p));
}

function isStaticAsset(pathname: string): boolean {
  return (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    /\.(ico|svg|png|jpg|jpeg|webp|css|js|map|woff2?)$/.test(pathname)
  );
}

/** Rebuild a Cookie header with one cookie's value replaced. */
function cookieHeaderWith(request: NextRequest, name: string, value: string): string {
  const jar = new Map(
    request.cookies.getAll().map((c) => [c.name, c.value] as const),
  );
  jar.set(name, value);
  return [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isStaticAsset(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(AUTH_COOKIE)?.value;
  const sessionCookie = request.cookies.get(REFRESH_COOKIE)?.value;

  let authenticated = !!token && isUsable(token);
  let refreshedToken: string | null = null;

  // Renew when the JWT is expired or close to it, and we hold a session cookie.
  // Logging out clears that cookie, so a signed-out user is never resurrected.
  if (sessionCookie && (!token || needsRefresh(token))) {
    refreshedToken = await exchangeSessionForJwt(
      sessionCookie,
      request.nextUrl.origin,
    );
    if (refreshedToken) {
      authenticated = true;
    } else if (!authenticated) {
      // The session cookie is dead and the JWT is unusable — sign them out
      // cleanly rather than bouncing them to /login on every navigation.
      const loginUrl = new URL("/login", request.url);
      if (!isPublicPath(pathname)) loginUrl.searchParams.set("redirect", pathname);
      const response = NextResponse.redirect(loginUrl);
      for (const name of [AUTH_COOKIE, REFRESH_COOKIE]) {
        response.cookies.set(name, "", { ...cookieOptions, maxAge: 0 });
      }
      return response;
    }
    // Refresh failed but the existing JWT is still usable — carry on with it.
  }

  /** Attach a freshly minted JWT to both the response and the ongoing request. */
  function withRefreshedCookie(response: NextResponse): NextResponse {
    if (refreshedToken) {
      response.cookies.set(AUTH_COOKIE, refreshedToken, cookieOptions);
    }
    return response;
  }

  // Public path (e.g. /login)
  if (isPublicPath(pathname)) {
    if (authenticated && pathname === "/login") {
      return withRefreshedCookie(
        NextResponse.redirect(new URL("/dashboard", request.url)),
      );
    }
    return withRefreshedCookie(NextResponse.next());
  }

  // Protected path — require auth
  if (!authenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Forward the new token on the current request too, so server components and
  // route handlers read the fresh JWT instead of the one about to expire.
  const headers = new Headers(request.headers);
  if (refreshedToken) {
    headers.set("cookie", cookieHeaderWith(request, AUTH_COOKIE, refreshedToken));
  }

  return withRefreshedCookie(NextResponse.next({ request: { headers } }));
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static, _next/image, favicon.ico
     * - public files (images, etc.)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
