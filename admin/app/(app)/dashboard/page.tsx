import { Building, TrendingUp, AlertTriangle, DollarSign } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { platformFetch } from "@/lib/api";
import { brl } from "@/lib/utils";

type Metrics = {
  tenants_total: number;
  tenants_active: number;
  tenants_trial: number;
  tenants_past_due: number;
  mrr_cents: number;
};

export default async function Dashboard() {
  let m: Metrics | null = null;
  try {
    m = await platformFetch<Metrics>("/platform/metrics");
  } catch {
    m = null;
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Visão geral da plataforma GEOP." />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Empresas"
          value={m?.tenants_total ?? "—"}
          hint={`${m?.tenants_active ?? 0} ativas`}
          icon={<Building className="h-4 w-4" />}
        />
        <StatCard
          title="Em trial"
          value={m?.tenants_trial ?? "—"}
          hint="período de avaliação"
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <StatCard
          title="Inadimplentes"
          value={m?.tenants_past_due ?? "—"}
          hint="exigem acompanhamento"
          icon={<AlertTriangle className="h-4 w-4" />}
        />
        <StatCard
          title="MRR"
          value={m ? brl(m.mrr_cents) : "—"}
          hint="assinaturas ativas"
          icon={<DollarSign className="h-4 w-4" />}
        />
      </section>
    </div>
  );
}
