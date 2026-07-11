"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, RefreshCw, Search } from "lucide-react";
import type { UsageRecord } from "./page";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fmtDate } from "@/lib/utils";

const METRIC_LABEL: Record<string, string> = {
  users: "Usuários",
  occurrences: "Ocorrências",
};

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function UsageClient({ initialRecords }: { initialRecords: UsageRecord[] }) {
  const router = useRouter();
  const [records] = useState(initialRecords);
  const [search, setSearch] = useState("");
  const [metricFilter, setMetricFilter] = useState("all");
  const [snapshotting, setSnapshotting] = useState(false);

  const metrics = Array.from(new Set(records.map((r) => r.metric))).sort();

  const filtered = records.filter((r) => {
    const matchSearch =
      !search || (r.company_name ?? "").toLowerCase().includes(search.toLowerCase());
    const matchMetric = metricFilter === "all" || r.metric === metricFilter;
    return matchSearch && matchMetric;
  });

  const byTenant = filtered.reduce<
    Record<string, { company_name: string | null; totals: Record<string, number> }>
  >((acc, r) => {
    const key = String(r.company_id);
    if (!acc[key]) acc[key] = { company_name: r.company_name, totals: {} };
    acc[key].totals[r.metric] = (acc[key].totals[r.metric] ?? 0) + r.value;
    return acc;
  }, {});

  const tenantRows = Object.entries(byTenant)
    .map(([company_id, data]) => ({ company_id, ...data }))
    .sort((a, b) => (a.company_name ?? "").localeCompare(b.company_name ?? ""));

  async function generateSnapshot() {
    setSnapshotting(true);
    try {
      await apiFetch("/usage/snapshot", { method: "POST" });
      router.refresh();
    } finally {
      setSnapshotting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Uso"
        description="Consumo de recursos por tenant (usuários, ocorrências)."
        actions={
          <Button variant="outline" onClick={generateSnapshot} loading={snapshotting}>
            <RefreshCw size={16} /> Gerar snapshot de hoje
          </Button>
        }
      />

      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
          <Input
            className="pl-9 w-56"
            placeholder="Buscar tenant…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setMetricFilter("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              metricFilter === "all"
                ? "bg-[#1D3461] text-white"
                : "bg-[var(--card)] border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
            }`}
          >
            Todas métricas
          </button>
          {metrics.map((m) => (
            <button
              key={m}
              onClick={() => setMetricFilter(m)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                metricFilter === m
                  ? "bg-[#1D3461] text-white"
                  : "bg-[var(--card)] border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              {METRIC_LABEL[m] ?? m}
            </button>
          ))}
        </div>
      </div>

      {tenantRows.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-6 w-6" />}
          title="Nenhum dado de uso encontrado"
          description="Gere um snapshot para registrar o consumo atual de cada tenant."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tenant</TableHead>
              {metrics
                .filter((m) => metricFilter === "all" || m === metricFilter)
                .map((m) => (
                  <TableHead key={m} className="text-right">
                    {METRIC_LABEL[m] ?? m}
                  </TableHead>
                ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {tenantRows.map((row) => (
              <TableRow key={row.company_id}>
                <TableCell className="font-medium">
                  {row.company_name ?? `#${row.company_id}`}
                </TableCell>
                {metrics
                  .filter((m) => metricFilter === "all" || m === metricFilter)
                  .map((m) => (
                    <TableCell key={m} className="text-right">
                      {row.totals[m] != null ? (
                        row.totals[m].toLocaleString("pt-BR")
                      ) : (
                        <span className="text-[var(--muted-foreground)]">—</span>
                      )}
                    </TableCell>
                  ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {filtered.length > 0 && (
        <details className="rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm overflow-hidden">
          <summary className="px-5 py-4 text-sm font-medium cursor-pointer hover:bg-[var(--accent)]">
            Ver registros individuais ({filtered.length})
          </summary>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Métrica</TableHead>
                <TableHead className="text-right">Valor</TableHead>
                <TableHead>Período</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 && <TableEmpty colSpan={4}>Nenhum registro.</TableEmpty>}
              {filtered.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.company_name ?? `#${r.company_id}`}</TableCell>
                  <TableCell>{METRIC_LABEL[r.metric] ?? r.metric}</TableCell>
                  <TableCell className="text-right font-medium">
                    {r.value.toLocaleString("pt-BR")}
                  </TableCell>
                  <TableCell className="text-xs text-[var(--muted-foreground)]">
                    {fmtDate(r.period_start)} → {fmtDate(r.period_end)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </details>
      )}
    </div>
  );
}
