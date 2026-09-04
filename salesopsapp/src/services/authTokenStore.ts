/**
 * authTokenStore.ts
 *
 * In-memory synchronous token store.
 * Used by httpClient interceptors which need sync access to the token.
 * The actual persistence (Keychain) is handled by tokenPersistence.ts.
 */

let _accessToken: string | null = null;

export const getAuthToken = (): string | null => _accessToken;

export const setAuthToken = (token: string | null): void => {
  _accessToken = token;
};

export const clearAuthToken = (): void => {
  _accessToken = null;
};
