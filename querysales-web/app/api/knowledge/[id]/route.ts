/**
 * GET /api/knowledge/[id] — get document detail.
 * DELETE /api/knowledge/[id] — delete document.
 * POST /api/knowledge/[id]?action=process — trigger ingestion.
 */

import { NextResponse } from "next/server";
import { apiGet, apiPost, apiDelete } from "@/lib/api-client";
import type { KnowledgeDocument } from "@/lib/types";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const doc = await apiGet<KnowledgeDocument>(`/api/knowledge/${id}`);
    return NextResponse.json(doc);
  } catch (err) {
    console.error("[api/knowledge/detail]", err);
    return NextResponse.json({ error: "Failed to fetch document." }, { status: 502 });
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    await apiDelete(`/api/knowledge/${id}`);
    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("[api/knowledge/delete]", err);
    return NextResponse.json({ error: "Delete failed." }, { status: 502 });
  }
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const url = new URL(request.url);
    const action = url.searchParams.get("action");

    if (action === "process") {
      const result = await apiPost<KnowledgeDocument>(`/api/knowledge/${id}/process`);
      return NextResponse.json(result);
    }

    return NextResponse.json({ error: "Unknown action." }, { status: 400 });
  } catch (err) {
    console.error("[api/knowledge/action]", err);
    return NextResponse.json({ error: "Action failed." }, { status: 502 });
  }
}
