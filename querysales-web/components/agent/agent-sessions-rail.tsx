"use client";

/** Left rail listing past agent chat sessions — pick one to resume it. */

import { MessageSquarePlusIcon, MessageSquareIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

export function AgentSessionsRail({
  sessions,
  activeId,
  loading,
  error,
  onSelect,
  onNewChat,
}: {
  sessions: RunSummary[];
  activeId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}) {
  return (
    <div className="flex h-[calc(100vh-11rem)] w-64 shrink-0 flex-col gap-2 rounded-xl border-[0.5px] border-line bg-card p-2">
      <Button variant="outline" size="sm" className="justify-start" onClick={onNewChat}>
        <MessageSquarePlusIcon />
        New chat
      </Button>

      <div className="flex-1 space-y-0.5 overflow-y-auto">
        {loading ? (
          <p className="px-2 py-3 text-xs text-fg-muted">Loading sessions…</p>
        ) : error ? (
          <p className="px-2 py-3 text-xs text-danger">{error}</p>
        ) : sessions.length === 0 ? (
          <p className="px-2 py-3 text-xs text-fg-muted">
            No past conversations yet.
          </p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(s.id)}
              aria-current={activeId === s.id ? "true" : undefined}
              className={cn(
                "flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors",
                activeId === s.id
                  ? "bg-muted text-fg"
                  : "text-fg-secondary hover:bg-muted hover:text-fg",
              )}
            >
              <MessageSquareIcon className="mt-0.5 size-3.5 shrink-0 text-fg-muted" />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 leading-snug">
                  {s.title ?? "New conversation"}
                </span>
                <span className="mt-0.5 block text-[11px] text-fg-muted">
                  {timeAgo(s.created_at)}
                </span>
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
