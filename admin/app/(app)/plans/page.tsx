import { Tag } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { platformFetch } from "@/lib/api";
import { brl, pluralize } from "@/lib/utils";

type Plan = {
  id: number;
  code: string;
  name: string;
  price_cents: number;
  currency: string;
  billing_period: string;
  active: boolean;
  public: boolean;
  limits: Record<string, number>;
  features: Record<string, boolean>;
};

export default async function PlansPage() {
  let plans: Plan[] = [];
  try {
    plans = await platformFetch<Plan[]>("/platform/plans");
  } catch {
    plans = [];
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Planos"
        description={`${plans.length} ${pluralize(plans.length, "plano configurado", "planos configurados")}`}
      />

      {plans.length === 0 ? (
        <EmptyState icon={<Tag className="h-6 w-6" />} title="Nenhum plano configurado" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <Card key={plan.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-lg font-bold">{plan.name}</h2>
                  <Badge variant={plan.active ? "success" : "default"}>
                    {plan.active ? "Ativo" : "Inativo"}
                  </Badge>
                </div>
                <p className="text-xs text-[var(--muted-foreground)] font-mono">{plan.code}</p>
                <p className="text-2xl font-bold text-[#1D3461] pt-2">{brl(plan.price_cents)}</p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {plan.billing_period === "monthly" ? "por mês" : plan.billing_period}
                </p>
              </CardHeader>
              {plan.limits && Object.keys(plan.limits).length > 0 && (
                <CardContent className="border-t border-[var(--border)] pt-4">
                  <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider mb-2">
                    Limites
                  </p>
                  <div className="space-y-1">
                    {Object.entries(plan.limits).map(([key, val]) => (
                      <div key={key} className="flex justify-between text-xs">
                        <span className="text-[var(--muted-foreground)]">{key.replace(/_/g, " ")}</span>
                        <span className="font-medium">{val}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
