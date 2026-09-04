/**
 * Dashboard page — server component fetching stats + recent leads.
 */

import { Card } from "@/components/ui/card";
import { Badge, leadStatusVariant } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import { apiGet } from "@/lib/api-client";
import type { DashboardStats, Lead } from "@/lib/types";
import Link from "next/link";

export default async function DashboardPage() {
  let stats: DashboardStats | null = null;
  let recentLeads: Lead[] = [];
  let error: string | null = null;

  try {
    [stats, recentLeads] = await Promise.all([
      apiGet<DashboardStats>("/api/dashboard/stats"),
      apiGet<Lead[]>("/api/leads"),
    ]);
  } catch (err) {
    error =
      err instanceof Error ? err.message : "Failed to load dashboard data.";
  }

  const kpis = stats
    ? [
        { label: "Total Leads", value: stats.total_leads },
        { label: "Qualified", value: stats.qualified_leads },
        { label: "Outreach Sent", value: stats.outreach_sent },
        { label: "Active Runs", value: stats.active_runs },
        { label: "Knowledge Docs", value: stats.knowledge_documents },
      ]
    : [];

  const leads = recentLeads.slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Dashboard</h1>
        <p className="text-text-secondary mt-1">
          Overview of your sales intelligence pipeline
        </p>
      </div>

      {error && (
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error}</p>
        </Card>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <p className="text-xs font-medium text-text-muted uppercase tracking-wide">
              {kpi.label}
            </p>
            <p className="text-3xl font-bold text-text mt-1">{kpi.value}</p>
          </Card>
        ))}
        {!stats &&
          !error &&
          Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <div className="h-3 w-20 rounded bg-surface-highlight animate-pulse" />
              <div className="h-8 w-12 rounded bg-surface-highlight animate-pulse mt-2" />
            </Card>
          ))}
      </div>

      {/* Recent leads table */}
      <Card padding="sm">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-base font-semibold text-text">Recent Leads</h2>
          <Link
            href="/leads"
            className="text-xs font-medium text-primary hover:text-primary-light transition"
          >
            View all →
          </Link>
        </div>

        {leads.length === 0 && !error ? (
          <EmptyState
            title="No leads yet"
            description="Run the seed script to populate demo data, or add leads manually."
            icon="🎯"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 font-medium text-text-muted">
                    Company
                  </th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">
                    Industry
                  </th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">
                    Score
                  </th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className="border-b border-border-light hover:bg-surface-highlight transition"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/leads/${lead.id}`}
                        className="font-medium text-text hover:text-primary transition"
                      >
                        {lead.company}
                      </Link>
                      {lead.name && (
                        <p className="text-xs text-text-muted">{lead.name}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {lead.industry ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {lead.score ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={leadStatusVariant(lead.status)}>
                        {lead.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
