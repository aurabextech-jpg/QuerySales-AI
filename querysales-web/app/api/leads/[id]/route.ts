/**
 * GET /api/leads/[id] — proxy to FastAPI lead detail.
 * POST /api/leads/[id]/analyze — trigger analysis.
 */

import { NextResponse } from "next/server";
import { apiGet, apiPost } from "@/lib/api-client";
import type { Lead, RunSummary } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const lead = await apiGet<Lead>(`/api/leads/${id}`);
    return NextResponse.json(lead);
  } catch (err) {
    console.error("[api/leads/detail]", err);
    return NextResponse.json({ error: "Failed to fetch lead." }, { status: 502 });
  }
}

/** Triggered by POST /api/leads/[id]?action=analyze */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const url = new URL(request.url);
    const action = url.searchParams.get("action");

    if (action === "analyze") {
      const run = await apiPost<RunSummary>(`/api/leads/${id}/analyze`);
      return NextResponse.json(run);
    }

    return NextResponse.json({ error: "Unknown action." }, { status: 400 });
  } catch (err) {
    console.error("[api/leads/action]", err);
    return NextResponse.json({ error: "Action failed." }, { status: 502 });
  }
}
