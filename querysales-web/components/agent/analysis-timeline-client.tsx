/**
 * AnalysisTimeline — client component that polls for agent events and renders
 * a progressive timeline. This is the most important screen in the demo.
 *
 * Polls GET /api/runs/{runId}/events?after_sequence=N every ~1s.
 * Stops polling on COMPLETE or ERROR phase, or on unmount.
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card } from "@/components/ui/card";
import type { AgentEvent, AgentPhase } from "@/lib/types";

interface AnalysisTimelineProps {
  runId: string;
}

/** Icon/color mapping for each phase. */
const phaseConfig: Record<
  AgentPhase,
  { icon: string; color: string; bgColor: string }
> = {
  OBSERVE: { icon: "👁", color: "text-info", bgColor: "bg-info-muted" },
  RETRIEVE: { icon: "🔍", color: "text-accent", bgColor: "bg-accent-muted" },
  REASON: { icon: "🧠", color: "text-primary", bgColor: "bg-primary-muted" },
  PLAN: { icon: "📋", color: "text-primary-light", bgColor: "bg-primary-muted" },
  TOOL_CALL: { icon: "🔧", color: "text-warning", bgColor: "bg-warning-muted" },
  RESULT: { icon: "✨", color: "text-accent-green", bgColor: "bg-accent-green-muted" },
  COMPLETE: { icon: "✅", color: "text-success", bgColor: "bg-success-muted" },
  ERROR: { icon: "❌", color: "text-error", bgColor: "bg-error-muted" },
};

const POLL_INTERVAL = 1000; // 1 second

export function AnalysisTimeline({ runId }: AnalysisTimelineProps) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [polling, setPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const lastSequenceRef = useRef(-1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchEvents = useCallback(async () => {
    try {
      const afterSeq = lastSequenceRef.current;
      const params = afterSeq >= 0 ? `?after_sequence=${afterSeq + 1}` : "";
      const res = await fetch(`/api/runs/${runId}/events${params}`);

      if (!res.ok) {
        // Don't stop polling on transient errors
        if (res.status >= 500) return;
        setError("Failed to fetch events.");
        setPolling(false);
        return;
      }

      const newEvents: AgentEvent[] = await res.json();

      if (newEvents.length > 0) {
        setEvents((prev) => [...prev, ...newEvents]);
        lastSequenceRef.current = newEvents[newEvents.length - 1].sequence;

        // Check for terminal phases
        const hasTerminal = newEvents.some(
          (e) => e.phase === "COMPLETE" || e.phase === "ERROR",
        );
        if (hasTerminal) {
          setPolling(false);
        }
      }
    } catch {
      // Network error — keep polling, it might recover
    }
  }, [runId]);

  useEffect(() => {
    if (!polling) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Immediate first fetch
    fetchEvents();

    // Then poll at interval
    intervalRef.current = setInterval(fetchEvents, POLL_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [polling, fetchEvents]);

  const isComplete = events.some((e) => e.phase === "COMPLETE");
  const isFailed = events.some((e) => e.phase === "ERROR");
  const lastEvent = events[events.length - 1];

  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text">
          {isComplete
            ? "Analysis Complete"
            : isFailed
              ? "Analysis Failed"
              : "Analyzing…"}
        </h3>
        {polling && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
            Processing
          </div>
        )}
      </div>

      {/* Timeline */}
      <div className="space-y-0">
        {events.map((event, index) => {
          const config = phaseConfig[event.phase] ?? phaseConfig.OBSERVE;
          const isLast = index === events.length - 1;

          return (
            <div
              key={event.id}
              className="flex gap-3 animate-in fade-in slide-in-from-top-2 duration-300"
            >
              {/* Timeline connector */}
              <div className="flex flex-col items-center">
                <div
                  className={`flex items-center justify-center w-8 h-8 rounded-full ${config.bgColor} ${config.color} text-sm shrink-0`}
                >
                  {config.icon}
                </div>
                {!isLast && (
                  <div className="w-0.5 flex-1 min-h-4 bg-border my-1" />
                )}
              </div>

              {/* Event content */}
              <div className={`pb-4 ${isLast ? "pb-0" : ""}`}>
                <p className="text-sm font-medium text-text">{event.label}</p>
                {event.detail && (
                  <p className="text-xs text-text-secondary mt-0.5 max-w-lg break-words">
                    {event.detail}
                  </p>
                )}
                {event.tool_name && (
                  <span className="inline-block mt-1 text-xs font-mono text-text-muted bg-surface-highlight px-2 py-0.5 rounded">
                    {event.tool_name}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state while waiting for first event */}
      {events.length === 0 && !error && (
        <div className="flex items-center gap-3 py-4">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <p className="text-sm text-text-muted">
            Waiting for agent to start…
          </p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-4 rounded-lg bg-error-muted border border-error/20 px-4 py-3 text-sm text-error">
          {error}
          <button
            onClick={() => {
              setError(null);
              setPolling(true);
            }}
            className="ml-2 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Completion summary */}
      {isComplete && lastEvent?.detail && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-sm text-text-secondary whitespace-pre-wrap">
            {lastEvent.detail}
          </p>
        </div>
      )}

      {/* Failed state with retry hint */}
      {isFailed && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-sm text-error">
            The analysis encountered an error. You can retry from the button above.
          </p>
        </div>
      )}
    </Card>
  );
}
