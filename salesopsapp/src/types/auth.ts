/**
 * Shared TypeScript types for Neon Auth
 */

export type User = {
  id: string;
  email: string;
  name?: string;
  emailVerified?: boolean;
  image?: string;
  createdAt?: string;
};

export type AuthSession = {
  token: string;
  user: User;
  expiresAt?: string;
};

export type SignInPayload = {
  email: string;
  password: string;
};

export type SignUpPayload = {
  name: string;
  email: string;
  password: string;
};

export type AuthError = {
  code: string;
  message: string;
};

export type AuthResult =
  | { success: true; session: AuthSession }
  | { success: false; error: AuthError };
