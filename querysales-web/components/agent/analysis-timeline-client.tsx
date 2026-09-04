"use client";

/**
 * AnalysisTimeline — the demo's centrepiece.
 *
 * Polls GET /api/runs/{runId}/events?after_sequence=N roughly once a second
 * and appends phases as the agent emits them. Polling rather than SSE is
 * deliberate: Vercel's Python runtime buffers responses, so a stream would
 * arrive all at once in production (Decision D6).
 *
 * Stops on COMPLETE / ERROR, on unmount, and after a run of consecutive
 * network failures — an unattended tab must never poll forever.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BrainIcon,
  CheckIcon,
  ClipboardListIcon,
  EyeIcon,
  OctagonXIcon,
  SearchIcon,
  SparklesIcon,
  WrenchIcon,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentEvent, AgentPhase } from "@/lib/types";

const POLL_INTERVAL = 1000;
const MAX_CONSECUTIVE_FAILURES = 8;

const PHASE_ICON: Record<AgentPhase, LucideIcon> = {
  OBSERVE: EyeIcon,
  RETRIEVE: SearchIcon,
  REASON: BrainIcon,
  PLAN: ClipboardListIcon,
  TOOL_CALL: WrenchIcon,
  RESULT: SparklesIcon,
  COMPLETE: CheckIcon,
  ERROR: OctagonXIcon,
};

function PhaseNode({ phase, done }: { phase: AgentPhase; done: boolean }) {
  const Icon = PHASE_ICON[phase] ?? EyeIcon;

  // Rule 1 holds: lime marks the *completed* terminal state only — it reads as
  // the agent's "done" signal, not as decoration on every row.
  const tone =
    phase === "ERROR"
      ? "border-danger/40 bg-danger-tint text-danger"
      : phase === "COMPLETE"
        ? "border-transparent bg-signal text-on-signal"
        : done
          ? "border-line bg-muted text-fg-secondary"
          : "border-line bg-muted text-fg-muted";

  return (
    <span
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full border-[0.5px]",
        tone,
      )}
    >
      <Icon className="size-3.5" />
    </span>
  );
}

export function AnalysisTimeline({
  runId,
  onComplete,
}: {
  runId: string;
  onComplete?: () => void;
}) {
  const router = useRouter();

  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [polling, setPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const lastSequence = useRef(-1);
  const failures = useRef(0);
  const notified = useRef(false);

  const fetchEvents = useCallback(async () => {
    try {
      const after = lastSequence.current;
      const query = after >= 0 ? `?after_sequence=${after + 1}` : "";
      const res = await fetch(`/api/runs/${runId}/events${query}`);

      if (!res.ok) {
        // 5xx is usually transient (cold serverless function) — keep trying.
        if (res.status >= 500) {
          failures.current += 1;
          if (failures.current >= MAX_CONSECUTIVE_FAILURES) {
            setError("Lost contact with the agent run.");
            setPolling(false);
          }
          return;
        }
        setError("Could not load agent events.");
        setPolling(false);
        return;
      }

      failures.current = 0;
      const incoming: AgentEvent[] = await res.json();
      if (incoming.length === 0) return;

      setEvents((prev) => [...prev, ...incoming]);
      lastSequence.current = incoming[incoming.length - 1].sequence;

      const finished = incoming.find(
        (e) => e.phase === "COMPLETE" || e.phase === "ERROR",
      );
      if (finished && !notified.current) {
        notified.current = true;
        setPolling(false);

        if (finished.phase === "COMPLETE") {
          toast.success("Analysis complete", {
            description: finished.detail ?? "The lead has been updated.",
          });
          // Pull the lead's new status/score into the server-rendered page.
          router.refresh();
          onComplete?.();
        } else {
          toast.error("Analysis failed", {
            description: finished.detail ?? "The agent could not finish this run.",
          });
        }
      }
    } catch {
      failures.current += 1;
      if (failures.current >= MAX_CONSECUTIVE_FAILURES) {
        setError("Network unavailable. Stopped watching this run.");
        setPolling(false);
      }
    }
  }, [runId, router, onComplete]);

  useEffect(() => {
    if (!polling) return;

    // The first poll is scheduled rather than called inline: fetchEvents sets
    // state, and doing that synchronously in an effect body cascades renders.
    const first = setTimeout(fetchEvents, 0);
    const interval = setInterval(fetchEvents, POLL_INTERVAL);

    return () => {
      clearTimeout(first);
      clearInterval(interval);
    };
  }, [polling, fetchEvents]);

  const complete = events.some((e) => e.phase === "COMPLETE");
  const failed = events.some((e) => e.phase === "ERROR");
  const running = polling && !complete && !failed;

  return (
    <Card className="gap-0 overflow-hidden p-0">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 hairline-b">
        <div className="flex items-center gap-2">
          {running && (
            <span className="size-1.5 rounded-full bg-signal animate-signal-pulse" />
          )}
          <h3 className="text-sm font-semibold text-fg">
            {complete
              ? "Analysis complete"
              : failed
                ? "Analysis failed"
                : "Agent working…"}
          </h3>
        </div>
        <span className="tabular text-xs text-fg-muted">
          {events.length} step{events.length === 1 ? "" : "s"}
        </span>
      </div>

      {/* Indeterminate progress while the agent runs */}
      {running && (
        <div className="h-px w-full overflow-hidden bg-line">
          <div className="h-full w-1/3 bg-signal animate-sweep" />
        </div>
      )}

      <div className="p-4">
        {events.length === 0 && !error ? (
          <div className="flex items-center gap-2.5 py-2">
            <span className="size-1.5 rounded-full bg-signal animate-signal-pulse" />
            <p className="text-sm text-fg-secondary">Starting the agent…</p>
          </div>
        ) : (
          <ol className="space-y-0">
            {events.map((event, i) => {
              const isLast = i === events.length - 1;
              return (
                <li key={event.id} className="animate-rise flex gap-3">
                  <div className="flex flex-col items-center">
                    <PhaseNode phase={event.phase} done={!isLast || complete} />
                    {!isLast && <div className="my-1 w-px flex-1 bg-line" />}
                  </div>

                  <div className={cn("min-w-0 flex-1", isLast ? "pb-0" : "pb-4")}>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-fg">{event.label}</p>
                      {event.tool_name && (
                        <code className="rounded border-[0.5px] border-line bg-muted px-1.5 py-0.5 font-mono text-[11px] text-fg-secondary">
                          {event.tool_name}
                        </code>
                      )}
                    </div>
                    {event.detail && (
                      <p className="mt-0.5 text-xs wrap-break-word text-fg-secondary">
                        {event.detail}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}

        {error && (
          <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border-[0.5px] border-danger/30 bg-danger-tint px-3 py-2.5">
            <p className="text-sm text-danger">{error}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setError(null);
                failures.current = 0;
                setPolling(true);
              }}
            >
              Retry
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
