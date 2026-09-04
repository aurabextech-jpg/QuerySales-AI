/**
 * Run detail page — shows the full event timeline for a completed run.
 */

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiGet } from "@/lib/api-client";
import type { RunSummary, AgentEvent, AgentPhase } from "@/lib/types";

interface RunDetailProps {
  params: Promise<{ id: string }>;
}

const phaseConfig: Record<AgentPhase, { icon: string; color: string; bgColor: string }> = {
  OBSERVE: { icon: "👁", color: "text-info", bgColor: "bg-info-muted" },
  RETRIEVE: { icon: "🔍", color: "text-accent", bgColor: "bg-accent-muted" },
  REASON: { icon: "🧠", color: "text-primary", bgColor: "bg-primary-muted" },
  PLAN: { icon: "📋", color: "text-primary-light", bgColor: "bg-primary-muted" },
  TOOL_CALL: { icon: "🔧", color: "text-warning", bgColor: "bg-warning-muted" },
  RESULT: { icon: "✨", color: "text-accent-green", bgColor: "bg-accent-green-muted" },
  COMPLETE: { icon: "✅", color: "text-success", bgColor: "bg-success-muted" },
  ERROR: { icon: "❌", color: "text-error", bgColor: "bg-error-muted" },
};

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = await params;

  let run: RunSummary | null = null;
  let events: AgentEvent[] = [];
  let error: string | null = null;

  try {
    [run, events] = await Promise.all([
      apiGet<RunSummary>(`/api/runs/${id}`),
      apiGet<AgentEvent[]>(`/api/runs/${id}/events`),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load run.";
  }

  if (error || !run) {
    return (
      <div className="space-y-6">
        <Link href="/runs" className="text-sm text-primary hover:text-primary-light transition">
          ← Back to runs
        </Link>
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error ?? "Run not found."}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link href="/runs" className="text-sm text-primary hover:text-primary-light transition">
        ← Back to runs
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <h1 className="text-2xl font-bold text-text">
          Agent Run — {run.lead_company ?? "Unknown"}
        </h1>
        <Badge
          variant={run.status === "completed" ? "success" : run.status === "failed" ? "error" : "primary"}
        >
          {run.status}
        </Badge>
        {run.score != null && (
          <span className="text-sm text-text-secondary">
            Score: <strong className="text-text">{run.score}/100</strong>
          </span>
        )}
        {run.qualification && (
          <span className="text-sm text-text-secondary">
            {run.qualification}
          </span>
        )}
      </div>

      {/* Event timeline */}
      <Card>
        <h2 className="text-base font-semibold text-text mb-4">Event Timeline</h2>

        {events.length === 0 ? (
          <p className="text-sm text-text-muted">No events recorded for this run.</p>
        ) : (
          <div className="space-y-0">
            {events.map((event, index) => {
              const config = phaseConfig[event.phase] ?? phaseConfig.OBSERVE;
              const isLast = index === events.length - 1;

              return (
                <div key={event.id} className="flex gap-3">
                  {/* Timeline connector */}
                  <div className="flex flex-col items-center">
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-full ${config.bgColor} ${config.color} text-sm shrink-0`}
                    >
                      {config.icon}
                    </div>
                    {!isLast && <div className="w-0.5 flex-1 min-h-4 bg-border my-1" />}
                  </div>

                  {/* Event content */}
                  <div className={`pb-4 ${isLast ? "pb-0" : ""} flex-1 min-w-0`}>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-text">{event.label}</p>
                      {event.tool_name && (
                        <span className="text-xs font-mono text-text-muted bg-surface-highlight px-2 py-0.5 rounded">
                          {event.tool_name}
                        </span>
                      )}
                    </div>
                    {event.detail && (
                      <p className="text-xs text-text-secondary mt-0.5 whitespace-pre-wrap break-words max-w-2xl overflow-x-auto">
                        {event.detail}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
