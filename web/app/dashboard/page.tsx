import { AppLayout } from "@/components/app-layout";
import { CommercialFunnelCard, type CommercialFunnel } from "@/components/commercial-funnel-card";
import { DashboardShell } from "@/components/dashboard-shell";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { redirect } from "next/navigation";

type DashboardMetrics = {
  open_occurrences: number;
  my_occurrences: number;
  completed_month: number;
  active_users: number;
  active_sectors: number;
  recent: Array<{
    id: number;
    title: string;
    module: string;
    area: string;
    owner: string;
    status: string;
    updated_at: string;
  }>;
  kpis: {
    work_orders: {
      total: number;
      by_status: Record<string, number>;
      by_priority: Record<string, number>;
      by_category: Record<string, number>;
      avg_resolution_hours: number | null;
      sla_compliance_pct: number | null;
      overdue: number;
      created_week: number;
      completed_week: number;
    };
    trend: Array<{
      date: string;
      work_orders: number;
    }>;
  };
};

export default async function DashboardPage() {
  try {
    const user = await currentTenantUser();
    let metrics: DashboardMetrics | null = null;
    try {
      metrics = await tenantFetch<DashboardMetrics>("/dashboard/metrics");
    } catch {
      // API may not be available yet
    }
    let funnel: CommercialFunnel | null = null;
    try {
      funnel = await tenantFetch<CommercialFunnel>("/commercial/funnel");
    } catch {
      // usuário pode não ter permissão commercial.view
    }
    return (
      <AppLayout user={user}>
        <DashboardShell user={user} metrics={metrics} />
        {funnel && <CommercialFunnelCard funnel={funnel} />}
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
