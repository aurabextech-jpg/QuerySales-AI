/**
 * lib/api-client.ts — Server-only HTTP client for the FastAPI backend.
 *
 * Reads the session JWT from the httpOnly cookie and attaches it as a
 * Bearer token. All server components and route handlers call the backend
 * through this module (Decision D4).
 */

import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AUTH_COOKIE } from "./auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Build headers with the JWT Bearer token from the cookie. */
async function buildHeaders(extra?: Record<string, string>): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Generic fetch wrapper. Maps 401 → redirect to /login, everything else
 * to a typed ApiError.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { params?: Record<string, string> },
): Promise<T> {
  // `params` is ours, not fetch's — pull it out so it never reaches fetch().
  const { params, ...fetchInit } = init ?? {};

  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(params ?? {})) {
    url.searchParams.set(key, value);
  }

  const headers = await buildHeaders(
    fetchInit.headers as Record<string, string> | undefined,
  );

  const res = await fetch(url.toString(), {
    ...fetchInit,
    headers,
    // Next.js caches fetch by default — opt out for dynamic requests
    cache: "no-store",
  });

  if (res.status === 401) {
    redirect("/login");
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, `API ${res.status}: ${path}`, body);
  }

  return res.json() as Promise<T>;
}

/* ── Convenience methods ─────────────────────────────────────────── */

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  return apiFetch<T>(path, { method: "GET", params });
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PATCH",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "DELETE" });
}
