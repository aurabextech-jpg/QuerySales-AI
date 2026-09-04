import Image from "next/image";
import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="flex flex-col items-center text-center">
        <Image
          src="/logo.png"
          alt=""
          width={44}
          height={44}
          priority
          className="mb-6 size-11 rounded-xl"
        />
        <p className="tabular text-xs font-medium tracking-widest text-fg-muted uppercase">
          404
        </p>
        <h1 className="mt-2 text-xl font-semibold text-fg">Page not found</h1>
        <p className="mt-1.5 max-w-sm text-sm text-fg-secondary">
          This page doesn&apos;t exist or has moved.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard">
            <ArrowLeftIcon />
            Back to dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}
