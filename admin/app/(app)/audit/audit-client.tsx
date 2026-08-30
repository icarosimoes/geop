"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { ChevronLeft, ChevronRight, Filter, Search } from "lucide-react";
import type { AuditLog, AuditPage } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function DetailsCell({ details }: { details: Record<string, unknown> | null }) {
  const [open, setOpen] = useState(false);
  if (!details) return <span className="text-[var(--muted-foreground)]">—</span>;
  const text = JSON.stringify(details);
  if (text.length <= 60)
    return <span className="text-xs text-[var(--muted-foreground)]">{text}</span>;
  return (
    <button
      onClick={() => setOpen((v) => !v)}
      className="text-xs text-left text-[var(--primary)] underline-offset-2 hover:underline"
    >
      {open ? (
        <span className="text-[var(--muted-foreground)] font-mono whitespace-pre-wrap break-all">
          {JSON.stringify(details, null, 2)}
        </span>
      ) : (
        `${text.slice(0, 58)}…`
      )}
    </button>
  );
}

export function AuditClient({
  data,
  filters,
}: {
  data: AuditPage;
  filters: { action: string; operator: string; date_from: string; date_to: string };
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [action, setAction] = useState(filters.action);
  const [operator, setOperator] = useState(filters.operator);
  const [dateFrom, setDateFrom] = useState(filters.date_from);
  const [dateTo, setDateTo] = useState(filters.date_to);

  function applyFilters(overrides: Partial<typeof filters> & { page?: number }) {
    const qs = new URLSearchParams();
    const a = overrides.action ?? action;
    const op = overrides.operator ?? operator;
    const df = overrides.date_from ?? dateFrom;
    const dt = overrides.date_to ?? dateTo;
    const pg = overrides.page ?? 1;
    if (a) qs.set("action", a);
    if (op) qs.set("operator", op);
    if (df) qs.set("date_from", df);
    if (dt) qs.set("date_to", dt);
    qs.set("page", String(pg));
    startTransition(() => router.push(`?${qs.toString()}`));
  }

  function clearFilters() {
    setAction("");
    setOperator("");
    setDateFrom("");
    setDateTo("");
    startTransition(() => router.push("?page=1"));
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const hasFilters = !!(filters.action || filters.operator || filters.date_from || filters.date_to);

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--muted-foreground)]">
          <Filter className="h-4 w-4" />
          Filtros
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Input
            placeholder="Ação (ex: create_tenant)"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyFilters({ action })}
          />
          <Input
            placeholder="E-mail do operador"
            value={operator}
            onChange={(e) => setOperator(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyFilters({ operator })}
          />
          <Input
            type="date"
            placeholder="De"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <Input
            type="date"
            placeholder="Até"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => applyFilters({ action, operator, date_from: dateFrom, date_to: dateTo })}
            disabled={isPending}
          >
            <Search className="h-3.5 w-3.5 mr-1.5" />
            Filtrar
          </Button>
          {hasFilters && (
            <Button size="sm" variant="outline" onClick={clearFilters} disabled={isPending}>
              Limpar
            </Button>
          )}
        </div>
      </div>

      {/* Contagem */}
      <div className="flex items-center justify-between text-sm text-[var(--muted-foreground)]">
        <span>
          {data.total === 0
            ? "Nenhum registro"
            : `${data.total} registro${data.total !== 1 ? "s" : ""} — página ${data.page} de ${totalPages}`}
        </span>
        {isPending && <span className="text-xs animate-pulse">Carregando…</span>}
      </div>

      {/* Tabela */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-36">Data</TableHead>
            <TableHead>Operador</TableHead>
            <TableHead>Ação</TableHead>
            <TableHead>Entidade</TableHead>
            <TableHead>IP</TableHead>
            <TableHead>Detalhes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.length === 0 && (
            <TableEmpty colSpan={6}>Nenhum registro de auditoria encontrado.</TableEmpty>
          )}
          {data.items.map((log: AuditLog) => (
            <TableRow key={log.id}>
              <TableCell className="text-xs text-[var(--muted-foreground)] whitespace-nowrap">
                {fmtDateTime(log.created_at)}
              </TableCell>
              <TableCell className="text-sm">
                {log.operator_email ?? <span className="text-[var(--muted-foreground)]">sistema</span>}
              </TableCell>
              <TableCell>
                <Badge variant="brand">{log.action}</Badge>
              </TableCell>
              <TableCell className="text-xs text-[var(--muted-foreground)]">
                {log.entity_type}
                {log.entity_id ? ` #${log.entity_id}` : ""}
              </TableCell>
              <TableCell className="text-xs text-[var(--muted-foreground)]">
                {log.ip_address ?? "—"}
              </TableCell>
              <TableCell className="max-w-xs">
                <DetailsCell details={log.details} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={data.page <= 1 || isPending}
            onClick={() => applyFilters({ page: data.page - 1 })}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-[var(--muted-foreground)]">
            {data.page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={data.page >= totalPages || isPending}
            onClick={() => applyFilters({ page: data.page + 1 })}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
