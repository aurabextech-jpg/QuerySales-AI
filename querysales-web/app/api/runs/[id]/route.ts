/**
 * GET /api/runs/[id] — proxy to FastAPI run detail.
 */

import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import type { RunSummary } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const run = await apiGet<RunSummary>(`/api/runs/${id}`);
    return NextResponse.json(run);
  } catch (err) {
    console.error("[api/runs/detail]", err);
    return NextResponse.json({ error: "Failed to fetch run." }, { status: 502 });
  }
}
