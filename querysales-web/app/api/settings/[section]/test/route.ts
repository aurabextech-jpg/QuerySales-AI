/**
 * POST /api/settings/{llm|embedding|email}/test — proxy connection tests
 * to the backend. Returns {success, message}; the secret never appears in
 * the result.
 */

import { NextResponse } from "next/server";
import { ApiError, apiPost } from "@/lib/api-client";

const VALID_SECTIONS = new Set(["llm", "embedding", "email"]);

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ section: string }> },
) {
  const { section } = await params;
  if (!VALID_SECTIONS.has(section)) {
    return NextResponse.json({ error: "Unknown settings section." }, { status: 404 });
  }

  try {
    const result = await apiPost<{ success: boolean; message: string }>(
      `/api/settings/${section}/test`,
    );
    return NextResponse.json(result);
  } catch (err) {
    console.error(`[api/settings/${section}/test] failed:`, err instanceof Error ? err.message : err);
    const status = err instanceof ApiError ? err.status : 500;
    return NextResponse.json({ error: "Test failed." }, { status: status >= 400 && status < 600 ? status : 502 });
  }
}
