/**
 * Leads list — server component. Sorting, search and facet filtering all run
 * client-side in LeadsTable, so the page fetches once and stays interactive.
 */

import { apiGet } from "@/lib/api-client";
import { LeadsTable } from "@/components/leads/leads-table";
import type { Lead } from "@/lib/types";

export default async function LeadsPage() {
  let leads: Lead[] = [];
  let error: string | null = null;

  try {
    leads = await apiGet<Lead[]>("/api/leads");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load leads.";
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-fg">Leads</h2>
        <p className="mt-0.5 text-sm text-fg-secondary">
          Search, sort and filter your pipeline. Open a lead to run the agent.
        </p>
      </div>

      <LeadsTable leads={leads} error={error} />
    </div>
  );
}
