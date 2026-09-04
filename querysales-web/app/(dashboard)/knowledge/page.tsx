/** Knowledge base — the corpus the agent searches with pgvector. */

import { apiGet } from "@/lib/api-client";
import {
  KnowledgeTable,
  KnowledgeUploadButton,
} from "@/components/knowledge/knowledge-table";
import type { KnowledgeDocument } from "@/lib/types";

export default async function KnowledgePage() {
  let docs: KnowledgeDocument[] = [];
  let error: string | null = null;

  try {
    docs = await apiGet<KnowledgeDocument[]>("/api/knowledge");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load documents.";
  }

  const indexed = docs.filter((d) => d.status === "indexed").length;
  const chunks = docs.reduce((sum, d) => sum + (d.chunk_count ?? 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-fg">Knowledge base</h2>
          <p className="mt-0.5 text-sm text-fg-secondary">
            {indexed} indexed{" "}
            {indexed === 1 ? "document" : "documents"} ·{" "}
            <span className="tabular">{chunks}</span> searchable chunks
          </p>
        </div>
        <KnowledgeUploadButton />
      </div>

      <KnowledgeTable docs={docs} error={error} />
    </div>
  );
}
