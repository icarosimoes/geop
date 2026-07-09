"use client";

import type { TenantUser } from "@/lib/api";
import {
  Building2, ChevronLeft, ChevronRight, FileText, Phone, Mail,
  Plus, Search, Trash2, X, AlertTriangle, CheckCircle2, Clock,
  Ban, RefreshCw, ChevronDown, User, DollarSign, Calendar,
  Edit2, Star,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import type {
  ContractDetail, ContractSummary, SupplierDetail, SupplierSummary, SupplierOption,
} from "./actions";
import {
  approveContractAction, createAmendmentAction, createContactAction, createContractAction,
  createSupplierAction, deleteContactAction, deleteContractAction, deleteSupplierAction,
  getContractAction, getSupplierAction, listContractsAction, listSuppliersAction,
  listSupplierOptionsAction, updateContractAction, updateContractStatusAction,
  updateContactAction, updateSupplierAction,
} from "./actions";

const CONTRACT_TYPE_LABELS: Record<string, string> = {
  servico: "Serviço", fornecimento: "Fornecimento", locacao: "Locação",
  comodato: "Comodato", consultoria: "Consultoria", licenca: "Licença",
  manutencao: "Manutenção", outro: "Outro",
};

const STATUS_LABELS: Record<string, string> = {
  rascunho: "Rascunho", aguardando_aprovacao: "Ag. Aprovação", ativo: "Ativo",
  em_renovacao: "Em Renovação", suspenso: "Suspenso", encerrado: "Encerrado",
  cancelado: "Cancelado",
};

const STATUS_COLORS: Record<string, string> = {
  rascunho: "badge-grey", aguardando_aprovacao: "badge-yellow", ativo: "badge-green",
  em_renovacao: "badge-blue", suspenso: "badge-orange", encerrado: "badge-grey",
  cancelado: "badge-red",
};

const AMENDMENT_TYPE_LABELS: Record<string, string> = {
  prazo: "Prazo", valor: "Valor", objeto: "Objeto", outros: "Outros",
};

const APPROVAL_STATUS_LABELS: Record<string, string> = {
  pendente: "Pendente", aprovado: "Aprovado", rejeitado: "Rejeitado",
};

function formatCurrency(value: string | null): string {
  if (!value) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Intl.DateTimeFormat("pt-BR").format(new Date(d + "T00:00:00"));
}

function ExpiryBadge({ days, alert }: { days: number | null; alert: boolean }) {
  if (days === null) return null;
  if (days < 0) return <span className="badge badge-red">Vencido há {Math.abs(days)}d</span>;
  if (alert) return <span className="badge badge-orange">{days}d p/ vencer</span>;
  return null;
}

// ---- Contract Form ----

function ContractForm({
  initial, suppliers, onSave, onCancel,
}: {
  initial?: ContractDetail | null;
  suppliers: SupplierOption[];
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) {
      if (v === "") continue;
      raw[k] = v;
    }
    if (raw.total_value) raw.total_value = raw.total_value;
    if (raw.monthly_value) raw.monthly_value = raw.monthly_value;
    if (raw.supplier_id) raw.supplier_id = Number(raw.supplier_id);
    if (raw.payment_day) raw.payment_day = Number(raw.payment_day);
    if (raw.alert_days) raw.alert_days = Number(raw.alert_days);
    raw.auto_renew = fd.get("auto_renew") === "on";

    const approvers = (fd.getAll("approver_ids") as string[]).map(Number).filter(Boolean);
    if (!initial) raw.approver_user_ids = approvers;

    setLoading(true);
    setError("");
    try {
      await onSave(raw);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="drawer-form">
      <div className="form-grid">
        <div className="field span-2">
          <label>Título *</label>
          <input name="title" required defaultValue={initial?.title} placeholder="Ex: Contrato de manutenção predial" />
        </div>
        <div className="field">
          <label>Número</label>
          <input name="number" defaultValue={initial?.number ?? ""} placeholder="Ex: CTR-2026-001" />
        </div>
        <div className="field">
          <label>Tipo</label>
          <select name="contract_type" defaultValue={initial?.contract_type ?? "servico"}>
            {Object.entries(CONTRACT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="field span-2">
          <label>Fornecedor</label>
          <select name="supplier_id" defaultValue={initial?.supplier_id ?? ""}>
            <option value="">— Selecione —</option>
            {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}{s.document ? ` (${s.document})` : ""}</option>)}
          </select>
        </div>
        <div className="field span-2">
          <label>Objeto / Descrição</label>
          <textarea name="description" rows={3} defaultValue={initial?.description ?? ""} placeholder="Descreva o objeto do contrato..." />
        </div>
        <div className="field">
          <label>Data de assinatura</label>
          <input type="date" name="signed_at" defaultValue={initial?.signed_at ?? ""} />
        </div>
        <div className="field">
          <label>Início da vigência</label>
          <input type="date" name="start_date" defaultValue={initial?.start_date ?? ""} />
        </div>
        <div className="field">
          <label>Fim da vigência</label>
          <input type="date" name="end_date" defaultValue={initial?.end_date ?? ""} />
        </div>
        <div className="field">
          <label>Alerta de vencimento (dias)</label>
          <input type="number" name="alert_days" defaultValue={initial?.alert_days ?? 60} min={1} max={365} />
        </div>
        <div className="field">
          <label>Renovação automática</label>
          <label className="checkbox-wrap">
            <input type="checkbox" name="auto_renew" defaultChecked={initial?.auto_renew} />
            <span>Sim</span>
          </label>
        </div>

        <div className="field-section-title span-2">Informações Financeiras</div>
        <div className="field">
          <label>Valor total (R$)</label>
          <input type="number" name="total_value" step="0.01" defaultValue={initial?.total_value ?? ""} placeholder="0,00" />
        </div>
        <div className="field">
          <label>Valor mensal (R$)</label>
          <input type="number" name="monthly_value" step="0.01" defaultValue={initial?.monthly_value ?? ""} placeholder="0,00" />
        </div>
        <div className="field">
          <label>Indexador</label>
          <select name="indexer" defaultValue={initial?.indexer ?? ""}>
            <option value="">— Nenhum —</option>
            <option value="fixo">Fixo</option>
            <option value="ipca">IPCA</option>
            <option value="igpm">IGPM</option>
            <option value="inpc">INPC</option>
          </select>
        </div>
        <div className="field">
          <label>Frequência de pagamento</label>
          <select name="payment_frequency" defaultValue={initial?.payment_frequency ?? ""}>
            <option value="">— Selecione —</option>
            <option value="mensal">Mensal</option>
            <option value="bimestral">Bimestral</option>
            <option value="trimestral">Trimestral</option>
            <option value="anual">Anual</option>
            <option value="unico">Pagamento único</option>
          </select>
        </div>
        <div className="field">
          <label>Dia de vencimento</label>
          <input type="number" name="payment_day" defaultValue={initial?.payment_day ?? ""} min={1} max={31} placeholder="Ex: 10" />
        </div>
        <div className="field">
          <label>Centro de custo</label>
          <input name="cost_center" defaultValue={initial?.cost_center ?? ""} placeholder="Ex: ADM-01" />
        </div>
        <div className="field span-2">
          <label>Categoria orçamentária</label>
          <input name="budget_category" defaultValue={initial?.budget_category ?? ""} placeholder="Ex: Despesas operacionais" />
        </div>
        <div className="field span-2">
          <label>Cláusulas e condições</label>
          <textarea name="conditions" rows={4} defaultValue={initial?.conditions ?? ""} placeholder="Condições gerais, penalidades, rescisão..." />
        </div>
        <div className="field span-2">
          <label>Observações internas</label>
          <textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} placeholder="Notas internas (não aparecem no contrato)" />
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="drawer-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar contrato"}</button>
      </div>
    </form>
  );
}

