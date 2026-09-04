/** Agent runs — server fetch, client-side sort/search/filter. */

import { apiGet } from "@/lib/api-client";
import { RunsTable } from "@/components/runs/runs-table";
import type { RunSummary } from "@/lib/types";

export default async function RunsPage() {
  let runs: RunSummary[] = [];
  let error: string | null = null;

  try {
    runs = await apiGet<RunSummary[]>("/api/runs");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load runs.";
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-fg">Agent runs</h2>
        <p className="mt-0.5 text-sm text-fg-secondary">
          Every analysis the agent has performed, with its full reasoning trace.
        </p>
      </div>

      <RunsTable runs={runs} error={error} />
    </div>
  );
}
