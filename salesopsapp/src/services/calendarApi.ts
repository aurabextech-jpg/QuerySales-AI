import { Platform } from 'react-native';
import httpClient from './httpClient';

export interface CalendarConfig {
  android: {
    web_client_id: string;
    scopes: string[];
  };
  ios: {
    web_client_id: string;
    ios_client_id: string | null;
    scopes: string[];
  };
  scopes: string[];
}

export interface CalendarStatus {
  connected: boolean;
  email?: string;
  lastSynced?: string;
}

export const calendarApi = {
  getCalendarConfig: async (): Promise<CalendarConfig> => {
    const response = await httpClient.get('/calendar/config');
    return response.data;
  },

  syncCalendar: async (authCode: string): Promise<{ success: boolean; email?: string }> => {
    const platform = Platform.OS === 'ios' ? 'ios' : 'android';
    const response = await httpClient.post('/calendar/sync', {
      auth_code: authCode,
      platform,
    });
    return {
      success: response.data.status === 'success',
      email: response.data.details?.email,
    };
  },

  getCalendarStatus: async (): Promise<CalendarStatus> => {
    const response = await httpClient.get('/calendar/status');
    return {
      connected: response.data.is_connected ?? false,
      email: response.data.email,
      lastSynced: response.data.last_synced,
    };
  },

  disconnectCalendar: async (): Promise<{ success: boolean }> => {
    const response = await httpClient.post('/calendar/disconnect');
    return { success: response.data.status === 'success' };
  },
};
