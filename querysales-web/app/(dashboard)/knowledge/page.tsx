/**
 * Knowledge page — placeholder for Phase 9.
 */

import { Card } from "@/components/ui/card";

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Knowledge Base</h1>
        <p className="text-text-secondary mt-1">
          Upload and manage documents for RAG-powered analysis
        </p>
      </div>

      <Card>
        <p className="text-sm text-text-muted">
          Knowledge document management will be built in Phase 9.
        </p>
      </Card>
    </div>
  );
}
