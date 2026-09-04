/**
 * POST /api/chat — proxy to the FastAPI conversational orchestrator.
 *
 * Calls /api/chat/stream, which returns the whole run as one JSON body: every
 * agent hand-off and tool call in `steps`, plus the final `message`. It is not
 * an event stream — Vercel's Python runtime buffers responses, so the backend
 * collects the events and returns them together (Decision D6).
 */

import { NextResponse } from "next/server";
import { apiPost } from "@/lib/api-client";
import type { ChatResponse } from "@/lib/types";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    if (!Array.isArray(body?.messages) || body.messages.length === 0) {
      return NextResponse.json(
        { error: "At least one message is required." },
        { status: 400 },
      );
    }

    const result = await apiPost<ChatResponse>("/api/chat/stream", {
      messages: body.messages,
      run_id: body.run_id ?? null,
    });

    return NextResponse.json(result);
  } catch (err) {
    console.error("[api/chat]", err);
    return NextResponse.json(
      { error: "The agent could not complete your request." },
      { status: 502 },
    );
  }
}
