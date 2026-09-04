/**
 * GET /api/settings/status — proxy to FastAPI settings status.
 */

import { NextResponse } from "next/server";
import { apiGet, apiPost } from "@/lib/api-client";
import type { SettingsStatus } from "@/lib/types";

export async function GET() {
  try {
    const status = await apiGet<SettingsStatus>("/api/settings/status");
    return NextResponse.json(status);
  } catch (err) {
    console.error("[api/settings/status]", err);
    return NextResponse.json({ error: "Failed to fetch settings." }, { status: 502 });
  }
}

/** POST /api/settings/status?action=test-{llm|embedding|email} */
export async function POST(request: Request) {
  try {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    if (action?.startsWith("test-")) {
      const section = action.replace("test-", "");
      const result = await apiPost<{ success: boolean; message: string }>(
        `/api/settings/${section}/test`,
      );
      return NextResponse.json(result);
    }
    return NextResponse.json({ error: "Unknown action." }, { status: 400 });
  } catch (err) {
    console.error("[api/settings/test]", err);
    return NextResponse.json({ error: "Test failed." }, { status: 502 });
  }
}