// ---- Supplier Form ----

function SupplierForm({
  initial, onSave, onCancel,
}: {
  initial?: SupplierDetail | null;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    setLoading(true);
    setError("");
    try { await onSave(raw); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar."); }
    finally { setLoading(false); }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="drawer-form">
      <div className="form-grid">
        <div className="field span-2">
          <label>Nome / Razão social *</label>
          <input name="name" required defaultValue={initial?.name} />
        </div>
        <div className="field">
          <label>Tipo de documento</label>
          <select name="document_type" defaultValue={initial?.document_type ?? ""}>
            <option value="">— Selecione —</option>
            <option value="cnpj">CNPJ</option>
            <option value="cpf">CPF</option>
          </select>
        </div>
        <div className="field">
          <label>CPF/CNPJ</label>
          <input name="document" defaultValue={initial?.document ?? ""} placeholder="00.000.000/0000-00" />
        </div>
        <div className="field span-2">
          <label>Categoria</label>
          <input name="category" defaultValue={initial?.category ?? ""} placeholder="Ex: Tecnologia, Limpeza, Segurança..." />
        </div>
        <div className="field">
          <label>E-mail</label>
          <input type="email" name="email" defaultValue={initial?.email ?? ""} />
        </div>
        <div className="field">
          <label>Telefone</label>
          <input name="phone" defaultValue={initial?.phone ?? ""} />
        </div>
        <div className="field span-2">
          <label>Website</label>
          <input name="website" defaultValue={initial?.website ?? ""} placeholder="https://" />
        </div>
        <div className="field-section-title span-2">Endereço</div>
        <div className="field span-2">
          <label>Logradouro</label>
          <input name="address_street" defaultValue={initial?.address_street ?? ""} />
        </div>
        <div className="field">
          <label>Número</label>
          <input name="address_number" defaultValue={initial?.address_number ?? ""} />
        </div>
        <div className="field">
          <label>Complemento</label>
          <input name="address_complement" defaultValue={initial?.address_complement ?? ""} />
        </div>
        <div className="field">
          <label>Cidade</label>
          <input name="address_city" defaultValue={initial?.address_city ?? ""} />
        </div>
        <div className="field" style={{ maxWidth: 80 }}>
          <label>UF</label>
          <input name="address_state" maxLength={2} defaultValue={initial?.address_state ?? ""} placeholder="SP" />
        </div>
        <div className="field">
          <label>CEP</label>
          <input name="address_zip" defaultValue={initial?.address_zip ?? ""} placeholder="00000-000" />
        </div>
        <div className="field span-2">
          <label>Observações</label>
          <textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} />
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="drawer-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar fornecedor"}</button>
      </div>
    </form>
  );
}

// ---- Contact Form ----

function ContactForm({ supplierId, onSave, onCancel }: { supplierId: number; onSave: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    raw.is_primary = fd.get("is_primary") === "on";
    setLoading(true);
    await createContactAction(supplierId, raw);
    setLoading(false);
    onSave();
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="inline-form">
      <div className="form-grid">
        <div className="field"><label>Nome *</label><input name="name" required /></div>
        <div className="field"><label>Cargo</label><input name="role" /></div>
        <div className="field"><label>E-mail</label><input type="email" name="email" /></div>
        <div className="field"><label>Telefone</label><input name="phone" /></div>
        <div className="field"><label>WhatsApp</label><input name="whatsapp" /></div>
        <div className="field">
          <label>Contato principal</label>
          <label className="checkbox-wrap"><input type="checkbox" name="is_primary" /><span>Sim</span></label>
        </div>
      </div>
      <div className="drawer-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? "Salvando…" : "Adicionar contato"}</button>
      </div>
    </form>
  );
}

