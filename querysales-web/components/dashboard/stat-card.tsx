import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * KPI tile. The number is the hero; the icon is a quiet neutral marker.
 * Rule 1 — no lime here: these are data, not actions.
 */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  accent = false,
  className,
}: {
  label: string;
  value: number | string;
  hint?: string;
  icon: LucideIcon;
  /** Renders the value in the data colour — for the one metric worth the eye. */
  accent?: boolean;
  className?: string;
}) {
  return (
    <Card className={cn("gap-0 p-4", className)}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium tracking-wide text-fg-muted uppercase">
          {label}
        </p>
        <Icon className="size-3.5 shrink-0 text-fg-muted" />
      </div>
      <p
        className={cn(
          "tabular mt-2 text-2xl leading-none font-semibold",
          accent ? "text-data" : "text-fg",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-1.5 text-xs text-fg-muted">{hint}</p>}
    </Card>
  );
}

export function StatCardSkeleton() {
  return (
    <Card className="gap-0 p-4">
      <div className="h-3 w-20 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-6 w-12 animate-pulse rounded bg-muted" />
      <div className="mt-2 h-3 w-16 animate-pulse rounded bg-muted" />
    </Card>
  );
}
