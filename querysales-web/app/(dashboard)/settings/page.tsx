/**
 * Settings — per-user configuration for LLM, embeddings, and email.
 *
 * Each user owns their own credentials (plan §52). Secrets are stored
 * encrypted (AES-256-GCM) and only ever returned masked. The three sections
 * load independently so one failing backend call cannot blank the page.
 */

import { DatabaseIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner } from "@/components/ui/states";
import { StatusPill } from "@/components/ui/status";
import { apiGet } from "@/lib/api-client";
import type { EmailConfig, EmbeddingConfig, LLMConfig } from "@/lib/types";
import { SettingsSectionForm } from "./settings-section-form";

async function loadSection<T>(
  path: string,
): Promise<{ data: T | null; error: string | null }> {
  try {
    return { data: await apiGet<T>(path), error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Failed to load.",
    };
  }
}

export default async function SettingsPage() {
  const [llm, embedding, email] = await Promise.all([
    loadSection<LLMConfig>("/api/settings/llm"),
    loadSection<EmbeddingConfig>("/api/settings/embedding"),
    loadSection<EmailConfig>("/api/settings/email"),
  ]);

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-fg">Settings</h2>
        <p className="mt-0.5 text-sm text-fg-secondary">
          Your own AI providers. Keys are encrypted at rest and never sent back
          to the browser.
        </p>
      </div>

      {llm.error ? (
        <ErrorBanner message={`AI / LLM — ${llm.error}`} />
      ) : (
        <SettingsSectionForm section="llm" config={llm.data} />
      )}

      {embedding.error ? (
        <ErrorBanner message={`Embeddings — ${embedding.error}`} />
      ) : (
        <SettingsSectionForm section="embedding" config={embedding.data} />
      )}

      {email.error ? (
        <ErrorBanner message={`Email — ${email.error}`} />
      ) : (
        <SettingsSectionForm section="email" config={email.data} />
      )}

      {/* Database — status only. Never the connection string. */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <DatabaseIcon className="size-4 text-fg-muted" />
            <CardTitle>Database</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
                PostgreSQL
              </dt>
              <dd className="mt-1.5">
                <StatusPill tone="qualified">Connected</StatusPill>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
                pgvector
              </dt>
              <dd className="mt-1.5">
                <StatusPill tone="qualified">Enabled</StatusPill>
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
