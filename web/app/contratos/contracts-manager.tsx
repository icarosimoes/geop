"use client";

import type { TenantUser } from "@/lib/api";
import {
  Search, Plus, X, AlertTriangle, CheckCircle2, Clock, FileText,
  Ban, RefreshCw, Edit2, Trash2, ChevronLeft, ChevronRight,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ContractDetail, ContractSummary, SupplierOption } from "./actions";
import {
  approveContractAction, createAmendmentAction, createContractAction,
  deleteContractAction, getContractAction, listContractsAction,
  listSupplierOptionsAction, updateContractAction, updateContractStatusAction,
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

const STATUS_CLASSES: Record<string, string> = {
  rascunho: "status-neutral", aguardando_aprovacao: "status-waiting", ativo: "status-done",
  em_renovacao: "status-progress", suspenso: "status-danger", encerrado: "status-neutral",
  cancelado: "status-danger",
};

const AMENDMENT_TYPE_LABELS: Record<string, string> = {
  prazo: "Prazo", valor: "Valor", objeto: "Objeto", outros: "Outros",
};

const APPROVAL_STATUS_LABELS: Record<string, string> = {
  pendente: "Pendente", aprovado: "Aprovado", rejeitado: "Rejeitado",
};

const APPROVAL_STATUS_CLASSES: Record<string, string> = {
  pendente: "status-waiting", aprovado: "status-done", rejeitado: "status-danger",
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
  if (days < 0) return <span className="status status-danger">Vencido há {Math.abs(days)}d</span>;
  if (alert) return <span className="status status-waiting">{days}d p/ vencer</span>;
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
    if (raw.supplier_id) raw.supplier_id = Number(raw.supplier_id);
    if (raw.payment_day) raw.payment_day = Number(raw.payment_day);
    if (raw.alert_days) raw.alert_days = Number(raw.alert_days);
    raw.auto_renew = fd.get("auto_renew") === "on";

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
    <form ref={formRef} onSubmit={handleSubmit}>
      {error && <div className="kanban-form-error">{error}</div>}

      <label>Título *<input name="title" required defaultValue={initial?.title} placeholder="Ex: Contrato de manutenção predial" /></label>

      <div className="form-grid">
        <label>Número<input name="number" defaultValue={initial?.number ?? ""} placeholder="Ex: CTR-2026-001" /></label>
        <label>Tipo
          <select name="contract_type" defaultValue={initial?.contract_type ?? "servico"}>
            {Object.entries(CONTRACT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>

      <label>Fornecedor
        <select name="supplier_id" defaultValue={initial?.supplier_id ?? ""}>
          <option value="">— Selecione —</option>
          {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}{s.document ? ` (${s.document})` : ""}</option>)}
        </select>
      </label>

      <label>Objeto / Descrição<textarea name="description" rows={3} defaultValue={initial?.description ?? ""} placeholder="Descreva o objeto do contrato..." /></label>

      <div className="form-grid">
        <label>Data de assinatura<input type="date" name="signed_at" defaultValue={initial?.signed_at ?? ""} /></label>
        <label>Alerta de vencimento (dias)<input type="number" name="alert_days" defaultValue={initial?.alert_days ?? 60} min={1} max={365} /></label>
        <label>Início da vigência<input type="date" name="start_date" defaultValue={initial?.start_date ?? ""} /></label>
        <label>Fim da vigência<input type="date" name="end_date" defaultValue={initial?.end_date ?? ""} /></label>
      </div>

      <label className="checkbox-row">
        <input type="checkbox" name="auto_renew" defaultChecked={initial?.auto_renew} />
        Renovação automática
      </label>

      <fieldset className="form-section">
        <legend>Informações financeiras</legend>
        <div className="form-grid">
          <label>Valor total (R$)<input type="number" name="total_value" step="0.01" defaultValue={initial?.total_value ?? ""} placeholder="0,00" /></label>
          <label>Valor mensal (R$)<input type="number" name="monthly_value" step="0.01" defaultValue={initial?.monthly_value ?? ""} placeholder="0,00" /></label>
          <label>Indexador
            <select name="indexer" defaultValue={initial?.indexer ?? ""}>
              <option value="">— Nenhum —</option>
              <option value="fixo">Fixo</option>
              <option value="ipca">IPCA</option>
              <option value="igpm">IGPM</option>
              <option value="inpc">INPC</option>
            </select>
          </label>
          <label>Frequência de pagamento
            <select name="payment_frequency" defaultValue={initial?.payment_frequency ?? ""}>
              <option value="">— Selecione —</option>
              <option value="mensal">Mensal</option>
              <option value="bimestral">Bimestral</option>
              <option value="trimestral">Trimestral</option>
              <option value="anual">Anual</option>
              <option value="unico">Pagamento único</option>
            </select>
          </label>
          <label>Dia de vencimento<input type="number" name="payment_day" defaultValue={initial?.payment_day ?? ""} min={1} max={31} placeholder="Ex: 10" /></label>
          <label>Centro de custo<input name="cost_center" defaultValue={initial?.cost_center ?? ""} placeholder="Ex: ADM-01" /></label>
        </div>
        <label>Categoria orçamentária<input name="budget_category" defaultValue={initial?.budget_category ?? ""} placeholder="Ex: Despesas operacionais" /></label>
      </fieldset>

      <label>Cláusulas e condições<textarea name="conditions" rows={4} defaultValue={initial?.conditions ?? ""} placeholder="Condições gerais, penalidades, rescisão..." /></label>
      <label>Observações internas<textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} placeholder="Notas internas (não aparecem no contrato)" /></label>

      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar contrato"}</button>
      </footer>
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
    <form ref={formRef} onSubmit={handleSubmit} className="form-section" style={{ marginBottom: "var(--sp-4)" }}>
      <div className="form-grid">
        <label>Tipo de aditivo *
          <select name="amendment_type" required>
            {Object.entries(AMENDMENT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>Data de assinatura<input type="date" name="signed_at" /></label>
      </div>
      <label>Descrição *<textarea name="description" required rows={3} /></label>
      <div className="form-grid">
        <label>Nova data de fim<input type="date" name="new_end_date" /></label>
        <label>Novo valor (R$)<input type="number" name="new_value" step="0.01" /></label>
      </div>
      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : "Registrar aditivo"}</button>
      </footer>
    </form>
  );
}

