"use client";

import { useState } from "react";
import {
  Ban, CheckCircle, Loader2, LogIn, MoreVertical, Pencil, Plus, Search, ShieldOff, Trash2,
} from "lucide-react";
import { toast } from "sonner";
import type { Tenant, Plan } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, type ConfirmDialogState } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { apiFetch } from "@/lib/client-fetch";
import { fmtDate, pluralize } from "@/lib/utils";
import { useCepLookup, useCnpjLookup } from "@/lib/use-document-lookup";
import { formatCEP, formatCNPJ, formatCPF, onlyDigits } from "@/lib/validators";

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

function SubscriptionMenu({
  tenant,
  onUpdated,
  requestConfirm,
}: {
  tenant: Tenant;
  onUpdated: (t: Tenant) => void;
  requestConfirm: (state: ConfirmDialogState) => void;
}) {
  const status = tenant.subscription_status ?? "";
  const actions = SUB_ACTIONS[status] ?? [];

  if (actions.length === 0) return null;

  async function apply(nextStatus: string) {
    try {
      await apiFetch(`/tenants/${tenant.id}/subscription`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      });
      onUpdated({ ...tenant, subscription_status: nextStatus });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao atualizar assinatura");
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" title="Gerenciar assinatura">
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Assinatura</DropdownMenuLabel>
        {actions.map((a) => (
          <DropdownMenuItem
            key={a.nextStatus}
            className={a.danger ? "text-[var(--danger)]" : "text-[var(--success)]"}
            onSelect={() =>
              requestConfirm({
                title: `${a.label} assinatura`,
                description: `${a.label} a assinatura de ${tenant.name}?`,
                confirmLabel: a.label,
                variant: a.danger ? "destructive" : "success",
                onConfirm: () => apply(a.nextStatus),
              })
            }
          >
            {a.icon} {a.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function NewTenantModal({
  plans,
  open,
  onClose,
  onCreated,
}: {
  plans: Plan[];
  open: boolean;
  onClose: () => void;
  onCreated: (t: Tenant) => void;
}) {
  const [form, setForm] = useState({
    name: "", slug: "", email: "", document: "",
    address_street: "", address_number: "", address_complement: "",
    address_neighborhood: "", address_city: "", address_state: "", address_zip: "",
    plan_id: plans[0]?.id ?? 0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  const cep = useCepLookup((fields) => {
    setForm((f) => ({
      ...f,
      address_street: fields.address_street ?? f.address_street,
      address_neighborhood: fields.address_neighborhood ?? f.address_neighborhood,
      address_city: fields.address_city ?? f.address_city,
      address_state: fields.address_state ?? f.address_state,
    }));
  });

  const cnpj = useCnpjLookup((fields) => {
    setForm((f) => ({
      ...f,
      name: fields.name || f.name,
      slug: f.slug || slugify(fields.name ?? ""),
      address_street: fields.address_street ?? f.address_street,
      address_number: fields.address_number ?? f.address_number,
      address_complement: fields.address_complement ?? f.address_complement,
      address_neighborhood: fields.address_neighborhood ?? f.address_neighborhood,
      address_city: fields.address_city ?? f.address_city,
      address_state: fields.address_state ?? f.address_state,
      address_zip: fields.address_zip ?? f.address_zip,
    }));
  });

  function slugify(s: string) {
    return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 30);
  }

  function handleDocumentBlur(value: string) {
    if (onlyDigits(value).length === 14) cnpj.handleBlur(value);
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
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Nova empresa</DialogTitle>
          <DialogDescription>Cria tenant + assinatura trial</DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-[var(--danger)] mb-3 p-3 bg-[var(--danger)]/10 rounded-lg">{error}</p>}
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>CNPJ / CPF</Label>
              <div className="relative flex items-center">
                <Input
                  value={form.document}
                  onChange={(e) => setField("document", onlyDigits(e.target.value).length > 11 ? formatCNPJ(e.target.value) : formatCPF(e.target.value))}
                  onBlur={(e) => handleDocumentBlur(e.target.value)}
                  placeholder="00.000.000/0000-00"
                />
                {cnpj.loading && <Loader2 size={16} className="absolute right-3 animate-spin text-[var(--muted-foreground)]" />}
              </div>
              {cnpj.notFound && <p className="text-xs text-[var(--danger)]">CNPJ não encontrado.</p>}
              {cnpj.rateLimited && <p className="text-xs text-[var(--muted-foreground)]">Consulta de CNPJ temporariamente indisponível (limite de uso) — preencha manualmente.</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Slug</Label>
              <Input value={form.slug} onChange={(e) => setField("slug", e.target.value)} required />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Nome da empresa</Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value, slug: f.slug || slugify(e.target.value) }))} required />
            </div>
            <div className="space-y-1.5">
              <Label>E-mail do tenant</Label>
              <Input type="email" value={form.email} onChange={(e) => setField("email", e.target.value)} required />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>CEP</Label>
              <div className="relative flex items-center">
                <Input
                  value={form.address_zip}
                  onChange={(e) => setField("address_zip", formatCEP(e.target.value))}
                  onBlur={(e) => cep.handleBlur(e.target.value)}
                  placeholder="00000-000"
                />
                {cep.loading && <Loader2 size={16} className="absolute right-3 animate-spin text-[var(--muted-foreground)]" />}
              </div>
              {cep.notFound && <p className="text-xs text-[var(--danger)]">CEP não encontrado.</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Logradouro</Label>
              <Input value={form.address_street} onChange={(e) => setField("address_street", e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label>Número</Label>
              <Input value={form.address_number} onChange={(e) => setField("address_number", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Bairro</Label>
              <Input value={form.address_neighborhood} onChange={(e) => setField("address_neighborhood", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Cidade / UF</Label>
              <div className="flex gap-2">
                <Input value={form.address_city} onChange={(e) => setField("address_city", e.target.value)} />
                <Input className="w-16" maxLength={2} value={form.address_state} onChange={(e) => setField("address_state", e.target.value.toUpperCase())} placeholder="UF" />
              </div>
            </div>
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
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancelar</Button>
            <Button type="submit" loading={loading}>Criar empresa</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditTenantModal({
  tenant,
  onClose,
  onUpdated,
}: {
  tenant: Tenant | null;
  onClose: () => void;
  onUpdated: (t: Tenant) => void;
}) {
  const [form, setForm] = useState({
    name: tenant?.name ?? "",
    email: tenant?.email ?? "",
    document: tenant?.document ?? "",
    trade_name: tenant?.trade_name ?? "",
    address_street: tenant?.address_street ?? "",
    address_number: tenant?.address_number ?? "",
    address_complement: tenant?.address_complement ?? "",
    address_neighborhood: tenant?.address_neighborhood ?? "",
    address_city: tenant?.address_city ?? "",
    address_state: tenant?.address_state ?? "",
    address_zip: tenant?.address_zip ?? "",
    timezone: tenant?.timezone ?? "America/Sao_Paulo",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  const cep = useCepLookup((fields) => {
    setForm((f) => ({
      ...f,
      address_street: fields.address_street ?? f.address_street,
      address_neighborhood: fields.address_neighborhood ?? f.address_neighborhood,
      address_city: fields.address_city ?? f.address_city,
      address_state: fields.address_state ?? f.address_state,
    }));
  });

  const cnpj = useCnpjLookup((fields) => {
    setForm((f) => ({
      ...f,
      name: fields.name || f.name,
      trade_name: fields.trade_name || f.trade_name,
      address_street: fields.address_street ?? f.address_street,
      address_number: fields.address_number ?? f.address_number,
      address_complement: fields.address_complement ?? f.address_complement,
      address_neighborhood: fields.address_neighborhood ?? f.address_neighborhood,
      address_city: fields.address_city ?? f.address_city,
      address_state: fields.address_state ?? f.address_state,
      address_zip: fields.address_zip ?? f.address_zip,
    }));
  });

  const ADDRESS_FIELDS = [
    "address_street", "address_number", "address_complement",
    "address_neighborhood", "address_city", "address_state", "address_zip",
  ] as const;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!tenant) return;
    setLoading(true);
    setError("");
    try {
      const body: Record<string, string> = {};
      if (form.name !== tenant.name) body.name = form.name;
      if (form.email !== (tenant.email ?? "")) body.email = form.email;
      if (form.document !== (tenant.document ?? "")) body.document = form.document;
      if (form.trade_name !== (tenant.trade_name ?? "")) body.trade_name = form.trade_name;
      for (const field of ADDRESS_FIELDS) {
        if (form[field] !== (tenant[field] ?? "")) body[field] = form[field];
      }
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
    <Dialog
      open={!!tenant}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent className="max-w-xl">
        {tenant && (
          <>
            <DialogHeader>
              <DialogTitle>Editar empresa</DialogTitle>
              <DialogDescription>{tenant.slug}</DialogDescription>
            </DialogHeader>
            {error && <p className="text-sm text-[var(--danger)] mb-3 p-3 bg-[var(--danger)]/10 rounded-lg">{error}</p>}
            <form onSubmit={submit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>CNPJ / CPF</Label>
                  <div className="relative flex items-center">
                    <Input
                      value={form.document}
                      onChange={(e) => setField("document", onlyDigits(e.target.value).length > 11 ? formatCNPJ(e.target.value) : formatCPF(e.target.value))}
                      onBlur={(e) => { if (onlyDigits(e.target.value).length === 14) cnpj.handleBlur(e.target.value); }}
                      placeholder="00.000.000/0000-00"
                    />
                    {cnpj.loading && <Loader2 size={16} className="absolute right-3 animate-spin text-[var(--muted-foreground)]" />}
                  </div>
                  {cnpj.notFound && <p className="text-xs text-[var(--danger)]">CNPJ não encontrado.</p>}
              {cnpj.rateLimited && <p className="text-xs text-[var(--muted-foreground)]">Consulta de CNPJ temporariamente indisponível (limite de uso) — preencha manualmente.</p>}
                </div>
                <div className="space-y-1.5">
                  <Label>Nome fantasia</Label>
                  <Input value={form.trade_name} onChange={(e) => setField("trade_name", e.target.value)} />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Nome da empresa</Label>
                <Input value={form.name} onChange={(e) => setField("name", e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label>E-mail</Label>
                <Input type="email" value={form.email} onChange={(e) => setField("email", e.target.value)} placeholder="contato@hotel.com" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>CEP</Label>
                  <div className="relative flex items-center">
                    <Input
                      value={form.address_zip}
                      onChange={(e) => setField("address_zip", formatCEP(e.target.value))}
                      onBlur={(e) => cep.handleBlur(e.target.value)}
                      placeholder="00000-000"
                    />
                    {cep.loading && <Loader2 size={16} className="absolute right-3 animate-spin text-[var(--muted-foreground)]" />}
                  </div>
                  {cep.notFound && <p className="text-xs text-[var(--danger)]">CEP não encontrado.</p>}
                </div>
                <div className="space-y-1.5">
                  <Label>Logradouro</Label>
                  <Input value={form.address_street} onChange={(e) => setField("address_street", e.target.value)} />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label>Número</Label>
                  <Input value={form.address_number} onChange={(e) => setField("address_number", e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Bairro</Label>
                  <Input value={form.address_neighborhood} onChange={(e) => setField("address_neighborhood", e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Cidade / UF</Label>
                  <div className="flex gap-2">
                    <Input value={form.address_city} onChange={(e) => setField("address_city", e.target.value)} />
                    <Input className="w-16" maxLength={2} value={form.address_state} onChange={(e) => setField("address_state", e.target.value.toUpperCase())} placeholder="UF" />
                  </div>
                </div>
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
              <DialogFooter>
                <Button type="button" variant="outline" onClick={onClose}>Cancelar</Button>
                <Button type="submit" loading={loading}>Salvar</Button>
              </DialogFooter>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function TenantsClient({ initialTenants, plans }: { initialTenants: Tenant[]; plans: Plan[] }) {
  const [tenants, setTenants] = useState<Tenant[]>(initialTenants);
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Tenant | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmDialogState | null>(null);

  const filtered = tenants.filter(
    (t) => t.name.toLowerCase().includes(search.toLowerCase()) || t.slug.toLowerCase().includes(search.toLowerCase()),
  );

  function requestConfirm(state: ConfirmDialogState) {
    setConfirmState(state);
  }

  async function impersonate(tenant: Tenant) {
    try {
      const res = await apiFetch<{ web_url: string }>(`/tenants/${tenant.id}/impersonate`, {
        method: "POST",
      });
      window.open(res.web_url, "_blank");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao entrar no tenant");
    }
  }

  function deleteTenant(tenant: Tenant) {
    requestConfirm({
      title: "Apagar empresa",
      description: `Apagar a empresa ${tenant.name} (${tenant.slug})? Essa ação não pode ser desfeita.`,
      confirmLabel: "Apagar",
      variant: "destructive",
      onConfirm: async () => {
        try {
          await apiFetch(`/tenants/${tenant.id}`, { method: "DELETE" });
          setTenants((prev) => prev.filter((item) => item.id !== tenant.id));
        } catch (err) {
          toast.error(err instanceof Error ? err.message : "Erro ao apagar empresa");
        }
      },
    });
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
                  <Button variant="ghost" size="icon" onClick={() => impersonate(t)} title="Entrar como administrador do tenant">
                    <LogIn className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => setEditing(t)} title="Editar empresa">
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <SubscriptionMenu
                    tenant={t}
                    onUpdated={(updated) => setTenants((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))}
                    requestConfirm={requestConfirm}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteTenant(t)}
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

      <NewTenantModal
        plans={plans}
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreated={(t) => setTenants((prev) => [t, ...prev])}
      />

      <EditTenantModal
        key={editing?.id ?? "none"}
        tenant={editing}
        onClose={() => setEditing(null)}
        onUpdated={(updated) => {
          setTenants((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
          setEditing(null);
        }}
      />

      <ConfirmDialog state={confirmState} onOpenChange={(o) => !o && setConfirmState(null)} />
    </div>
  );
}
