/**
 * Dashboard shell — fixed rail on desktop, sheet drawer on mobile, sticky
 * topbar, and the ⌘K palette mounted once for every page underneath.
 */

import { CommandPalette } from "@/components/command-palette";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <CommandPalette />
      <div className="md:pl-(--sidebar-width)">
        <Topbar />
        <main className="mx-auto w-full max-w-6xl px-4 py-6 md:px-6 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
