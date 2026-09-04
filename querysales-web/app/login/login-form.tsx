"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowRightIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") ?? "/dashboard";

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
    <div className="signal-wash flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center text-center">
          <Image
            src="/logo.png"
            alt=""
            width={44}
            height={44}
            priority
            className="mb-4 size-11 rounded-xl"
          />
          <h1 className="text-xl font-semibold text-fg">QuerySales AI</h1>
          <p className="mt-1 text-sm text-fg-secondary">
            Your autonomous AI sales employee
          </p>
        </div>

        <Card>
          <CardContent className="pt-1">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div
                  role="alert"
                  className="rounded-lg border-[0.5px] border-danger/30 bg-danger-tint px-3 py-2.5 text-sm text-danger"
                >
                  {error}
                </div>
              )}

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
              <Button
                type="submit"
                size="lg"
                disabled={loading}
                className="w-full glow-signal"
              >
                {loading ? "Signing in…" : "Sign in"}
                {!loading && <ArrowRightIcon />}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-fg-muted">
          Knowledge → RAG → Reasoning → Tool calling → Sales action
        </p>
      </div>
    </div>
  );
}
