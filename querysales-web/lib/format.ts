/** Shared display formatters. */

/** "just now" · "12m ago" · "3h ago" · "2d ago" · a date beyond a week. */
export function timeAgo(input: string | null | undefined): string {
  if (!input) return "—";

  const then = new Date(input).getTime();
  if (Number.isNaN(then)) return "—";

  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return new Date(input).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/** Elapsed time between two timestamps, e.g. "18s" or "2m 04s". */
export function duration(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  if (!start || !end) return "—";

  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";

  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

/** Bytes → "1.4 MB". */
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
