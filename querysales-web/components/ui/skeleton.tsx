/** Skeleton loader — animated placeholder for loading states. */

interface SkeletonProps {
  className?: string;
  lines?: number;
}

export function Skeleton({ className = "", lines = 1 }: SkeletonProps) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-surface-highlight animate-pulse"
          style={{ width: i === lines - 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

/** Card-shaped skeleton for dashboard tiles. */
export function SkeletonCard() {
  return (
    <div className="glass-card p-6 space-y-3">
      <div className="h-3 w-24 rounded bg-surface-highlight animate-pulse" />
      <div className="h-8 w-16 rounded bg-surface-highlight animate-pulse" />
      <div className="h-3 w-32 rounded bg-surface-highlight animate-pulse" />
    </div>
  );
}
