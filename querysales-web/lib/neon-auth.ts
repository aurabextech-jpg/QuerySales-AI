/**
 * lib/neon-auth.ts — Server-side calls to Neon Auth (Better Auth).
 *
 * Shared by the login route handler and the proxy's silent refresh, so the two
 * quirks below are handled in exactly one place.
 *
 * Two Better Auth behaviours, verified against the live instance (2026-09-04),
 * shape this module:
 *  - The CSRF check requires an `Origin` header whenever the request carries
 *    `sec-fetch-mode: cors` — which Node's fetch (undici) always sends.
 *  - `GET /token` authenticates via the `__Secure-*.session_token` cookie from
 *    the sign-in response; passing that token as a Bearer is rejected with 401.
 *    Node's fetch has no cookie jar, so the cookie must be forwarded by hand.
 */

const NEON_AUTH_URL = process.env.NEON_AUTH_URL ?? "";

/** Headers that satisfy Better Auth's Origin/CSRF check. */
function authHeaders(origin: string): Record<string, string> {
  return { Origin: origin };
}

/**
 * Pull the session cookie pair (`name=value`) out of a sign-in response.
 * Returns the first cookie whose name contains `session_token`.
 */
export function extractSessionCookie(res: Response): string | null {
  const cookies = res.headers.getSetCookie?.() ?? [];
  for (const cookie of cookies) {
    const pair = cookie.split(";")[0];
    if (pair.includes("session_token")) return pair;
  }
  // Fallback for runtimes without getSetCookie()
  const raw = res.headers.get("set-cookie");
  if (raw?.includes("session_token")) return raw.split(";")[0];
  return null;
}

/**
 * Exchange a Better Auth session cookie for a fresh JWT.
 * Returns null on any failure — callers treat that as "session is over".
 */
export async function exchangeSessionForJwt(
  sessionCookie: string,
  origin: string,
): Promise<string | null> {
  if (!NEON_AUTH_URL) return null;

  try {
    const res = await fetch(`${NEON_AUTH_URL}/token`, {
      headers: { Cookie: sessionCookie, ...authHeaders(origin) },
      cache: "no-store",
    });

    if (!res.ok) return null;

    const data: unknown = await res.json().catch(() => null);
    if (typeof data === "string") return data;
    if (data && typeof data === "object" && "token" in data) {
      const token = (data as { token?: unknown }).token;
      return typeof token === "string" ? token : null;
    }
    return null;
  } catch {
    // Network failure, DNS, timeout — indistinguishable from an invalid
    // session here, and both mean "cannot renew right now".
    return null;
  }
}

/** Sign in with email + password. Returns the raw response for the caller to read. */
export async function signInWithPassword(
  email: string,
  password: string,
  origin: string,
): Promise<Response> {
  return fetch(`${NEON_AUTH_URL}/sign-in/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(origin) },
    body: JSON.stringify({ email, password }),
    // Don't follow redirects — we need the set-cookie off this exact response.
    redirect: "manual",
    cache: "no-store",
  });
}
