"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
import { BotIcon } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTableToolbar, SortableHead, type Facet } from "@/components/ui/data-table";
import { EmptyState, ErrorBanner } from "@/components/ui/states";
import { RunStatusPill, Score } from "@/components/ui/status";
import { Card } from "@/components/ui/card";
import { useDataTable, type Sortable } from "@/hooks/use-data-table";
import { duration, timeAgo } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

type ColumnKey = "lead" | "status" | "score" | "qualification" | "created";

export function RunsTable({
  runs,
  error,
}: {
  runs: RunSummary[];
  error?: string | null;
}) {
  const sortValue = useCallback((run: RunSummary, key: ColumnKey): Sortable => {
    switch (key) {
      case "lead":
        return run.lead_company;
      case "status":
        return run.status;
      case "score":
        return run.score;
      case "qualification":
        return run.qualification;
      case "created":
        return run.created_at;
    }
  }, []);

  const searchValue = useCallback(
    (run: RunSummary) =>
      [run.lead_company, run.qualification, run.status, run.workflow_type]
        .filter(Boolean)
        .join(" "),
    [],
  );

  const filters = useMemo(
    () => ({
      status: (run: RunSummary, value: string) => run.status === value,
      qualification: (run: RunSummary, value: string) =>
        run.qualification === value,
    }),
    [],
  );

  const table = useDataTable<RunSummary, ColumnKey>({
    rows: runs,
    sortValue,
    searchValue,
    filters,
    initialSort: { key: "created", direction: "desc" },
  });

  // Facet options come from the data, so we never offer a filter that
  // would return nothing.
  const qualifications = Array.from(
    new Set(runs.map((r) => r.qualification).filter(Boolean)),
  ) as string[];

  const facets: Facet[] = [
    {
      name: "status",
      label: "Status",
      options: [
        { value: "completed", label: "Completed" },
        { value: "running", label: "Running" },
        { value: "failed", label: "Failed" },
      ],
    },
    ...(qualifications.length > 0
      ? [
          {
            name: "qualification",
            label: "Outcome",
            options: qualifications.map((q) => ({ value: q, label: q })),
          },
        ]
      : []),
  ];

  if (error) return <ErrorBanner message={error} />;

  return (
    <div className="space-y-4">
      <DataTableToolbar
        search={table.search}
        onSearchChange={table.setSearch}
        searchPlaceholder="Search runs by lead or outcome…"
        facets={facets}
        facetValues={table.facets}
        onFacetChange={table.setFacet}
        activeFilterCount={table.activeFilterCount}
        onReset={table.reset}
        showing={table.rows.length}
        total={table.total}
      />

      {table.rows.length === 0 ? (
        <Card className="p-0">
          <EmptyState
            icon={BotIcon}
            title={
              table.activeFilterCount > 0 ? "No matching runs" : "No agent runs yet"
            }
            description={
              table.activeFilterCount > 0
                ? "Try a different search term or clear the filters."
                : "Open a lead and click Analyze to watch the agent work."
            }
          />
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHead columnKey="lead" sort={table.sort} onSort={table.toggleSort}>
                    Lead
                  </SortableHead>
                  <SortableHead columnKey="status" sort={table.sort} onSort={table.toggleSort}>
                    Status
                  </SortableHead>
                  <SortableHead
                    columnKey="score"
                    sort={table.sort}
                    onSort={table.toggleSort}
                    align="right"
                  >
                    Score
                  </SortableHead>
                  <SortableHead
                    columnKey="qualification"
                    sort={table.sort}
                    onSort={table.toggleSort}
                  >
                    Outcome
                  </SortableHead>
                  <SortableHead
                    columnKey="created"
                    sort={table.sort}
                    onSort={table.toggleSort}
                    align="right"
                  >
                    When
                  </SortableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {table.rows.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      <Link
                        href={`/runs/${run.id}`}
                        className="font-medium text-fg underline-offset-4 hover:underline"
                      >
                        {run.lead_company ?? "Unknown lead"}
                      </Link>
                      <p className="text-xs text-fg-muted">
                        {duration(run.created_at, run.completed_at)}
                      </p>
                    </TableCell>
                    <TableCell>
                      <RunStatusPill status={run.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Score value={run.score} suffix="" />
                    </TableCell>
                    <TableCell className="text-fg-secondary">
                      {run.qualification ?? "—"}
                    </TableCell>
                    <TableCell className="text-right text-xs text-fg-muted">
                      {timeAgo(run.created_at)}
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
