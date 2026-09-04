/** Gmail-style Mail workspace: folders, list, detail, draft editor. */

"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { AnalysisTimeline } from "@/components/agent/analysis-timeline-client";
import { Card } from "@/components/ui/card";
import type {
  GenerateDraftsResult,
  MailDraft,
  MailFolderCounts,
  MailListResponse,
  MailMessageDetail,
  MailMessageListItem,
  SyncResult,
} from "@/lib/types";
import { DraftEditor } from "./components/draft-editor";
import { FolderRail, type MailView } from "./components/folder-rail";
import { MessageList } from "./components/message-list";
import { MessageView } from "./components/message-view";

async function mailFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/mail${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as
      | { detail?: string | { message?: string }[] }
      | null;
    const detail = Array.isArray(body?.detail)
      ? body?.detail.map((e) => e.message).join(", ")
      : body?.detail;
    throw new Error(detail ?? `Request failed (${res.status}).`);
  }
  return res.json() as Promise<T>;
}

export function MailClient({ initial }: { initial: MailListResponse }) {
  const router = useRouter();
  const [view, setView] = useState<MailView>("inbox");
  const [messages, setMessages] = useState<MailMessageListItem[]>(initial.messages);
  const [counts, setCounts] = useState<MailFolderCounts>(initial.counts);
  const [drafts, setDrafts] = useState<MailDraft[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openMessage, setOpenMessage] = useState<MailMessageDetail | null>(null);
  const [openDraft, setOpenDraft] = useState<MailDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatingRunId, setGeneratingRunId] = useState<string | null>(null);

  const loadFolder = useCallback(async (next: MailView) => {
    setView(next);
    setSelected(new Set());
    setOpenMessage(null);
    setOpenDraft(null);
    setError(null);
    setLoading(true);
    try {
      if (next === "drafts") {
        setDrafts(await mailFetch<MailDraft[]>("/drafts"));
      } else {
        const res = await mailFetch<MailListResponse>(`/messages?folder=${next}`);
        setMessages(res.messages);
        setCounts(res.counts);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load folder.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function handleSync() {
    setBusy(true);
    setError(null);
    try {
      const res = await mailFetch<SyncResult>("/sync", { method: "POST" });
      await loadFolder(view === "drafts" ? "inbox" : view);
      if (res.errors.length > 0) {
        setError(`Synced ${res.synced} message(s) with issues: ${res.errors.join(" ")}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const res = await mailFetch<GenerateDraftsResult>("/drafts/generate", {
        method: "POST",
        body: JSON.stringify({ message_ids: [...selected] }),
      });
      if (res.status === "failed") {
        setError(res.errors[0] ?? "Draft generation failed.");
      } else {
        setGeneratingRunId(res.run_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function messageAction(path: string, method: string) {
    setBusy(true);
    setError(null);
    try {
      await mailFetch<unknown>(path, { method });
      await loadFolder(view);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function bulkAction(pathFor: (id: string) => string, method: string) {
    setBusy(true);
    setError(null);
    try {
      await Promise.all(
        [...selected].map((id) => mailFetch<unknown>(pathFor(id), { method })),
      );
      await loadFolder(view);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function openMessageDetail(id: string) {
    setError(null);
    try {
      const detail = await mailFetch<MailMessageDetail>(`/messages/${id}`);
      setOpenDraft(null);
      setOpenMessage(detail);
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, read: true } : m)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open message.");
    }
  }

  function replyTo(message: MailMessageDetail) {
    setOpenDraft({
      id: "",
      inbound_message_id: message.id,
      run_id: null,
      to_addr: message.from_addr,
      subject: message.subject.startsWith("Re:")
        ? message.subject
        : `Re: ${message.subject}`,
      body: `\n\n---\nOn ${new Date(message.received_at).toLocaleString()}, ${message.from_addr} wrote:\n${message.body_text}`,
      status: "draft",
      sent_message_id: null,
      created_at: "",
      updated_at: "",
    });
  }

  async function saveDraft(fields: { to_addr: string; subject: string; body: string }) {
    if (!openDraft) return;
    if (openDraft.id === "") {
      const created = await mailFetch<MailDraft>("/drafts", {
        method: "POST",
        body: JSON.stringify({ ...fields, inbound_message_id: openDraft.inbound_message_id }),
      });
      setOpenDraft(created);
      return;
    }
    const updated = await mailFetch<MailDraft>(`/drafts/${openDraft.id}`, {
      method: "PUT",
      body: JSON.stringify(fields),
    });
    setOpenDraft(updated);
  }

  async function sendDraft() {
    if (!openDraft) return;
    let draftId = openDraft.id;
    if (draftId === "") {
      const created = await mailFetch<MailDraft>("/drafts", {
        method: "POST",
        body: JSON.stringify({
          to_addr: openDraft.to_addr,
          subject: openDraft.subject,
          body: openDraft.body,
          inbound_message_id: openDraft.inbound_message_id,
        }),
      });
      draftId = created.id;
    }
    await mailFetch<unknown>(`/drafts/${draftId}/send`, { method: "POST" });
    setOpenDraft(null);
    router.refresh();
    await loadFolder("sent");
  }

  async function discardDraft() {
    if (!openDraft || openDraft.id === "") return;
    await mailFetch<MailDraft>(`/drafts/${openDraft.id}/discard`, { method: "POST" });
    setOpenDraft(null);
    await loadFolder(view);
  }

  const listItems: MailMessageListItem[] =
    view === "drafts"
      ? drafts.map((d) => ({
          id: d.id,
          direction: "outbound" as const,
          from_addr: "Draft",
          to_addrs: d.to_addr,
          subject: d.subject,
          snippet: d.body.slice(0, 200),
          received_at: d.updated_at,
          read: true,
          trashed: false,
        }))
      : messages;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-fg">Mail</h1>
        <p className="mt-0.5 text-sm text-fg-secondary">
          Sync incoming email, generate AI reply drafts, and approve them before sending.
        </p>
      </div>

      {generatingRunId && (
        <AnalysisTimeline
          runId={generatingRunId}
          onComplete={() => {
            setGeneratingRunId(null);
            void loadFolder("drafts");
          }}
        />
      )}

      <div className="flex gap-4">
        <FolderRail active={view} counts={counts} onSelect={(v) => void loadFolder(v)} />

        <Card className="h-[calc(100vh-220px)] min-w-0 flex-1 gap-0 p-0">
          <MessageList
            view={view}
            messages={listItems}
            selected={selected}
            openId={openMessage?.id ?? openDraft?.id ?? null}
            loading={loading}
            error={error}
            busy={busy}
            onToggle={(id) =>
              setSelected((prev) => {
                const next = new Set(prev);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
            onOpen={(id) => {
              if (view === "drafts") {
                const draft = drafts.find((d) => d.id === id);
                if (draft) {
                  setOpenMessage(null);
                  setOpenDraft(draft);
                }
              } else {
                void openMessageDetail(id);
              }
            }}
            onSync={() => void handleSync()}
            onGenerate={() => void handleGenerate()}
            onTrash={() => void bulkAction((id) => `/messages/${id}/trash`, "POST")}
            onRestore={() => void bulkAction((id) => `/messages/${id}/restore`, "POST")}
            onDeletePermanent={() => void bulkAction((id) => `/messages/${id}`, "DELETE")}
            onMarkUnread={() => void bulkAction((id) => `/messages/${id}/unread`, "POST")}
          />
        </Card>

        {(openMessage || openDraft) && (
          <Card className="h-[calc(100vh-220px)] w-[42%] shrink-0 gap-0 p-0">
            {openDraft ? (
              <DraftEditor
                draft={openDraft}
                busy={busy}
                onSave={saveDraft}
                onSend={sendDraft}
                onDiscard={discardDraft}
                onClose={() => setOpenDraft(null)}
              />
            ) : openMessage ? (
              <MessageView
                message={openMessage}
                busy={busy}
                onReply={() => replyTo(openMessage)}
                onTrash={() => void messageAction(`/messages/${openMessage.id}/trash`, "POST")}
                onRestore={() =>
                  void messageAction(`/messages/${openMessage.id}/restore`, "POST")
                }
                onDeletePermanent={() =>
                  void messageAction(`/messages/${openMessage.id}`, "DELETE")
                }
                onClose={() => setOpenMessage(null)}
              />
            ) : null}
          </Card>
        )}
      </div>
    </div>
  );
}
