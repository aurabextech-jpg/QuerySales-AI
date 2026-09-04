/**
 * POST /api/auth/login — Sign in via Neon Auth and store JWT as httpOnly cookie.
 *
 * Mirrors salesopsapp/src/services/authService.ts flow:
 * 1. POST {NEON_AUTH_URL}/sign-in/email → extract session token
 * 2. GET  {NEON_AUTH_URL}/token         → exchange for JWT
 * 3. Set JWT as httpOnly cookie
 */

import { NextResponse } from "next/server";
import { AUTH_COOKIE } from "@/lib/auth";

const NEON_AUTH_URL = process.env.NEON_AUTH_URL!;

/**
 * Extract session token from Neon Auth response.
 * Better Auth may return it in the body or as a set-cookie header.
 * Preserves base64 padding by rejoining with '='.
 */
function extractToken(data: unknown, headers: Headers): string | null {
  const body = data as Record<string, unknown>;
  if (body?.token && typeof body.token === "string") return body.token;

  const cookie = headers.get("set-cookie");
  if (cookie) {
    const firstPart = cookie.split(";")[0];
    const parts = firstPart.split("=");
    if (parts.length > 1) {
      return parts.slice(1).join("=");
    }
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

    // Step 1: Sign in
    const signInRes = await fetch(`${NEON_AUTH_URL}/sign-in/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

    const sessionToken = extractToken(signInData, signInRes.headers);
    if (!sessionToken) {
      return NextResponse.json(
        { error: "No session token received from auth provider." },
        { status: 502 },
      );
    }

    // Step 2: Exchange for JWT
    const tokenRes = await fetch(`${NEON_AUTH_URL}/token`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
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
