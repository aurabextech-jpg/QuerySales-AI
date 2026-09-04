import httpClient from './httpClient';

export interface Lead {
  name: string;
  lead_name: string;
  status: string;
  source: string | null;
  creation: string;
  email_id: string;
  mobile_no: string;
}

export interface LeadsResponse {
  status: string;
  limit: number;
  offset: number;
  total_returned: number;
  data: Lead[];
}

export const discoveryApi = {
  getLeads: async (limit = 20, offset = 0): Promise<LeadsResponse> => {
    const response = await httpClient.get('/dashboard/leads', {
      params: { limit, offset },
    });
    return response.data;
  },
};
