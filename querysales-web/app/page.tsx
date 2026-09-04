import { redirect } from "next/navigation";

/** Root page — redirect to dashboard (auth gate handles unauthenticated). */
export default function RootPage() {
  redirect("/dashboard");
}
