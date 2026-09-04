"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
import { TargetIcon } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTableToolbar, SortableHead, type Facet } from "@/components/ui/data-table";
import { EmptyState, ErrorBanner } from "@/components/ui/states";
import { LeadStatusPill, Score } from "@/components/ui/status";
import { Card } from "@/components/ui/card";
import { useDataTable, type Sortable } from "@/hooks/use-data-table";
import type { Lead, LeadStatus } from "@/lib/types";

type ColumnKey = "company" | "contact" | "industry" | "score" | "status";

const STATUSES: LeadStatus[] = [
  "New",
  "Analyzing",
  "Qualified",
  "Nurture",
  "Disqualified",
  "Contacted",
];

/**
 * Sortable, searchable, filterable lead table.
 *
 * The page fetches on the server and hands plain rows down; all sorting and
 * filtering happens here so a click never costs a round trip.
 */
export function LeadsTable({
  leads,
  error,
  compact = false,
}: {
  leads: Lead[];
  error?: string | null;
  /** Dashboard variant: no toolbar, top rows only. */
  compact?: boolean;
}) {
  const sortValue = useCallback((lead: Lead, key: ColumnKey): Sortable => {
    switch (key) {
      case "company":
        return lead.company;
      case "contact":
        return lead.name;
      case "industry":
        return lead.industry;
      case "score":
        return lead.score;
      case "status":
        return lead.status;
    }
  }, []);

  const searchValue = useCallback(
    (lead: Lead) =>
      [lead.company, lead.name, lead.email, lead.industry]
        .filter(Boolean)
        .join(" "),
    [],
  );

  const filters = useMemo(
    () => ({
      status: (lead: Lead, value: string) => lead.status === value,
      scored: (lead: Lead, value: string) =>
        value === "scored" ? lead.score != null : lead.score == null,
    }),
    [],
  );

  const table = useDataTable<Lead, ColumnKey>({
    rows: leads,
    sortValue,
    searchValue,
    filters,
    initialSort: compact ? undefined : { key: "score", direction: "desc" },
  });

  const facets: Facet[] = [
    {
      name: "status",
      label: "Status",
      options: STATUSES.map((s) => ({ value: s, label: s })),
    },
    {
      name: "scored",
      label: "Scoring",
      options: [
        { value: "scored", label: "Scored" },
        { value: "unscored", label: "Not scored" },
      ],
    },
  ];

  const rows = compact ? leads.slice(0, 6) : table.rows;

  if (error) return <ErrorBanner message={error} />;

  return (
    <div className="space-y-4">
      {!compact && (
        <DataTableToolbar
          search={table.search}
          onSearchChange={table.setSearch}
          searchPlaceholder="Search company, contact, email…"
          facets={facets}
          facetValues={table.facets}
          onFacetChange={table.setFacet}
          activeFilterCount={table.activeFilterCount}
          onReset={table.reset}
          showing={table.rows.length}
          total={table.total}
        />
      )}

      {rows.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={TargetIcon}
            title={table.activeFilterCount > 0 ? "No matching leads" : "No leads yet"}
            description={
              table.activeFilterCount > 0
                ? "Try a different search term or clear the filters."
                : "Seed the demo data to populate your pipeline."
            }
          />
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {compact ? (
                    <>
                      <TableHead>Company</TableHead>
                      <TableHead>Industry</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                      <TableHead>Status</TableHead>
                    </>
                  ) : (
                    <>
                      <SortableHead columnKey="company" sort={table.sort} onSort={table.toggleSort}>
                        Company
                      </SortableHead>
                      <SortableHead columnKey="contact" sort={table.sort} onSort={table.toggleSort}>
                        Contact
                      </SortableHead>
                      <SortableHead columnKey="industry" sort={table.sort} onSort={table.toggleSort}>
                        Industry
                      </SortableHead>
                      <SortableHead
                        columnKey="score"
                        sort={table.sort}
                        onSort={table.toggleSort}
                        align="right"
                      >
                        Score
                      </SortableHead>
                      <SortableHead columnKey="status" sort={table.sort} onSort={table.toggleSort}>
                        Status
                      </SortableHead>
                    </>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((lead) => (
                  <TableRow key={lead.id} className="group">
                    <TableCell>
                      <Link
                        href={`/leads/${lead.id}`}
                        className="font-medium text-fg underline-offset-4 hover:underline"
                      >
                        {lead.company}
                      </Link>
                      {compact && lead.name && (
                        <p className="text-xs text-fg-muted">{lead.name}</p>
                      )}
                    </TableCell>
                    {!compact && (
                      <TableCell className="text-fg-secondary">
                        {lead.name ?? "—"}
                        {lead.email && (
                          <p className="truncate text-xs text-fg-muted">{lead.email}</p>
                        )}
                      </TableCell>
                    )}
                    <TableCell className="text-fg-secondary">
                      {lead.industry ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Score value={lead.score} suffix="" />
                    </TableCell>
                    <TableCell>
                      <LeadStatusPill status={lead.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}
