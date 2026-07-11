"use client";

import { useState } from "react";
import { AlertCircle, Building, CheckCircle, Clock, MessageSquare, Phone } from "lucide-react";
import type { SupportRequest } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  contacted: "Contatado",
  resolved: "Resolvido",
};

const STATUS_VARIANT: Record<string, "warning" | "brand" | "success" | "default"> = {
  pending: "warning",
  contacted: "brand",
  resolved: "success",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <AlertCircle className="h-3.5 w-3.5" />,
  contacted: <Phone className="h-3.5 w-3.5" />,
  resolved: <CheckCircle className="h-3.5 w-3.5" />,
};

function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

async function updateStatus(id: number, status: string) {
  const res = await fetch(`/api/proxy/support-requests/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<SupportRequest>;
}

export function SupportClient({ initialRequests }: { initialRequests: SupportRequest[] }) {
  const [requests, setRequests] = useState(initialRequests);
  const [filter, setFilter] = useState<string>("all");
  const [updating, setUpdating] = useState<number | null>(null);

  const filtered = filter === "all" ? requests : requests.filter((r) => r.status === filter);

  async function changeStatus(id: number, status: string) {
    setUpdating(id);
    try {
      const updated = await updateStatus(id, status);
      setRequests((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } finally {
      setUpdating(null);
    }
  }

  const counts = {
    all: requests.length,
    pending: requests.filter((r) => r.status === "pending").length,
    contacted: requests.filter((r) => r.status === "contacted").length,
    resolved: requests.filter((r) => r.status === "resolved").length,
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pedidos de Suporte"
        description="Solicitações enviadas pelos tenants via botão de ajuda."
      />

      <div className="flex gap-2 flex-wrap">
        {(["all", "pending", "contacted", "resolved"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === s
                ? "bg-[#1D3461] text-white"
                : "bg-[var(--card)] border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
            }`}
          >
            {s === "all" ? "Todos" : STATUS_LABEL[s]} <span className="ml-1 opacity-70">({counts[s]})</span>
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={<MessageSquare className="h-6 w-6" />} title="Nenhum pedido encontrado" />
      ) : (
        <div className="space-y-3">
          {filtered.map((req) => (
            <div
              key={req.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm p-5 flex flex-col sm:flex-row sm:items-start gap-4"
            >
              <div className="flex-1 min-w-0 space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{req.contact_name}</span>
                  <Badge variant={STATUS_VARIANT[req.status] ?? "default"}>
                    <span className="flex items-center gap-1">
                      {STATUS_ICON[req.status]}
                      {STATUS_LABEL[req.status] ?? req.status}
                    </span>
                  </Badge>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--muted-foreground)]">
                  {req.company_name && (
                    <span className="flex items-center gap-1">
                      <Building className="h-3.5 w-3.5" /> {req.company_name}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Phone className="h-3.5 w-3.5" /> {req.contact_whatsapp}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" /> {fmtDateTime(req.created_at)}
                  </span>
                </div>

                {req.message && (
                  <p className="text-sm bg-[var(--accent)] rounded-lg px-3 py-2 mt-1">{req.message}</p>
                )}
              </div>

              <div className="flex gap-2 shrink-0">
                {req.status !== "contacted" && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={updating === req.id}
                    onClick={() => changeStatus(req.id, "contacted")}
                  >
                    Contatado
                  </Button>
                )}
                {req.status !== "resolved" && (
                  <Button
                    size="sm"
                    variant="success"
                    disabled={updating === req.id}
                    onClick={() => changeStatus(req.id, "resolved")}
                  >
                    Resolver
                  </Button>
                )}
                {req.status === "resolved" && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={updating === req.id}
                    onClick={() => changeStatus(req.id, "pending")}
                  >
                    Reabrir
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
