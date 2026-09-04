/**
 * Leads list page — server component with search/filter via searchParams.
 */

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge, leadStatusVariant } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import { apiGet } from "@/lib/api-client";
import type { Lead } from "@/lib/types";
import { LeadsSearch } from "./leads-search";

const STATUSES = ["", "New", "Analyzing", "Qualified", "Nurture", "Disqualified", "Contacted"];

interface LeadsPageProps {
  searchParams: Promise<{ search?: string; status?: string }>;
}

export default async function LeadsPage({ searchParams }: LeadsPageProps) {
  const params = await searchParams;
  const search = params.search ?? "";
  const statusFilter = params.status ?? "";

  let leads: Lead[] = [];
  let error: string | null = null;

  try {
    const apiParams: Record<string, string> = {};
    if (search) apiParams.search = search;
    if (statusFilter) apiParams.status = statusFilter;
    leads = await apiGet<Lead[]>("/api/leads", apiParams);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load leads.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Leads</h1>
          <p className="text-text-secondary mt-1">
            {leads.length} lead{leads.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Search + filter bar */}
      <LeadsSearch search={search} status={statusFilter} statuses={STATUSES} />

      {error && (
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error}</p>
        </Card>
      )}

      {leads.length === 0 && !error ? (
        <EmptyState
          title="No leads found"
          description={
            search || statusFilter
              ? "Try adjusting your search or filter."
              : "Run the seed script to populate demo leads."
          }
          icon="🎯"
        />
      ) : (
        <Card padding="sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 font-medium text-text-muted">Company</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Contact</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Industry</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Score</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Status</th>
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
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {lead.name ?? "—"}
                      {lead.email && (
                        <p className="text-xs text-text-muted">{lead.email}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{lead.industry ?? "—"}</td>
                    <td className="px-4 py-3 text-text-secondary">{lead.score ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Badge variant={leadStatusVariant(lead.status)}>{lead.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
