/**
 * lib/types.ts — TypeScript types mirroring backend Pydantic models.
 */

/* ── Leads ─────────────────────────────────────────────────────────── */

export type LeadStatus =
  | "New"
  | "Analyzing"
  | "Qualified"
  | "Nurture"
  | "Disqualified"
  | "Contacted";

export interface Lead {
  id: string;
  name: string | null;
  company: string;
  email: string | null;
  industry: string | null;
  website: string | null;
  status: LeadStatus;
  score: number | null;
  pain_points: string[] | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadCreate {
  name?: string;
  company: string;
  email?: string;
  industry?: string;
  website?: string;
  status?: LeadStatus;
  notes?: string;
}

export interface LeadUpdate {
  name?: string;
  company?: string;
  email?: string;
  industry?: string;
  website?: string;
  status?: LeadStatus;
  score?: number;
  pain_points?: string[];
  notes?: string;
}

/* ── Dashboard ─────────────────────────────────────────────────────── */

export interface DashboardStats {
  total_leads: number;
  qualified_leads: number;
  outreach_sent: number;
  active_runs: number;
  knowledge_documents: number;
  pipeline: Record<string, number>;
}

/* ── Runs / Events ─────────────────────────────────────────────────── */

export type AgentPhase =
  | "OBSERVE"
  | "RETRIEVE"
  | "REASON"
  | "PLAN"
  | "TOOL_CALL"
  | "RESULT"
  | "COMPLETE"
  | "ERROR";

export interface AgentEvent {
  id: string;
  run_id: string;
  sequence: number;
  phase: AgentPhase;
  label: string;
  detail: string | null;
  tool_name: string | null;
  created_at: string;
}

export interface RunSummary {
  id: string;
  status: string;
  workflow_type: string | null;
  lead_id: string | null;
  lead_company: string | null;
  score: number | null;
  qualification: string | null;
  created_at: string;
  completed_at: string | null;
}

/* ── Knowledge ─────────────────────────────────────────────────────── */

export interface KnowledgeDocument {
  id: string;
  filename: string;
  title: string | null;
  file_type: string;
  status: string;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
}

/* ── Outreach ──────────────────────────────────────────────────────── */

export interface OutreachDraft {
  id: string;
  run_id: string;
  lead_id: string;
  subject: string;
  body: string;
  status: string;
  created_at: string;
}

/* ── Settings ──────────────────────────────────────────────────────── */

/** Mirrors backend LLMConfigResponse (GET /api/settings/llm). */
export interface LLMConfig {
  configured: boolean;
  provider_name: string | null;
  base_url: string | null;
  model: string | null;
  temperature: number | null;
  max_tokens: number | null;
  api_key_masked: string | null;
}

/** Mirrors backend EmbeddingConfigResponse (GET /api/settings/embedding). */
export interface EmbeddingConfig {
  configured: boolean;
  provider_name: string | null;
  base_url: string | null;
  model: string | null;
  dimension: number | null;
  api_key_masked: string | null;
}

/** Mirrors backend EmailConfigResponse (GET /api/settings/email). */
export interface EmailConfig {
  configured: boolean;
  provider: string | null;
  email_address: string | null;
  smtp_host: string | null;
  smtp_port: number | null;
  has_password: boolean;
}

export type SettingsSection = "llm" | "embedding" | "email";
