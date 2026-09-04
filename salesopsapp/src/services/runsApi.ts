import httpClient from './httpClient';

export interface Run {
  id: string;
  status: 'completed' | 'running' | 'failed' | string;
  mode: string;
  workflow_type: string;
  created_at: string;
  tool_call_count: number;
  trace_count: number;
}

export interface RunsResponse {
  runs: Run[];
  total: number;
}

export const runsApi = {
  getRuns: async (limit = 20, offset = 0): Promise<Run[]> => {
    const response = await httpClient.get('/runs/', {
      params: { limit, offset },
    });
    return Array.isArray(response.data) ? response.data : response.data.runs ?? [];
  },
};
