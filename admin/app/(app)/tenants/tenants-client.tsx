"use client";

import { useEffect, useRef, useState } from "react";
import {
  Ban, CheckCircle, MoreVertical, Pencil, Plus, Search, ShieldOff, Trash2, X,
} from "lucide-react";
import type { Tenant, Plan } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { fmtDate, pluralize } from "@/lib/utils";

const STATUS_LABEL: Record<string, string> = {
  trial: "Trial", active: "Ativo", past_due: "Inadimplente",
  canceled: "Cancelado", suspended: "Suspenso",
};

const STATUS_VARIANT: Record<string, "brand" | "success" | "danger" | "warning" | "default"> = {
  trial: "brand", active: "success", past_due: "danger",
  canceled: "default", suspended: "warning",
};

const SUB_ACTIONS: Record<string, { label: string; nextStatus: string; icon: React.ReactNode; danger?: boolean }[]> = {
  trial:     [{ label: "Suspender", nextStatus: "suspended", icon: <ShieldOff className="h-3.5 w-3.5" />, danger: true },
              { label: "Cancelar",  nextStatus: "canceled",  icon: <Ban className="h-3.5 w-3.5" />, danger: true }],
  active:    [{ label: "Suspender", nextStatus: "suspended", icon: <ShieldOff className="h-3.5 w-3.5" />, danger: true },
              { label: "Cancelar",  nextStatus: "canceled",  icon: <Ban className="h-3.5 w-3.5" />, danger: true }],
  past_due:  [{ label: "Reativar",  nextStatus: "active",    icon: <CheckCircle className="h-3.5 w-3.5" /> },
              { label: "Suspender", nextStatus: "suspended", icon: <ShieldOff className="h-3.5 w-3.5" />, danger: true }],
  suspended: [{ label: "Reativar",  nextStatus: "active",    icon: <CheckCircle className="h-3.5 w-3.5" /> },
              { label: "Cancelar",  nextStatus: "canceled",  icon: <Ban className="h-3.5 w-3.5" />, danger: true }],
  canceled:  [{ label: "Reativar (trial)", nextStatus: "trial", icon: <CheckCircle className="h-3.5 w-3.5" /> }],
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

function SubscriptionMenu({ tenant, onUpdated }: { tenant: Tenant; onUpdated: (t: Tenant) => void }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const status = tenant.subscription_status ?? "";
  const actions = SUB_ACTIONS[status] ?? [];

  useEffect(() => {
    if (!open) return;
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (actions.length === 0) return null;

  async function apply(nextStatus: string, label: string) {
    if (!confirm(`${label} a assinatura de ${tenant.name}?`)) return;
    setLoading(true);
    setOpen(false);
    try {
      await apiFetch(`/tenants/${tenant.id}/subscription`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      });
      onUpdated({ ...tenant, subscription_status: nextStatus });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div ref={ref} className="relative">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen((v) => !v)}
        disabled={loading}
        title="Gerenciar assinatura"
      >
        <MoreVertical className="h-4 w-4" />
      </Button>
      {open && (
        <div className="absolute right-0 top-9 z-50 w-48 rounded-xl border border-[var(--border)] bg-[var(--popover)] shadow-xl py-1 animate-in">
          <p className="px-3 py-1.5 text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Assinatura</p>
          {actions.map((a) => (
            <button
              key={a.nextStatus}
              onClick={() => apply(a.nextStatus, a.label)}
              className={`flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-[var(--accent)] ${a.danger ? "text-[var(--danger)]" : "text-[var(--success)]"}`}
            >
              {a.icon} {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NewTenantModal({ plans, onClose, onCreated }: { plans: Plan[]; onClose: () => void; onCreated: (t: Tenant) => void }) {
  const [form, setForm] = useState({ name: "", slug: "", email: "", plan_id: plans[0]?.id ?? 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function slugify(s: string) {
    return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 30);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const t = await apiFetch<Tenant>("/tenants", { method: "POST", body: JSON.stringify(form) });
      onCreated(t);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar empresa");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-[var(--card)] rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in">
        <div className="px-6 py-4 flex items-center justify-between" style={{ background: "linear-gradient(135deg, #1D3461, #142548)" }}>
          <div>
            <h2 className="text-lg font-bold text-white">Nova empresa</h2>
            <p className="text-xs text-white/60 mt-0.5">Cria tenant + assinatura trial</p>
          </div>
          <button onClick={onClose} className="text-white/60 hover:text-white"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6">
          {error && <p className="text-sm text-[var(--danger)] mb-3 p-3 bg-[var(--danger)]/10 rounded-lg">{error}</p>}
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Nome da empresa</Label>
                <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value, slug: slugify(e.target.value) }))} required />
              </div>
              <div className="space-y-1.5">
                <Label>Slug</Label>
                <Input value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} required />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>E-mail do tenant</Label>
              <Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required />
            </div>
            <div className="space-y-1.5">
              <Label>Plano</Label>
              <select
                className="flex h-9 w-full rounded-md border border-[var(--input)] bg-transparent px-3 py-1 text-sm shadow-sm"
                value={form.plan_id}
                onChange={(e) => setForm((f) => ({ ...f, plan_id: parseInt(e.target.value) }))}
              >
                <option value="0">Sem plano</option>
                {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancelar</Button>
              <Button type="submit" loading={loading}>Criar empresa</Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function EditTenantModal({ tenant, onClose, onUpdated }: { tenant: Tenant; onClose: () => void; onUpdated: (t: Tenant) => void }) {
  const [form, setForm] = useState({
    name: tenant.name,
    email: tenant.email ?? "",
    document: tenant.document ?? "",
    timezone: tenant.timezone ?? "America/Sao_Paulo",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const body: Record<string, string> = {};
      if (form.name !== tenant.name) body.name = form.name;
      if (form.email !== (tenant.email ?? "")) body.email = form.email;
      if (form.document !== (tenant.document ?? "")) body.document = form.document;
      if (form.timezone !== (tenant.timezone ?? "America/Sao_Paulo")) body.timezone = form.timezone;
      if (Object.keys(body).length === 0) { onClose(); return; }
      await apiFetch(`/tenants/${tenant.id}`, { method: "PATCH", body: JSON.stringify(body) });
      onUpdated({ ...tenant, ...body });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-[var(--card)] rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in">
        <div className="px-6 py-4 flex items-center justify-between" style={{ background: "linear-gradient(135deg, #1D3461, #142548)" }}>
          <div>
            <h2 className="text-lg font-bold text-white">Editar empresa</h2>
            <p className="text-xs text-white/60 mt-0.5">{tenant.slug}</p>
          </div>
          <button onClick={onClose} className="text-white/60 hover:text-white"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-6">
          {error && <p className="text-sm text-[var(--danger)] mb-3 p-3 bg-[var(--danger)]/10 rounded-lg">{error}</p>}
          <form onSubmit={submit} className="space-y-3">
            <div className="space-y-1.5">
              <Label>Nome da empresa</Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
            </div>
            <div className="space-y-1.5">
              <Label>E-mail</Label>
              <Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="contato@hotel.com" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>CNPJ / CPF</Label>
                <Input value={form.document} onChange={(e) => setForm((f) => ({ ...f, document: e.target.value }))} placeholder="00.000.000/0000-00" />
              </div>
              <div className="space-y-1.5">
                <Label>Fuso horário</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-[var(--input)] bg-transparent px-3 py-1 text-sm shadow-sm"
                  value={form.timezone}
                  onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
                >
                  <option value="America/Sao_Paulo">Brasília (GMT-3)</option>
                  <option value="America/Manaus">Manaus (GMT-4)</option>
                  <option value="America/Belem">Belém (GMT-3)</option>
                  <option value="America/Fortaleza">Fortaleza (GMT-3)</option>
                  <option value="America/Recife">Recife (GMT-3)</option>
                  <option value="America/Bahia">Salvador (GMT-3)</option>
                  <option value="America/Cuiaba">Cuiabá (GMT-4)</option>
                  <option value="America/Campo_Grande">Campo Grande (GMT-4)</option>
                  <option value="America/Porto_Velho">Porto Velho (GMT-4)</option>
                  <option value="America/Rio_Branco">Rio Branco (GMT-5)</option>
                  <option value="America/Noronha">Fernando de Noronha (GMT-2)</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancelar</Button>
              <Button type="submit" loading={loading}>Salvar</Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export function TenantsClient({ initialTenants, plans }: { initialTenants: Tenant[]; plans: Plan[] }) {
  const [tenants, setTenants] = useState<Tenant[]>(initialTenants);
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Tenant | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [error, setError] = useState("");

  const filtered = tenants.filter(
    (t) => t.name.toLowerCase().includes(search.toLowerCase()) || t.slug.toLowerCase().includes(search.toLowerCase()),
  );

  async function deleteTenant(tenant: Tenant) {
    if (!confirm(`Apagar a empresa ${tenant.name} (${tenant.slug})?`)) return;
    setDeleting(tenant.id);
    setError("");
    try {
      await apiFetch(`/tenants/${tenant.id}`, { method: "DELETE" });
      setTenants((prev) => prev.filter((item) => item.id !== tenant.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao apagar");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Empresas"
        description={`${tenants.length} ${pluralize(tenants.length, "empresa registrada", "empresas registradas")}`}
        actions={
          <Button onClick={() => setShowModal(true)}>
            <Plus size={16} /> Nova empresa
          </Button>
        }
      />

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
        <Input
          className="pl-9"
          placeholder="Buscar por nome ou slug…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && <p className="rounded-xl border border-[var(--danger)]/20 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">{error}</p>}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Empresa</TableHead>
            <TableHead>Plano</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Usuários</TableHead>
            <TableHead className="text-right">Criado em</TableHead>
            <TableHead className="text-right">Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 && (
            <TableEmpty colSpan={6}>
              {tenants.length === 0 ? "Nenhuma empresa registrada." : "Nenhum resultado para a busca."}
            </TableEmpty>
          )}
          {filtered.map((t) => (
            <TableRow key={t.id}>
              <TableCell>
                <p className="font-medium">{t.name}</p>
                <p className="text-xs text-[var(--muted-foreground)] font-mono">{t.slug}</p>
              </TableCell>
              <TableCell>
                {t.plan_name
                  ? <span className="text-xs font-medium">{t.plan_name}</span>
                  : <span className="text-xs text-[var(--muted-foreground)]">—</span>}
              </TableCell>
              <TableCell>
                {t.subscription_status
                  ? <Badge variant={STATUS_VARIANT[t.subscription_status] ?? "default"}>
                      {STATUS_LABEL[t.subscription_status] ?? t.subscription_status}
                    </Badge>
                  : <span className="text-xs text-[var(--muted-foreground)]">sem plano</span>}
              </TableCell>
              <TableCell className="text-right">{t.users_count}</TableCell>
              <TableCell className="text-right text-xs text-[var(--muted-foreground)]">{fmtDate(t.created_at)}</TableCell>
              <TableCell>
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" size="icon" onClick={() => setEditing(t)} title="Editar empresa">
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <SubscriptionMenu
                    tenant={t}
                    onUpdated={(updated) => setTenants((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteTenant(t)}
                    disabled={deleting === t.id}
                    title="Apagar empresa"
                    className="hover:bg-[var(--danger)]/10 hover:text-[var(--danger)]"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {showModal && (
        <NewTenantModal
          plans={plans}
          onClose={() => setShowModal(false)}
          onCreated={(t) => setTenants((prev) => [t, ...prev])}
        />
      )}

      {editing && (
        <EditTenantModal
          tenant={editing}
          onClose={() => setEditing(null)}
          onUpdated={(updated) => {
            setTenants((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}
