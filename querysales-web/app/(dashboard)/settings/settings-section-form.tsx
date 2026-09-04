/**
 * Settings section form — client component for editing one config section.
 *
 * Each user manages their own providers (plan §52): the form PUTs to
 * /api/settings/{section}, tests via POST /api/settings/{section}/test,
 * and can remove the config with DELETE. Secrets are only ever *sent* —
 * the key input starts empty ("leave blank to keep the current key") and
 * the stored key is displayed masked, never fetched into the browser.
 */

"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type {
  EmbeddingConfig,
  EmailConfig,
  LLMConfig,
  SettingsSection,
} from "@/lib/types";

type SectionConfig = LLMConfig | EmbeddingConfig | EmailConfig;

interface Field {
  name: string;
  label: string;
  type: "text" | "password" | "number";
  placeholder?: string;
  hint?: string;
  step?: string;
}

const INPUT_CLASS =
  "w-full rounded-lg border border-border bg-surface-highlight px-4 py-2.5 text-text placeholder:text-text-muted outline-none focus:border-primary focus:ring-1 focus:ring-primary transition";

const SECTIONS: Record<
  SettingsSection,
  { title: string; description: string; fields: Field[] }
> = {
  llm: {
    title: "AI / LLM",
    description:
      "Any OpenAI-compatible endpoint powers agent reasoning and outreach generation.",
    fields: [
      { name: "base_url", label: "Base URL", type: "text", placeholder: "https://api.openai.com/v1" },
      { name: "model", label: "Model", type: "text", placeholder: "gpt-4o-mini" },
      {
        name: "api_key",
        label: "API key",
        type: "password",
        placeholder: "sk-••••••••••••",
        hint: "Leave blank to keep the current key.",
      },
      { name: "temperature", label: "Temperature", type: "number", step: "0.1", placeholder: "0.7" },
      { name: "max_tokens", label: "Max tokens", type: "number", placeholder: "4096" },
    ],
  },
  embedding: {
    title: "Embeddings",
    description:
      "Embedding model for knowledge vectorization. Dimension is fixed at 1536.",
    fields: [
      { name: "base_url", label: "Base URL", type: "text", placeholder: "https://api.openai.com/v1" },
      { name: "model", label: "Model", type: "text", placeholder: "text-embedding-3-small" },
      {
        name: "api_key",
        label: "API key",
        type: "password",
        placeholder: "sk-••••••••••••",
        hint: "Leave blank to keep the current key.",
      },
    ],
  },
  email: {
    title: "Email / Outreach",
    description:
      "SMTP credentials for sending outreach emails. Gmail: use an App Password.",
    fields: [
      { name: "email_address", label: "Email address", type: "text", placeholder: "you@gmail.com" },
      { name: "smtp_host", label: "SMTP host", type: "text", placeholder: "smtp.gmail.com" },
      { name: "smtp_port", label: "SMTP port", type: "number", placeholder: "587" },
      {
        name: "smtp_password",
        label: "SMTP password",
        type: "password",
        placeholder: "••••••••••••",
        hint: "Leave blank to keep the current password.",
      },
    ],
  },
};

/** Non-secret values from the loaded config; secret fields stay empty. */
function initialValues(
  section: SettingsSection,
  config: SectionConfig | null,
): Record<string, string> {
  if (!config?.configured) {
    return section === "email"
      ? { email_address: "", smtp_host: "smtp.gmail.com", smtp_port: "587" }
      : section === "llm"
        ? { base_url: "", model: "", temperature: "0.7", max_tokens: "4096" }
        : { base_url: "", model: "" };
  }
  if (section === "llm") {
    const c = config as LLMConfig;
    return {
      base_url: c.base_url ?? "",
      model: c.model ?? "",
      temperature: String(c.temperature ?? 0.7),
      max_tokens: String(c.max_tokens ?? 4096),
    };
  }
  if (section === "embedding") {
    const c = config as EmbeddingConfig;
    return { base_url: c.base_url ?? "", model: c.model ?? "" };
  }
  const c = config as EmailConfig;
  return {
    email_address: c.email_address ?? "",
    smtp_host: c.smtp_host ?? "smtp.gmail.com",
    smtp_port: String(c.smtp_port ?? 587),
  };
}

