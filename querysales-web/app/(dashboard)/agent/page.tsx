/**
 * Agent — conversational interface onto the SalesOps orchestrator.
 *
 * Distinct from the per-lead Analyze flow: that runs the autonomous sales
 * analyst against one lead, this is the open-ended assistant that can search
 * the pipeline, query the CRM, and draft outreach on request.
 */

import { AgentChat } from "@/components/agent/agent-chat-client";

export default function AgentPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold text-fg">Agent</h2>
        <p className="mt-0.5 text-sm text-fg-secondary">
          Talk to your AI sales employee. It reasons, calls tools, and shows you
          every step it took.
        </p>
      </div>

      <AgentChat />
    </div>
  );
}
