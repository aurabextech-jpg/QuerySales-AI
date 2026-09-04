/**
 * store/slices/authSlice.ts
 *
 * Redux slice for authentication state.
 * Manages: user, token, isLoading, error.
 * Async thunks handle all auth operations and token persistence.
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import * as authService from '../../services/authService';
import {
  storeTokens,
  getStoredTokens,
  clearStoredTokens,
} from '../../services/tokenPersistence';
import { setAuthToken, clearAuthToken } from '../../services/authTokenStore';
import type { User } from '../../types/auth';

// ─── State shape ─────────────────────────────────────────────────────────────

type AuthState = {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
};

const initialState: AuthState = {
  user: null,
  token: null,
  isLoading: true, // starts true while restoring session
  error: null,
};

// ─── Async Thunks ────────────────────────────────────────────────────────────

/**
 * Restore session from Keychain on app startup.
 * Validates the stored token with the Neon Auth server.
 */
export const restoreSession = createAsyncThunk(
  'auth/restoreSession',
  async () => {
    const stored = await getStoredTokens();
    if (!stored) return null;

    // Validate with server
    const user = await authService.getSession(stored.accessToken);
    if (!user) {
      await clearStoredTokens();
      return null;
    }

    // Set token in-memory for httpClient interceptor
    setAuthToken(stored.accessToken);

    return { token: stored.accessToken, user };
  },
);

/**
 * Sign in with email + password.
 */
export const signIn = createAsyncThunk(
  'auth/signIn',
  async (
    { email, password }: { email: string; password: string },
    { rejectWithValue },
  ) => {
    const result = await authService.signIn({ email, password });
    if (!result.success) {
      return rejectWithValue(result.error.message);
    }

    const { token, user } = result.session;

    // Persist to Keychain + set in-memory
    await storeTokens({ accessToken: token, email: user.email });

    return { token, user };
  },
);

/**
 * Sign up with name, email, password.
 */
export const signUp = createAsyncThunk(
  'auth/signUp',
  async (
    {
      name,
      email,
      password,
    }: { name: string; email: string; password: string },
    { rejectWithValue },
  ) => {
    const result = await authService.signUp({ name, email, password });
    if (!result.success) {
      return rejectWithValue(result.error.message);
    }

    const { token, user } = result.session;
    await storeTokens({ accessToken: token, email: user.email });

    return { token, user };
  },
);

/**
 * Sign out — clear server session + local storage.
 */
export const signOut = createAsyncThunk(
  'auth/signOut',
  async (_, { getState }) => {
    const state = getState() as { auth: AuthState };
    if (state.auth.token) {
      await authService.signOutRequest(state.auth.token);
    }
    await clearStoredTokens();
  },
);

// ─── Slice ───────────────────────────────────────────────────────────────────

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // ── restoreSession ──
    builder
      .addCase(restoreSession.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(restoreSession.fulfilled, (state, action) => {
        state.isLoading = false;
        if (action.payload) {
          state.token = action.payload.token;
          state.user = action.payload.user;
        }
      })
      .addCase(restoreSession.rejected, (state) => {
        state.isLoading = false;
      });

    // ── signIn ──
    builder
      .addCase(signIn.pending, (state) => {
        state.error = null;
      })
      .addCase(signIn.fulfilled, (state, action) => {
        state.token = action.payload.token;
        state.user = action.payload.user;
        state.error = null;
      })
      .addCase(signIn.rejected, (state, action) => {
        state.error = (action.payload as string) ?? 'Sign in failed.';
      });

    // ── signUp ──
    builder
      .addCase(signUp.pending, (state) => {
        state.error = null;
      })
      .addCase(signUp.fulfilled, (state, action) => {
        state.token = action.payload.token;
        state.user = action.payload.user;
        state.error = null;
      })
      .addCase(signUp.rejected, (state, action) => {
        state.error = (action.payload as string) ?? 'Sign up failed.';
      });

    // ── signOut ──
    builder
      .addCase(signOut.fulfilled, (state) => {
        state.token = null;
        state.user = null;
        state.error = null;
      });
  },
});

export const { clearError } = authSlice.actions;
export default authSlice.reducer;
