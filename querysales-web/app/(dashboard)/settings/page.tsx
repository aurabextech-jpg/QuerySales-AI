/**
 * Settings page — placeholder for Phase 9.
 */

import { Card } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Settings</h1>
        <p className="text-text-secondary mt-1">
          Configure LLM, embedding, and email providers
        </p>
      </div>

      <Card>
        <p className="text-sm text-text-muted">
          Per-user configuration forms will be built in Phase 9.
        </p>
      </Card>
    </div>
  );
}
