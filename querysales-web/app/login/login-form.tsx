"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowRightIcon } from "lucide-react";
import { toast } from "sonner";
import { AuthError, AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") ?? "/dashboard";
  const justSignedUp = searchParams.get("created") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        const message = data.error ?? "Login failed.";
        setError(message);
        toast.error("Sign-in failed", { description: message });
        return;
      }

      router.push(redirect);
    } catch {
      const message = "Could not reach the server. Please try again.";
      setError(message);
      toast.error("Network error", { description: message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      subtitle="Your autonomous AI sales employee"
      footer={
        <>
          New to QuerySales?{" "}
          <Link href="/signup" className="font-medium text-fg underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {justSignedUp && !error && (
          <p className="rounded-lg bg-muted px-3 py-2.5 text-sm text-fg-secondary">
            Account created. Sign in to continue.
          </p>
        )}
        {error && <AuthError message={error} />}

        <div>
          <Label htmlFor="email" className="mb-1.5">
            Email
          </Label>
          <Input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            disabled={loading}
            className="h-9"
          />
        </div>

        <div>
          <Label htmlFor="password" className="mb-1.5">
            Password
          </Label>
          <Input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            className="h-9"
          />
        </div>

        {/* Rule 2 — the single lime action on this screen. */}
        <Button type="submit" size="lg" disabled={loading} className="w-full glow-signal">
          {loading ? "Signing in…" : "Sign in"}
          {!loading && <ArrowRightIcon />}
        </Button>
      </form>
    </AuthShell>
  );
}
