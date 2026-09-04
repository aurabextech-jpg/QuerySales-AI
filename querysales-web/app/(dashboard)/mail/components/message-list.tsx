/** Selectable message list with folder-context toolbar. */

"use client";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { MailMessageListItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { MailView } from "./folder-rail";

/**
 * states.tsx ships Empty/Error but no loading primitive, so the list renders
 * the app's inline "working" idiom — a pulsing signal dot — while a folder
 * loads (matches analysis-timeline-client.tsx).
 */
function LoadingMessages() {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-16 text-center">
      <span className="size-1.5 rounded-full bg-signal animate-signal-pulse" />
      <p className="text-sm text-fg-secondary">Loading messages…</p>
    </div>
  );
}

export function MessageList({
  view,
  messages,
  selected,
  openId,
  loading,
  error,
  busy,
  onToggle,
  onOpen,
  onSync,
  onGenerate,
  onTrash,
  onRestore,
  onDeletePermanent,
  onMarkUnread,
}: {
  view: MailView;
  messages: MailMessageListItem[];
  selected: Set<string>;
  openId: string | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
  onSync: () => void;
  onGenerate: () => void;
  onTrash: () => void;
  onRestore: () => void;
  onDeletePermanent: () => void;
  onMarkUnread: () => void;
}) {
  if (loading) return <LoadingMessages />;
  if (error) return <ErrorState message={error} />;
  if (messages.length === 0) {
    return view === "inbox" ? (
      <EmptyState
        title="No messages yet"
        description="Sync your inbox to pull in incoming email."
        action={
          <Button onClick={onSync} disabled={busy}>
            Sync inbox
          </Button>
        }
      />
    ) : (
      <EmptyState title="Nothing here" description="This folder is empty." />
    );
  }

  const anySelected = selected.size > 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 hairline-b px-3 py-2">
        {view === "inbox" && (
          <>
            <Button size="sm" variant="outline" onClick={onSync} disabled={busy}>
              Sync inbox
            </Button>
            <Button size="sm" onClick={onGenerate} disabled={!anySelected || busy}>
              Generate drafts
            </Button>
          </>
        )}
        {anySelected && view !== "trash" && (
          <>
            <Button size="sm" variant="outline" onClick={onTrash} disabled={busy}>
              Trash
            </Button>
            <Button size="sm" variant="outline" onClick={onMarkUnread} disabled={busy}>
              Mark unread
            </Button>
          </>
        )}
        {anySelected && view === "trash" && (
          <>
            <Button size="sm" variant="outline" onClick={onRestore} disabled={busy}>
              Restore
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={onDeletePermanent}
              disabled={busy}
            >
              Delete forever
            </Button>
          </>
        )}
      </div>

      <ul className="flex-1 divide-y divide-line overflow-y-auto">
        {messages.map((m) => (
          <li
            key={m.id}
            className={cn(
              "flex cursor-pointer items-start gap-3 px-3 py-3 transition-colors hover:bg-muted",
              openId === m.id && "bg-muted",
            )}
            onClick={() => onOpen(m.id)}
          >
            <input
              type="checkbox"
              checked={selected.has(m.id)}
              onClick={(e) => e.stopPropagation()}
              onChange={() => onToggle(m.id)}
              className="mt-1 accent-[var(--primary)]"
              aria-label={`Select ${m.subject || m.id}`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span
                  className={cn(
                    "truncate text-sm",
                    m.read ? "text-fg-secondary" : "font-semibold text-fg",
                  )}
                >
                  {m.direction === "inbound" ? m.from_addr : `To: ${m.to_addrs}`}
                </span>
                <span className="tabular shrink-0 text-xs text-fg-muted">
                  {new Date(m.received_at).toLocaleDateString()}
                </span>
              </div>
              <p
                className={cn(
                  "truncate text-sm",
                  m.read ? "text-fg-secondary" : "font-medium text-fg",
                )}
              >
                {m.subject || "(no subject)"}
              </p>
              <p className="truncate text-xs text-fg-muted">{m.snippet}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
