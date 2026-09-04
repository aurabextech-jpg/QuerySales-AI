/** Mail workspace — server component seeds the initial inbox view. */

import { apiGet } from "@/lib/api-client";
import type { MailListResponse } from "@/lib/types";
import { MailClient } from "./mail-client";

export const dynamic = "force-dynamic";

export default async function MailPage() {
  let initial: MailListResponse = {
    messages: [],
    counts: { inbox: 0, sent: 0, drafts: 0, trash: 0, inbox_unread: 0 },
  };
  try {
    initial = await apiGet<MailListResponse>("/api/mail/messages", { folder: "inbox" });
  } catch {
    /* client shows error/empty states and can retry via Sync */
  }
  return <MailClient initial={initial} />;
}
