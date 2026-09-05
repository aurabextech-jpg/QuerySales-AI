"use client";

/**
 * Renders agent chat markdown (tables, bold/italic, lists, code, links) with
 * the app's own design tokens instead of relying on a typography plugin —
 * this repo has no @tailwindcss/typography and shouldn't grow one just for
 * one chat bubble.
 */

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

const components: Components = {
  p: ({ className, ...props }) => (
    <p className={cn("mb-2 leading-relaxed last:mb-0", className)} {...props} />
  ),
  strong: ({ className, ...props }) => (
    <strong className={cn("font-semibold text-fg", className)} {...props} />
  ),
  em: ({ className, ...props }) => (
    <em className={cn("italic", className)} {...props} />
  ),
  ul: ({ className, ...props }) => (
    <ul
      className={cn("mb-2 ml-4 list-disc space-y-1 last:mb-0", className)}
      {...props}
    />
  ),
  ol: ({ className, ...props }) => (
    <ol
      className={cn("mb-2 ml-4 list-decimal space-y-1 last:mb-0", className)}
      {...props}
    />
  ),
  li: ({ className, ...props }) => (
    <li className={cn("leading-relaxed", className)} {...props} />
  ),
  a: ({ className, ...props }) => (
    <a
      className={cn(
        "text-signal underline underline-offset-2 hover:text-signal/80",
        className,
      )}
      target="_blank"
      rel="noreferrer"
      {...props}
    />
  ),
  h1: ({ className, ...props }) => (
    <h1
      className={cn(
        "mt-3 mb-2 text-base font-semibold text-fg first:mt-0",
        className,
      )}
      {...props}
    />
  ),
  h2: ({ className, ...props }) => (
    <h2
      className={cn(
        "mt-3 mb-2 text-sm font-semibold text-fg first:mt-0",
        className,
      )}
      {...props}
    />
  ),
  h3: ({ className, ...props }) => (
    <h3
      className={cn(
        "mt-2 mb-1 text-sm font-semibold text-fg first:mt-0",
        className,
      )}
      {...props}
    />
  ),
  blockquote: ({ className, ...props }) => (
    <blockquote
      className={cn(
        "mb-2 border-l-2 border-line pl-3 text-fg-secondary italic last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  hr: ({ className, ...props }) => (
    <hr className={cn("my-3 border-line", className)} {...props} />
  ),
  code: ({ className, ...props }) => (
    <code
      className={cn(
        "rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-fg-secondary",
        className,
      )}
      {...props}
    />
  ),
  pre: ({ className, ...props }) => (
    <pre
      className={cn(
        "mb-2 overflow-x-auto rounded-lg border-[0.5px] border-line bg-muted/60 p-3 font-mono text-[11px] leading-relaxed last:mb-0 [&>code]:bg-transparent [&>code]:p-0",
        className,
      )}
      {...props}
    />
  ),
  table: ({ className, ...props }) => (
    <div className="mb-2 overflow-x-auto rounded-lg border-[0.5px] border-line last:mb-0">
      <table className={cn("w-full border-collapse text-xs", className)} {...props} />
    </div>
  ),
  thead: ({ className, ...props }) => (
    <thead className={cn("bg-muted/60", className)} {...props} />
  ),
  th: ({ className, ...props }) => (
    <th
      className={cn(
        "border-b-[0.5px] border-line px-2.5 py-1.5 text-left font-medium text-fg",
        className,
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }) => (
    <td
      className={cn(
        "border-b-[0.5px] border-line px-2.5 py-1.5 align-top text-fg-secondary",
        className,
      )}
      {...props}
    />
  ),
};

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="text-sm break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
