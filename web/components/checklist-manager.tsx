"use client";

import { useEffect, useState } from "react";
import { CheckSquare, GripVertical, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import type { ChecklistTemplateDetail } from "@/app/actions";
import {
  createChecklistTemplateAction,
  updateChecklistTemplateAction,
  deleteChecklistTemplateAction,
  fetchChecklistTemplateAction,
} from "@/app/actions";

interface TemplateRow {
  id: number;
  name: string;
  description: string | null;
  recurrence: string;
  category: string | null;
  assigned_user_name: string | null;
  active: boolean;
  item_count: number;
}

interface ChecklistItem {
  label: string;
  sort_order: number;
}

const RECURRENCE_LABELS: Record<string, string> = {
  daily: "Diário", weekly: "Semanal", biweekly: "Quinzenal", monthly: "Mensal",
};

export function ChecklistManager({ templates }: { templates: TemplateRow[] }) {
  const [records, setRecords] = useState(templates);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<"new" | ChecklistTemplateDetail | null>(null);
  const [toast, setToast] = useState("");

  useEffect(() => { setRecords(templates); }, [templates]);

  const filtered = query
    ? records.filter((r) => r.name.toLowerCase().includes(query.toLowerCase()))
    : records;

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  async function handleEdit(id: number) {
    const detail = await fetchChecklistTemplateAction(id);
    if (detail) setEditing(detail);
  }

  async function handleDelete(r: TemplateRow) {
    if (!confirm(`Excluir "${r.name}"? Esta ação não pode ser desfeita.`)) return;
    const result = await deleteChecklistTemplateAction(r.id);
    if (result.ok) {
      setRecords((prev) => prev.filter((t) => t.id !== r.id));
      showToast("Checklist excluído.");
    }
  }

  return (
    <>
      <header className="module-heading">
        <div>
          <h1>Checklists</h1>
          <p>Modelos de checklist para inspeções e verificações recorrentes.</p>
        </div>
        <button className="primary-button" onClick={() => setEditing("new")}>
          <Plus size={18} /> Novo checklist
        </button>
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <label><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar checklists..." /></label>
        </div>

        {filtered.length === 0 ? (
          <div className="module-state">
            <CheckSquare size={30} />
            <strong>Nenhum checklist</strong>
            <span>Crie um modelo de checklist para começar.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Checklist</th>
                  <th>Itens</th>
                  <th>Recorrência</th>
                  <th>Responsável</th>
                  <th>Status</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} onClick={() => handleEdit(r.id)} style={{ cursor: "pointer" }}>
                    <td>
                      <strong>{r.name}</strong>
                      {r.description && <small style={{ display: "block", color: "var(--muted)", fontSize: "var(--font-xs)" }}>{r.description}</small>}
                    </td>
                    <td><span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><CheckSquare size={14} /> {r.item_count}</span></td>
                    <td>{RECURRENCE_LABELS[r.recurrence] ?? r.recurrence}</td>
                    <td>{r.assigned_user_name ?? "Não atribuído"}</td>
                    <td><span className={r.active ? "status status-done" : "status status-waiting"}>{r.active ? "Ativo" : "Inativo"}</span></td>
                    <td>
                      <div className="row-actions">
                        <button onClick={(e) => { e.stopPropagation(); handleEdit(r.id); }} aria-label="Editar"><Pencil size={16} /></button>
                        <button onClick={(e) => { e.stopPropagation(); handleDelete(r); }} aria-label="Excluir"><Trash2 size={16} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{filtered.length} checklist(s)</span>
        </footer>
      </section>

      {editing && (
        <ChecklistFormModal
          template={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(msg) => { setEditing(null); showToast(msg); window.location.reload(); }}
        />
      )}

      {toast && <div className="module-toast" role="status">{toast}</div>}
    </>
  );
}

function ChecklistFormModal({
  template,
  onClose,
  onSaved,
}: {
  template: ChecklistTemplateDetail | null;
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const isNew = !template;
  const [name, setName] = useState(template?.name ?? "");
  const [description, setDescription] = useState(template?.description ?? "");
  const [recurrence, setRecurrence] = useState(template?.recurrence ?? "daily");
  const [active, setActive] = useState(template?.active ?? true);
  const [items, setItems] = useState<ChecklistItem[]>(
    template?.items?.map((i) => ({ label: i.label, sort_order: i.sort_order })) ?? []
  );
  const [newItemLabel, setNewItemLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addItem() {
    const label = newItemLabel.trim();
    if (!label) return;
    setItems((prev) => [...prev, { label, sort_order: prev.length }]);
    setNewItemLabel("");
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index).map((item, i) => ({ ...item, sort_order: i })));
  }

  function moveItem(from: number, to: number) {
    if (to < 0 || to >= items.length) return;
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setItems(next.map((item, i) => ({ ...item, sort_order: i })));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);

    const body = {
      name: name.trim(),
      description: description.trim() || undefined,
      recurrence,
      active,
      items: items.map((item, i) => ({ label: item.label, sort_order: i })),
    };

    const result = isNew
      ? await createChecklistTemplateAction(body)
      : await updateChecklistTemplateAction(template.id, body);

    setSaving(false);
    if (result.ok) {
      onSaved(isNew ? "Checklist criado com sucesso." : "Checklist atualizado.");
    } else {
      setError(result.error ?? "Erro ao salvar.");
    }
  }

  return (
    <div className="modal-layer" role="presentation">
      <section className="record-modal" role="dialog" aria-modal="true" style={{ maxWidth: 600 }}>
        <header>
          <div>
            <span>{isNew ? "Novo checklist" : `#${template.id}`}</span>
            <h2>{isNew ? "Criar checklist" : "Editar checklist"}</h2>
          </div>
          <button className="icon-button" onClick={onClose}><X /></button>
        </header>

        <form onSubmit={handleSubmit}>
          {error && <div className="kanban-form-error">{error}</div>}

          <label>Nome *<input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Ex: Checklist de abertura manhã" /></label>
          <label>Descrição<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="Instruções ou observações (opcional)" /></label>

          <div className="form-grid">
            <label>Recorrência
              <select value={recurrence} onChange={(e) => setRecurrence(e.target.value)}>
                <option value="daily">Diário</option>
                <option value="weekly">Semanal</option>
                <option value="biweekly">Quinzenal</option>
                <option value="monthly">Mensal</option>
              </select>
            </label>
            <label>Status
              <select value={active ? "true" : "false"} onChange={(e) => setActive(e.target.value === "true")}>
                <option value="true">Ativo</option>
                <option value="false">Inativo</option>
              </select>
            </label>
          </div>

          <fieldset className="form-section">
            <legend><CheckSquare size={14} /> Itens do checklist ({items.length})</legend>

            {items.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)", marginBottom: "var(--sp-3)" }}>
                {items.map((item, i) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: "var(--sp-2)",
                    padding: "var(--sp-2) var(--sp-3)",
                    background: "var(--field-bg)", borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--field-border)",
                  }}>
                    <button type="button" onClick={() => moveItem(i, i - 1)} disabled={i === 0}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 2 }}>
                      <GripVertical size={14} />
                    </button>
                    <CheckSquare size={16} style={{ color: "var(--blue)", flexShrink: 0 }} />
                    <span style={{ flex: 1, fontSize: "var(--font-base)" }}>{item.label}</span>
                    <button type="button" onClick={() => removeItem(i)}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "var(--red)", padding: 4 }}>
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: "flex", gap: "var(--sp-2)" }}>
              <input
                value={newItemLabel}
                onChange={(e) => setNewItemLabel(e.target.value)}
                placeholder="Adicionar item..."
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addItem(); } }}
                style={{ flex: 1 }}
              />
              <button type="button" onClick={addItem} disabled={!newItemLabel.trim()}
                style={{ display: "inline-flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
                <Plus size={14} /> Adicionar
              </button>
            </div>
          </fieldset>

          <footer>
            <button type="button" onClick={onClose}>Cancelar</button>
            <button type="submit" disabled={saving || !name.trim()}>
              {saving ? "Salvando..." : isNew ? "Criar checklist" : "Salvar"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
