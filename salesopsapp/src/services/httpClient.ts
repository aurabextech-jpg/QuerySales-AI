/**
 * httpClient.ts
 *
 * Central axios instance with interceptors for:
 * - Auto-attaching Authorization header
 * - Dev-mode request/response logging
 * - 401 automatic token refresh + retry
 * - Consistent error extraction
 */

import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
  AxiosResponse,
  AxiosRequestHeaders,
} from 'axios';
import { Platform } from 'react-native';
import {
  clearStoredTokens,
  refreshTokensWithStoredRefreshToken,
} from './tokenPersistence';
import { getAuthToken, setAuthToken } from './authTokenStore';
import { config } from '../config';

const BASE_URL = config.API_URL;
const PLATFORM_CHANNEL = Platform.OS === 'ios' ? 'ios' : 'android';

// ─── Create axios instance ───────────────────────────────────────────────────

const httpClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-Channel': PLATFORM_CHANNEL,
  },
});

export const API_BASE = BASE_URL;
export { setAuthToken, getAuthToken };

// ─── Request interceptor: attach Bearer token ────────────────────────────────

const withAuthHeader = (
  requestConfig: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig => {
  if (!requestConfig.headers) {
    requestConfig.headers = {} as AxiosRequestHeaders;
  }
  const token = getAuthToken();
  if (token) {
    requestConfig.headers.Authorization = `Bearer ${token}`;
  }
  return requestConfig;
};

// ─── Logging helpers (dev only) ──────────────────────────────────────────────

const logResponse = (response: AxiosResponse) => {
  if (__DEV__) {
    const method = response.config.method?.toUpperCase() || 'GET';
    const url = (response.config.baseURL || '') + (response.config.url || '');
    console.log(`[HTTP ${method}] ${url} → ${response.status}`, response.data);
  }
};

const logError = (error: AxiosError) => {
  if (__DEV__) {
    const method = error.config?.method?.toUpperCase() || 'GET';
    const url = (error.config?.baseURL || '') + (error.config?.url || '');
    console.log(
      `[HTTP ${method}] ${url} ✕ ${error.response?.status ?? 'NO_RESPONSE'}`,
      error.response?.data || error.message,
    );
  }
};

// ─── Error message extraction ────────────────────────────────────────────────

export const extractErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    if (error.response?.data) {
      const data = error.response.data as { message?: string; error?: string };
      return data?.message || data?.error || error.message;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred.';
};

// ─── Register interceptors ──────────────────────────────────────────────────

httpClient.interceptors.request.use(withAuthHeader);

httpClient.interceptors.response.use(
  (response: AxiosResponse) => {
    logResponse(response);
    return response;
  },
  async (error: AxiosError) => {
    logError(error);
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Handle 401: attempt token refresh, then retry the original request
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry
    ) {
      originalRequest._retry = true;
      const refreshed = await refreshTokensWithStoredRefreshToken();
      if (refreshed) {
        const token = getAuthToken();
        if (token) {
          originalRequest.headers = originalRequest.headers ?? {};
          (originalRequest.headers as AxiosRequestHeaders).Authorization =
            `Bearer ${token}`;
        }
        return httpClient(originalRequest);
      }
      // Refresh failed — clear tokens (will force logout via Redux state)
      await clearStoredTokens();
    }

    return Promise.reject(new Error(extractErrorMessage(error)));
  },
);

export default httpClient;
