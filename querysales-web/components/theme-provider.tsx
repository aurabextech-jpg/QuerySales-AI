"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type * as React from "react";

/**
 * Theme provider — next-themes with `attribute="class"`, which is what
 * shadcn's `@custom-variant dark (&:is(.dark *))` reads. Every colour comes
 * from the CSS variables in globals.css, never a hardcoded hex.
 */
export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
