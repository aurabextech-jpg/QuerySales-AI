/**
 * PUT/DELETE /api/settings/integrations/{provider} — proxy integration config
 * writes to the backend. Secrets flow straight through to FastAPI (AES-256-GCM
 * encrypted at rest there) and are never logged here.
 */

import { NextResponse } from "next/server";
import { ApiError, apiDelete, apiPut } from "@/lib/api-client";
import type { Integration } from "@/lib/types";

/** FastAPI errors return {detail: string | [{msg}, ...]} — surface one message. */
function errorFrom(err: unknown, fallback: string): { status: number; message: string } {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((d) => (typeof d?.msg === "string" ? d.msg : ""))
              .filter(Boolean)
              .join("; ")
          : `${fallback} (${err.status})`;
    return { status: err.status >= 400 && err.status < 600 ? err.status : 502, message };
  }
  return { status: 500, message: fallback };
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ provider: string }> },
) {
  const { provider } = await params;
  try {
    const body = await request.json();
    const result = await apiPut<Integration>(
      `/api/settings/integrations/${provider}`,
      body,
    );
    return NextResponse.json(result);
  } catch (err) {
    // Never log the body — it can carry a plaintext secret on its way through.
    console.error(
      `[api/settings/integrations/${provider}] PUT failed:`,
      err instanceof Error ? err.message : err,
    );
    const { status, message } = errorFrom(err, "Save failed.");
    return NextResponse.json({ error: message }, { status });
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ provider: string }> },
) {
  const { provider } = await params;
  try {
    const result = await apiDelete<unknown>(`/api/settings/integrations/${provider}`);
    return NextResponse.json(result);
  } catch (err) {
    console.error(
      `[api/settings/integrations/${provider}] DELETE failed:`,
      err instanceof Error ? err.message : err,
    );
    const { status, message } = errorFrom(err, "Remove failed.");
    return NextResponse.json({ error: message }, { status });
  }
}
