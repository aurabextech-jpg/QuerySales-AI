/**
 * lib/auth.ts — Request-scoped session helpers for server components and
 * route handlers. Pure claim/expiry logic lives in lib/jwt.ts.
 *
 * Two cookies, both httpOnly (Decision D4):
 *
 *   qs_session  the Neon Auth JWT. Short-lived — Better Auth mints these with a
 *               small `exp` (minutes), so it cannot be the thing that decides
 *               how long a login lasts.
 *   qs_refresh  the Better Auth session cookie captured at sign-in. Long-lived,
 *               and the credential `GET {NEON_AUTH_URL}/token` accepts to mint a
 *               fresh JWT. This is what keeps a session alive.
 *
 * The proxy refreshes the JWT transparently, so a user stays signed in for the
 * life of the session cookie rather than the life of one JWT.
 */

import { cookies } from "next/headers";
import { AUTH_COOKIE, decodeJwtPayload } from "./jwt";

export {
  AUTH_COOKIE,
  REFRESH_COOKIE,
  SESSION_MAX_AGE,
  REFRESH_THRESHOLD_SECONDS,
  cookieOptions,
  decodeJwtPayload,
  secondsUntilExpiry,
  isUsable,
  needsRefresh,
} from "./jwt";

/** Read the JWT from the httpOnly cookie. Returns null if absent. */
export async function getSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(AUTH_COOKIE)?.value ?? null;
}

/** Minimal user shape decoded from the JWT payload. */
export interface SessionUser {
  id: string;
  email: string;
  name?: string;
}

/** Extract user info from the JWT cookie. Returns null if not logged in. */
export async function getSessionUser(): Promise<SessionUser | null> {
  const token = await getSessionToken();
  if (!token) return null;

  const payload = decodeJwtPayload(token);
  const sub = payload?.sub as string | undefined;
  if (!sub) return null;

  const email = (payload?.email as string) ?? (payload?.email_address as string);
  return { id: sub, email: email ?? "", name: payload?.name as string | undefined };
}
