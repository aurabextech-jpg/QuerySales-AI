"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowRightIcon } from "lucide-react";
import { toast } from "sonner";
import { AuthError, AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const MIN_PASSWORD_LENGTH = 8;
// A new account has no LLM, embedding or email keys yet (rule §3.4), so the
// agent cannot do anything until they are added — start there.
const AFTER_SIGNUP = "/settings";

export function SignupForm() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        const message = data.error ?? "Could not create the account.";
        setError(message);
        toast.error("Sign-up failed", { description: message });
        return;
      }

      if (data.signedIn === false) {
        router.push("/login?created=1");
        return;
      }

      toast.success("Welcome to QuerySales AI", {
        description: "Add your AI and email keys to get started.",
      });
      router.push(AFTER_SIGNUP);
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
      subtitle="Create your account"
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-fg underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <AuthError message={error} />}

        <div>
          <Label htmlFor="name" className="mb-1.5">
            Full name
          </Label>
          <Input
            id="name"
            required
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ayesha Khan"
            disabled={loading}
            className="h-9"
          />
        </div>

        <div>
          <Label htmlFor="email" className="mb-1.5">
            Work email
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
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
            disabled={loading}
            className="h-9"
          />
        </div>

        <div>
          <Label htmlFor="confirm" className="mb-1.5">
            Confirm password
          </Label>
          <Input
            id="confirm"
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            className="h-9"
          />
        </div>

        <Button type="submit" size="lg" disabled={loading} className="w-full glow-signal">
          {loading ? "Creating account…" : "Create account"}
          {!loading && <ArrowRightIcon />}
        </Button>
      </form>
    </AuthShell>
  );
}
