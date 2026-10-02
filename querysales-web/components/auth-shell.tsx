/**
 * AuthShell — the branded frame shared by the sign-in and sign-up pages.
 */

import Image from "next/image";
import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

export function AuthShell({
  subtitle,
  children,
  footer,
}: {
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="signal-wash flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
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
          <p className="mt-1 text-sm text-fg-secondary">{subtitle}</p>
        </div>

        <Card>
          <CardContent className="pt-1">{children}</CardContent>
        </Card>

        <div className="mt-6 space-y-3 text-center">
          <p className="text-sm text-fg-secondary">{footer}</p>
          <p className="text-xs text-fg-muted">
            Knowledge → RAG → Reasoning → Tool calling → Sales action
          </p>
        </div>
      </div>
    </div>
  );
}

/** The inline error banner both auth forms show above their fields. */
export function AuthError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border-[0.5px] border-danger/30 bg-danger-tint px-3 py-2.5 text-sm text-danger"
    >
      {message}
    </div>
  );
}
