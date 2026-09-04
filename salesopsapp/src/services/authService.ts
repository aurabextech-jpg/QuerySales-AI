/**
 * authService.ts
 *
 * Neon Auth API calls.
 * Flow: sign-in/sign-up → get session token → exchange for JWT via /token endpoint.
 * The JWT is what gets stored and used for all subsequent API calls.
 */

import axios from 'axios';
import { config } from '../config';
import type { AuthResult, SignInPayload, SignUpPayload } from '../types/auth';
import { extractErrorMessage } from './httpClient';

const AUTH_HEADERS = {
  'Content-Type': 'application/json',
  Origin: 'http://localhost:8081',
};

/**
 * Extract a session token from Neon Auth's response.
 * Better Auth may return it in the body (`token`) or as a `set-cookie` header.
 */
const extractToken = (response: { data: any; headers: any }): string | undefined => {
  // Body token
  if (response.data?.token) return response.data.token;

  // Cookie token — preserve base64 padding by joining with '='
  const cookie: string | undefined = response.headers['set-cookie']?.[0];
  if (cookie) {
    const firstPart = cookie.split(';')[0];
    const parts = firstPart.split('=');
    if (parts.length > 1) {
      return parts.slice(1).join('=');
    }
  }

  return undefined;
};

/**
 * Exchange a Neon Auth session token for a proper JWT.
 * This JWT is what the backend can decode and verify.
 *
 * GET /token with Authorization: Bearer <sessionToken>
 */
const exchangeForJWT = async (sessionToken: string): Promise<string | null> => {
  try {
    const response = await axios.get(`${config.NEON_AUTH_URL}/token`, {
      headers: {
        ...AUTH_HEADERS,
        Authorization: `Bearer ${sessionToken}`,
      },
    });

    if (__DEV__) {
      console.log('[authService.exchangeForJWT] response.data:', JSON.stringify(response.data));
    }

    // The /token endpoint returns the JWT — could be in response.data.token or response.data directly
    const jwt: string | undefined =
      response.data?.token ?? (typeof response.data === 'string' ? response.data : undefined);

    return jwt ?? null;
  } catch (error) {
    if (__DEV__) {
      console.log('[authService.exchangeForJWT] error:', extractErrorMessage(error));
    }
    return null;
  }
};

/**
 * Sign in with email + password.
 * After authentication, exchanges the session token for a JWT.
 */
export const signIn = async ({ email, password }: SignInPayload): Promise<AuthResult> => {
  try {
    const response = await axios.post(
      `${config.NEON_AUTH_URL}/sign-in/email`,
      { email, password },
      { headers: AUTH_HEADERS },
    );

    if (__DEV__) {
      console.log('[authService.signIn] response.data:', JSON.stringify(response.data));
    }

    const sessionToken = extractToken(response);
    if (!sessionToken) {
      return { success: false, error: { code: 'NO_TOKEN', message: 'No session token received.' } };
    }

    // Exchange session token for JWT
    const jwt = await exchangeForJWT(sessionToken);
    if (!jwt) {
      return { success: false, error: { code: 'JWT_EXCHANGE_FAILED', message: 'Failed to exchange session for JWT.' } };
    }

    return {
      success: true,
      session: {
        token: jwt,
        user: {
          id: response.data?.user?.id ?? 'unknown',
          email: response.data?.user?.email ?? email,
          name: response.data?.user?.name,
          emailVerified: response.data?.user?.emailVerified,
          image: response.data?.user?.image,
          createdAt: response.data?.user?.createdAt,
        },
      },
    };
  } catch (error) {
    return { success: false, error: { code: 'SIGN_IN_FAILED', message: extractErrorMessage(error) } };
  }
};

/**
 * Sign up with name, email, and password.
 * After registration, exchanges the session token for a JWT.
 */
export const signUp = async ({ name, email, password }: SignUpPayload): Promise<AuthResult> => {
  try {
    const response = await axios.post(
      `${config.NEON_AUTH_URL}/sign-up/email`,
      { name, email, password },
      { headers: AUTH_HEADERS },
    );

    if (__DEV__) {
      console.log('[authService.signUp] response.data:', JSON.stringify(response.data));
    }

    const sessionToken = extractToken(response);
    if (!sessionToken) {
      return { success: false, error: { code: 'NO_TOKEN', message: 'No session token received.' } };
    }

    // Exchange session token for JWT
    const jwt = await exchangeForJWT(sessionToken);
    if (!jwt) {
      return { success: false, error: { code: 'JWT_EXCHANGE_FAILED', message: 'Failed to exchange session for JWT.' } };
    }

    return {
      success: true,
      session: {
        token: jwt,
        user: {
          id: response.data?.user?.id ?? 'unknown',
          email: response.data?.user?.email ?? email,
          name: response.data?.user?.name ?? name,
          emailVerified: response.data?.user?.emailVerified,
          image: response.data?.user?.image,
          createdAt: response.data?.user?.createdAt,
        },
      },
    };
  } catch (error) {
    return { success: false, error: { code: 'SIGN_UP_FAILED', message: extractErrorMessage(error) } };
  }
};

/**
 * Sign out using the token.
 */
export const signOutRequest = async (token: string): Promise<void> => {
  try {
    await axios.post(
      `${config.NEON_AUTH_URL}/sign-out`,
      {},
      { headers: { ...AUTH_HEADERS, Authorization: `Bearer ${token}` } },
    );
  } catch {
    // Ignore sign-out errors — local session is cleared regardless
  }
};

/**
 * Validate a stored token by calling the get-session endpoint.
 * Returns the user if valid, null if expired/invalid.
 */
export const getSession = async (
  token: string,
): Promise<{ id: string; email: string; name?: string } | null> => {
  try {
    const response = await axios.get(`${config.NEON_AUTH_URL}/get-session`, {
      headers: { ...AUTH_HEADERS, Authorization: `Bearer ${token}` },
    });
    const user = response.data?.user;
    if (!user?.id) return null;
    return { id: user.id, email: user.email, name: user.name };
  } catch {
    return null;
  }
};
