/** Folder rail — Inbox / Sent / Drafts / Trash with live counts. */

"use client";

import type { MailFolderCounts } from "@/lib/types";
import { cn } from "@/lib/utils";

export type MailView = "inbox" | "sent" | "drafts" | "trash";

const FOLDERS: { key: MailView; label: string }[] = [
  { key: "inbox", label: "Inbox" },
  { key: "sent", label: "Sent" },
  { key: "drafts", label: "Drafts" },
  { key: "trash", label: "Trash" },
];

export function FolderRail({
  active,
  counts,
  onSelect,
}: {
  active: MailView;
  counts: MailFolderCounts;
  onSelect: (view: MailView) => void;
}) {
  const countFor = (view: MailView) =>
    view === "inbox" ? counts.inbox_unread : counts[view];

  return (
    <nav className="w-40 shrink-0 space-y-1">
      {FOLDERS.map((f) => (
        <button
          key={f.key}
          type="button"
          onClick={() => onSelect(f.key)}
          aria-current={active === f.key ? "true" : undefined}
          className={cn(
            "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            // Rule 2: the one lime CTA on this screen is "Generate drafts", so
            // the rail's selected state stays a neutral highlight rather than
            // competing with it.
            active === f.key
              ? "bg-muted text-fg"
              : "text-fg-secondary hover:bg-muted hover:text-fg",
          )}
        >
          <span>{f.label}</span>
          {countFor(f.key) > 0 && (
            <span className="tabular rounded-full bg-line px-2 py-0.5 text-xs text-fg-secondary">
              {countFor(f.key)}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
