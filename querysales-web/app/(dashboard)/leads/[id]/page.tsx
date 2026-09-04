/**
 * Lead detail — server component. `params` is a Promise in Next 16.
 */

import Link from "next/link";
import { ArrowLeftIcon, ExternalLinkIcon, MailIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";
import { LeadStatusPill, Score } from "@/components/ui/status";
import { Separator } from "@/components/ui/separator";
import { apiGet } from "@/lib/api-client";
import { timeAgo } from "@/lib/format";
import type { Lead } from "@/lib/types";
import { AnalyzeButton } from "./analyze-button";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-fg">{children}</dd>
    </div>
  );
}

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let lead: Lead | null = null;
  let error: string | null = null;

  try {
    lead = await apiGet<Lead>(`/api/leads/${id}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load lead.";
  }

  if (!lead) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/leads">
            <ArrowLeftIcon />
            Back to leads
          </Link>
        </Button>
        <Card className="p-0">
          <ErrorState message={error ?? "Lead not found."} />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        size="sm"
        asChild
        className="-ml-2 text-fg-secondary hover:text-fg"
      >
        <Link href="/leads">
          <ArrowLeftIcon />
          Back to leads
        </Link>
      </Button>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-xl font-semibold text-fg">{lead.company}</h2>
            <LeadStatusPill status={lead.status} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-secondary">
            {lead.name && <span>{lead.name}</span>}
            {lead.industry && (
              <>
                <span className="text-fg-muted">·</span>
                <span>{lead.industry}</span>
              </>
            )}
            <span className="text-fg-muted">·</span>
            <span className="text-fg-muted">
              Updated {timeAgo(lead.updated_at)}
            </span>
          </div>
        </div>

        {lead.score != null && (
          <div className="shrink-0 rounded-xl border-[0.5px] border-line bg-muted px-4 py-2.5 text-center">
            <p className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
              Lead score
            </p>
            <p className="mt-0.5">
              <Score value={lead.score} className="text-xl" />
            </p>
          </div>
        )}
      </div>

      {/* The CTA + live timeline */}
      <AnalyzeButton leadId={lead.id} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Lead information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Contact">{lead.name ?? "—"}</Field>
              <Field label="Email">
                {lead.email ? (
                  <a
                    href={`mailto:${lead.email}`}
                    className="inline-flex items-center gap-1.5 text-fg underline-offset-4 hover:underline"
                  >
                    <MailIcon className="size-3.5 text-fg-muted" />
                    {lead.email}
                  </a>
                ) : (
                  "—"
                )}
              </Field>
              <Field label="Industry">{lead.industry ?? "—"}</Field>
              <Field label="Website">
                {lead.website ? (
                  <a
                    href={
                      lead.website.startsWith("http")
                        ? lead.website
                        : `https://${lead.website}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-fg underline-offset-4 hover:underline"
                  >
                    {lead.website}
                    <ExternalLinkIcon className="size-3 text-fg-muted" />
                  </a>
                ) : (
                  "—"
                )}
              </Field>
            </dl>

            {lead.notes && (
              <>
                <Separator />
                <div>
                  <p className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
                    Notes
                  </p>
                  <p className="mt-2 text-sm whitespace-pre-wrap text-fg-secondary">
                    {lead.notes}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pain points</CardTitle>
          </CardHeader>
          <CardContent>
            {lead.pain_points && lead.pain_points.length > 0 ? (
              <ul className="space-y-2.5">
                {lead.pain_points.map((point, i) => (
                  <li key={i} className="flex gap-2.5 text-sm text-fg-secondary">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-dot-neutral" />
                    {point}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-fg-muted">
                None identified yet. Run the agent to surface them.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
