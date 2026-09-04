/**
 * POST /api/auth/login — Sign in via Neon Auth and store JWT as httpOnly cookie.
 *
 * Flow:
 * 1. POST {NEON_AUTH_URL}/sign-in/email → session cookie in the response
 * 2. GET  {NEON_AUTH_URL}/token         → exchange the session cookie for a JWT
 * 3. Set JWT as httpOnly cookie
 *
 * Two Neon Auth (Better Auth) quirks, both verified against the live instance
 * (2026-09-04), shape this code:
 * - The CSRF check requires an Origin header when the request carries
 *   `sec-fetch-mode: cors` — which Node's fetch (undici) always sends.
 * - GET /token authenticates via the `__Secure-*.session_token` cookie from
 *   the sign-in response; the body token as a Bearer is rejected with 401.
 *   Node's fetch has no cookie jar, so the cookie must be forwarded manually.
 */

import { NextResponse } from "next/server";
import { AUTH_COOKIE } from "@/lib/auth";

const NEON_AUTH_URL = process.env.NEON_AUTH_URL!;

/** Request headers that satisfy Better Auth's Origin/CSRF check. */
const authHeaders = (origin: string) => ({ Origin: origin });

/**
 * Extract the session cookie pair (`name=value`) from the sign-in response.
 * Returns the first cookie whose name contains `session_token`.
 */
function extractSessionCookie(res: Response): string | null {
  const cookies = res.headers.getSetCookie?.() ?? [];
  for (const cookie of cookies) {
    const pair = cookie.split(";")[0];
    if (pair.includes("session_token")) return pair;
  }
  // Fallback for runtimes without getSetCookie()
  const raw = res.headers.get("set-cookie");
  if (raw?.includes("session_token")) {
    return raw.split(";")[0];
  }
  return null;
}

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
    const signInRes = await fetch(`${NEON_AUTH_URL}/sign-in/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(origin) },
      body: JSON.stringify({ email, password }),
      // Don't follow redirects — we need the set-cookie
      redirect: "manual",
    });

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
        { error: "No session cookie received from auth provider." },
        { status: 502 },
      );
    }

    // Step 2: Exchange for JWT — authenticated by the forwarded session cookie
    const tokenRes = await fetch(`${NEON_AUTH_URL}/token`, {
      headers: { Cookie: sessionCookie, ...authHeaders(origin) },
    });

    const tokenData = await tokenRes.json().catch(() => ({}));
    const jwt: string | null =
      (tokenData as Record<string, string>).token ??
      (typeof tokenData === "string" ? (tokenData as string) : null);

    if (!jwt) {
      return NextResponse.json(
        { error: "Failed to exchange session token for JWT." },
        { status: 502 },
      );
    }

    // Step 3: Set httpOnly cookie
    const response = NextResponse.json({
      success: true,
      user: (signInData as Record<string, unknown>).user ?? { email },
    });

    response.cookies.set(AUTH_COOKIE, jwt, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7, // 7 days
      path: "/",
    });

    return response;
  } catch (err) {
    console.error("[auth/login] Unexpected error:", err);
    return NextResponse.json(
      { error: "An unexpected error occurred. Please try again." },
      { status: 500 },
    );
  }
}
