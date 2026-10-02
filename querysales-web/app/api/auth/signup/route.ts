/**
 * POST /api/auth/signup — Create a Neon Auth account and sign the user in.
 *
 * Flow:
 *   1. POST {NEON_AUTH_URL}/sign-up/email → account + session cookie
 *      (Better Auth signs new users in by default)
 *   2. If the instance did not start a session (e.g. auto sign-in disabled),
 *      sign in with the same credentials.
 *   3. Exchange the session for a JWT and store both cookies, as login does.
 *
 * The FastAPI backend creates the local `users` row on the first request that
 * carries the new JWT (core/security.py:get_current_user), so nothing else is
 * needed here.
 */

import { NextResponse } from "next/server";
import {
  extractSessionCookie,
  signInWithPassword,
  signUpWithPassword,
} from "@/lib/neon-auth";
import { authErrorMessage, startSession } from "@/lib/session-response";

// Better Auth's default minimum; checked here so the user gets a clear message
// before a round-trip to the auth provider.
const MIN_PASSWORD_LENGTH = 8;
const MAX_NAME_LENGTH = 100;

export async function POST(request: Request) {
  try {
    const body: unknown = await request.json().catch(() => null);
    const { name, email, password } = (body ?? {}) as Record<string, unknown>;

    if (typeof name !== "string" || !name.trim() || name.length > MAX_NAME_LENGTH) {
      return NextResponse.json({ error: "Please enter your name." }, { status: 400 });
    }
    if (typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json({ error: "Please enter a valid email." }, { status: 400 });
    }
    if (typeof password !== "string" || password.length < MIN_PASSWORD_LENGTH) {
      return NextResponse.json(
        { error: `Password must be at least ${MIN_PASSWORD_LENGTH} characters.` },
        { status: 400 },
      );
    }

    const origin = new URL(request.url).origin;

    const signUpRes = await signUpWithPassword(name.trim(), email, password, origin);
    const signUpData: unknown = await signUpRes.json().catch(() => ({}));

    if (signUpRes.status >= 400) {
      // e.g. "User already exists. Use another email."
      return NextResponse.json(
        { error: authErrorMessage(signUpData, "Could not create the account.") },
        { status: signUpRes.status === 422 ? 409 : 400 },
      );
    }

    let sessionCookie = extractSessionCookie(signUpRes);
    let user = (signUpData as { user?: unknown }).user ?? { email };

    if (!sessionCookie) {
      const signInRes = await signInWithPassword(email, password, origin);
      const signInData: unknown = await signInRes.json().catch(() => ({}));
      sessionCookie = signInRes.status < 400 ? extractSessionCookie(signInRes) : null;
      user = (signInData as { user?: unknown }).user ?? user;
    }

    if (!sessionCookie) {
      // Account exists but could not be signed in (e.g. email verification
      // required) — send the user to the login page rather than failing.
      return NextResponse.json(
        { success: true, signedIn: false, message: "Account created. Please sign in." },
        { status: 201 },
      );
    }

    return startSession(sessionCookie, origin, user);
  } catch (err) {
    console.error("[auth/signup] Unexpected error:", err);
    return NextResponse.json(
      { error: "An unexpected error occurred. Please try again." },
      { status: 500 },
    );
  }
}
