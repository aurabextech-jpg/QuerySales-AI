/** Badge — small status indicator with color variants. */

import type { LeadStatus } from "@/lib/types";

type BadgeVariant = "default" | "primary" | "success" | "warning" | "error" | "info";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-surface-highlight text-text-secondary border-border",
  primary: "bg-primary-muted text-primary border-primary/20",
  success: "bg-success-muted text-success border-success/20",
  warning: "bg-warning-muted text-warning border-warning/20",
  error: "bg-error-muted text-error border-error/20",
  info: "bg-info-muted text-info border-info/20",
};

/** Map lead statuses to badge variants. */
export function leadStatusVariant(status: LeadStatus): BadgeVariant {
  switch (status) {
    case "New":
      return "info";
    case "Analyzing":
      return "primary";
    case "Qualified":
      return "success";
    case "Nurture":
      return "warning";
    case "Disqualified":
      return "error";
    case "Contacted":
      return "default";
    default:
      return "default";
  }
}

export function Badge({ children, variant = "default", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
