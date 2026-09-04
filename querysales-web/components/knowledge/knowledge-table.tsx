"use client";

import { useCallback, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { BookOpenIcon, Trash2Icon, UploadIcon } from "lucide-react";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTableToolbar, SortableHead, type Facet } from "@/components/ui/data-table";
import { EmptyState, ErrorBanner } from "@/components/ui/states";
import { DocStatusPill } from "@/components/ui/status";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDataTable, type Sortable } from "@/hooks/use-data-table";
import { timeAgo } from "@/lib/format";
import type { KnowledgeDocument } from "@/lib/types";

const MAX_SIZE_MB = 10;
const ALLOWED = [".md", ".txt", ".pdf"];

type ColumnKey = "document" | "type" | "chunks" | "status" | "created";

/** Upload control — validates client-side against the same rules as the API. */
export function KnowledgeUploadButton() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!ALLOWED.includes(ext)) {
      toast.error("Unsupported file type", {
        description: `Use ${ALLOWED.join(", ")}.`,
      });
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      toast.error("File too large", {
        description: `Maximum size is ${MAX_SIZE_MB} MB.`,
      });
      if (inputRef.current) inputRef.current.value = "";
      return;
    }

    setUploading(true);
    const pending = toast.loading(`Indexing ${file.name}…`, {
      description: "Extracting → chunking → embedding",
    });

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/knowledge", { method: "POST", body: formData });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error("Upload failed", { id: pending, description: data.error });
        return;
      }

      toast.success("Document indexed", {
        id: pending,
        description: `${file.name} is now searchable by the agent.`,
      });
      router.refresh();
    } catch {
      toast.error("Network error", {
        id: pending,
        description: "The upload did not reach the server.",
      });
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED.join(",")}
        onChange={handleChange}
        className="hidden"
      />
      {/* Rule 2 — the single lime action on the knowledge screen. */}
      <Button onClick={() => inputRef.current?.click()} disabled={uploading}>
        <UploadIcon />
        {uploading ? "Uploading…" : "Upload knowledge"}
      </Button>
    </>
  );
}

export function KnowledgeTable({
  docs,
  error,
}: {
  docs: KnowledgeDocument[];
  error?: string | null;
}) {
  const router = useRouter();
  const [deleting, setDeleting] = useState<string | null>(null);

  const sortValue = useCallback(
    (doc: KnowledgeDocument, key: ColumnKey): Sortable => {
      switch (key) {
        case "document":
          return doc.title ?? doc.filename;
        case "type":
          return doc.file_type;
        case "chunks":
          return doc.chunk_count;
        case "status":
          return doc.status;
        case "created":
          return doc.created_at;
      }
    },
    [],
  );

  const searchValue = useCallback(
    (doc: KnowledgeDocument) => `${doc.title ?? ""} ${doc.filename}`,
    [],
  );

  const filters = useMemo(
    () => ({
      status: (doc: KnowledgeDocument, value: string) => doc.status === value,
      type: (doc: KnowledgeDocument, value: string) => doc.file_type === value,
    }),
    [],
  );

  const table = useDataTable<KnowledgeDocument, ColumnKey>({
    rows: docs,
    sortValue,
    searchValue,
    filters,
    initialSort: { key: "created", direction: "desc" },
  });

  const types = Array.from(new Set(docs.map((d) => d.file_type).filter(Boolean)));

  const facets: Facet[] = [
    {
      name: "status",
      label: "Status",
      options: [
        { value: "indexed", label: "Indexed" },
        { value: "uploaded", label: "Uploaded" },
        { value: "embedding", label: "Embedding" },
        { value: "failed", label: "Failed" },
      ],
    },
    ...(types.length > 1
      ? [
          {
            name: "type",
            label: "Type",
            options: types.map((t) => ({ value: t, label: t.toUpperCase() })),
          },
        ]
      : []),
  ];

  async function handleDelete(doc: KnowledgeDocument) {
    const name = doc.title ?? doc.filename;
    if (!window.confirm(`Delete "${name}"? Its indexed chunks are removed too.`)) {
      return;
    }

    setDeleting(doc.id);
    try {
      const res = await fetch(`/api/knowledge/${doc.id}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error("Could not delete", { description: data.error });
        return;
      }
      toast.success("Document deleted", { description: name });
      router.refresh();
    } catch {
      toast.error("Network error", { description: "The document was not deleted." });
    } finally {
      setDeleting(null);
    }
  }

  if (error) return <ErrorBanner message={error} />;

  return (
    <div className="space-y-4">
      <DataTableToolbar
        search={table.search}
        onSearchChange={table.setSearch}
        searchPlaceholder="Search documents…"
        facets={facets}
        facetValues={table.facets}
        onFacetChange={table.setFacet}
        activeFilterCount={table.activeFilterCount}
        onReset={table.reset}
        showing={table.rows.length}
        total={table.total}
      />

      {table.rows.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={BookOpenIcon}
            title={
              table.activeFilterCount > 0
                ? "No matching documents"
                : "No knowledge yet"
            }
            description={
              table.activeFilterCount > 0
                ? "Try a different search term or clear the filters."
                : "Upload Markdown, text, or PDF files. The agent searches them with pgvector during analysis."
            }
          />
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHead columnKey="document" sort={table.sort} onSort={table.toggleSort}>
                    Document
                  </SortableHead>
                  <SortableHead columnKey="type" sort={table.sort} onSort={table.toggleSort}>
                    Type
                  </SortableHead>
                  <SortableHead
                    columnKey="chunks"
                    sort={table.sort}
                    onSort={table.toggleSort}
                    align="right"
                  >
                    Chunks
                  </SortableHead>
                  <SortableHead columnKey="status" sort={table.sort} onSort={table.toggleSort}>
                    Status
                  </SortableHead>
                  <SortableHead
                    columnKey="created"
                    sort={table.sort}
                    onSort={table.toggleSort}
                    align="right"
                  >
                    Added
                  </SortableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {table.rows.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>
                      <p className="font-medium text-fg">
                        {doc.title ?? doc.filename}
                      </p>
                      <p className="truncate text-xs text-fg-muted">{doc.filename}</p>
                      {doc.status === "failed" && doc.error_message && (
                        <p className="mt-1 text-xs text-danger">{doc.error_message}</p>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-fg-secondary uppercase">
                      {doc.file_type}
                    </TableCell>
                    <TableCell className="tabular text-right text-fg-secondary">
                      {doc.chunk_count}
                    </TableCell>
                    <TableCell>
                      <DocStatusPill status={doc.status} />
                    </TableCell>
                    <TableCell className="text-right text-xs text-fg-muted">
                      {timeAgo(doc.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Delete ${doc.title ?? doc.filename}`}
                        disabled={deleting === doc.id}
                        onClick={() => handleDelete(doc)}
                        className="text-fg-muted hover:text-danger"
                      >
                        <Trash2Icon />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}
