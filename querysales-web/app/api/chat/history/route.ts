/**
 * GET /api/chat/history?run_id= — proxy to the FastAPI conversation history.
 */

import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import type { ChatHistory } from "@/lib/types";

export async function GET(request: Request) {
  try {
    const runId = new URL(request.url).searchParams.get("run_id");
    if (!runId) {
      return NextResponse.json({ error: "run_id is required." }, { status: 400 });
    }

    const history = await apiGet<ChatHistory>("/api/chat/history", {
      run_id: runId,
    });
    return NextResponse.json(history);
  } catch (err) {
    console.error("[api/chat/history]", err);
    return NextResponse.json(
      { error: "Failed to load conversation history." },
      { status: 502 },
    );
  }
}
