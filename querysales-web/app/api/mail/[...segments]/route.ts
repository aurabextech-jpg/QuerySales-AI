/**
 * /api/mail/* — catch-all proxy to the FastAPI mail router.
 * Attaches the session JWT server-side; backend error bodies pass through
 * so the client can surface `detail` verbatim.
 */

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { AUTH_COOKIE } from "@/lib/auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

type Params = { params: Promise<{ segments: string[] }> };

async function forward(request: Request, { params }: Params) {
  const { segments } = await params;
  const target = new URL(`${API_URL}/api/mail/${segments.join("/")}`);
  target.search = new URL(request.url).search;

  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  try {
    const res = await fetch(target.toString(), init);
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (err) {
    console.error("[api/mail] proxy failed:", err instanceof Error ? err.message : err);
    return NextResponse.json(
      { detail: "The mail service is unreachable right now." },
      { status: 502 },
    );
  }
}

export async function GET(request: Request, ctx: Params) {
  return forward(request, ctx);
}
export async function POST(request: Request, ctx: Params) {
  return forward(request, ctx);
}
export async function PUT(request: Request, ctx: Params) {
  return forward(request, ctx);
}
export async function DELETE(request: Request, ctx: Params) {
  return forward(request, ctx);
}
