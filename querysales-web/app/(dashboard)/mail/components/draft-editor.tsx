/** Editable reply draft: Save, Approve & send, Discard. */

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { MailDraft } from "@/lib/types";

export function DraftEditor({
  draft,
  busy,
  onSave,
  onSend,
  onDiscard,
  onClose,
}: {
  draft: MailDraft;
  busy: boolean;
  onSave: (fields: { to_addr: string; subject: string; body: string }) => Promise<void>;
  onSend: () => Promise<void>;
  onDiscard: () => Promise<void>;
  onClose: () => void;
}) {
  const [toAddr, setToAddr] = useState(draft.to_addr);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between hairline-b px-4 py-3">
        <h2 className="text-base font-semibold text-fg">
          {draft.status === "sent" ? "Sent reply" : "Reply draft"}
        </h2>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <div className="space-y-1">
          <Label htmlFor="draft-to">To</Label>
          <Input id="draft-to" value={toAddr} onChange={(e) => setToAddr(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="draft-subject">Subject</Label>
          <Input
            id="draft-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="draft-body">Message</Label>
          <Textarea
            id="draft-body"
            rows={14}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>

      {draft.status === "draft" && (
        <div className="flex items-center gap-2 hairline-t px-4 py-3">
          <Button
            onClick={() => run(() => onSave({ to_addr: toAddr, subject, body }))}
            disabled={busy}
            variant="outline"
          >
            Save
          </Button>
          <Button onClick={() => run(onSend)} disabled={busy}>
            Approve &amp; send
          </Button>
          <Button onClick={() => run(onDiscard)} disabled={busy} variant="ghost">
            Discard
          </Button>
        </div>
      )}
    </div>
  );
}
