/**
 * Integration card — one third-party provider (ERPNext · Google Places ·
 * Google Calendar).
 *
 * The field list is driven entirely by the backend registry, so adding a
 * provider server-side needs no change here. Secret inputs start empty and
 * carry a "leave blank to keep" hint — the stored value is only ever shown
 * masked, never fetched into the browser (plan §47).
 */

"use client";

import { useState, type FormEvent } from "react";
import { CheckCircle2Icon, PlugZapIcon, SaveIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusPill } from "@/components/ui/status";
import { useRouter } from "next/navigation";
import type { Integration } from "@/lib/types";

export function IntegrationCard({ integration }: { integration: Integration }) {
  const router = useRouter();

  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const field of integration.fields) {
      // Secrets always start blank; public values prefill from the server.
      initial[field.name] = field.secret
        ? ""
        : (integration.values[field.name] ?? "");
    }
    return initial;
  });
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);

  const disabled = busy !== null;

  function set(name: string, value: string) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setBusy("save");
    try {
      // Send only non-empty fields: an untouched secret must keep its stored
      // value rather than being overwritten with "".
      const payload = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v.trim() !== ""),
      );

      const res = await fetch(`/api/settings/integrations/${integration.provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true, values: payload }),
      });
      const data = await res.json();

      if (!res.ok) {
        toast.error(`${integration.label} not saved`, { description: data.error });
        return;
      }

      toast.success(`${integration.label} saved`);
      setValues((v) => {
        const cleared = { ...v };
        for (const field of integration.fields) {
          if (field.secret) cleared[field.name] = "";
        }
        return cleared;
      });
      router.refresh();
    } catch {
      toast.error("Network error", { description: "Please try again." });
    } finally {
      setBusy(null);
    }
  }

  async function handleTest() {
    setBusy("test");
    const pending = toast.loading(`Testing ${integration.label}…`);
    try {
      const res = await fetch(
        `/api/settings/integrations/${integration.provider}/test`,
        { method: "POST" },
      );
      const data = await res.json();
      if (!res.ok || !data.success) {
        toast.error("Connection failed", { id: pending, description: data.message });
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
        `Remove the ${integration.label} configuration? The agent will lose access to it.`,
      )
    ) {
      return;
    }
    setBusy("remove");
    try {
      const res = await fetch(`/api/settings/integrations/${integration.provider}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error("Could not remove", { description: data.error });
        return;
      }
      toast.success(`${integration.label} removed`);
      router.refresh();
    } catch {
      toast.error("Network error", { description: "Please try again." });
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>{integration.label}</CardTitle>
            <p className="mt-1 text-sm text-fg-secondary">{integration.description}</p>
          </div>
          <StatusPill tone={integration.configured ? "qualified" : "neutral"}>
            {integration.configured ? "Connected" : "Not configured"}
          </StatusPill>
        </div>
      </CardHeader>

      <CardContent>
        {Object.keys(integration.masked).length > 0 && (
          <div className="mb-4 space-y-1">
            {Object.entries(integration.masked).map(([name, mask]) => (
              <p key={name} className="flex items-center gap-1.5 text-xs text-fg-muted">
                <CheckCircle2Icon className="size-3.5 shrink-0 text-dot-qualified" />
                {integration.fields.find((f) => f.name === name)?.label ?? name}{" "}
                <code className="rounded border-[0.5px] border-line bg-muted px-1.5 py-0.5 font-mono text-fg-secondary">
                  {mask}
                </code>
              </p>
            ))}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {integration.fields.map((field) => (
              <div
                key={field.name}
                className={field.secret ? undefined : "sm:col-span-2"}
              >
                <Label
                  htmlFor={`${integration.provider}-${field.name}`}
                  className="mb-1.5"
                >
                  {field.label}
                  {!field.required && (
                    <span className="ml-1 font-normal text-fg-muted">(optional)</span>
                  )}
                </Label>
                <Input
                  id={`${integration.provider}-${field.name}`}
                  name={field.name}
                  type={field.secret ? "password" : "text"}
                  autoComplete="off"
                  value={values[field.name] ?? ""}
                  onChange={(e) => set(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  disabled={disabled}
                />
                {(field.help || field.secret) && (
                  <p className="mt-1 text-xs text-fg-muted">
                    {field.help ||
                      (integration.masked[field.name]
                        ? "Leave blank to keep the stored value."
                        : "")}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Rule 2 — save is the lime action; test and remove stay quiet. */}
            <Button type="submit" size="sm" disabled={disabled}>
              <SaveIcon />
              {busy === "save" ? "Saving…" : "Save"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={disabled || !integration.configured}
            >
              <PlugZapIcon />
              {busy === "test" ? "Testing…" : "Test connection"}
            </Button>
            {integration.configured && (
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
