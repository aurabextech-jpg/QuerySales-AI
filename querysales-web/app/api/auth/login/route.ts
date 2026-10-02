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
import { extractSessionCookie, signInWithPassword } from "@/lib/neon-auth";
import { authErrorMessage, startSession } from "@/lib/session-response";

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

    const signInRes = await signInWithPassword(email, password, origin);
    const signInData: unknown = await signInRes.json().catch(() => ({}));

    if (signInRes.status >= 400) {
      return NextResponse.json(
        { error: authErrorMessage(signInData, "Invalid email or password.") },
        { status: 401 },
      );
    }

    const sessionCookie = extractSessionCookie(signInRes);
    if (!sessionCookie) {
      return NextResponse.json(
        { error: "No session cookie received from the auth provider." },
        { status: 502 },
      );
    }

    const user = (signInData as { user?: unknown }).user ?? { email };
    return startSession(sessionCookie, origin, user);
  } catch (err) {
    console.error("[auth/login] Unexpected error:", err);
    return NextResponse.json(
      { error: "An unexpected error occurred. Please try again." },
      { status: 500 },
    );
  }
}
