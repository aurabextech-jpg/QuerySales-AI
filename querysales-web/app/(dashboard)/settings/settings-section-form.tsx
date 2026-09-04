/**
 * Settings section form — one config section (LLM · embeddings · email).
 *
 * Secrets are only ever *sent*: the key input starts empty ("leave blank to
 * keep the current key") and the stored value is shown masked. The browser
 * never receives the plaintext (plan §47).
 */

"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2Icon, PlugZapIcon, SaveIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusPill } from "@/components/ui/status";
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
  wide?: boolean;
}

const SECTIONS: Record<
  SettingsSection,
  { title: string; description: string; fields: Field[] }
> = {
  llm: {
    title: "AI / LLM",
    description:
      "Any OpenAI-compatible endpoint powers agent reasoning and outreach generation.",
    fields: [
      {
        name: "base_url",
        label: "Base URL",
        type: "text",
        placeholder: "https://api.openai.com/v1",
        wide: true,
      },
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
      "Vectorizes your knowledge base. Dimension is fixed at 1536 to match the pgvector column.",
    fields: [
      {
        name: "base_url",
        label: "Base URL",
        type: "text",
        placeholder: "https://api.openai.com/v1",
        wide: true,
      },
      {
        name: "model",
        label: "Model",
        type: "text",
        placeholder: "text-embedding-3-small",
      },
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
      "SMTP credentials for sending approved outreach. For Gmail, use an App Password.",
    fields: [
      {
        name: "email_address",
        label: "Email address",
        type: "text",
        placeholder: "you@gmail.com",
        wide: true,
      },
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
    if (section === "email")
      return { email_address: "", smtp_host: "smtp.gmail.com", smtp_port: "587" };
    if (section === "llm")
      return { base_url: "", model: "", temperature: "0.7", max_tokens: "4096" };
    return { base_url: "", model: "" };
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

export function SettingsSectionForm({
  section,
  config,
}: {
  section: SettingsSection;
  config: SectionConfig | null;
}) {
  const meta = SECTIONS[section];
  const router = useRouter();

  const [values, setValues] = useState<Record<string, string>>(() => ({
    ...initialValues(section, config),
    api_key: "",
    smtp_password: "",
  }));
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);

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
    try {
      const res = await fetch(`/api/settings/${section}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildBody(section, values)),
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(`${meta.title} not saved`, { description: data.error });
        return;
      }
      toast.success(`${meta.title} saved`);
      setValues((v) => ({ ...v, api_key: "", smtp_password: "" }));
      router.refresh();
    } catch {
      toast.error("Network error", { description: "Please try again." });
    } finally {
      setBusy(null);
    }
  }

  async function handleTest() {
    setBusy("test");
    const pending = toast.loading(`Testing ${meta.title.toLowerCase()}…`);
    try {
      const res = await fetch(`/api/settings/${section}/test`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.success) {
        toast.error("Connection failed", {
          id: pending,
          description: data.message ?? data.error,
        });
        return;
      }
      toast.success("Connection successful", {
        id: pending,
        description: data.message,
      });
    } catch {
      toast.error("Network error", { id: pending, description: "Please try again." });
    } finally {
      setBusy(null);
    }
  }

  async function handleRemove() {
    if (
      !window.confirm(
        `Remove the ${meta.title} configuration? The agent will lose access to this provider.`,
      )
    ) {
      return;
    }
    setBusy("remove");
    try {
      const res = await fetch(`/api/settings/${section}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error("Could not remove", { description: data.error });
        return;
      }
      toast.success(`${meta.title} configuration removed`);
      router.refresh();
    } catch {
      toast.error("Network error", { description: "Please try again." });
    } finally {
      setBusy(null);
    }
  }

  const disabled = busy !== null;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>{meta.title}</CardTitle>
            <p className="mt-1 text-sm text-fg-secondary">{meta.description}</p>
          </div>
          <StatusPill tone={configured ? "qualified" : "neutral"}>
            {configured ? "Configured" : "Not configured"}
          </StatusPill>
        </div>
      </CardHeader>

      <CardContent>
        {(maskedKey || (section === "email" && hasPassword)) && (
          <p className="mb-4 flex items-center gap-1.5 text-xs text-fg-muted">
            <CheckCircle2Icon className="size-3.5 text-dot-qualified" />
            {maskedKey ? (
              <>
                Stored key{" "}
                <code className="rounded border-[0.5px] border-line bg-muted px-1.5 py-0.5 font-mono text-fg-secondary">
                  {maskedKey}
                </code>
              </>
            ) : (
              "Password saved — never sent back to the browser."
            )}
          </p>
        )}

        <form onSubmit={handleSave} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {meta.fields.map((field) => (
              <div key={field.name} className={field.wide ? "sm:col-span-2" : undefined}>
                <Label htmlFor={`${section}-${field.name}`} className="mb-1.5">
                  {field.label}
                </Label>
                <Input
                  id={`${section}-${field.name}`}
                  name={field.name}
                  type={field.type}
                  step={field.step}
                  autoComplete="off"
                  value={values[field.name] ?? ""}
                  onChange={(e) => set(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  disabled={disabled}
                />
                {field.hint && (
                  <p className="mt-1 text-xs text-fg-muted">{field.hint}</p>
                )}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Rule 2 — save is the lime action; test and remove stay quiet. */}
            <Button type="submit" size="sm" disabled={disabled}>
              <SaveIcon />
              {busy === "save"
                ? "Saving…"
                : configured
                  ? "Save changes"
                  : "Save configuration"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={disabled || !configured}
            >
              <PlugZapIcon />
              {busy === "test" ? "Testing…" : "Test connection"}
            </Button>
            {configured && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleRemove}
                disabled={disabled}
                className="ml-auto text-fg-muted hover:text-danger"
              >
                <Trash2Icon />
                Remove
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
