/**
 * GET /api/knowledge — proxy to FastAPI knowledge documents list.
 * POST /api/knowledge — upload a new document (multipart).
 */

import { NextResponse } from "next/server";
import { apiGet, apiFetch } from "@/lib/api-client";
import type { KnowledgeDocument } from "@/lib/types";

export async function GET() {
  try {
    const docs = await apiGet<KnowledgeDocument[]>("/api/knowledge");
    return NextResponse.json(docs);
  } catch (err) {
    console.error("[api/knowledge]", err);
    return NextResponse.json({ error: "Failed to fetch knowledge." }, { status: 502 });
  }
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    // Proxy the multipart upload to FastAPI
    const result = await apiFetch<KnowledgeDocument>("/api/knowledge", {
      method: "POST",
      body: formData,
      headers: {}, // Let fetch set Content-Type with boundary
    });
    return NextResponse.json(result);
  } catch (err) {
    console.error("[api/knowledge/upload]", err);
    return NextResponse.json({ error: "Upload failed." }, { status: 502 });
  }
}
