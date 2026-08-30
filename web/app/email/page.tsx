import { AppLayout } from "@/components/app-layout";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { redirect } from "next/navigation";
import { EmailClient } from "./email-client";

type EmailAccount = {
  id: number;
  name: string;
  provider: string;
  protocol: "imap" | "pop3";
  imap_host: string;
  imap_port: number;
  imap_ssl: boolean;
  username: string;
  active: boolean;
  last_synced_at: string | null;
  created_at: string;
};

type MessageListItem = {
  id: number;
  account_id: number;
  uid: string;
  from_addr: string;
  from_name: string | null;
  subject: string | null;
  received_at: string | null;
  is_read: boolean;
  is_flagged: boolean;
};

type MessagePage = {
  items: MessageListItem[];
  total: number;
  page: number;
  page_size: number;
};

type AlertRule = {
  id: number;
  name: string;
  active: boolean;
  filter_type: "subject" | "domain" | "sender";
  filter_value: string;
  whatsapp_targets: { number: string; label?: string | null }[];
  account_ids: number[];
  created_at: string;
  updated_at: string;
};

export default async function EmailPage() {
  let user;
  try {
    user = await currentTenantUser();
  } catch {
    redirect("/login");
  }

  const [accounts, messagesData, alertRules] = await Promise.allSettled([
    tenantFetch<EmailAccount[]>("/email-client/accounts"),
    tenantFetch<MessagePage>("/email-client/messages?page=1&page_size=50"),
    tenantFetch<AlertRule[]>("/email-client/alert-rules"),
  ]);

  return (
    <AppLayout user={user}>
      <EmailClient
        initialAccounts={accounts.status === "fulfilled" ? accounts.value : []}
        initialMessages={
          messagesData.status === "fulfilled" ? messagesData.value.items : []
        }
        initialAlertRules={alertRules.status === "fulfilled" ? alertRules.value : []}
      />
    </AppLayout>
  );
}
