/**
 * lib/jwt.ts — Pure JWT claim helpers. No Next.js imports.
 *
 * Kept free of `next/headers` so the proxy can import it without dragging in
 * request-scoped APIs that are invalid in that runtime — and so the refresh
 * timing logic can be tested on its own.
 *
 * Nothing here verifies a signature. Verification happens in FastAPI against
 * the Neon Auth JWKS; these claims are only used for UI and refresh timing.
 */

/** Cookie holding the short-lived Neon Auth JWT. */
export const AUTH_COOKIE = "qs_session";

/** Cookie holding the long-lived Better Auth session, used to mint new JWTs. */
export const REFRESH_COOKIE = "qs_refresh";

/** How long a signed-in session lasts before a fresh password login is needed. */
export const SESSION_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

/**
 * Renew the JWT when fewer than this many seconds remain — cheap insurance
 * against a token expiring mid-request after the proxy waved it through.
 */
export const REFRESH_THRESHOLD_SECONDS = 5 * 60;

export const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: SESSION_MAX_AGE,
} as const;

/** Decode a JWT payload without verifying it. Returns null on malformed input. */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const decoded: unknown = JSON.parse(
      Buffer.from(parts[1], "base64url").toString("utf-8"),
    );
    if (!decoded || typeof decoded !== "object" || Array.isArray(decoded)) {
      return null;
    }
    return decoded as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Seconds until expiry. Negative if already expired, null if there is no `exp`. */
export function secondsUntilExpiry(token: string): number | null {
  const exp = decodeJwtPayload(token)?.exp;
  if (typeof exp !== "number") return null;
  return exp - Math.floor(Date.now() / 1000);
}

/** Usable right now — not expired, whether or not it is due for renewal. */
export function isUsable(token: string): boolean {
  const remaining = secondsUntilExpiry(token);
  return remaining !== null && remaining > 0;
}

/** Expired, or close enough that it should be renewed now. */
export function needsRefresh(token: string): boolean {
  const remaining = secondsUntilExpiry(token);
  // A token with no readable `exp` cannot be reasoned about — renew it rather
  // than trusting it indefinitely.
  if (remaining === null) return true;
  return remaining < REFRESH_THRESHOLD_SECONDS;
}
