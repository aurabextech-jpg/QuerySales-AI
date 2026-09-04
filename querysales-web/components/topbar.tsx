"use client";

import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { MonitorIcon, MoonIcon, SearchIcon, SunIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMobileTrigger } from "@/components/sidebar";
import { cn } from "@/lib/utils";

const TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/agent": "Agent",
  "/leads": "Leads",
  "/knowledge": "Knowledge",
  "/runs": "Agent Runs",
  "/settings": "Settings",
};

/** Nothing to subscribe to — these snapshots only need to differ per render pass. */
const noopSubscribe = () => () => {};

/**
 * True once hydrated. `useSyncExternalStore` is the right primitive here: it
 * returns the server snapshot during SSR and the client one after hydration,
 * without a setState-in-effect round trip.
 */
function useHydrated() {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const hydrated = useHydrated();

  // The server cannot know the chosen theme, so the icon stays neutral until
  // hydration — otherwise the markup mismatches and React warns.
  const Icon = !hydrated
    ? MonitorIcon
    : theme === "light"
      ? SunIcon
      : theme === "dark"
        ? MoonIcon
        : MonitorIcon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="Change theme">
          <Icon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        <DropdownMenuItem onSelect={() => setTheme("light")}>
          <SunIcon />
          Light
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("dark")}>
          <MoonIcon />
          Dark
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("system")}>
          <MonitorIcon />
          System
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Opens the ⌘K palette by re-dispatching the shortcut the palette listens for. */
function CommandTrigger() {
  const isMac = useSyncExternalStore(
    noopSubscribe,
    () => /Mac|iPhone|iPad/.test(navigator.userAgent),
    () => false,
  );

  function open() {
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }),
    );
  }

  return (
    <button
      type="button"
      onClick={open}
      className={cn(
        "hairline flex h-8 items-center gap-2 rounded-lg bg-muted/60 px-2.5 text-xs text-fg-muted transition-colors",
        "hover:bg-muted hover:text-fg-secondary",
      )}
    >
      <SearchIcon className="size-3.5" />
      <span className="hidden sm:inline">Search…</span>
      <kbd className="hidden rounded border-[0.5px] border-line bg-surface px-1.5 py-0.5 font-mono text-[10px] sm:inline">
        {isMac ? "⌘" : "Ctrl"} K
      </kbd>
    </button>
  );
}

/** Sticky application topbar — page title, command search, theme. */
export function Topbar() {
  const pathname = usePathname();
  const title =
    TITLES[pathname] ??
    Object.entries(TITLES).find(([href]) => pathname.startsWith(`${href}/`))?.[1] ??
    "QuerySales AI";

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 bg-background/80 px-4 backdrop-blur-md hairline-b md:px-6">
      <SidebarMobileTrigger />
      <h1 className="text-sm font-semibold text-fg">{title}</h1>
      <div className="ml-auto flex items-center gap-1.5">
        <CommandTrigger />
        <ThemeToggle />
      </div>
    </header>
  );
}
