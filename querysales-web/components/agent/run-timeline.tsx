"use client";

/**
 * Expandable trace timeline for a finished run. Each phase collapses to a
 * one-line summary; expanding shows the full detail — the knowledge query and
 * its sources, tool arguments, or the outreach draft.
 */

import { useState } from "react";
import {
  BrainIcon,
  CheckIcon,
  ChevronRightIcon,
  ClipboardListIcon,
  EyeIcon,
  OctagonXIcon,
  SearchIcon,
  SparklesIcon,
  WrenchIcon,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentEvent, AgentPhase } from "@/lib/types";

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

/** Detail long enough to be worth hiding behind a disclosure. */
const EXPAND_THRESHOLD = 120;

function TraceRow({ event, last }: { event: AgentEvent; last: boolean }) {
  const Icon = PHASE_ICON[event.phase] ?? EyeIcon;
  const detail = event.detail ?? "";
  const expandable = detail.length > EXPAND_THRESHOLD;
  const [open, setOpen] = useState(false);

  const nodeTone =
    event.phase === "ERROR"
      ? "border-danger/40 bg-danger-tint text-danger"
      : event.phase === "COMPLETE"
        ? "border-transparent bg-signal text-on-signal"
        : "border-line bg-muted text-fg-secondary";

  const body = (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className={cn(
            "flex size-7 shrink-0 items-center justify-center rounded-full border-[0.5px]",
            nodeTone,
          )}
        >
          <Icon className="size-3.5" />
        </span>
        {!last && <div className="my-1 w-px flex-1 bg-line" />}
      </div>

      <div className={cn("min-w-0 flex-1", last ? "pb-1" : "pb-5")}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-medium tracking-wider text-fg-muted uppercase">
            {event.phase}
          </span>
          {event.tool_name && (
            <code className="rounded border-[0.5px] border-line bg-muted px-1.5 py-0.5 font-mono text-[11px] text-fg-secondary">
              {event.tool_name}
            </code>
          )}
        </div>

        <p className="mt-1 flex items-center gap-1.5 text-sm font-medium text-fg">
          {event.label}
          {expandable && (
            <ChevronRightIcon
              className={cn(
                "size-3.5 shrink-0 text-fg-muted transition-transform",
                open && "rotate-90",
              )}
            />
          )}
        </p>

        {detail &&
          (expandable && !open ? (
            <p className="mt-1 line-clamp-1 text-xs text-fg-secondary">{detail}</p>
          ) : (
            detail && (
              <pre className="mt-2 max-h-80 overflow-auto rounded-lg border-[0.5px] border-line bg-muted/60 p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-fg-secondary">
                {detail}
              </pre>
            )
          ))}
      </div>
    </div>
  );

  if (!expandable) {
    return <li className="px-4 pt-4 first:pt-4">{body}</li>;
  }

  return (
    <li className="px-4 pt-4 first:pt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full cursor-pointer text-left"
      >
        {body}
      </button>
    </li>
  );
}

export function RunTimeline({ events }: { events: AgentEvent[] }) {
  return (
    <ol className="pb-4">
      {events.map((event, i) => (
        <TraceRow
          key={event.id}
          event={event}
          last={i === events.length - 1}
        />
      ))}
    </ol>
  );
}
