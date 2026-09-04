/**
 * proxy.ts — Auth gate (Next.js 16 proxy, replaces middleware.ts).
 *
 * Redirects unauthenticated users to /login; redirects authenticated
 * users away from /login to /dashboard.
 *
 * The proxy runtime is nodejs (not edge), so Buffer is available.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { AUTH_COOKIE, decodeJwtPayload } from "@/lib/auth";

const PUBLIC_PATHS = ["/login", "/api/auth"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname.startsWith(p));
}

function isJwtValid(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload) return false;
  const exp = payload.exp as number | undefined;
  if (!exp) return false;
  // exp is in seconds; Date.now() is in milliseconds
  return exp * 1000 > Date.now();
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip static files
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.match(/\.(ico|svg|png|jpg|jpeg|webp|css|js)$/)
  ) {
    return NextResponse.next();
  }

  // request.cookies is synchronous on NextRequest
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  const authenticated = !!token && isJwtValid(token);

  // Public path (e.g. /login)
  if (isPublicPath(pathname)) {
    if (authenticated && pathname === "/login") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  // Protected path — require auth
  if (!authenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
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
