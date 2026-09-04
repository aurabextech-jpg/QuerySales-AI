/**
 * Login page — wraps the client form in a Suspense boundary
 * (required by Next.js 16 for useSearchParams).
 */

import { Suspense } from "react";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
