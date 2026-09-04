/**
 * AnalyzeButton — the primary CTA of the whole product. Starts an agent run
 * and mounts the live timeline beneath it.
 */

"use client";

import { useState } from "react";
import { RotateCwIcon, SparklesIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { AnalysisTimeline } from "@/components/agent/analysis-timeline-client";
import type { RunSummary } from "@/lib/types";

export function AnalyzeButton({ leadId }: { leadId: string }) {
  const [starting, setStarting] = useState(false);
  const [run, setRun] = useState<RunSummary | null>(null);

  async function analyze() {
    setStarting(true);
    setRun(null);

    try {
      const res = await fetch(`/api/leads/${leadId}?action=analyze`, {
        method: "POST",
      });
      const data = await res.json();

      if (!res.ok) {
        toast.error("Could not start analysis", {
          description: data.error ?? "The agent did not start.",
          action: { label: "Retry", onClick: () => void analyze() },
        });
        return;
      }

      setRun(data);
    } catch {
      toast.error("Network error", {
        description: "Could not reach the server.",
        action: { label: "Retry", onClick: () => void analyze() },
      });
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Rule 2 — the single lime button on this screen. */}
      <Button
        onClick={analyze}
        disabled={starting}
        size="lg"
        className="w-full glow-signal sm:w-auto"
      >
        {run ? <RotateCwIcon /> : <SparklesIcon />}
        {starting
          ? "Starting…"
          : run
            ? "Re-analyze"
            : "Analyze with QuerySales AI"}
      </Button>

      {run && <AnalysisTimeline runId={run.id} />}
    </div>
  );
}
