/** Full message pane with reply + folder actions. */

"use client";

import { Button } from "@/components/ui/button";
import type { MailMessageDetail } from "@/lib/types";

export function MessageView({
  message,
  busy,
  onReply,
  onTrash,
  onRestore,
  onDeletePermanent,
  onClose,
}: {
  message: MailMessageDetail;
  busy: boolean;
  onReply: () => void;
  onTrash: () => void;
  onRestore: () => void;
  onDeletePermanent: () => void;
  onClose: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 hairline-b px-4 py-3">
        <h2 className="truncate text-base font-semibold text-fg">
          {message.subject || "(no subject)"}
        </h2>
        <div className="flex shrink-0 items-center gap-2">
          {!message.trashed && (
            <Button size="sm" onClick={onReply} disabled={busy}>
              Reply
            </Button>
          )}
          {!message.trashed ? (
            <Button size="sm" variant="outline" onClick={onTrash} disabled={busy}>
              Trash
            </Button>
          ) : (
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
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
      <div className="space-y-1 hairline-b px-4 py-3 text-sm">
        <p className="text-fg">
          <span className="text-fg-muted">From:</span> {message.from_addr}
        </p>
        <p className="text-fg">
          <span className="text-fg-muted">To:</span> {message.to_addrs}
        </p>
        <p className="text-fg-muted">
          {new Date(message.received_at).toLocaleString()}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4 text-sm whitespace-pre-wrap text-fg">
        {message.body_text || "(empty message)"}
      </div>
    </div>
  );
}
