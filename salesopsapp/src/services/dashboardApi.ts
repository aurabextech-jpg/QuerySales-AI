import httpClient from './httpClient';

export interface PipelineStats {
  total_leads: number;
  open: number;
  replied: number;
  opportunity: number;
  converted: number;
  do_not_contact: number;
}

export interface UsageStats {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  total_messages: number;
  total_tool_calls: number;
  total_tokens_used: number;
  total_cost_usd: number;
}

export interface ActivityItem {
  type: 'message' | 'tool_call';
  description: string;
  timestamp: string;
}

export interface Lead {
  name: string;
  lead_name: string;
  status: string;
  source: string | null;
  creation: string;
  email_id: string;
  mobile_no: string;
}

export interface DashboardStats {
  pipeline: PipelineStats;
  usage: UsageStats;
  recent_activity: ActivityItem[];
  categorized_leads: Record<string, Lead[]>;
  raw_leads: Lead[];
}

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const response = await httpClient.get('/dashboard/stats');
    return response.data;
  },
};
