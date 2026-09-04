/**
 * Dashboard page — placeholder for Phase 8.
 * Server component that will fetch /api/dashboard/stats.
 */

import { Card } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Dashboard</h1>
        <p className="text-text-secondary mt-1">
          Overview of your sales intelligence pipeline
        </p>
      </div>

      {/* KPI placeholder — Phase 8 will populate with real data */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {["Total Leads", "Qualified", "Outreach Sent", "Active Runs"].map(
          (label) => (
            <Card key={label}>
              <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
                {label}
              </p>
              <p className="text-2xl font-bold text-text mt-1">—</p>
            </Card>
          ),
        )}
      </div>

      <Card>
        <h2 className="text-lg font-semibold text-text mb-4">
          Recent Activity
        </h2>
        <p className="text-sm text-text-muted">
          Dashboard data will load here once the backend is connected.
        </p>
      </Card>
    </div>
  );
}
