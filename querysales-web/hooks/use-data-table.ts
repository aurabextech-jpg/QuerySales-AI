"use client";

import { useMemo, useState, useCallback } from "react";

export type SortDirection = "asc" | "desc";

export interface SortState<K extends string> {
  key: K;
  direction: SortDirection;
}

/** A value the table knows how to compare. `null`/`undefined` always sort last. */
export type Sortable = string | number | boolean | null | undefined;

interface UseDataTableOptions<Row, K extends string> {
  rows: Row[];
  /** Pulls the comparable value for a column key. */
  sortValue: (row: Row, key: K) => Sortable;
  /** Free-text search — return the haystack for a row. Omit to disable search. */
  searchValue?: (row: Row) => string;
  /** Facet filters: key → predicate factory. Applied when the facet is set. */
  filters?: Record<string, (row: Row, value: string) => boolean>;
  initialSort?: SortState<K>;
}

/**
 * Client-side sort · search · facet-filter for a table of already-fetched rows.
 *
 * Server components fetch and pass plain data; the interactive table wraps it
 * in this hook. Row counts here are demo-scale (tens, not thousands), so
 * sorting in the browser is the right trade — it keeps filtering instant and
 * avoids a round trip per click.
 */
export function useDataTable<Row, K extends string>({
  rows,
  sortValue,
  searchValue,
  filters,
  initialSort,
}: UseDataTableOptions<Row, K>) {
  const [sort, setSort] = useState<SortState<K> | null>(initialSort ?? null);
  const [search, setSearch] = useState("");
  const [facets, setFacets] = useState<Record<string, string>>({});

  /** Click a header: asc → desc → unsorted. */
  const toggleSort = useCallback((key: K) => {
    setSort((current) => {
      if (current?.key !== key) return { key, direction: "asc" };
      if (current.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  }, []);

  const setFacet = useCallback((name: string, value: string) => {
    setFacets((f) => {
      const next = { ...f };
      if (!value || value === "all") delete next[name];
      else next[name] = value;
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setSearch("");
    setFacets({});
  }, []);

  const visible = useMemo(() => {
    let out = rows;

    const needle = search.trim().toLowerCase();
    if (needle && searchValue) {
      out = out.filter((row) => searchValue(row).toLowerCase().includes(needle));
    }

    if (filters) {
      for (const [name, value] of Object.entries(facets)) {
        const predicate = filters[name];
        if (predicate) out = out.filter((row) => predicate(row, value));
      }
    }

    if (sort) {
      // Copy before sorting — never mutate the array handed in by the server.
      out = [...out].sort((a, b) => {
        const av = sortValue(a, sort.key);
        const bv = sortValue(b, sort.key);

        // Missing values sink to the bottom regardless of direction, so an
        // unscored lead never outranks a scored one just by flipping the arrow.
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;

        const cmp =
          typeof av === "number" && typeof bv === "number"
            ? av - bv
            : String(av).localeCompare(String(bv), undefined, {
                numeric: true,
                sensitivity: "base",
              });

        return sort.direction === "asc" ? cmp : -cmp;
      });
    }

    return out;
  }, [rows, search, facets, sort, sortValue, searchValue, filters]);

  const activeFilterCount =
    Object.keys(facets).length + (search.trim() ? 1 : 0);

  return {
    rows: visible,
    total: rows.length,
    sort,
    toggleSort,
    search,
    setSearch,
    facets,
    setFacet,
    reset,
    activeFilterCount,
  };
}
