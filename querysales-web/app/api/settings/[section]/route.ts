/**
 * PUT/DELETE /api/settings/{llm|embedding|email} — proxy config writes to
 * the backend. Secrets flow straight through to FastAPI (encrypted at rest
 * there) and are never logged here.
 */

import { NextResponse } from "next/server";
import { ApiError, apiDelete, apiPut } from "@/lib/api-client";

const VALID_SECTIONS = new Set(["llm", "embedding", "email"]);

/** FastAPI errors return {detail: string | [{msg}, ...]} — surface one message. */
function errorFrom(err: unknown, fallback: string): { status: number; message: string } {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => (typeof d?.msg === "string" ? d.msg : "")).filter(Boolean).join("; ")
          : `${fallback} (${err.status})`;
    return { status: err.status >= 400 && err.status < 600 ? err.status : 502, message };
  }
  return { status: 500, message: fallback };
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ section: string }> },
) {
  const { section } = await params;
  if (!VALID_SECTIONS.has(section)) {
    return NextResponse.json({ error: "Unknown settings section." }, { status: 404 });
  }

  try {
    const body = await request.json();
    const result = await apiPut<unknown>(`/api/settings/${section}`, body);
    return NextResponse.json(result);
  } catch (err) {
    console.error(`[api/settings/${section}] PUT failed:`, err instanceof Error ? err.message : err);
    const { status, message } = errorFrom(err, "Save failed.");
    return NextResponse.json({ error: message }, { status });
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ section: string }> },
) {
  const { section } = await params;
  if (!VALID_SECTIONS.has(section)) {
    return NextResponse.json({ error: "Unknown settings section." }, { status: 404 });
  }

  try {
    const result = await apiDelete<unknown>(`/api/settings/${section}`);
    return NextResponse.json(result);
  } catch (err) {
    console.error(`[api/settings/${section}] DELETE failed:`, err instanceof Error ? err.message : err);
    const { status, message } = errorFrom(err, "Remove failed.");
    return NextResponse.json({ error: message }, { status });
  }
}
