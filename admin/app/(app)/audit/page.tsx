import { Suspense } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { platformFetch } from "@/lib/api";
import { AuditClient } from "./audit-client";

export type AuditLog = {
  id: number;
  operator_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
};

export type AuditPage = {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
};

async function fetchAuditLogs(params: {
  page: number;
  action?: string;
  operator?: string;
  date_from?: string;
  date_to?: string;
}): Promise<AuditPage> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page));
  qs.set("page_size", "50");
  if (params.action) qs.set("action", params.action);
  if (params.operator) qs.set("operator", params.operator);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);

  try {
    return await platformFetch<AuditPage>(`/platform/audit?${qs.toString()}`);
  } catch {
    return { items: [], total: 0, page: 1, page_size: 50 };
  }
}

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page ?? "1") || 1);
  const action = sp.action ?? "";
  const operator = sp.operator ?? "";
  const date_from = sp.date_from ?? "";
  const date_to = sp.date_to ?? "";

  const data = await fetchAuditLogs({ page, action, operator, date_from, date_to });

  return (
    <div className="space-y-6">
      <PageHeader title="Auditoria" description="Ações administrativas na plataforma." />
      <Suspense>
        <AuditClient
          data={data}
          filters={{ action, operator, date_from, date_to }}
        />
      </Suspense>
    </div>
  );
}
