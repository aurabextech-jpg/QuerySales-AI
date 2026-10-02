/**
 * lib/session-response.ts — Turn a Better Auth session into our two cookies.
 *
 * Shared by sign-in and sign-up: both end with a session cookie from Neon Auth
 * that must be exchanged for a JWT, then stored httpOnly (Decision D4).
 */

import "server-only";
import { NextResponse } from "next/server";
import { AUTH_COOKIE, REFRESH_COOKIE, cookieOptions } from "@/lib/auth";
import { exchangeSessionForJwt } from "@/lib/neon-auth";

export async function startSession(
  sessionCookie: string,
  origin: string,
  user: unknown,
): Promise<NextResponse> {
  const jwt = await exchangeSessionForJwt(sessionCookie, origin);
  if (!jwt) {
    return NextResponse.json(
      { error: "Failed to exchange the session for an access token." },
      { status: 502 },
    );
  }

  const response = NextResponse.json({ success: true, user });
  response.cookies.set(AUTH_COOKIE, jwt, cookieOptions);
  // Kept so the proxy can mint a fresh JWT when this short-lived one expires.
  response.cookies.set(REFRESH_COOKIE, sessionCookie, cookieOptions);
  return response;
}

/** Better Auth error bodies carry `message`; fall back to a generic line. */
export function authErrorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "message" in data) {
    const { message } = data as { message: unknown };
    if (typeof message === "string" && message) return message;
  }
  return fallback;
}
