/**
 * tokenPersistence.ts
 *
 * Secure token persistence via react-native-keychain.
 * Stores the session token (and optionally a refresh token) in the device keychain.
 */

import * as Keychain from 'react-native-keychain';
import { setAuthToken, clearAuthToken } from './authTokenStore';

const KEYCHAIN_SERVICE = 'salesopsapp-auth';

export type StoredTokens = {
  accessToken: string;
  refreshToken?: string;
  email?: string;
};

/**
 * Persist tokens securely to the device keychain.
 */
export const storeTokens = async (tokens: StoredTokens): Promise<void> => {
  const payload = JSON.stringify(tokens);
  await Keychain.setGenericPassword(tokens.email ?? 'user', payload, {
    service: KEYCHAIN_SERVICE,
  });
  // Also set in-memory for immediate interceptor use
  setAuthToken(tokens.accessToken);
};

/**
 * Retrieve stored tokens from the keychain.
 * Returns null if no tokens are stored.
 */
export const getStoredTokens = async (): Promise<StoredTokens | null> => {
  try {
    const credentials = await Keychain.getGenericPassword({
      service: KEYCHAIN_SERVICE,
    });
    if (!credentials) return null;

    const parsed: StoredTokens = JSON.parse(credentials.password);
    return parsed;
  } catch {
    return null;
  }
};

/**
 * Clear all stored tokens from keychain and in-memory store.
 */
export const clearStoredTokens = async (): Promise<void> => {
  await Keychain.resetGenericPassword({ service: KEYCHAIN_SERVICE });
  clearAuthToken();
};

/**
 * Attempt to refresh the access token using the stored refresh token.
 * Returns true if refresh succeeded and the new token has been set.
 *
 * NOTE: Neon Auth (Better Auth) does not currently support refresh tokens
 * via a dedicated endpoint for React Native. This is a placeholder
 * that returns false. The 401 interceptor will fall through to logout.
 */
export const refreshTokensWithStoredRefreshToken =
  async (): Promise<boolean> => {
    // Neon Auth session tokens don't have a standard refresh flow
    // from React Native — if the token is expired, the user must re-login.
    return false;
  };
