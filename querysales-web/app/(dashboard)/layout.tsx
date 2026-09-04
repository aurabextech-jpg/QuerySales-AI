/**
 * Dashboard layout — sidebar + content area.
 * All pages under (dashboard) get the sidebar automatically.
 */

import { Sidebar } from "@/components/sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      {/* Content area — offset by sidebar width on desktop */}
      <main className="flex-1 md:ml-[var(--sidebar-width)] min-h-screen">
        <div className="p-6 md:p-8 max-w-7xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
