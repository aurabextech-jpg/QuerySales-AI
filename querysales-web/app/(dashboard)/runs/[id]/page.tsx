/**
 * Run detail — the full agent trace. Each phase is expandable so a reviewer
 * can see the exact knowledge query, tool arguments, and outreach draft.
 */

import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { RunStatusPill, Score } from "@/components/ui/status";
import { RunTimeline } from "@/components/agent/run-timeline";
import { apiGet } from "@/lib/api-client";
import { duration, timeAgo } from "@/lib/format";
import type { AgentEvent, RunSummary } from "@/lib/types";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
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

  if (!run) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/runs">
            <ArrowLeftIcon />
            Back to runs
          </Link>
        </Button>
        <Card className="p-0">
          <ErrorState message={error ?? "Run not found."} />
        </Card>
      </div>
    );
  }

  const meta = [
    { label: "Started", value: timeAgo(run.created_at) },
    { label: "Duration", value: duration(run.created_at, run.completed_at) },
    { label: "Steps", value: String(events.length) },
  ];

  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        size="sm"
        asChild
        className="-ml-2 text-fg-secondary hover:text-fg"
      >
        <Link href="/runs">
          <ArrowLeftIcon />
          Back to runs
        </Link>
      </Button>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
            Agent run
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <h2 className="text-xl font-semibold text-fg">
              {run.lead_company ?? "Unknown lead"}
            </h2>
            <RunStatusPill status={run.status} />
          </div>
          {run.qualification && (
            <p className="mt-1 text-sm text-fg-secondary">{run.qualification}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-4">
          {run.lead_id && (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/leads/${run.lead_id}`}>View lead</Link>
            </Button>
          )}
          {run.score != null && (
            <div className="rounded-xl border-[0.5px] border-line bg-muted px-4 py-2.5 text-center">
              <p className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
                Score
              </p>
              <p className="mt-0.5">
                <Score value={run.score} className="text-xl" />
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Run metadata */}
      <div className="grid grid-cols-3 gap-3">
        {meta.map((item) => (
          <Card key={item.label} className="gap-0 p-3">
            <p className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
              {item.label}
            </p>
            <p className="tabular mt-1 text-sm font-medium text-fg">{item.value}</p>
          </Card>
        ))}
      </div>

      <Card className="gap-0 p-0">
        <CardHeader className="py-4 hairline-b">
          <CardTitle>Reasoning trace</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {events.length === 0 ? (
            <EmptyState
              title="No events recorded"
              description="This run did not emit any phase events."
            />
          ) : (
            <RunTimeline events={events} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
