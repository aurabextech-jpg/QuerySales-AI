/**
 * POST /api/auth/login — Sign in via Neon Auth and store the session.
 *
 * Flow:
 *   1. POST {NEON_AUTH_URL}/sign-in/email → session cookie in the response
 *   2. GET  {NEON_AUTH_URL}/token         → exchange that cookie for a JWT
 *   3. Store both: the JWT for API calls, the session cookie so the proxy can
 *      mint a new JWT when this one expires.
 *
 * Storing the session cookie is what stops the app logging people out after a
 * few minutes: Better Auth JWTs are short-lived, so the JWT alone cannot decide
 * how long a login lasts.
 */

import { NextResponse } from "next/server";
import { AUTH_COOKIE, REFRESH_COOKIE, cookieOptions } from "@/lib/auth";
import {
  exchangeSessionForJwt,
  extractSessionCookie,
  signInWithPassword,
} from "@/lib/neon-auth";

export async function POST(request: Request) {
  try {
    const { email, password } = await request.json();

    if (!email || !password) {
      return NextResponse.json(
        { error: "Email and password are required." },
        { status: 400 },
      );
    }

    const origin = new URL(request.url).origin;

    // Step 1: Sign in
    const signInRes = await signInWithPassword(email, password, origin);
    const signInData = await signInRes.json().catch(() => ({}));

    if (signInRes.status >= 400) {
      const message =
        (signInData as Record<string, string>).message ??
        "Invalid email or password.";
      return NextResponse.json({ error: message }, { status: 401 });
    }

    const sessionCookie = extractSessionCookie(signInRes);
    if (!sessionCookie) {
      return NextResponse.json(
        { error: "No session cookie received from the auth provider." },
        { status: 502 },
      );
    }

    // Step 2: Exchange for a JWT
    const jwt = await exchangeSessionForJwt(sessionCookie, origin);
    if (!jwt) {
      return NextResponse.json(
        { error: "Failed to exchange the session for an access token." },
        { status: 502 },
      );
    }

    // Step 3: Store both cookies
    const response = NextResponse.json({
      success: true,
      user: (signInData as Record<string, unknown>).user ?? { email },
    });

    response.cookies.set(AUTH_COOKIE, jwt, cookieOptions);
    response.cookies.set(REFRESH_COOKIE, sessionCookie, cookieOptions);

    return response;
  } catch (err) {
    console.error("[auth/login] Unexpected error:", err);
    return NextResponse.json(
      { error: "An unexpected error occurred. Please try again." },
      { status: 500 },
    );
  }
}
