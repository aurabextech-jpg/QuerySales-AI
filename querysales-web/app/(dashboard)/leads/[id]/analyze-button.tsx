/**
 * AnalyzeButton — client component that triggers analysis and shows the live timeline.
 */

"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { AnalysisTimeline } from "@/components/agent/analysis-timeline-client";
import type { RunSummary } from "@/lib/types";

interface AnalyzeButtonProps {
  leadId: string;
}

export function AnalyzeButton({ leadId }: AnalyzeButtonProps) {
  const [loading, setLoading] = useState(false);
  const [run, setRun] = useState<RunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = useCallback(async () => {
    setLoading(true);
    setError(null);
    setRun(null);

    try {
      const res = await fetch(`/api/leads/${leadId}?action=analyze`, {
        method: "POST",
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error ?? "Analysis failed to start.");
        setLoading(false);
        return;
      }

      setRun(data);
    } catch {
      setError("Network error. Could not start analysis.");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  return (
    <div className="space-y-4">
      <Button
        onClick={handleAnalyze}
        loading={loading}
        disabled={loading}
        size="lg"
        className="aurora-gradient text-white shadow-lg shadow-primary/20"
      >
        {loading ? "Starting…" : run ? "Re-analyze" : "Analyze with QuerySales AI"}
      </Button>

      {error && (
        <div className="rounded-lg bg-error-muted border border-error/20 px-4 py-3 text-sm text-error">
          {error}
          <button
            onClick={handleAnalyze}
            className="ml-2 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {run && <AnalysisTimeline runId={run.id} />}
    </div>
  );
}
