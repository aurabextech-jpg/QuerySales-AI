/**
 * GET /api/runs — proxy to FastAPI runs list.
 */

import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import type { RunSummary } from "@/lib/types";

export async function GET(request: Request) {
  try {
    const workflowType = new URL(request.url).searchParams.get("workflow_type");
    const runs = await apiGet<RunSummary[]>(
      "/api/runs",
      workflowType ? { workflow_type: workflowType } : undefined,
    );
    return NextResponse.json(runs);
  } catch (err) {
    console.error("[api/runs]", err);
    return NextResponse.json({ error: "Failed to fetch runs." }, { status: 502 });
  }
}
