import { platformFetch } from "@/lib/api";
import { UsageClient } from "./usage-client";

export type UsageRecord = {
  id: number;
  company_id: number;
  company_name: string | null;
  metric: string;
  value: number;
  period_start: string;
  period_end: string;
  created_at: string;
};

export default async function UsagePage() {
  let records: UsageRecord[] = [];
  try {
    records = await platformFetch<UsageRecord[]>("/platform/usage?limit=200");
  } catch {
    records = [];
  }

  return <UsageClient initialRecords={records} />;
}
