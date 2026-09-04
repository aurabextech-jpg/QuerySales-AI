/**
 * Knowledge page — document list + upload.
 */

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import { apiGet } from "@/lib/api-client";
import type { KnowledgeDocument } from "@/lib/types";
import { KnowledgeUpload } from "./knowledge-upload";

export default async function KnowledgePage() {
  let docs: KnowledgeDocument[] = [];
  let error: string | null = null;

  try {
    docs = await apiGet<KnowledgeDocument[]>("/api/knowledge");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load documents.";
  }

  const statusColor = (s: string) => {
    switch (s) {
      case "indexed":
        return "success" as const;
      case "failed":
        return "error" as const;
      case "uploading":
      case "extracting":
      case "chunking":
      case "embedding":
        return "primary" as const;
      default:
        return "default" as const;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Knowledge Base</h1>
          <p className="text-text-secondary mt-1">
            {docs.length} document{docs.length !== 1 ? "s" : ""}
          </p>
        </div>
        <KnowledgeUpload />
      </div>

      {error && (
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error}</p>
        </Card>
      )}

      {docs.length === 0 && !error ? (
        <EmptyState
          title="No documents yet"
          description="Upload markdown, text, or PDF files to power the RAG knowledge search."
          icon="📚"
        />
      ) : (
        <Card padding="sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 font-medium text-text-muted">Document</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Type</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Chunks</th>
                  <th className="px-4 py-2.5 font-medium text-text-muted">Status</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr
                    key={doc.id}
                    className="border-b border-border-light hover:bg-surface-highlight transition"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-text">
                        {doc.title ?? doc.filename}
                      </p>
                      <p className="text-xs text-text-muted">{doc.filename}</p>
                    </td>
                    <td className="px-4 py-3 text-text-secondary uppercase text-xs">
                      {doc.file_type}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{doc.chunk_count}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusColor(doc.status)}>{doc.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
