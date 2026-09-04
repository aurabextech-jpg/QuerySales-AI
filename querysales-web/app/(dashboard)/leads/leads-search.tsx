/**
 * Leads search bar — client component for search input + status filter.
 * Submits as a GET form to update URL searchParams (server refetch).
 */

"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState, type FormEvent } from "react";

interface LeadsSearchProps {
  search: string;
  status: string;
  statuses: string[];
}

export function LeadsSearch({ search, status, statuses }: LeadsSearchProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [searchValue, setSearchValue] = useState(search);
  const [statusValue, setStatusValue] = useState(status);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (searchValue) params.set("search", searchValue);
    if (statusValue) params.set("status", statusValue);
    router.push(`${pathname}?${params.toString()}`);
  }

  function handleStatusChange(value: string) {
    setStatusValue(value);
    const params = new URLSearchParams();
    if (searchValue) params.set("search", searchValue);
    if (value) params.set("status", value);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col sm:flex-row gap-3"
    >
      <input
        type="text"
        placeholder="Search by company, name, or email…"
        value={searchValue}
        onChange={(e) => setSearchValue(e.target.value)}
        className="flex-1 rounded-lg border border-border bg-surface-highlight px-4 py-2.5 text-sm text-text placeholder:text-text-muted outline-none focus:border-primary focus:ring-1 focus:ring-primary transition"
      />
      <select
        value={statusValue}
        onChange={(e) => handleStatusChange(e.target.value)}
        className="rounded-lg border border-border bg-surface-highlight px-4 py-2.5 text-sm text-text outline-none focus:border-primary focus:ring-1 focus:ring-primary transition"
      >
        <option value="">All statuses</option>
        {statuses.filter(Boolean).map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-dark transition"
      >
        Search
      </button>
    </form>
  );
}
