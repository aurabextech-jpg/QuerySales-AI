"use client";

/**
 * Agent chat — the conversational surface onto the SalesOps orchestrator.
 *
 * The backend returns the whole run in one body (Decision D6): `steps` holds
 * every agent hand-off and tool call, `message` the final answer. So there is
 * no token-by-token stream to render — instead each assistant turn carries a
 * collapsible trace of what the agent actually did to produce it.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowUpIcon,
  BotIcon,
  ChevronRightIcon,
  UserIcon,
  WrenchIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ChatHistory, ChatResponse, ChatStep, RunSummary } from "@/lib/types";
import { MarkdownContent } from "./markdown-content";
import { AgentSessionsRail } from "./agent-sessions-rail";

interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: ChatStep[];
  failed?: boolean;
}

const SUGGESTIONS = [
  "Show me my pipeline status",
  "Which leads should I prioritise this week?",
  "Find manufacturing companies in Lahore",
  "Draft a follow-up email for Acme Manufacturing",
];

/** Collapsible record of the agent's hand-offs and tool calls for one turn. */
function StepTrace({ steps }: { steps: ChatStep[] }) {
  const [open, setOpen] = useState(false);

  const toolCalls = steps.filter((s) => s.type === "tool_start");
  if (steps.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-md text-xs text-fg-muted transition-colors hover:text-fg-secondary"
      >
        <WrenchIcon className="size-3" />
        {toolCalls.length > 0
          ? `${toolCalls.length} tool call${toolCalls.length === 1 ? "" : "s"}`
          : `${steps.length} step${steps.length === 1 ? "" : "s"}`}
        <ChevronRightIcon
          className={cn("size-3 transition-transform", open && "rotate-90")}
        />
      </button>

      {open && (
        <ol className="mt-2 space-y-1.5 rounded-lg border-[0.5px] border-line bg-muted/50 p-3">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-2 text-xs">
              <span className="tabular shrink-0 text-fg-muted">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0 flex-1">
                {step.type === "agent" ? (
                  <span className="text-fg-secondary">
                    Delegated to{" "}
                    <span className="font-medium text-fg">{step.agent}</span>
                  </span>
                ) : (
                  <>
                    <code className="font-mono text-fg-secondary">
                      {step.tool}
                    </code>
                    {step.type === "tool_result" && step.content && (
                      <p className="mt-0.5 line-clamp-3 wrap-break-word text-fg-muted">
                        {step.content}
                      </p>
                    )}
                  </>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === "user";

  return (
    <div className={cn("animate-rise flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full border-[0.5px] border-line bg-muted text-fg-secondary">
          <BotIcon className="size-3.5" />
        </span>
      )}

      <div className={cn("min-w-0", isUser ? "max-w-[80%]" : "flex-1")}>
        <div
          className={cn(
            "rounded-xl px-3.5 py-2.5 text-sm wrap-break-word",
            isUser
              ? "bg-muted text-fg whitespace-pre-wrap"
              : turn.failed
                ? "border-[0.5px] border-danger/30 bg-danger-tint text-danger whitespace-pre-wrap"
                : "border-[0.5px] border-line bg-surface text-fg",
          )}
        >
          {isUser || turn.failed ? (
            turn.content
          ) : (
            <MarkdownContent content={turn.content} />
          )}
        </div>
        {turn.steps && turn.steps.length > 0 && <StepTrace steps={turn.steps} />}
      </div>

      {isUser && (
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full border-[0.5px] border-line bg-muted text-fg-secondary">
          <UserIcon className="size-3.5" />
        </span>
      )}
    </div>
  );
}

export function AgentChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);

  const [sessions, setSessions] = useState<RunSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/runs?workflow_type=chat");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to load sessions.");
      setSessions(data as RunSummary[]);
      setSessionsError(null);
    } catch (err) {
      setSessionsError(
        err instanceof Error ? err.message : "Failed to load sessions.",
      );
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Scheduled rather than called inline: loadSessions sets state, and doing
    // that synchronously in an effect body cascades renders.
    const timer = setTimeout(loadSessions, 0);
    return () => clearTimeout(timer);
  }, [loadSessions]);

  // Keep the newest turn in view as the conversation grows.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns, busy]);

  const loadSession = useCallback(
    async (id: string) => {
      if (busy || id === runId) return;
      setBusy(true);
      try {
        const res = await fetch(`/api/chat/history?run_id=${id}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "Failed to load session.");

        const history = data as ChatHistory;
        setRunId(history.run_id);
        setTurns(
          history.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
          })),
        );
      } catch (err) {
        toast.error("Could not load that conversation", {
          description: err instanceof Error ? err.message : undefined,
        });
      } finally {
        setBusy(false);
        inputRef.current?.focus();
      }
    },
    [busy, runId],
  );

  const send = useCallback(
    async (text: string) => {
      const prompt = text.trim();
      if (!prompt || busy) return;

      const userTurn: Turn = {
        id: `u-${Date.now()}`,
        role: "user",
        content: prompt,
      };

      // Snapshot the history the backend needs *before* the optimistic update,
      // so a failed send never leaves a phantom turn in the transcript we replay.
      const history = [
        ...turns.map((t) => ({ role: t.role, content: t.content })),
        { role: "user" as const, content: prompt },
      ];
      const isNewSession = runId === null;

      setTurns((prev) => [...prev, userTurn]);
      setInput("");
      setBusy(true);

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: history, run_id: runId }),
        });

        const data = await res.json();

        if (!res.ok) {
          setTurns((prev) => [
            ...prev,
            {
              id: `a-${Date.now()}`,
              role: "assistant",
              content: data.error ?? "The agent could not answer that.",
              failed: true,
            },
          ]);
          toast.error("Agent request failed", { description: data.error });
          return;
        }

        const reply = data as ChatResponse;
        setRunId(reply.run_id);
        setTurns((prev) => [
          ...prev,
          {
            id: `a-${reply.run_id}-${prev.length}`,
            role: "assistant",
            content: reply.message,
            steps: reply.steps,
          },
        ]);
        if (isNewSession) void loadSessions();
      } catch {
        setTurns((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: "Could not reach the server. Please try again.",
            failed: true,
          },
        ]);
        toast.error("Network error");
      } finally {
        setBusy(false);
        inputRef.current?.focus();
      }
    },
    [busy, turns, runId, loadSessions],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter is a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  function reset() {
    setTurns([]);
    setRunId(null);
    setInput("");
    inputRef.current?.focus();
  }

  return (
    <div className="flex gap-4">
      <AgentSessionsRail
        sessions={sessions}
        activeId={runId}
        loading={sessionsLoading}
        error={sessionsError}
        onSelect={(id) => void loadSession(id)}
        onNewChat={reset}
      />

      <Card className="flex h-[calc(100vh-11rem)] min-w-0 flex-1 flex-col gap-0 overflow-hidden p-0">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-4 py-3 hairline-b">
          <div className="flex items-center gap-2">
            {busy && (
              <span className="size-1.5 rounded-full bg-signal animate-signal-pulse" />
            )}
            <h3 className="text-sm font-semibold text-fg">
              {busy ? "Agent working…" : "SalesOps agent"}
            </h3>
          </div>
        </div>

        {busy && (
          <div className="h-px w-full overflow-hidden bg-line">
            <div className="h-full w-1/3 bg-signal animate-sweep" />
          </div>
        )}

        {/* Transcript */}
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
          {turns.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center px-6 text-center">
              <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-muted text-fg-muted">
                <BotIcon className="size-5" />
              </div>
              <h4 className="text-sm font-semibold text-fg">
                Ask your AI sales employee
              </h4>
              <p className="mt-1 max-w-sm text-sm text-fg-secondary">
                It can search your pipeline, analyse leads, draft outreach, and
                call your connected tools.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    onClick={() => void send(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {turns.map((turn) => (
                <Bubble key={turn.id} turn={turn} />
              ))}
              {busy && (
                <div className="flex gap-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full border-[0.5px] border-line bg-muted text-fg-secondary">
                    <BotIcon className="size-3.5" />
                  </span>
                  <div className="flex items-center gap-2 rounded-xl border-[0.5px] border-line bg-surface px-3.5 py-2.5">
                    <span className="size-1.5 rounded-full bg-signal animate-signal-pulse" />
                    <span className="text-sm text-fg-secondary">
                      Reasoning and calling tools…
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Composer */}
        <div className="p-3 hairline-t">
          <div className="flex items-end gap-2">
            <Textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask the agent to find leads, analyse your pipeline, or draft outreach…"
              rows={1}
              disabled={busy}
              aria-label="Message the agent"
              className="max-h-40 min-h-9 flex-1 resize-none"
            />
            {/* Rule 2 — the single lime action on this screen. */}
            <Button
              size="icon"
              onClick={() => void send(input)}
              disabled={busy || !input.trim()}
              aria-label="Send message"
            >
              <ArrowUpIcon />
            </Button>
          </div>
          <p className="mt-1.5 text-[11px] text-fg-muted">
            Enter to send · Shift + Enter for a new line
          </p>
        </div>
      </Card>
    </div>
  );
}
