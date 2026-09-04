/**
 * Branded 404 page — replaces the default Next.js "page could not be found".
 */

import Image from "next/image";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="text-center">
        <Image
          src="/logo.png"
          alt="QuerySales AI"
          width={64}
          height={64}
          priority
          className="inline-block w-16 h-16 mb-6"
        />
        <p className="text-sm font-medium text-primary mb-2">404</p>
        <h1 className="text-2xl font-bold text-text">
          This page could not be found
        </h1>
        <p className="text-text-secondary mt-2 mb-8">
          The page you are looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/dashboard"
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-dark transition"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
