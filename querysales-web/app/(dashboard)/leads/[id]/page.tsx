/**
 * Lead detail page — server component.
 * Shows lead info + Analyze CTA. params is Promise in Next 16.
 */

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge, leadStatusVariant } from "@/components/ui/badge";
import { apiGet } from "@/lib/api-client";
import type { Lead } from "@/lib/types";
import { AnalyzeButton } from "./analyze-button";

interface LeadDetailProps {
  params: Promise<{ id: string }>;
}

export default async function LeadDetailPage({ params }: LeadDetailProps) {
  const { id } = await params;

  let lead: Lead | null = null;
  let error: string | null = null;

  try {
    lead = await apiGet<Lead>(`/api/leads/${id}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load lead.";
  }

  if (error || !lead) {
    return (
      <div className="space-y-6">
        <Link
          href="/leads"
          className="text-sm text-primary hover:text-primary-light transition"
        >
          ← Back to leads
        </Link>
        <Card className="border-error/30 bg-error-muted">
          <p className="text-sm text-error">{error ?? "Lead not found."}</p>
        </Card>
      </div>
    );
  }

  const infoRows = [
    { label: "Contact", value: lead.name ?? "—" },
    { label: "Email", value: lead.email ?? "—" },
    { label: "Industry", value: lead.industry ?? "—" },
    { label: "Website", value: lead.website ?? "—" },
    { label: "Score", value: lead.score?.toString() ?? "Not scored" },
  ];

  return (
    <div className="space-y-6">
      <Link
        href="/leads"
        className="text-sm text-primary hover:text-primary-light transition"
      >
        ← Back to leads
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-text">{lead.company}</h1>
            <Badge variant={leadStatusVariant(lead.status)}>{lead.status}</Badge>
          </div>
          {lead.name && (
            <p className="text-text-secondary mt-1">{lead.name}</p>
          )}
        </div>
        <AnalyzeButton leadId={lead.id} />
      </div>

      {/* Lead info */}
      <Card>
        <h2 className="text-base font-semibold text-text mb-4">Lead Information</h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {infoRows.map((row) => (
            <div key={row.label}>
              <dt className="text-xs font-medium text-text-muted uppercase tracking-wide">
                {row.label}
              </dt>
              <dd className="text-sm text-text mt-0.5">{row.value}</dd>
            </div>
          ))}
        </dl>

        {lead.pain_points && lead.pain_points.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <dt className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">
              Pain Points
            </dt>
            <ul className="list-disc list-inside text-sm text-text-secondary space-y-1">
              {lead.pain_points.map((pp, i) => (
                <li key={i}>{pp}</li>
              ))}
            </ul>
          </div>
        )}

        {lead.notes && (
          <div className="mt-4 pt-4 border-t border-border">
            <dt className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">
              Notes
            </dt>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">
              {lead.notes}
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
