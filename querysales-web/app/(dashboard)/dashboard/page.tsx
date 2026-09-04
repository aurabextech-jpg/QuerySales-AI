/**
 * Dashboard — server component. Fetches stats + leads + recent runs in
 * parallel; each panel degrades on its own so one failing call never blanks
 * the page.
 */

import Link from "next/link";
import {
  ArrowRightIcon,
  BookOpenIcon,
  BotIcon,
  CircleCheckIcon,
  MailIcon,
  SparklesIcon,
  TargetIcon,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorBanner } from "@/components/ui/states";
import { RunStatusPill, Score } from "@/components/ui/status";
import { StatCard, StatCardSkeleton } from "@/components/dashboard/stat-card";
import { LeadsTable } from "@/components/leads/leads-table";
import { apiGet } from "@/lib/api-client";
import { timeAgo } from "@/lib/format";
import type { DashboardStats, Lead, RunSummary } from "@/lib/types";

async function safe<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const [stats, leads, runs] = await Promise.all([
    safe(apiGet<DashboardStats>("/api/dashboard/stats")),
    safe(apiGet<Lead[]>("/api/leads")),
    safe(apiGet<RunSummary[]>("/api/runs")),
  ]);

  const recentRuns = (runs ?? []).slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Page intro */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-fg">Pipeline overview</h2>
          <p className="mt-0.5 text-sm text-fg-secondary">
            What your AI sales employee has been working on.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link href="/agent">
              <SparklesIcon />
              Ask the agent
            </Link>
          </Button>
          {/* Rule 2 — the single lime action on this screen */}
          <Button asChild>
            <Link href="/leads">
              Analyze a lead
              <ArrowRightIcon />
            </Link>
          </Button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {stats ? (
          <>
            <StatCard label="Total leads" value={stats.total_leads} icon={TargetIcon} />
            <StatCard
              label="Qualified"
              value={stats.qualified_leads}
              icon={CircleCheckIcon}
              accent
              hint={
                stats.total_leads > 0
                  ? `${Math.round((stats.qualified_leads / stats.total_leads) * 100)}% of pipeline`
                  : undefined
              }
            />
            <StatCard label="Outreach sent" value={stats.outreach_sent} icon={MailIcon} />
            <StatCard label="Active runs" value={stats.active_runs} icon={BotIcon} />
            <StatCard
              label="Knowledge docs"
              value={stats.knowledge_documents}
              icon={BookOpenIcon}
            />
          </>
        ) : (
          Array.from({ length: 5 }).map((_, i) => <StatCardSkeleton key={i} />)
        )}
      </div>

      {!stats && (
        <ErrorBanner message="Dashboard statistics are unavailable. The backend may be unreachable." />
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent leads */}
        <section className="space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-fg">Recent leads</h3>
            <Link
              href="/leads"
              className="inline-flex items-center gap-1 text-xs font-medium text-fg-secondary transition-colors hover:text-fg"
            >
              View all
              <ArrowRightIcon className="size-3" />
            </Link>
          </div>
          <LeadsTable
            leads={leads ?? []}
            error={leads ? null : "Could not load leads."}
            compact
          />
        </section>

        {/* Agent activity */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-fg">Agent activity</h3>
            <Link
              href="/runs"
              className="inline-flex items-center gap-1 text-xs font-medium text-fg-secondary transition-colors hover:text-fg"
            >
              View all
              <ArrowRightIcon className="size-3" />
            </Link>
          </div>

          <Card className="p-0">
            {recentRuns.length === 0 ? (
              <EmptyState
                icon={BotIcon}
                title="No runs yet"
                description="Analyze a lead to see the agent work."
              />
            ) : (
              <ul className="divide-y-[0.5px] divide-line">
                {recentRuns.map((run) => (
                  <li key={run.id}>
                    <Link
                      href={`/runs/${run.id}`}
                      className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/60"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-fg">
                          {run.lead_company ?? "Unknown lead"}
                        </p>
                        <div className="mt-1 flex items-center gap-2">
                          <RunStatusPill status={run.status} />
                          {run.score != null && <Score value={run.score} />}
                        </div>
                      </div>
                      <span className="shrink-0 text-xs text-fg-muted">
                        {timeAgo(run.created_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>
      </div>
    </div>
  );
}