/** Build the PUT body matching the backend's *ConfigUpdate models. */
function buildBody(section: SettingsSection, values: Record<string, string>) {
  if (section === "llm") {
    return {
      provider_name: "openai",
      base_url: values.base_url,
      model: values.model,
      ...(values.api_key ? { api_key: values.api_key } : {}),
      temperature: Number(values.temperature) || 0.7,
      max_tokens: Number(values.max_tokens) || 4096,
    };
  }
  if (section === "embedding") {
    return {
      provider_name: "openai",
      base_url: values.base_url,
      model: values.model,
      ...(values.api_key ? { api_key: values.api_key } : {}),
      dimension: 1536, // fixed by Decision D2
    };
  }
  return {
    provider: "gmail_smtp",
    email_address: values.email_address,
    smtp_host: values.smtp_host || "smtp.gmail.com",
    smtp_port: Number(values.smtp_port) || 587,
    ...(values.smtp_password ? { smtp_password: values.smtp_password } : {}),
  };
}

interface SettingsSectionFormProps {
  section: SettingsSection;
  config: SectionConfig | null;
}

export function SettingsSectionForm({ section, config }: SettingsSectionFormProps) {
  const meta = SECTIONS[section];
  const router = useRouter();

  const [values, setValues] = useState<Record<string, string>>(() => {
    const base = initialValues(section, config);
    return { ...base, api_key: "", smtp_password: "" };
  });
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const maskedKey =
    config && "api_key_masked" in config ? config.api_key_masked : null;
  const hasPassword =
    config && "has_password" in config ? config.has_password : false;
  const configured = config?.configured ?? false;

  function set(name: string, value: string) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setBusy("save");
    setMessage(null);
    try {
      const res = await fetch(`/api/settings/${section}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildBody(section, values)),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage({ ok: false, text: data.error ?? "Save failed." });
        return;
      }
      setMessage({ ok: true, text: "Configuration saved." });
      setValues((v) => ({ ...v, api_key: "", smtp_password: "" }));
      router.refresh();
    } catch {
      setMessage({ ok: false, text: "Network error. Please try again." });
    } finally {
      setBusy(null);
    }
  }

  async function handleTest() {
    setBusy("test");
    setMessage(null);
    try {
      const res = await fetch(`/api/settings/${section}/test`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setMessage({ ok: false, text: data.error ?? "Test failed." });
        return;
      }
      setMessage({ ok: data.success, text: data.message });
    } catch {
      setMessage({ ok: false, text: "Network error. Please try again." });
    } finally {
      setBusy(null);
    }
  }

  async function handleRemove() {
    if (
      !window.confirm(
        "Remove this configuration? The agent will lose access to this provider.",
      )
    ) {
      return;
    }
    setBusy("remove");
    setMessage(null);
    try {
      const res = await fetch(`/api/settings/${section}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setMessage({ ok: false, text: data.error ?? "Remove failed." });
        return;
      }
      setMessage({ ok: true, text: "Configuration removed." });
      router.refresh();
    } catch {
      setMessage({ ok: false, text: "Network error. Please try again." });
    } finally {
      setBusy(null);
    }
  }

  const disabled = busy !== null;

  return (
    <Card>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-text">{meta.title}</h2>
          <p className="text-sm text-text-secondary mt-0.5">{meta.description}</p>
        </div>
        <Badge variant={configured ? "success" : "warning"}>
          {configured ? "Configured" : "Not configured"}
        </Badge>
      </div>

      {maskedKey && (
        <p className="text-xs text-text-muted mb-3">
          Current key:{" "}
          <code className="font-mono text-text-secondary bg-surface-highlight px-2 py-0.5 rounded">
            {maskedKey}
          </code>
        </p>
      )}
      {section === "email" && hasPassword && (
        <p className="text-xs text-text-muted mb-3">Password saved (hidden).</p>
      )}

      <form onSubmit={handleSave} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {meta.fields.map((field) => (
            <div key={field.name}>
              <label
                htmlFor={`${section}-${field.name}`}
                className="block text-sm font-medium text-text-secondary mb-1.5"
              >
                {field.label}
              </label>
              <input
                id={`${section}-${field.name}`}
                name={field.name}
                type={field.type}
                step={field.step}
                autoComplete="off"
                value={values[field.name] ?? ""}
                onChange={(e) => set(field.name, e.target.value)}
                placeholder={field.placeholder}
                className={INPUT_CLASS}
                disabled={disabled}
              />
              {field.hint && (
                <p className="text-xs text-text-muted mt-1">{field.hint}</p>
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="sm" loading={busy === "save"} disabled={disabled}>
            {configured ? "Save changes" : "Save configuration"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleTest}
            loading={busy === "test"}
            disabled={disabled || !configured}
          >
            Test connection
          </Button>
          {configured && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleRemove}
              loading={busy === "remove"}
              disabled={disabled}
              className="text-error hover:text-error"
            >
              Remove
            </Button>
          )}
          {message && (
            <span
              className={`text-sm ${message.ok ? "text-success" : "text-error"}`}
              role="status"
            >
              {message.ok ? "✓" : "✗"} {message.text}
            </span>
          )}
        </div>
      </form>
    </Card>
  );
}
