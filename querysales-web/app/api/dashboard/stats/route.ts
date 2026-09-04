/**
 * GET /api/dashboard/stats — proxy to FastAPI dashboard stats.
 */

import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api-client";
import type { DashboardStats } from "@/lib/types";

export async function GET() {
  try {
    const stats = await apiGet<DashboardStats>("/api/dashboard/stats");
    return NextResponse.json(stats);
  } catch (err) {
    console.error("[api/dashboard/stats]", err);
    return NextResponse.json(
      { error: "Failed to fetch dashboard stats." },
      { status: 502 },
    );
  }
}
