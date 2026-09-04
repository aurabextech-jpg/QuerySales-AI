/**
 * POST /api/auth/logout — Clear both session cookies.
 *
 * The refresh cookie must go too: leaving it behind would let the proxy mint a
 * new JWT on the next request and silently sign the user back in.
 */

import { NextResponse } from "next/server";
import { AUTH_COOKIE, REFRESH_COOKIE, cookieOptions } from "@/lib/auth";

export async function POST() {
  const response = NextResponse.json({ success: true });

  for (const name of [AUTH_COOKIE, REFRESH_COOKIE]) {
    response.cookies.set(name, "", { ...cookieOptions, maxAge: 0 });
  }

  return response;
}
