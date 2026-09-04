/**
 * GET /api/leads — proxy to FastAPI leads list.
 * Supports ?search= and ?status= query parameters.
 */

import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import type { Lead } from "@/lib/types";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const params: Record<string, string> = {};
    const search = url.searchParams.get("search");
    const status = url.searchParams.get("status");
    if (search) params.search = search;
    if (status) params.status = status;

    const leads = await apiGet<Lead[]>("/api/leads", params);
    return NextResponse.json(leads);
  } catch (err) {
    console.error("[api/leads]", err);
    return NextResponse.json(
      { error: "Failed to fetch leads." },
      { status: 502 },
    );
  }
}