// ---- Amendment Form ----

function AmendmentForm({ contractId, onSave, onCancel }: { contractId: number; onSave: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    const raw: Record<string, unknown> = {};
    for (const [k, v] of fd.entries()) { if (v !== "") raw[k] = v; }
    setLoading(true);
    await createAmendmentAction(contractId, raw);
    setLoading(false);
    onSave();
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="inline-form">
      <div className="form-grid">
        <div className="field">
          <label>Tipo de aditivo *</label>
          <select name="amendment_type" required>
            {Object.entries(AMENDMENT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="field"><label>Data de assinatura</label><input type="date" name="signed_at" /></div>
        <div className="field span-2"><label>Descrição *</label><textarea name="description" required rows={3} /></div>
        <div className="field"><label>Nova data de fim</label><input type="date" name="new_end_date" /></div>
        <div className="field"><label>Novo valor (R$)</label><input type="number" name="new_value" step="0.01" /></div>
      </div>
      <div className="drawer-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? "Salvando…" : "Registrar aditivo"}</button>
      </div>
    </form>
  );
}

// ---- Main Component ----

export function ContractsManager({
  user, initialTab, initialContracts, contractsTotal,
  initialSuppliers, suppliersTotal, initialPage, initialSearch,
  initialStatus, initialContractType,
}: {
  user: TenantUser;
  initialTab: string;
  initialContracts: ContractSummary[];
  contractsTotal: number;
  initialSuppliers: SupplierSummary[];
  suppliersTotal: number;
  initialPage: number;
  initialSearch: string;
  initialStatus: string;
  initialContractType: string;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [tab, setTab] = useState(initialTab);
  const [contracts, setContracts] = useState(initialContracts);
  const [cTotal, setCTotal] = useState(contractsTotal);
  const [suppliers, setSuppliers] = useState(initialSuppliers);
  const [sTotal, setSTotal] = useState(suppliersTotal);
  const [page, setPage] = useState(initialPage);
  const [search, setSearch] = useState(initialSearch);
  const [status, setStatus] = useState(initialStatus);
  const [contractType, setContractType] = useState(initialContractType);

  const [selectedContract, setSelectedContract] = useState<ContractDetail | null>(null);
  const [selectedSupplier, setSelectedSupplier] = useState<SupplierDetail | null>(null);
  const [supplierOptions, setSupplierOptions] = useState<SupplierOption[]>([]);
  const [drawerMode, setDrawerMode] = useState<"none" | "contract-form" | "supplier-form" | "contract-detail" | "supplier-detail">("none");
  const [detailTab, setDetailTab] = useState<"info" | "financial" | "amendments" | "approvals">("info");
  const [showAmendmentForm, setShowAmendmentForm] = useState(false);
  const [showContactForm, setShowContactForm] = useState(false);
  const [approvalComment, setApprovalComment] = useState("");
  const [statusChangeTarget, setStatusChangeTarget] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listSupplierOptionsAction().then(setSupplierOptions);
  }, []);

  function switchTab(t: string) {
    setTab(t);
    setPage(1);
    setSearch("");
    setStatus("");
    setContractType("");
    router.push(`/contratos?tab=${t}`);
  }

  async function refreshContracts(p = page, s = search, st = status, ct = contractType) {
    const data = await listContractsAction({ page: p, search: s || undefined, status: st || undefined, contract_type: ct || undefined });
    setContracts(data.items);
    setCTotal(data.total);
  }

  async function refreshSuppliers(p = page, s = search) {
    const data = await listSuppliersAction({ page: p, search: s || undefined });
    setSuppliers(data.items);
    setSTotal(data.total);
  }

  async function openContractDetail(id: number) {
    setLoading(true);
    const detail = await getContractAction(id);
    setSelectedContract(detail);
    setDetailTab("info");
    setDrawerMode("contract-detail");
    setLoading(false);
  }

  async function openSupplierDetail(id: number) {
    setLoading(true);
    const detail = await getSupplierAction(id);
    setSelectedSupplier(detail);
    setDrawerMode("supplier-detail");
    setLoading(false);
  }

  function closeDrawer() {
    setDrawerMode("none");
    setSelectedContract(null);
    setSelectedSupplier(null);
    setShowAmendmentForm(false);
    setShowContactForm(false);
  }

  async function handleCreateContract(data: Record<string, unknown>) {
    const res = await createContractAction(data);
    if (!res.ok) throw new Error(res.error);
    closeDrawer();
    await refreshContracts();
    await listSupplierOptionsAction().then(setSupplierOptions);
  }

  async function handleUpdateContract(data: Record<string, unknown>) {
    if (!selectedContract) return;
    const res = await updateContractAction(selectedContract.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getContractAction(selectedContract.id);
    setSelectedContract(updated);
    setDrawerMode("contract-detail");
    await refreshContracts();
  }

  async function handleCreateSupplier(data: Record<string, unknown>) {
    const res = await createSupplierAction(data);
    if (!res.ok) throw new Error(res.error);
    closeDrawer();
    await refreshSuppliers();
    await listSupplierOptionsAction().then(setSupplierOptions);
  }

  async function handleUpdateSupplier(data: Record<string, unknown>) {
    if (!selectedSupplier) return;
    const res = await updateSupplierAction(selectedSupplier.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getSupplierAction(selectedSupplier.id);
    setSelectedSupplier(updated);
    setDrawerMode("supplier-detail");
    await refreshSuppliers();
  }

  async function handleDeleteContract(id: number) {
    if (!confirm("Excluir este contrato?")) return;
    await deleteContractAction(id);
    closeDrawer();
    await refreshContracts();
  }

  async function handleDeleteSupplier(id: number) {
    if (!confirm("Excluir este fornecedor?")) return;
    await deleteSupplierAction(id);
    closeDrawer();
    await refreshSuppliers();
  }

  async function handleStatusChange(id: number, newStatus: string) {
    if (!confirm(`Alterar status para "${STATUS_LABELS[newStatus] ?? newStatus}"?`)) return;
    await updateContractStatusAction(id, newStatus);
    const updated = await getContractAction(id);
    setSelectedContract(updated);
    await refreshContracts();
  }

  async function handleApproval(approved: boolean) {
    if (!selectedContract) return;
    const res = await approveContractAction(selectedContract.id, approved, approvalComment || undefined);
    if (!res.ok) { alert(res.error); return; }
    setApprovalComment("");
    const updated = await getContractAction(selectedContract.id);
    setSelectedContract(updated);
    await refreshContracts();
  }

  const pageSize = 20;
  const cPages = Math.ceil(cTotal / pageSize);
  const sPages = Math.ceil(sTotal / pageSize);

  const canApprove = selectedContract?.approval_steps.some(
    (s) => s.approver_user_id === user.id && s.status === "pendente"
  );

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Gestão</p>
          <h1>Contratos</h1>
          <p>Gerencie contratos, fornecedores e fluxo de aprovação.</p>
        </div>
        <div className="heading-actions">
          {tab === "contratos" ? (
            <button className="btn-primary" onClick={() => setDrawerMode("contract-form")}>
              <Plus size={16} /> Novo contrato
            </button>
          ) : (
            <button className="btn-primary" onClick={() => setDrawerMode("supplier-form")}>
              <Plus size={16} /> Novo fornecedor
            </button>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div className="tab-bar">
        <button className={tab === "contratos" ? "tab active" : "tab"} onClick={() => switchTab("contratos")}>
          <FileText size={15} /> Contratos
        </button>
        <button className={tab === "fornecedores" ? "tab active" : "tab"} onClick={() => switchTab("fornecedores")}>
          <Building2 size={15} /> Fornecedores
        </button>
      </div>

      {/* Filters */}
      <div className="list-toolbar">
        <div className="search-wrap">
          <Search size={15} />
          <input
            placeholder={tab === "contratos" ? "Buscar contrato…" : "Buscar fornecedor…"}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setPage(1);
                tab === "contratos" ? refreshContracts(1, search, status, contractType) : refreshSuppliers(1, search);
              }
            }}
          />
        </div>
        {tab === "contratos" && (
          <>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); refreshContracts(1, search, e.target.value, contractType); }}>
              <option value="">Todos os status</option>
              {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select value={contractType} onChange={(e) => { setContractType(e.target.value); setPage(1); refreshContracts(1, search, status, e.target.value); }}>
              <option value="">Todos os tipos</option>
              {Object.entries(CONTRACT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button className="btn-icon-sm" title="Vencendo em 60 dias" onClick={() => {
              setStatus("ativo");
              listContractsAction({ page: 1, status: "ativo", expiring_in_days: 60 }).then((d) => { setContracts(d.items); setCTotal(d.total); setPage(1); });
            }}>
              <AlertTriangle size={15} /> Vencendo
            </button>
          </>
        )}
      </div>

      {/* Contracts table */}
      {tab === "contratos" && (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Título / Nº</th>
                <th>Tipo</th>
                <th>Fornecedor</th>
                <th>Vigência</th>
                <th>Valor mensal</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {contracts.length === 0 && (
                <tr><td colSpan={6} className="empty-cell">Nenhum contrato encontrado.</td></tr>
              )}
              {contracts.map((c) => (
                <tr key={c.id} className="clickable" onClick={() => openContractDetail(c.id)}>
                  <td>
                    <div className="cell-title">{c.title}</div>
                    {c.number && <div className="cell-sub">{c.number}</div>}
                  </td>
                  <td>{CONTRACT_TYPE_LABELS[c.contract_type] ?? c.contract_type}</td>
                  <td>{c.supplier_name ?? "—"}</td>
                  <td>
                    <div>{c.start_date ? formatDate(c.start_date) : "—"}</div>
                    {c.end_date && <div className="cell-sub">{formatDate(c.end_date)}</div>}
                    <ExpiryBadge days={c.days_until_expiry ?? null} alert={c.expiry_alert} />
                  </td>
                  <td>{formatCurrency(c.monthly_value)}</td>
                  <td><span className={`badge ${STATUS_COLORS[c.status] ?? "badge-grey"}`}>{STATUS_LABELS[c.status] ?? c.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {cPages > 1 && (
            <div className="pagination">
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refreshContracts(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {cPages}</span>
              <button disabled={page >= cPages} onClick={() => { const p = page + 1; setPage(p); refreshContracts(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </div>
      )}

      {/* Suppliers table */}
      {tab === "fornecedores" && (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>CNPJ/CPF</th>
                <th>Categoria</th>
                <th>Contato</th>
                <th>Contratos</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.length === 0 && (
                <tr><td colSpan={6} className="empty-cell">Nenhum fornecedor encontrado.</td></tr>
              )}
              {suppliers.map((s) => (
                <tr key={s.id} className="clickable" onClick={() => openSupplierDetail(s.id)}>
                  <td><div className="cell-title">{s.name}</div></td>
                  <td>{s.document ?? "—"}</td>
                  <td>{s.category ?? "—"}</td>
                  <td>
                    {s.email && <div className="cell-sub"><Mail size={12} /> {s.email}</div>}
                    {s.phone && <div className="cell-sub"><Phone size={12} /> {s.phone}</div>}
                  </td>
                  <td>
                    <span className="badge badge-blue">{s.contract_count} contrato{s.contract_count !== 1 ? "s" : ""}</span>
                  </td>
                  <td><span className={`badge ${s.active ? "badge-green" : "badge-grey"}`}>{s.active ? "Ativo" : "Inativo"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {sPages > 1 && (
            <div className="pagination">
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refreshSuppliers(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {sPages}</span>
              <button disabled={page >= sPages} onClick={() => { const p = page + 1; setPage(p); refreshSuppliers(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </div>
      )}

      {/* Drawer overlay */}
      {drawerMode !== "none" && (
        <div className="drawer-overlay" onClick={closeDrawer}>
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h2>
                {drawerMode === "contract-form" && (selectedContract ? "Editar contrato" : "Novo contrato")}
                {drawerMode === "supplier-form" && (selectedSupplier ? "Editar fornecedor" : "Novo fornecedor")}
                {drawerMode === "contract-detail" && selectedContract?.title}
                {drawerMode === "supplier-detail" && selectedSupplier?.name}
              </h2>
              <button className="btn-icon" onClick={closeDrawer}><X size={20} /></button>
            </div>

            {/* Contract form */}
            {drawerMode === "contract-form" && (
              <ContractForm
                initial={selectedContract}
                suppliers={supplierOptions}
                onSave={selectedContract ? handleUpdateContract : handleCreateContract}
                onCancel={closeDrawer}
              />
            )}

            {/* Supplier form */}
            {drawerMode === "supplier-form" && (
              <SupplierForm
                initial={selectedSupplier}
                onSave={selectedSupplier ? handleUpdateSupplier : handleCreateSupplier}
                onCancel={closeDrawer}
              />
            )}

            {/* Contract detail */}
            {drawerMode === "contract-detail" && selectedContract && (
              <div className="drawer-content">
                <div className="detail-meta-row">
                  <span className={`badge ${STATUS_COLORS[selectedContract.status] ?? "badge-grey"}`}>
                    {STATUS_LABELS[selectedContract.status] ?? selectedContract.status}
                  </span>
                  <span className="badge badge-grey">{CONTRACT_TYPE_LABELS[selectedContract.contract_type] ?? selectedContract.contract_type}</span>
                  {selectedContract.end_date && (
                    <ExpiryBadge
                      days={(() => { const d = (new Date(selectedContract.end_date + "T00:00:00").getTime() - Date.now()) / 86400000 | 0; return d; })()}
                      alert={(() => { const d = (new Date(selectedContract.end_date + "T00:00:00").getTime() - Date.now()) / 86400000 | 0; return d <= selectedContract.alert_days; })()}
                    />
                  )}
                </div>

                {/* Status actions */}
                <div className="status-actions">
                  {selectedContract.status === "rascunho" && (
                    <button className="btn-sm btn-blue" onClick={() => handleStatusChange(selectedContract.id, "aguardando_aprovacao")}>
                      <CheckCircle2 size={14} /> Enviar para aprovação
                    </button>
                  )}
                  {selectedContract.status === "ativo" && (
                    <>
                      <button className="btn-sm btn-yellow" onClick={() => handleStatusChange(selectedContract.id, "em_renovacao")}>
                        <RefreshCw size={14} /> Renovação
                      </button>
                      <button className="btn-sm btn-orange" onClick={() => handleStatusChange(selectedContract.id, "suspenso")}>
                        <Ban size={14} /> Suspender
                      </button>
                      <button className="btn-sm btn-grey" onClick={() => handleStatusChange(selectedContract.id, "encerrado")}>
                        <Clock size={14} /> Encerrar
                      </button>
                    </>
                  )}
                  {(selectedContract.status === "suspenso" || selectedContract.status === "em_renovacao") && (
                    <button className="btn-sm btn-green" onClick={() => handleStatusChange(selectedContract.id, "ativo")}>
                      <CheckCircle2 size={14} /> Ativar
                    </button>
                  )}
                  <button className="btn-sm btn-secondary" onClick={() => { setDrawerMode("contract-form"); }}>
                    <Edit2 size={14} /> Editar
                  </button>
                  <button className="btn-sm btn-red" onClick={() => handleDeleteContract(selectedContract.id)}>
                    <Trash2 size={14} /> Excluir
                  </button>
                </div>

                {/* Detail tabs */}
                <div className="tab-bar mini">
                  {(["info", "financial", "amendments", "approvals"] as const).map((t) => (
                    <button key={t} className={detailTab === t ? "tab active" : "tab"} onClick={() => setDetailTab(t)}>
                      {t === "info" && "Informações"}
                      {t === "financial" && "Financeiro"}
                      {t === "amendments" && `Aditivos (${selectedContract.amendments.length})`}
                      {t === "approvals" && `Aprovações (${selectedContract.approval_steps.length})`}
                    </button>
                  ))}
                </div>

                {detailTab === "info" && (
                  <div className="detail-fields">
                    <div className="detail-field"><label>Fornecedor</label><span>{selectedContract.supplier_name ?? "—"}</span></div>
                    <div className="detail-field"><label>Responsável</label><span>{selectedContract.responsible_name ?? "—"}</span></div>
                    <div className="detail-field"><label>Assinatura</label><span>{formatDate(selectedContract.signed_at)}</span></div>
                    <div className="detail-field"><label>Início</label><span>{formatDate(selectedContract.start_date)}</span></div>
                    <div className="detail-field"><label>Fim</label><span>{formatDate(selectedContract.end_date)}</span></div>
                    <div className="detail-field"><label>Renovação automática</label><span>{selectedContract.auto_renew ? "Sim" : "Não"}</span></div>
                    {selectedContract.description && (
                      <div className="detail-field span-2"><label>Objeto</label><p className="text-block">{selectedContract.description}</p></div>
                    )}
                    {selectedContract.conditions && (
                      <div className="detail-field span-2"><label>Cláusulas</label><p className="text-block">{selectedContract.conditions}</p></div>
                    )}
                    {selectedContract.notes && (
                      <div className="detail-field span-2"><label>Observações</label><p className="text-block">{selectedContract.notes}</p></div>
                    )}
                  </div>
                )}

                {detailTab === "financial" && (
                  <div className="detail-fields">
                    <div className="detail-field"><label>Valor total</label><span>{formatCurrency(selectedContract.total_value)}</span></div>
                    <div className="detail-field"><label>Valor mensal</label><span>{formatCurrency(selectedContract.monthly_value)}</span></div>
                    <div className="detail-field"><label>Indexador</label><span>{selectedContract.indexer?.toUpperCase() ?? "—"}</span></div>
                    <div className="detail-field"><label>Frequência pag.</label><span>{selectedContract.payment_frequency ?? "—"}</span></div>
                    <div className="detail-field"><label>Dia de vencimento</label><span>{selectedContract.payment_day ?? "—"}</span></div>
                    <div className="detail-field"><label>Centro de custo</label><span>{selectedContract.cost_center ?? "—"}</span></div>
                    <div className="detail-field span-2"><label>Categoria orçamentária</label><span>{selectedContract.budget_category ?? "—"}</span></div>
                  </div>
                )}

                {detailTab === "amendments" && (
                  <div>
                    <div className="section-header">
                      <span>Aditivos</span>
                      {!showAmendmentForm && (
                        <button className="btn-sm btn-secondary" onClick={() => setShowAmendmentForm(true)}>
                          <Plus size={14} /> Novo aditivo
                        </button>
                      )}
                    </div>
                    {showAmendmentForm && (
                      <AmendmentForm
                        contractId={selectedContract.id}
                        onSave={async () => {
                          setShowAmendmentForm(false);
                          const updated = await getContractAction(selectedContract.id);
                          setSelectedContract(updated);
                          await refreshContracts();
                        }}
                        onCancel={() => setShowAmendmentForm(false)}
                      />
                    )}
                    {selectedContract.amendments.length === 0 && !showAmendmentForm && (
                      <p className="empty-section">Nenhum aditivo registrado.</p>
                    )}
                    {selectedContract.amendments.map((a) => (
                      <div key={a.id} className="timeline-item">
                        <div className="timeline-badge">{AMENDMENT_TYPE_LABELS[a.amendment_type] ?? a.amendment_type}</div>
                        <div className="timeline-body">
                          <p>{a.description}</p>
                          {a.new_end_date && <div className="cell-sub">Nova data de fim: {formatDate(a.new_end_date)}</div>}
                          {a.new_value && <div className="cell-sub">Novo valor: {formatCurrency(a.new_value)}</div>}
                          {a.signed_at && <div className="cell-sub">Assinado em: {formatDate(a.signed_at)}</div>}
                          <div className="cell-sub timeline-meta">{a.created_by_name ?? "—"} · {new Intl.DateTimeFormat("pt-BR").format(new Date(a.created_at))}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {detailTab === "approvals" && (
                  <div>
                    {canApprove && selectedContract.status === "aguardando_aprovacao" && (
                      <div className="approval-panel">
                        <p>Você é um aprovador deste contrato.</p>
                        <textarea
                          placeholder="Comentário (opcional)"
                          value={approvalComment}
                          onChange={(e) => setApprovalComment(e.target.value)}
                          rows={2}
                        />
                        <div className="approval-buttons">
                          <button className="btn-sm btn-red" onClick={() => handleApproval(false)}><Ban size={14} /> Rejeitar</button>
                          <button className="btn-sm btn-green" onClick={() => handleApproval(true)}><CheckCircle2 size={14} /> Aprovar</button>
                        </div>
                      </div>
                    )}
                    {selectedContract.approval_steps.length === 0 && (
                      <p className="empty-section">Nenhuma etapa de aprovação configurada.</p>
                    )}
                    {selectedContract.approval_steps.map((s) => (
                      <div key={s.id} className="timeline-item">
                        <div className={`timeline-badge ${s.status === "aprovado" ? "badge-green" : s.status === "rejeitado" ? "badge-red" : "badge-yellow"}`}>
                          {APPROVAL_STATUS_LABELS[s.status] ?? s.status}
                        </div>
                        <div className="timeline-body">
                          <strong>Etapa {s.step_order}: {s.approver_name ?? `Usuário #${s.approver_user_id}`}</strong>
                          {s.comment && <p className="cell-sub">{s.comment}</p>}
                          {s.decided_at && <div className="cell-sub">{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(s.decided_at))}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Supplier detail */}
            {drawerMode === "supplier-detail" && selectedSupplier && (
              <div className="drawer-content">
                <div className="detail-meta-row">
                  <span className={`badge ${selectedSupplier.active ? "badge-green" : "badge-grey"}`}>{selectedSupplier.active ? "Ativo" : "Inativo"}</span>
                  {selectedSupplier.category && <span className="badge badge-blue">{selectedSupplier.category}</span>}
                </div>
                <div className="status-actions">
                  <button className="btn-sm btn-secondary" onClick={() => setDrawerMode("supplier-form")}>
                    <Edit2 size={14} /> Editar
                  </button>
                  <button className="btn-sm btn-red" onClick={() => handleDeleteSupplier(selectedSupplier.id)}>
                    <Trash2 size={14} /> Excluir
                  </button>
                </div>

                <div className="detail-fields">
                  {selectedSupplier.document && <div className="detail-field"><label>CNPJ/CPF</label><span>{selectedSupplier.document}</span></div>}
                  {selectedSupplier.email && <div className="detail-field"><label>E-mail</label><a href={`mailto:${selectedSupplier.email}`}>{selectedSupplier.email}</a></div>}
                  {selectedSupplier.phone && <div className="detail-field"><label>Telefone</label><span>{selectedSupplier.phone}</span></div>}
                  {selectedSupplier.website && <div className="detail-field span-2"><label>Website</label><a href={selectedSupplier.website} target="_blank" rel="noopener noreferrer">{selectedSupplier.website}</a></div>}
                  {(selectedSupplier.address_street) && (
                    <div className="detail-field span-2">
                      <label>Endereço</label>
                      <span>{[selectedSupplier.address_street, selectedSupplier.address_number, selectedSupplier.address_complement, selectedSupplier.address_city, selectedSupplier.address_state, selectedSupplier.address_zip].filter(Boolean).join(", ")}</span>
                    </div>
                  )}
                  {selectedSupplier.notes && <div className="detail-field span-2"><label>Observações</label><p className="text-block">{selectedSupplier.notes}</p></div>}
                </div>

                <div className="section-header">
                  <span>Contatos ({selectedSupplier.contacts.length})</span>
                  {!showContactForm && (
                    <button className="btn-sm btn-secondary" onClick={() => setShowContactForm(true)}>
                      <Plus size={14} /> Adicionar
                    </button>
                  )}
                </div>
                {showContactForm && (
                  <ContactForm
                    supplierId={selectedSupplier.id}
                    onSave={async () => {
                      setShowContactForm(false);
                      const updated = await getSupplierAction(selectedSupplier.id);
                      setSelectedSupplier(updated);
                    }}
                    onCancel={() => setShowContactForm(false)}
                  />
                )}
                {selectedSupplier.contacts.length === 0 && !showContactForm && (
                  <p className="empty-section">Nenhum contato cadastrado.</p>
                )}
                {selectedSupplier.contacts.map((c) => (
                  <div key={c.id} className="contact-card">
                    <div className="contact-header">
                      <div>
                        <strong>{c.name}</strong>
                        {c.is_primary && <Star size={12} className="primary-star" />}
                        {c.role && <span className="cell-sub">{c.role}</span>}
                      </div>
                      <button className="btn-icon-sm" onClick={async () => {
                        if (!confirm("Remover contato?")) return;
                        await deleteContactAction(c.id);
                        const updated = await getSupplierAction(selectedSupplier.id);
                        setSelectedSupplier(updated);
                      }}><Trash2 size={14} /></button>
                    </div>
                    {c.email && <div className="cell-sub"><Mail size={12} /> {c.email}</div>}
                    {c.phone && <div className="cell-sub"><Phone size={12} /> {c.phone}</div>}
                    {c.whatsapp && <div className="cell-sub"><Phone size={12} /> WhatsApp: {c.whatsapp}</div>}
                    {c.notes && <p className="cell-sub">{c.notes}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .tab-bar { display:flex; gap:2px; border-bottom:1px solid var(--border); margin-bottom:16px; }
        .tab-bar.mini { margin:12px 0 8px; }
        .tab { padding:8px 14px; background:none; border:none; border-bottom:2px solid transparent; cursor:pointer; font-size:.85rem; color:var(--text-muted); display:flex; align-items:center; gap:6px; }
        .tab.active { color:var(--primary); border-bottom-color:var(--primary); font-weight:600; }
        .list-toolbar { display:flex; align-items:center; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
        .search-wrap { display:flex; align-items:center; gap:6px; background:var(--input-bg); border:1px solid var(--border); border-radius:6px; padding:6px 10px; min-width:220px; }
        .search-wrap input { border:none; background:none; outline:none; font-size:.875rem; width:100%; }
        .list-toolbar select { padding:6px 10px; border:1px solid var(--border); border-radius:6px; font-size:.85rem; background:var(--input-bg); }
        .data-table-wrap { overflow-x:auto; }
        .data-table { width:100%; border-collapse:collapse; font-size:.875rem; }
        .data-table th { text-align:left; padding:8px 12px; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; color:var(--text-muted); border-bottom:1px solid var(--border); }
        .data-table td { padding:10px 12px; border-bottom:1px solid var(--border-light,#f0f0f0); vertical-align:top; }
        .data-table tr.clickable { cursor:pointer; }
        .data-table tr.clickable:hover td { background:var(--hover-bg,rgba(0,0,0,.03)); }
        .cell-title { font-weight:500; }
        .cell-sub { font-size:.8rem; color:var(--text-muted); display:flex; align-items:center; gap:4px; margin-top:2px; }
        .empty-cell { text-align:center; color:var(--text-muted); padding:32px; }
        .pagination { display:flex; align-items:center; gap:8px; justify-content:flex-end; margin-top:12px; font-size:.85rem; }
        .pagination button { padding:4px 8px; border:1px solid var(--border); border-radius:4px; background:none; cursor:pointer; }
        .pagination button:disabled { opacity:.4; cursor:default; }
        .badge { display:inline-flex; align-items:center; padding:2px 8px; border-radius:99px; font-size:.75rem; font-weight:600; }
        .badge-grey { background:#f3f4f6; color:#374151; }
        .badge-green { background:#d1fae5; color:#065f46; }
        .badge-blue { background:#dbeafe; color:#1d4ed8; }
        .badge-yellow { background:#fef3c7; color:#92400e; }
        .badge-orange { background:#fed7aa; color:#9a3412; }
        .badge-red { background:#fee2e2; color:#991b1b; }
        .heading-actions { display:flex; gap:8px; }
        .btn-primary { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; background:var(--primary,#2563eb); color:#fff; border:none; border-radius:6px; font-size:.875rem; font-weight:500; cursor:pointer; }
        .btn-secondary { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; background:none; border:1px solid var(--border); border-radius:6px; font-size:.875rem; cursor:pointer; }
        .btn-icon { background:none; border:none; cursor:pointer; color:var(--text-muted); }
        .btn-icon-sm { background:none; border:none; cursor:pointer; color:var(--text-muted); padding:2px; }
        .btn-sm { display:inline-flex; align-items:center; gap:4px; padding:5px 10px; border-radius:6px; font-size:.8rem; cursor:pointer; border:none; }
        .btn-blue { background:#dbeafe; color:#1d4ed8; }
        .btn-green { background:#d1fae5; color:#065f46; }
        .btn-yellow { background:#fef3c7; color:#92400e; }
        .btn-orange { background:#fed7aa; color:#9a3412; }
        .btn-red { background:#fee2e2; color:#991b1b; }
        .btn-grey { background:#f3f4f6; color:#374151; }
        .btn-sm.btn-secondary { background:var(--input-bg); border:1px solid var(--border); color:var(--text); }
        .drawer-overlay { position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:100; display:flex; justify-content:flex-end; }
        .drawer-panel { width:min(680px,95vw); background:var(--bg,#fff); height:100vh; overflow-y:auto; display:flex; flex-direction:column; }
        .drawer-header { display:flex; align-items:center; justify-content:space-between; padding:20px 24px 16px; border-bottom:1px solid var(--border); }
        .drawer-header h2 { font-size:1.1rem; font-weight:600; margin:0; }
        .drawer-form { padding:16px 24px 24px; overflow-y:auto; flex:1; }
        .drawer-content { padding:16px 24px; overflow-y:auto; flex:1; }
        .form-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
        .field { display:flex; flex-direction:column; gap:4px; }
        .field.span-2 { grid-column:span 2; }
        .field label { font-size:.8rem; font-weight:500; color:var(--text-muted); }
        .field input, .field select, .field textarea { padding:7px 10px; border:1px solid var(--border); border-radius:6px; font-size:.875rem; background:var(--input-bg,#fff); }
        .field-section-title { font-size:.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--text-muted); padding-top:8px; border-top:1px solid var(--border-light,#f0f0f0); }
        .checkbox-wrap { display:flex; align-items:center; gap:8px; font-size:.875rem; cursor:pointer; }
        .form-error { color:#991b1b; font-size:.85rem; margin-top:8px; }
        .drawer-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:16px; padding-top:12px; border-top:1px solid var(--border-light,#f0f0f0); }
        .inline-form { background:var(--hover-bg,rgba(0,0,0,.02)); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin:8px 0 12px; }
        .detail-meta-row { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
        .status-actions { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
        .detail-fields { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:16px; }
        .detail-field { display:flex; flex-direction:column; gap:2px; }
        .detail-field.span-2 { grid-column:span 2; }
        .detail-field label { font-size:.75rem; font-weight:500; color:var(--text-muted); text-transform:uppercase; letter-spacing:.04em; }
        .detail-field span, .detail-field a { font-size:.875rem; }
        .text-block { font-size:.875rem; white-space:pre-wrap; margin:0; line-height:1.5; }
        .section-header { display:flex; align-items:center; justify-content:space-between; margin:12px 0 8px; }
        .section-header span { font-weight:600; font-size:.9rem; }
        .empty-section { color:var(--text-muted); font-size:.875rem; text-align:center; padding:16px; }
        .timeline-item { display:flex; gap:10px; padding:10px 0; border-bottom:1px solid var(--border-light,#f0f0f0); }
        .timeline-badge { flex-shrink:0; font-size:.75rem; font-weight:600; padding:3px 8px; border-radius:99px; background:#f3f4f6; color:#374151; height:fit-content; }
        .timeline-body p { margin:0; font-size:.875rem; }
        .timeline-meta { color:var(--text-muted); margin-top:4px; }
        .approval-panel { background:var(--hover-bg,rgba(0,0,0,.02)); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin-bottom:12px; }
        .approval-panel p { margin:0 0 8px; font-size:.875rem; font-weight:500; }
        .approval-panel textarea { width:100%; padding:7px 10px; border:1px solid var(--border); border-radius:6px; font-size:.875rem; resize:vertical; box-sizing:border-box; }
        .approval-buttons { display:flex; gap:8px; justify-content:flex-end; margin-top:8px; }
        .contact-card { padding:10px 12px; border:1px solid var(--border); border-radius:8px; margin-bottom:8px; }
        .contact-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:4px; }
        .contact-header strong { font-size:.875rem; }
        .primary-star { color:#f59e0b; margin-left:4px; }
      `}</style>
    </>
  );
}
