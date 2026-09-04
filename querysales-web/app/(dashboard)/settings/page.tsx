/**
 * Settings page — per-user configuration for LLM, embedding, and email.
 *
 * Each user has their own configuration (plan §52): secrets are stored
 * server-side, encrypted (AES-256-GCM), and only ever returned masked.
 * The three sections load independently — one failing backend call must
 * not blank the whole page.
 */

import { Card } from "@/components/ui/card";
import { apiGet } from "@/lib/api-client";
import type { EmailConfig, EmbeddingConfig, LLMConfig } from "@/lib/types";
import { SettingsSectionForm } from "./settings-section-form";

async function loadSection<T>(path: string): Promise<{ data: T | null; error: string | null }> {
  try {
    return { data: await apiGet<T>(path), error: null };
  } catch (err) {
    return { data: null, error: err instanceof Error ? err.message : "Failed to load." };
  }
}

function SectionError({ title, error }: { title: string; error: string }) {
  return (
    <Card className="border-error/30 bg-error-muted">
      <h2 className="text-base font-semibold text-text mb-1">{title}</h2>
      <p className="text-sm text-error">{error}</p>
    </Card>
  );
}

export default async function SettingsPage() {
  const [llm, embedding, email] = await Promise.all([
    loadSection<LLMConfig>("/api/settings/llm"),
    loadSection<EmbeddingConfig>("/api/settings/embedding"),
    loadSection<EmailConfig>("/api/settings/email"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Settings</h1>
        <p className="text-text-secondary mt-1">
          Configure your own AI providers — keys are encrypted at rest and
          never exposed to the browser.
        </p>
      </div>

      {llm.error ? (
        <SectionError title="AI / LLM" error={llm.error} />
      ) : (
        <SettingsSectionForm section="llm" config={llm.data} />
      )}

      {embedding.error ? (
        <SectionError title="Embeddings" error={embedding.error} />
      ) : (
        <SettingsSectionForm section="embedding" config={embedding.data} />
      )}

      {email.error ? (
        <SectionError title="Email / Outreach" error={email.error} />
      ) : (
        <SettingsSectionForm section="email" config={email.data} />
      )}
    </div>
  );
}
