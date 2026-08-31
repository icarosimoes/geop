"use client";

import { useState } from "react";
import { AlertCircle, Building, CheckCircle, ChevronDown, ChevronUp, Clock, MessageSquare, Phone } from "lucide-react";
import type { SupportRequest } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/client-fetch";

type TimelineEntry = {
  id: number;
  event_type: string;
  user: string;
  message: string | null;
  changes: Record<string, { from: string; to: string }> | null;
  created_at: string;
};

function fetchTicketTimeline(id: number) {
  return apiFetch<TimelineEntry[]>(`/support-requests/${id}/timeline`);
}

function TicketThread({ requestId }: { requestId: number }) {
  const [timeline, setTimeline] = useState<TimelineEntry[] | null>(null);

  if (timeline === null) {
    fetchTicketTimeline(requestId).then(setTimeline).catch(() => setTimeline([]));
    return <p className="text-sm text-[var(--muted-foreground)] mt-2">Carregando tratativa…</p>;
  }

  if (timeline.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)] mt-2">Sem tratativa registrada ainda.</p>;
  }

  return (
    <ul className="mt-2 space-y-2">
      {timeline.map((entry) => (
        <li key={entry.id} className="text-sm border-l-2 border-[var(--border)] pl-3">
          <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
            <strong className="text-[var(--foreground)]">{entry.user}</strong>
            <span>·</span>
            <span>{new Date(entry.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</span>
          </div>
          {entry.event_type === "comment" && entry.message && <p>{entry.message}</p>}
          {entry.changes && (
            <p className="text-[var(--muted-foreground)]">
              {Object.entries(entry.changes).map(([k, v]) => (
                <span key={k}>
                  {k}: &quot;{v.from}&quot; → &quot;{v.to}&quot;
                </span>
              ))}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

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

const PRIORITY_LABEL: Record<string, string> = {
  BAIXA: "Baixa",
  MEDIA: "Média",
  ALTA: "Alta",
};

const PRIORITY_VARIANT: Record<string, "warning" | "brand" | "success" | "default"> = {
  BAIXA: "default",
  MEDIA: "brand",
  ALTA: "warning",
};

function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function updateRequest(id: number, body: { status: string; response_message?: string }) {
  return apiFetch<SupportRequest>(`/support-requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function SupportClient({ initialRequests }: { initialRequests: SupportRequest[] }) {
  const [requests, setRequests] = useState(initialRequests);
  const [filter, setFilter] = useState<string>("all");
  const [updating, setUpdating] = useState<number | null>(null);
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState<Record<number, number>>({});

  const filtered = filter === "all" ? requests : requests.filter((r) => r.status === filter);

  async function changeStatus(id: number, status: string) {
    setUpdating(id);
    try {
      const updated = await updateRequest(id, { status });
      setRequests((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setRefreshKey((prev) => ({ ...prev, [id]: (prev[id] ?? 0) + 1 }));
    } finally {
      setUpdating(null);
    }
  }

  async function sendReply(id: number, currentStatus: string) {
    const text = (replyDrafts[id] ?? "").trim();
    if (!text) return;
    setUpdating(id);
    try {
      const nextStatus = currentStatus === "pending" ? "contacted" : currentStatus;
      const updated = await updateRequest(id, { status: nextStatus, response_message: text });
      setRequests((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setReplyDrafts((prev) => ({ ...prev, [id]: "" }));
      setRefreshKey((prev) => ({ ...prev, [id]: (prev[id] ?? 0) + 1 }));
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
                  <span className="font-semibold">{req.subject ?? req.contact_name}</span>
                  <Badge variant={STATUS_VARIANT[req.status] ?? "default"}>
                    <span className="flex items-center gap-1">
                      {STATUS_ICON[req.status]}
                      {STATUS_LABEL[req.status] ?? req.status}
                    </span>
                  </Badge>
                  <Badge variant={PRIORITY_VARIANT[req.priority] ?? "default"}>
                    {PRIORITY_LABEL[req.priority] ?? req.priority}
                  </Badge>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--muted-foreground)]">
                  <span>{req.contact_name}</span>
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

                <button
                  type="button"
                  onClick={() => setExpandedId(expandedId === req.id ? null : req.id)}
                  className="flex items-center gap-1 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                >
                  {expandedId === req.id ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  Ver tratativa
                </button>
                {expandedId === req.id && (
                  <TicketThread key={`${req.id}-${refreshKey[req.id] ?? 0}`} requestId={req.id} />
                )}

                <div className="flex gap-2 items-start pt-1">
                  <textarea
                    value={replyDrafts[req.id] ?? ""}
                    onChange={(e) =>
                      setReplyDrafts((prev) => ({ ...prev, [req.id]: e.target.value }))
                    }
                    placeholder="Responder ao tenant…"
                    rows={2}
                    className="flex-1 min-w-0 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm"
                  />
                  <Button
                    size="sm"
                    disabled={updating === req.id || !(replyDrafts[req.id] ?? "").trim()}
                    onClick={() => sendReply(req.id, req.status)}
                  >
                    Enviar resposta
                  </Button>
                </div>
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
