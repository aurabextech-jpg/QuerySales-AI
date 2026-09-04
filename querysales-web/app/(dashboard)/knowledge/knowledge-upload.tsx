/**
 * Knowledge upload button + dialog — client component.
 */

"use client";

import { useState, useRef, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const MAX_SIZE_MB = 10;
const ALLOWED_TYPES = [".md", ".txt", ".pdf"];

export function KnowledgeUpload() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);

    // Client-side validation
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_TYPES.includes(ext)) {
      setError(`File type ${ext} not allowed. Use ${ALLOWED_TYPES.join(", ")}.`);
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File too large. Maximum ${MAX_SIZE_MB}MB.`);
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/knowledge", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Upload failed.");
        return;
      }

      router.refresh();
    } catch {
      setError("Network error during upload.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <input
        ref={fileRef}
        type="file"
        accept={ALLOWED_TYPES.join(",")}
        onChange={handleFileChange}
        className="hidden"
      />
      <Button
        onClick={() => fileRef.current?.click()}
        loading={uploading}
        variant="secondary"
      >
        Upload Knowledge
      </Button>
      {error && (
        <p className="text-xs text-error max-w-xs">{error}</p>
      )}
    </div>
  );
}
