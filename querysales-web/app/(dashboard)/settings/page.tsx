/**
 * Settings page — configuration status for LLM, embedding, and email providers.
 */

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiGet } from "@/lib/api-client";
import type { SettingsStatus } from "@/lib/types";
import { SettingsTestButtons } from "./settings-test-buttons";

export default async function SettingsPage() {
  let status: SettingsStatus | null = null;
  let error: string | null = null;

  try {
    status = await apiGet<SettingsStatus>("/api/settings/status");
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load settings.";
  }

  const sections = status
    ? [
        {
          key: "llm" as const,
          title: "AI / LLM",
          description: "Large language model for agent reasoning and outreach generation.",
          ...status.llm,
        },
        {
          key: "embedding" as const,
          title: "Embeddings",
          description: "Embedding model for knowledge document vectorization.",
          ...status.embedding,
        },
        {
          key: "email" as const,
          title: "Email / Outreach",
          description: "SMTP credentials for sending outreach emails.",
          ...status.email,
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Settings</h1>
        <p className="text-text-secondary mt-1">
          Configure your AI providers and email settings
        </p>
      </div>

      {error && (
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error}</p>
        </Card>
      )}

      <div className="space-y-4">
        {sections.map((section) => (
          <Card key={section.key}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h2 className="text-base font-semibold text-text">{section.title}</h2>
                <p className="text-sm text-text-secondary mt-0.5">
                  {section.description}
                </p>
              </div>
              <Badge variant={section.configured ? "success" : "warning"}>
                {section.configured ? "Configured" : "Not configured"}
              </Badge>
            </div>

            {section.masked && (
              <div className="mb-3">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-1">
                  Current key
                </p>
                <code className="text-sm font-mono text-text-secondary bg-surface-highlight px-3 py-1.5 rounded">
                  {section.masked}
                </code>
              </div>
            )}

            <SettingsTestButtons section={section.key} configured={section.configured} />
          </Card>
        ))}
      </div>

      {/* Database info — always read-only */}
      <Card>
        <h2 className="text-base font-semibold text-text mb-3">Database</h2>
        <div className="flex items-center gap-3">
          <Badge variant="success">PostgreSQL Connected</Badge>
          <Badge variant="success">pgvector Enabled</Badge>
        </div>
        <p className="text-xs text-text-muted mt-2">
          Connection details are managed server-side and never exposed to the browser.
        </p>
      </Card>
    </div>
  );
}