// ---- Main Component ----

export function ContractsManager({
  user, initialContracts, contractsTotal, initialPage, initialSearch,
  initialStatus, initialContractType,
}: {
  user: TenantUser;
  initialContracts: ContractSummary[];
  contractsTotal: number;
  initialPage: number;
  initialSearch: string;
  initialStatus: string;
  initialContractType: string;
}) {
  const [contracts, setContracts] = useState(initialContracts);
  const [cTotal, setCTotal] = useState(contractsTotal);
  const [page, setPage] = useState(initialPage);
  const [search, setSearch] = useState(initialSearch);
  const [status, setStatus] = useState(initialStatus);
  const [contractType, setContractType] = useState(initialContractType);

  const [selectedContract, setSelectedContract] = useState<ContractDetail | null>(null);
  const [supplierOptions, setSupplierOptions] = useState<SupplierOption[]>([]);
  const [modalMode, setModalMode] = useState<"none" | "form" | "detail">("none");
  const [detailTab, setDetailTab] = useState<"info" | "financial" | "amendments" | "approvals">("info");
  const [showAmendmentForm, setShowAmendmentForm] = useState(false);
  const [approvalComment, setApprovalComment] = useState("");

  useEffect(() => {
    listSupplierOptionsAction().then(setSupplierOptions);
  }, []);

  async function refreshContracts(p = page, s = search, st = status, ct = contractType) {
    const data = await listContractsAction({ page: p, search: s || undefined, status: st || undefined, contract_type: ct || undefined });
    setContracts(data.items);
    setCTotal(data.total);
  }

  async function openContractDetail(id: number) {
    const detail = await getContractAction(id);
    setSelectedContract(detail);
    setDetailTab("info");
    setModalMode("detail");
  }

  function closeModal() {
    setModalMode("none");
    setSelectedContract(null);
    setShowAmendmentForm(false);
  }

  async function handleCreateContract(data: Record<string, unknown>) {
    const res = await createContractAction(data);
    if (!res.ok) throw new Error(res.error);
    closeModal();
    await refreshContracts();
    await listSupplierOptionsAction().then(setSupplierOptions);
  }

  async function handleUpdateContract(data: Record<string, unknown>) {
    if (!selectedContract) return;
    const res = await updateContractAction(selectedContract.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getContractAction(selectedContract.id);
    setSelectedContract(updated);
    setModalMode("detail");
    await refreshContracts();
  }

  async function handleDeleteContract(id: number) {
    if (!confirm("Excluir este contrato?")) return;
    await deleteContractAction(id);
    closeModal();
    await refreshContracts();
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

  const canApprove = selectedContract?.approval_steps.some(
    (s) => s.approver_user_id === user.id && s.status === "pendente"
  );

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Gestão</p>
          <h1>Contratos</h1>
          <p>Gerencie contratos e fluxo de aprovação.</p>
        </div>
        <button className="primary-button" onClick={() => { setSelectedContract(null); setModalMode("form"); }}>
          <Plus size={18} /> Novo contrato
        </button>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label>
            <Search size={18} />
            <input
              placeholder="Buscar contrato..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { setPage(1); refreshContracts(1, search, status, contractType); }
              }}
            />
          </label>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); refreshContracts(1, search, e.target.value, contractType); }}>
            <option value="">Todos os status</option>
            {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select value={contractType} onChange={(e) => { setContractType(e.target.value); setPage(1); refreshContracts(1, search, status, e.target.value); }}>
            <option value="">Todos os tipos</option>
            {Object.entries(CONTRACT_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button onClick={() => {
            setStatus("ativo");
            listContractsAction({ page: 1, status: "ativo", expiring_in_days: 60 }).then((d) => { setContracts(d.items); setCTotal(d.total); setPage(1); });
          }}>
            <AlertTriangle size={15} /> Vencendo
          </button>
        </div>

        {contracts.length === 0 ? (
          <div className="module-state">
            <FileText />
            <strong>Nenhum contrato encontrado</strong>
            <span>Ajuste os filtros ou crie um novo contrato.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
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
                {contracts.map((c) => (
                  <tr key={c.id} onClick={() => openContractDetail(c.id)}>
                    <td>
                      <strong>{c.title}</strong>
                      {c.number && <small style={{ display: "block", color: "var(--muted)", fontSize: "var(--font-xs)" }}>{c.number}</small>}
                    </td>
                    <td>{CONTRACT_TYPE_LABELS[c.contract_type] ?? c.contract_type}</td>
                    <td>{c.supplier_name ?? "—"}</td>
                    <td>
                      <div>{c.start_date ? formatDate(c.start_date) : "—"}{c.end_date && ` – ${formatDate(c.end_date)}`}</div>
                      <ExpiryBadge days={c.days_until_expiry ?? null} alert={c.expiry_alert} />
                    </td>
                    <td>{formatCurrency(c.monthly_value)}</td>
                    <td><span className={`status ${STATUS_CLASSES[c.status] ?? "status-neutral"}`}>{STATUS_LABELS[c.status] ?? c.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{cTotal} contrato{cTotal !== 1 ? "s" : ""}</span>
          {cPages > 1 && (
            <div>
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refreshContracts(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {cPages}</span>
              <button disabled={page >= cPages} onClick={() => { const p = page + 1; setPage(p); refreshContracts(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </footer>
      </section>

      {/* Create / edit modal */}
      {modalMode === "form" && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" style={{ maxWidth: 720 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Gestão</span>
                <h2>{selectedContract ? "Editar contrato" : "Novo contrato"}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <ContractForm
              initial={selectedContract}
              suppliers={supplierOptions}
              onSave={selectedContract ? handleUpdateContract : handleCreateContract}
              onCancel={closeModal}
            />
          </section>
        </div>
      )}

      {/* Detail modal */}
      {modalMode === "detail" && selectedContract && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal has-timeline" role="dialog" aria-modal="true" style={{ maxWidth: 780 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>#{selectedContract.id}</span>
                <h2>{selectedContract.title}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>

            <form onSubmit={(e) => e.preventDefault()}>
              <div className="contract-badges">
                <span className={`status ${STATUS_CLASSES[selectedContract.status] ?? "status-neutral"}`}>
                  {STATUS_LABELS[selectedContract.status] ?? selectedContract.status}
                </span>
                <span className="status status-neutral">{CONTRACT_TYPE_LABELS[selectedContract.contract_type] ?? selectedContract.contract_type}</span>
                {selectedContract.end_date && (
                  <ExpiryBadge
                    days={(() => { const d = (new Date(selectedContract.end_date + "T00:00:00").getTime() - Date.now()) / 86400000 | 0; return d; })()}
                    alert={(() => { const d = (new Date(selectedContract.end_date + "T00:00:00").getTime() - Date.now()) / 86400000 | 0; return d <= selectedContract.alert_days; })()}
                  />
                )}
              </div>

              <div className="contract-actions">
                {selectedContract.status === "rascunho" && (
                  <button type="button" className="secondary-button" onClick={() => handleStatusChange(selectedContract.id, "aguardando_aprovacao")}>
                    <CheckCircle2 size={14} /> Enviar para aprovação
                  </button>
                )}
                {selectedContract.status === "ativo" && (
                  <>
                    <button type="button" className="secondary-button" onClick={() => handleStatusChange(selectedContract.id, "em_renovacao")}>
                      <RefreshCw size={14} /> Renovação
                    </button>
                    <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleStatusChange(selectedContract.id, "suspenso")}>
                      <Ban size={14} /> Suspender
                    </button>
                    <button type="button" className="secondary-button" onClick={() => handleStatusChange(selectedContract.id, "encerrado")}>
                      <Clock size={14} /> Encerrar
                    </button>
                  </>
                )}
                {(selectedContract.status === "suspenso" || selectedContract.status === "em_renovacao") && (
                  <button type="button" className="secondary-button" style={{ color: "var(--green)" }} onClick={() => handleStatusChange(selectedContract.id, "ativo")}>
                    <CheckCircle2 size={14} /> Ativar
                  </button>
                )}
                <button type="button" className="secondary-button" onClick={() => setModalMode("form")}>
                  <Edit2 size={14} /> Editar
                </button>
                <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleDeleteContract(selectedContract.id)}>
                  <Trash2 size={14} /> Excluir
                </button>
              </div>

              <div className="detail-tabs">
                {(["info", "financial", "amendments", "approvals"] as const).map((t) => (
                  <button key={t} type="button" className={detailTab === t ? "active" : ""} onClick={() => setDetailTab(t)}>
                    {t === "info" && "Informações"}
                    {t === "financial" && "Financeiro"}
                    {t === "amendments" && `Aditivos (${selectedContract.amendments.length})`}
                    {t === "approvals" && `Aprovações (${selectedContract.approval_steps.length})`}
                  </button>
                ))}
              </div>

              {detailTab === "info" && (
                <div className="form-grid">
                  <label>Fornecedor<span>{selectedContract.supplier_name ?? "—"}</span></label>
                  <label>Responsável<span>{selectedContract.responsible_name ?? "—"}</span></label>
                  <label>Assinatura<span>{formatDate(selectedContract.signed_at)}</span></label>
                  <label>Início<span>{formatDate(selectedContract.start_date)}</span></label>
                  <label>Fim<span>{formatDate(selectedContract.end_date)}</span></label>
                  <label>Renovação automática<span>{selectedContract.auto_renew ? "Sim" : "Não"}</span></label>
                  {selectedContract.description && (
                    <label style={{ gridColumn: "1 / -1" }}>Objeto<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedContract.description}</span></label>
                  )}
                  {selectedContract.conditions && (
                    <label style={{ gridColumn: "1 / -1" }}>Cláusulas<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedContract.conditions}</span></label>
                  )}
                  {selectedContract.notes && (
                    <label style={{ gridColumn: "1 / -1" }}>Observações<span style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}>{selectedContract.notes}</span></label>
                  )}
                </div>
              )}

              {detailTab === "financial" && (
                <div className="form-grid">
                  <label>Valor total<span>{formatCurrency(selectedContract.total_value)}</span></label>
                  <label>Valor mensal<span>{formatCurrency(selectedContract.monthly_value)}</span></label>
                  <label>Indexador<span>{selectedContract.indexer?.toUpperCase() ?? "—"}</span></label>
                  <label>Frequência de pagamento<span>{selectedContract.payment_frequency ?? "—"}</span></label>
                  <label>Dia de vencimento<span>{selectedContract.payment_day ?? "—"}</span></label>
                  <label>Centro de custo<span>{selectedContract.cost_center ?? "—"}</span></label>
                  <label style={{ gridColumn: "1 / -1" }}>Categoria orçamentária<span>{selectedContract.budget_category ?? "—"}</span></label>
                </div>
              )}

              {detailTab === "amendments" && (
                <div>
                  <div className="section-header">
                    <strong>Aditivos</strong>
                    {!showAmendmentForm && (
                      <button type="button" className="secondary-button" onClick={() => setShowAmendmentForm(true)}>
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
                    <p className="empty-hint">Nenhum aditivo registrado.</p>
                  )}
                  {selectedContract.amendments.map((a) => (
                    <div key={a.id} className="timeline-entry">
                      <span className="status status-neutral">{AMENDMENT_TYPE_LABELS[a.amendment_type] ?? a.amendment_type}</span>
                      <div>
                        <p style={{ margin: 0 }}>{a.description}</p>
                        {a.new_end_date && <small style={{ display: "block", color: "var(--muted)" }}>Nova data de fim: {formatDate(a.new_end_date)}</small>}
                        {a.new_value && <small style={{ display: "block", color: "var(--muted)" }}>Novo valor: {formatCurrency(a.new_value)}</small>}
                        {a.signed_at && <small style={{ display: "block", color: "var(--muted)" }}>Assinado em: {formatDate(a.signed_at)}</small>}
                        <small style={{ display: "block", color: "var(--muted)", marginTop: "var(--sp-1)" }}>
                          {a.created_by_name ?? "—"} · {new Intl.DateTimeFormat("pt-BR").format(new Date(a.created_at))}
                        </small>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {detailTab === "approvals" && (
                <div>
                  {canApprove && selectedContract.status === "aguardando_aprovacao" && (
                    <div className="approval-box">
                      <p style={{ margin: "0 0 var(--sp-2)", fontWeight: 700 }}>Você é um aprovador deste contrato.</p>
                      <textarea
                        placeholder="Comentário (opcional)"
                        value={approvalComment}
                        onChange={(e) => setApprovalComment(e.target.value)}
                        rows={2}
                      />
                      <div style={{ display: "flex", gap: "var(--sp-2)", justifyContent: "flex-end", marginTop: "var(--sp-2)" }}>
                        <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleApproval(false)}>
                          <Ban size={14} /> Rejeitar
                        </button>
                        <button type="button" className="secondary-button" style={{ color: "var(--green)" }} onClick={() => handleApproval(true)}>
                          <CheckCircle2 size={14} /> Aprovar
                        </button>
                      </div>
                    </div>
                  )}
                  {selectedContract.approval_steps.length === 0 && (
                    <p className="empty-hint">Nenhuma etapa de aprovação configurada.</p>
                  )}
                  {selectedContract.approval_steps.map((s) => (
                    <div key={s.id} className="timeline-entry">
                      <span className={`status ${APPROVAL_STATUS_CLASSES[s.status] ?? "status-waiting"}`}>
                        {APPROVAL_STATUS_LABELS[s.status] ?? s.status}
                      </span>
                      <div>
                        <strong>Etapa {s.step_order}: {s.approver_name ?? `Usuário #${s.approver_user_id}`}</strong>
                        {s.comment && <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "var(--font-sm)" }}>{s.comment}</p>}
                        {s.decided_at && <small style={{ display: "block", color: "var(--muted)", marginTop: 4 }}>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(s.decided_at))}</small>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </form>
          </section>
        </div>
      )}

      <style>{`
        .contract-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .contract-actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .detail-tabs { display: flex; gap: var(--sp-1); border-bottom: 1px solid var(--line); }
        .detail-tabs button { padding: var(--sp-2) var(--sp-3); border: 0; border-bottom: 2px solid transparent; background: none; cursor: pointer; font-size: var(--font-sm); font-weight: 600; color: var(--muted); }
        .detail-tabs button.active { color: var(--blue); border-bottom-color: var(--blue); }
        .section-header { display: flex; align-items: center; justify-content: space-between; }
        .empty-hint { color: var(--muted); font-size: var(--font-sm); text-align: center; padding: var(--sp-5) 0; }
        .timeline-entry { display: flex; gap: var(--sp-3); padding: var(--sp-3) 0; border-bottom: 1px solid var(--line); }
        .timeline-entry:last-child { border-bottom: 0; }
        .approval-box { border: 1px solid var(--line); border-radius: var(--radius-md); padding: var(--sp-4); background: #fafbfd; }
        .approval-box textarea { width: 100%; padding: var(--sp-3); border: 1px solid var(--field-border); border-radius: var(--radius-md); background: var(--field-bg); resize: vertical; box-sizing: border-box; }
        .checkbox-row { display: flex !important; flex-direction: row !important; align-items: center; gap: var(--sp-2); }
        .checkbox-row input { width: auto !important; min-height: 0 !important; }
        .record-modal.has-timeline label > span { font-size: var(--font-base); font-weight: 400; color: var(--ink); }
      `}</style>
    </>
  );
}
