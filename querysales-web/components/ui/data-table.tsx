"use client";

import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, SearchIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableHead } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { SortState } from "@/hooks/use-data-table";

/**
 * Sortable column header. The arrow is the only affordance — headers stay
 * neutral text (rule 1: lime is for actions, not labels).
 */
export function SortableHead<K extends string>({
  columnKey,
  sort,
  onSort,
  children,
  align = "left",
  className,
}: {
  columnKey: K;
  sort: SortState<K> | null;
  onSort: (key: K) => void;
  children: React.ReactNode;
  align?: "left" | "right";
  className?: string;
}) {
  const active = sort?.key === columnKey;
  const Icon = !active
    ? ArrowUpDownIcon
    : sort.direction === "asc"
      ? ArrowUpIcon
      : ArrowDownIcon;

  return (
    <TableHead className={cn(align === "right" && "text-right", className)}>
      <button
        type="button"
        onClick={() => onSort(columnKey)}
        aria-label={`Sort by ${String(children)}`}
        className={cn(
          "group -mx-1.5 inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 transition-colors",
          "hover:text-fg",
          active ? "text-fg" : "text-fg-muted",
          align === "right" && "flex-row-reverse",
        )}
      >
        {children}
        <Icon
          className={cn(
            "size-3 transition-opacity",
            active ? "opacity-100" : "opacity-0 group-hover:opacity-60",
          )}
        />
      </button>
    </TableHead>
  );
}

export interface FacetOption {
  value: string;
  label: string;
}

export interface Facet {
  name: string;
  label: string;
  options: FacetOption[];
}

/**
 * Table toolbar — search box, facet selects, active-filter reset.
 * Sits above every list in the app so filtering feels the same everywhere.
 */
export function DataTableToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Search…",
  facets = [],
  facetValues,
  onFacetChange,
  activeFilterCount,
  onReset,
  showing,
  total,
  children,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  facets?: Facet[];
  facetValues: Record<string, string>;
  onFacetChange: (name: string, value: string) => void;
  activeFilterCount: number;
  onReset: () => void;
  showing: number;
  total: number;
  /** Extra controls, e.g. a sort select or an upload button. */
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-fg-muted" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-8 pl-8"
            aria-label={searchPlaceholder}
          />
        </div>

        {facets.map((facet) => (
          <Select
            key={facet.name}
            value={facetValues[facet.name] ?? "all"}
            onValueChange={(value) => onFacetChange(facet.name, value)}
          >
            <SelectTrigger className="h-8 w-full sm:w-[150px]" size="sm">
              <SelectValue placeholder={facet.label} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All {facet.label.toLowerCase()}</SelectItem>
              {facet.options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ))}

        {activeFilterCount > 0 && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <XIcon />
            Clear
          </Button>
        )}

        {children}
      </div>

      <p className="text-xs text-fg-muted tabular">
        {showing === total
          ? `${total} result${total === 1 ? "" : "s"}`
          : `${showing} of ${total}`}
      </p>
    </div>
  );
}
