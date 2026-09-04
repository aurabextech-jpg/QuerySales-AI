/**
 * POST /api/settings/integrations/{provider}/test — proxy the connection test.
 * The backend decrypts server-side and returns only {success, message}.
 */

import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api-client";
import type { TestResult } from "@/lib/types";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ provider: string }> },
) {
  const { provider } = await params;
  try {
    const result = await apiPost<TestResult>(
      `/api/settings/integrations/${provider}/test`,
    );
    return NextResponse.json(result);
  } catch (err) {
    console.error(
      `[api/settings/integrations/${provider}/test] failed:`,
      err instanceof Error ? err.message : err,
    );
    return NextResponse.json(
      { success: false, message: "Could not reach the provider." },
      { status: 502 },
    );
  }
}
