import { AppLayout } from "@/components/app-layout";
import { ReportsShell } from "@/components/reports-shell";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { redirect } from "next/navigation";

type ReportTrendDay = { date: string; count: number };

export type WorkOrderReport = {
  total: number;
  by_status: Record<string, number>;
  completion_rate_pct: number | null;
  by_sector: Record<string, number>;
  overdue: number;
  trend: ReportTrendDay[];
};

export type FiscalRequestSlaReport = {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  sla_compliance_pct: number | null;
  avg_resolution_hours: number | null;
  sla_states: Record<string, number>;
  overdue: number;
  trend: ReportTrendDay[];
};

export default async function RelatoriosPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const query = await searchParams;
  const dateFrom = query.date_from ?? "";
  const dateTo = query.date_to ?? "";
  const qs = new URLSearchParams();
  if (dateFrom) qs.set("date_from", dateFrom);
  if (dateTo) qs.set("date_to", dateTo);
  const suffix = qs.toString() ? `?${qs}` : "";

  try {
    const user = await currentTenantUser();
    let workOrders: WorkOrderReport | null = null;
    let fiscalSla: FiscalRequestSlaReport | null = null;
    let forbidden = false;
    try {
      [workOrders, fiscalSla] = await Promise.all([
        tenantFetch<WorkOrderReport>(`/reports/work-orders${suffix}`),
        tenantFetch<FiscalRequestSlaReport>(`/reports/fiscal-requests-sla${suffix}`),
      ]);
    } catch (error) {
      if (error instanceof Error && error.message === "unauthorized") throw error;
      forbidden = true;
    }
    return (
      <AppLayout user={user}>
        <ReportsShell
          dateFrom={dateFrom}
          dateTo={dateTo}
          workOrders={workOrders}
          fiscalSla={fiscalSla}
          forbidden={forbidden}
        />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
