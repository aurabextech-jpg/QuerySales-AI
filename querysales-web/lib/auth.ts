/**
 * lib/auth.ts — Cookie-based auth helpers shared by route handlers and middleware.
 *
 * The JWT lives in an httpOnly cookie (Decision D4). Server components and route
 * handlers read it via lib/api-client.ts; the middleware reads it directly to
 * decide redirects.
 */

import { cookies } from "next/headers";

export const AUTH_COOKIE = "qs_session";

/** Read the JWT from the httpOnly cookie. Returns null if absent. */
export async function getSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(AUTH_COOKIE)?.value ?? null;
}

/** Minimal user shape decoded from the JWT payload (or fetched from auth). */
export interface SessionUser {
  id: string;
  email: string;
  name?: string;
}

/**
 * Decode a JWT payload without verification (the backend already signed it;
 * we just need the claims for UI). Verification happens in the FastAPI backend.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(
      Buffer.from(parts[1], "base64url").toString("utf-8"),
    );
    return payload;
  } catch {
    return null;
  }
}

/** Extract user info from the JWT cookie. Returns null if not logged in. */
export async function getSessionUser(): Promise<SessionUser | null> {
  const token = await getSessionToken();
  if (!token) return null;
  const payload = decodeJwtPayload(token);
  if (!payload) return null;
  const sub = payload.sub as string | undefined;
  const email = (payload.email as string) ?? (payload.email_address as string);
  const name = payload.name as string | undefined;
  if (!sub) return null;
  return { id: sub, email: email ?? "", name };
}
