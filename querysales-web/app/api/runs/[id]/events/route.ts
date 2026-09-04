/**
 * GET /api/runs/[id]/events — proxy to FastAPI agent events for polling.
 * Supports ?after_sequence=N for incremental fetching.
 */

import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import type { AgentEvent } from "@/lib/types";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const url = new URL(request.url);
    const afterSeq = url.searchParams.get("after_sequence");
    const apiParams: Record<string, string> = {};
    if (afterSeq) apiParams.after_sequence = afterSeq;

    const events = await apiGet<AgentEvent[]>(
      `/api/runs/${id}/events`,
      apiParams,
    );
    return NextResponse.json(events);
  } catch (err) {
    console.error("[api/runs/events]", err);
    return NextResponse.json(
      { error: "Failed to fetch events." },
      { status: 502 },
    );
  }
}
