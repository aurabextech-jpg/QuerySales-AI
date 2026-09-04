"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  BookOpenIcon,
  BotIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MailIcon,
  MenuIcon,
  SettingsIcon,
  SparklesIcon,
  TargetIcon,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboardIcon },
  { href: "/mail", label: "Mail", icon: MailIcon },
  { href: "/agent", label: "Agent", icon: SparklesIcon },
  { href: "/leads", label: "Leads", icon: TargetIcon },
  { href: "/knowledge", label: "Knowledge", icon: BookOpenIcon },
  { href: "/runs", label: "Agent Runs", icon: BotIcon },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-4 py-4">
      <Image
        src="/logo.png"
        alt=""
        width={30}
        height={30}
        priority
        className="size-[30px] rounded-lg"
      />
      <div className="min-w-0">
        <p className="truncate text-[13px] leading-tight font-semibold text-fg">
          QuerySales AI
        </p>
        <p className="truncate text-[11px] leading-tight text-fg-muted">
          Sales Intelligence
        </p>
      </div>
    </div>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
      {NAV_ITEMS.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors",
              // Rule 1: lime marks the active nav item — the one "action" state
              // in the rail. Everything else stays neutral.
              active
                ? "bg-signal text-on-signal"
                : "text-fg-secondary hover:bg-muted hover:text-fg",
            )}
          >
            <item.icon className="size-4 shrink-0" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SignOutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleLogout() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/login");
    } catch {
      toast.error("Could not sign out. Please try again.");
      setBusy(false);
    }
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleLogout}
      disabled={busy}
      className="w-full justify-start text-fg-secondary hover:text-fg"
    >
      <LogOutIcon />
      {busy ? "Signing out…" : "Sign out"}
    </Button>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <Brand />
      <div className="mx-2 hairline-b" />
      <NavLinks onNavigate={onNavigate} />
      <div className="mx-2 hairline-t" />
      <div className="p-2">
        <SignOutButton />
      </div>
    </div>
  );
}

/** Desktop rail — fixed, hairline right edge. */
export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-(--sidebar-width) bg-sidebar hairline-r md:block">
      <SidebarBody />
    </aside>
  );
}

/** Mobile trigger — lives in the topbar, opens a sheet. */
export function SidebarMobileTrigger() {
  // The drawer closes from the nav links' onNavigate callback, so no effect
  // has to watch the pathname.
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Open navigation">
          <MenuIcon />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-(--sidebar-width) p-0">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <SidebarBody onNavigate={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}
