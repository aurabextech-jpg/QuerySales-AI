/**
 * Agent Runs page — list of user's agent runs.
 */

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import { apiGet } from "@/lib/api-client";
import type { RunSummary } from "@/lib/types";

export default async function RunsPage() {
  let runs: RunSummary[] = [];
  let error: string | null = null;

  try {
    runs = await apiGet<RunSummary[]>("/api/runs");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load runs.";
  }

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Agent Runs</h1>
        <p className="text-text-secondary mt-1">
          {runs.length} run{runs.length !== 1 ? "s" : ""}
        </p>
      </div>

      {error && (
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error}</p>
        </Card>
      )}

      {runs.length === 0 && !error ? (
        <EmptyState
          title="No agent runs yet"
          description="Analyze a lead to see the AI agent in action."
          icon="🤖"
        />
      ) : (
        <Card padding="sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 font-medium text-text-muted">Lead</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Status</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Score</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Qualification</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">When</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="border-b border-border-light hover:bg-surface-highlight transition"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/runs/${run.id}`}
                        className="font-medium text-text hover:text-primary transition"
                      >
                        {run.lead_company ?? "Unknown"}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={
                          run.status === "completed"
                            ? "success"
                            : run.status === "failed"
                              ? "error"
                              : "primary"
                        }
                      >
                        {run.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {run.score ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {run.qualification ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-text-muted text-xs">
                      {timeAgo(run.created_at)}
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
