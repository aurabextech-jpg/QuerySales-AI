/**
 * Settings test buttons — client component for testing connections.
 */

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface SettingsTestButtonsProps {
  section: string;
  configured: boolean;
}

export function SettingsTestButtons({ section, configured }: SettingsTestButtonsProps) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  async function handleTest() {
    setTesting(true);
    setResult(null);

    try {
      const res = await fetch(`/api/settings/status?action=test-${section}`, {
        method: "POST",
      });
      const data = await res.json();

      if (!res.ok) {
        setResult({ success: false, message: data.error ?? "Test failed." });
        return;
      }

      setResult(data);
    } catch {
      setResult({ success: false, message: "Network error." });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button
        onClick={handleTest}
        loading={testing}
        variant="secondary"
        size="sm"
        disabled={!configured}
      >
        Test Connection
      </Button>

      {result && (
        <span
          className={`text-sm ${result.success ? "text-success" : "text-error"}`}
        >
          {result.success ? "✓ Success" : `✗ ${result.message}`}
        </span>
      )}
    </div>
  );
}
