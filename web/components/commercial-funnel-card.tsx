import Link from "next/link";
import { FileText, CheckCircle2, Truck, Receipt, Wallet } from "lucide-react";

export type CommercialFunnel = {
  quoted_count: number;
  quoted_total: string;
  approved_count: number;
  approved_total: string;
  delivered_count: number;
  invoiced_total: string;
  received_total: string;
};

function formatCurrency(value: string): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

export function CommercialFunnelCard({ funnel }: { funnel: CommercialFunnel }) {
  const stages = [
    { label: "Orçado", count: funnel.quoted_count, total: funnel.quoted_total, icon: FileText, accent: "accent-blue" },
    { label: "Aprovado", count: funnel.approved_count, total: funnel.approved_total, icon: CheckCircle2, accent: "accent-green" },
    { label: "Entregue", count: funnel.delivered_count, total: null, icon: Truck, accent: "accent-purple" },
    { label: "Faturado", count: null, total: funnel.invoiced_total, icon: Receipt, accent: "accent-orange" },
    { label: "Recebido", count: null, total: funnel.received_total, icon: Wallet, accent: "accent-green" },
  ];

  return (
    <section className="kpi-section" aria-label="Funil comercial">
      <h2>Funil comercial</h2>
      <div className="kpi-panel">
        <div className="kpi-stat-grid commercial-funnel-grid">
          {stages.map((stage) => (
            <div className="kpi-stat" key={stage.label}>
              <span className="kpi-stat-label">
                <stage.icon size={14} style={{ verticalAlign: "-2px", marginRight: 4 }} />
                {stage.label}
              </span>
              <span className={`kpi-stat-value ${stage.accent}`}>
                {stage.total != null ? formatCurrency(stage.total) : stage.count}
              </span>
              {stage.count != null && stage.total != null && (
                <small className="commercial-funnel-count">{stage.count} orçamento{stage.count !== 1 ? "s" : ""}</small>
              )}
            </div>
          ))}
        </div>
        <footer className="commercial-funnel-footer">
          <Link href="/comercial/orcamentos" className="text-button">Ver orçamentos</Link>
          <Link href="/comercial/vendas" className="text-button">Ver vendas</Link>
        </footer>
      </div>
      <style>{`
        .commercial-funnel-grid { grid-template-columns: repeat(5, minmax(120px, 1fr)); }
        .commercial-funnel-count { display: block; color: var(--muted); font-size: var(--font-xs); margin-top: 2px; }
        .commercial-funnel-footer { display: flex; gap: var(--sp-4); margin-top: var(--sp-3); }
        @media (max-width: 900px) {
          .commercial-funnel-grid { grid-template-columns: repeat(2, 1fr); }
        }
      `}</style>
    </section>
  );
}
