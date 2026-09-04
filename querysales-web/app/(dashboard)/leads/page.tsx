/**
 * Leads page — placeholder for Phase 8.
 */

import { Card } from "@/components/ui/card";

export default function LeadsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text">Leads</h1>
          <p className="text-text-secondary mt-1">
            Manage and analyze your sales leads
          </p>
        </div>
      </div>

      <Card>
        <p className="text-sm text-text-muted">
          Leads list with search, filters, and analysis will be built in Phase 8.
        </p>
      </Card>
    </div>
  );
}
