"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BookOpenIcon,
  BotIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MonitorIcon,
  MoonIcon,
  SettingsIcon,
  SparklesIcon,
  SunIcon,
  TargetIcon,
} from "lucide-react";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { Dot } from "@/components/ui/status";
import type { KnowledgeDocument, Lead } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboardIcon, shortcut: "D" },
  { href: "/agent", label: "Agent Chat", icon: SparklesIcon, shortcut: "A" },
  { href: "/leads", label: "Leads", icon: TargetIcon, shortcut: "L" },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpenIcon, shortcut: "K" },
  { href: "/runs", label: "Agent Runs", icon: BotIcon, shortcut: "R" },
  { href: "/settings", label: "Settings", icon: SettingsIcon, shortcut: "S" },
];

/**
 * ⌘K command palette — navigation plus live search across the user's leads
 * and knowledge documents.
 *
 * Records load once on first open and are cached for the session: the palette
 * has to feel instant, and a demo-scale dataset is small enough to filter in
 * the browser. cmdk does the matching.
 */
export function CommandPalette() {
  const router = useRouter();
  const { setTheme } = useTheme();

  const [open, setOpen] = useState(false);
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [docs, setDocs] = useState<KnowledgeDocument[] | null>(null);
  const [loading, setLoading] = useState(false);

  /**
   * Load searchable records the first time the palette opens. This runs from
   * the open event rather than an effect — fetching is a response to the user
   * acting, not state synchronization.
   */
  const loadRecords = useCallback(async () => {
    if (leads !== null || loading) return;
    setLoading(true);

    const [leadResult, docResult] = await Promise.allSettled([
      fetch("/api/leads").then((r) => (r.ok ? r.json() : [])),
      fetch("/api/knowledge").then((r) => (r.ok ? r.json() : [])),
    ]);

    setLeads(leadResult.status === "fulfilled" ? leadResult.value : []);
    setDocs(docResult.status === "fulfilled" ? docResult.value : []);
    setLoading(false);
  }, [leads, loading]);

  const handleOpenChange = useCallback(
    (next: boolean) => {
      setOpen(next);
      if (next) void loadRecords();
    },
    [loadRecords],
  );

  // ⌘K / Ctrl+K anywhere in the app. Re-subscribing when the handler or open
  // state changes is cheaper than the ref indirection it would replace.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleOpenChange(!open);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [handleOpenChange, open]);

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router],
  );

  const logout = useCallback(async () => {
    setOpen(false);
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }, [router]);

  return (
    <CommandDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Command palette"
      description="Search leads, documents, and pages"
    >
      {/* CommandDialog renders only the dialog shell in this shadcn version —
          the cmdk context comes from <Command>, so it must be mounted here or
          CommandInput throws on a missing store. */}
      <Command>
        <CommandInput placeholder="Search leads, knowledge, pages…" />
        <CommandList>
          <CommandEmpty>{loading ? "Loading…" : "No results found."}</CommandEmpty>

          <CommandGroup heading="Go to">
            {NAV.map((item) => (
              <CommandItem
                key={item.href}
                value={`nav ${item.label}`}
                onSelect={() => go(item.href)}
              >
                <item.icon />
                {item.label}
                <CommandShortcut>{item.shortcut}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>

          {leads && leads.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Leads">
                {leads.slice(0, 40).map((lead) => (
                  <CommandItem
                    key={lead.id}
                    value={`lead ${lead.company} ${lead.name ?? ""} ${lead.industry ?? ""} ${lead.email ?? ""}`}
                    onSelect={() => go(`/leads/${lead.id}`)}
                  >
                    <Dot
                      tone={
                        lead.status === "Qualified"
                          ? "qualified"
                          : lead.status === "Nurture"
                            ? "nurture"
                            : lead.status === "Disqualified"
                              ? "danger"
                              : "neutral"
                      }
                    />
                    <span className="truncate">{lead.company}</span>
                    {lead.industry && (
                      <CommandShortcut className="truncate font-normal tracking-normal">
                        {lead.industry}
                      </CommandShortcut>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}

          {docs && docs.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Knowledge">
                {docs.slice(0, 20).map((doc) => (
                  <CommandItem
                    key={doc.id}
                    value={`doc ${doc.title ?? ""} ${doc.filename}`}
                    onSelect={() => go("/knowledge")}
                  >
                    <BookOpenIcon />
                    <span className="truncate">{doc.title ?? doc.filename}</span>
                    <CommandShortcut className="uppercase">
                      {doc.file_type}
                    </CommandShortcut>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}

          <CommandSeparator />
          <CommandGroup heading="Theme">
            <CommandItem value="theme dark" onSelect={() => setTheme("dark")}>
              <MoonIcon />
              Dark
            </CommandItem>
            <CommandItem value="theme light" onSelect={() => setTheme("light")}>
              <SunIcon />
              Light
            </CommandItem>
            <CommandItem value="theme system" onSelect={() => setTheme("system")}>
              <MonitorIcon />
              System
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />
          <CommandGroup heading="Account">
            <CommandItem value="sign out logout" onSelect={logout}>
              <LogOutIcon />
              Sign out
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
