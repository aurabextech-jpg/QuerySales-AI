/**
 * Status pills — rule 3: badges are never filled with colour. They are a
 * neutral outline pill carrying a 6px colour dot. Colour lives only in the
 * dot, so a table of statuses reads as one calm row of neutral chips.
 */

import { cn } from "@/lib/utils";
import type { LeadStatus } from "@/lib/types";

type DotTone = "qualified" | "nurture" | "neutral" | "danger" | "active";

const dotTone: Record<DotTone, string> = {
  qualified: "bg-dot-qualified",
  nurture: "bg-dot-nurture",
  neutral: "bg-dot-neutral",
  danger: "bg-danger",
  active: "bg-dot-qualified animate-signal-pulse",
};

export function Dot({
  tone = "neutral",
  className,
}: {
  tone?: DotTone;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn("size-1.5 shrink-0 rounded-full", dotTone[tone], className)}
    />
  );
}

export function StatusPill({
  tone = "neutral",
  children,
  className,
}: {
  tone?: DotTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        "hairline bg-transparent text-fg-secondary",
        className,
      )}
    >
      <Dot tone={tone} />
      {children}
    </span>
  );
}

/* ── Domain mappings ─────────────────────────────────────────────────── */

const leadTone: Record<LeadStatus, DotTone> = {
  New: "neutral",
  Analyzing: "active",
  Qualified: "qualified",
  Nurture: "nurture",
  Disqualified: "danger",
  Contacted: "neutral",
};

export function LeadStatusPill({ status }: { status: LeadStatus }) {
  return <StatusPill tone={leadTone[status] ?? "neutral"}>{status}</StatusPill>;
}

export function RunStatusPill({ status }: { status: string }) {
  const tone: DotTone =
    status === "completed"
      ? "qualified"
      : status === "failed"
        ? "danger"
        : "active";
  return <StatusPill tone={tone}>{status}</StatusPill>;
}

export function DocStatusPill({ status }: { status: string }) {
  const tone: DotTone =
    status === "indexed"
      ? "qualified"
      : status === "failed"
        ? "danger"
        : status === "uploaded"
          ? "neutral"
          : "active";
  return <StatusPill tone={tone}>{status}</StatusPill>;
}

/**
 * Score — data colour (--data), never lime (rule 1). Tabular figures so
 * columns of scores line up.
 */
export function Score({
  value,
  suffix = "/100",
  className,
}: {
  value: number | null | undefined;
  suffix?: string;
  className?: string;
}) {
  if (value == null) {
    return <span className="text-sm text-fg-muted">—</span>;
  }
  return (
    <span className={cn("tabular font-semibold text-data", className)}>
      {value}
      <span className="text-fg-muted font-normal">{suffix}</span>
    </span>
  );
}
