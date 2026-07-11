import { platformFetch } from "@/lib/api";
import { SupportClient } from "./support-client";

export type SupportRequest = {
  id: number;
  company_id: number;
  company_name: string | null;
  contact_name: string;
  contact_whatsapp: string;
  message: string | null;
  status: string;
  created_at: string;
};

export default async function SupportRequestsPage() {
  let requests: SupportRequest[] = [];
  try {
    requests = await platformFetch<SupportRequest[]>("/platform/support-requests");
  } catch {
    requests = [];
  }

  return <SupportClient initialRequests={requests} />;
}
