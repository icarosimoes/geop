"use client";

import {
  ChevronLeft, ChevronRight, Edit2, Plus, Search, Trash2, Wallet, X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CostCenterDetail, CostCenterOption, CostCenterSummary } from "./actions";
import {
  createCostCenterAction, deleteCostCenterAction, getCostCenterAction,
  listCostCenterOptionsAction, listCostCentersAction, updateCostCenterAction,
} from "./actions";

// ---- Cost Center Form ----

function CostCenterForm({
  initial, options, onSave, onCancel,
}: {
  initial?: CostCenterDetail | null;
  options: CostCenterOption[];
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
    if (raw.parent_id) raw.parent_id = Number(raw.parent_id);
    raw.active = fd.get("active") === "on";
    setLoading(true);
    setError("");
    try { await onSave(raw); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar."); }
    finally { setLoading(false); }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit}>
      {error && <div className="kanban-form-error">{error}</div>}

      <label>Nome *<input name="name" required defaultValue={initial?.name} /></label>

      <div className="form-grid">
        <label>Código<input name="code" defaultValue={initial?.code ?? ""} placeholder="Ex: ADM-01" /></label>
        <label>Centro de custo pai
          <select name="parent_id" defaultValue={initial?.parent_id ?? ""}>
            <option value="">— Nenhum —</option>
            {options.filter((o) => o.id !== initial?.id).map((o) => (
              <option key={o.id} value={o.id}>{o.name}{o.code ? ` (${o.code})` : ""}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="checkbox-row"><input type="checkbox" name="active" defaultChecked={initial ? initial.active : true} /> Ativo</label>

      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando…" : initial ? "Salvar" : "Criar centro de custo"}</button>
      </footer>
    </form>
  );
}

// ---- Main Component ----

export function CostCenterManager() {
  const [costCenters, setCostCenters] = useState<CostCenterSummary[]>([]);
  const [options, setOptions] = useState<CostCenterOption[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const [selected, setSelected] = useState<CostCenterDetail | null>(null);
  const [modalMode, setModalMode] = useState<"none" | "form" | "detail">("none");

  useEffect(() => {
    refresh(1, "");
    listCostCenterOptionsAction().then(setOptions);
  }, []);

  async function refresh(p = page, s = search) {
    setLoading(true);
    const data = await listCostCentersAction({ page: p, search: s || undefined });
    setCostCenters(data.items);
    setTotal(data.total);
    setLoading(false);
  }

  async function refreshOptions() {
    setOptions(await listCostCenterOptionsAction());
  }

  async function openDetail(id: number) {
    const detail = await getCostCenterAction(id);
    setSelected(detail);
    setModalMode("detail");
  }

  function closeModal() {
    setModalMode("none");
    setSelected(null);
  }

  async function handleCreate(data: Record<string, unknown>) {
    const res = await createCostCenterAction(data);
    if (!res.ok) throw new Error(res.error);
    closeModal();
    await refresh();
    await refreshOptions();
  }

  async function handleUpdate(data: Record<string, unknown>) {
    if (!selected) return;
    const res = await updateCostCenterAction(selected.id, data);
    if (!res.ok) throw new Error(res.error);
    const updated = await getCostCenterAction(selected.id);
    setSelected(updated);
    setModalMode("detail");
    await refresh();
    await refreshOptions();
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir este centro de custo?")) return;
    await deleteCostCenterAction(id);
    closeModal();
    await refresh();
    await refreshOptions();
  }

  const pageSize = 20;
  const pages = Math.ceil(total / pageSize);

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Cadastros</p>
          <h1>Centros de custo</h1>
          <p>Cadastro de centros de custo usados no rateio de contratos.</p>
        </div>
        <button className="primary-button" onClick={() => { setSelected(null); setModalMode("form"); }}>
          <Plus size={18} /> Novo centro de custo
        </button>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label>
            <Search size={18} />
            <input
              placeholder="Buscar centro de custo..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { setPage(1); refresh(1, search); }
              }}
            />
          </label>
        </div>

        {!loading && costCenters.length === 0 ? (
          <div className="module-state">
            <Wallet />
            <strong>Nenhum centro de custo encontrado</strong>
            <span>Ajuste a busca ou cadastre um novo centro de custo.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Código</th>
                  <th>Centro pai</th>
                  <th>Contratos</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {costCenters.map((c) => (
                  <tr key={c.id} onClick={() => openDetail(c.id)}>
                    <td><strong>{c.name}</strong></td>
                    <td>{c.code ?? "—"}</td>
                    <td>{c.parent_name ?? "—"}</td>
                    <td>{c.contract_count} contrato{c.contract_count !== 1 ? "s" : ""}</td>
                    <td><span className={`status ${c.active ? "status-done" : "status-neutral"}`}>{c.active ? "Ativo" : "Inativo"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{total} centro{total !== 1 ? "s" : ""} de custo</span>
          {pages > 1 && (
            <div>
              <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); refresh(p); }}><ChevronLeft size={16} /></button>
              <span>{page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => { const p = page + 1; setPage(p); refresh(p); }}><ChevronRight size={16} /></button>
            </div>
          )}
        </footer>
      </section>

      {/* Create / edit modal */}
      {modalMode === "form" && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Cadastros</span>
                <h2>{selected ? "Editar centro de custo" : "Novo centro de custo"}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <CostCenterForm
              initial={selected}
              options={options}
              onSave={selected ? handleUpdate : handleCreate}
              onCancel={closeModal}
            />
          </section>
        </div>
      )}

      {/* Detail modal */}
      {modalMode === "detail" && selected && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>#{selected.id}</span>
                <h2>{selected.name}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>

            <form onSubmit={(e) => e.preventDefault()}>
              <div className="supplier-badges">
                <span className={`status ${selected.active ? "status-done" : "status-neutral"}`}>{selected.active ? "Ativo" : "Inativo"}</span>
              </div>

              <div className="supplier-actions">
                <button type="button" className="secondary-button" onClick={() => setModalMode("form")}>
                  <Edit2 size={14} /> Editar
                </button>
                <button type="button" className="secondary-button" style={{ color: "var(--red)" }} onClick={() => handleDelete(selected.id)}>
                  <Trash2 size={14} /> Excluir
                </button>
              </div>

              <div className="form-grid">
                {selected.code && <label>Código<span>{selected.code}</span></label>}
                {selected.parent_name && <label>Centro pai<span>{selected.parent_name}</span></label>}
              </div>
            </form>
          </section>
        </div>
      )}

      <style>{`
        .supplier-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .supplier-actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
        .checkbox-row { display: flex !important; flex-direction: row !important; align-items: center; gap: var(--sp-2); }
        .checkbox-row input { width: auto !important; min-height: 0 !important; }
        .record-modal label > span { font-size: var(--font-base); font-weight: 400; color: var(--ink); }
      `}</style>
    </>
  );
}
