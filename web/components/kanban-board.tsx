"use client";

import {
  cloneWorkOrderAction,
  createWorkOrderAction,
  deleteWorkOrderAction,
  fetchRegistryOptions,
  fetchWorkOrderCategories,
  searchUsers,
  transitionWorkOrderAction,
  updateWorkOrderAction,
  type RegistryOption,
  type UserOption,
} from "@/app/actions";
import type { TenantUser } from "@/lib/api";
import type { ModuleDefinition, ModuleRecord } from "@/lib/module-definitions";
import {
  Copy, Download, FileText, GripVertical, LayoutGrid, List, Pencil, Plus, Search, Trash2, X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";

const KANBAN_COLUMNS = [
  { key: "aberta", label: "Aberta", color: "#3b82f6" },
  { key: "em_andamento", label: "Em andamento", color: "#f59e0b" },
  { key: "aguardando_material", label: "Aguardando", color: "#8b5cf6" },
  { key: "concluida", label: "Concluída", color: "#10b981" },
  { key: "validada", label: "Validada", color: "#6b7280" },
];

const PRIORITIES = [
  { value: "urgente", label: "Urgente" },
  { value: "alta", label: "Alta" },
  { value: "media", label: "Média" },
  { value: "baixa", label: "Baixa" },
];

function priorityBadge(priority: string | undefined) {
  if (!priority) return null;
  const colors: Record<string, string> = {
    urgente: "#ef4444",
    alta: "#f97316",
    media: "#eab308",
    baixa: "#22c55e",
  };
  return (
    <span
      className="kanban-priority"
      style={{ "--priority-color": colors[priority] ?? "#94a3b8" } as React.CSSProperties}
    >
      {priority}
    </span>
  );
}

function statusBadge(status: string) {
  const col = KANBAN_COLUMNS.find((c) => c.key === status);
  return (
    <span className="status" style={{ background: `${col?.color ?? "#94a3b8"}22`, color: col?.color ?? "#64748b" }}>
      {col?.label ?? status}
    </span>
  );
}

function UserMultiSelect({ name, defaultValues }: { name: string; defaultValues?: { id: number; name: string }[] }) {
  const [selected, setSelected] = useState<{ id: number; name: string }[]>(defaultValues ?? []);
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<UserOption[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listId = `${name}-multi-listbox`;

  function handleChange(v: string) {
    setQuery(v);
    setActiveIndex(-1);
    clearTimeout(timer.current);
    if (v.trim().length < 2) { setOptions([]); setOpen(false); return; }
    timer.current = setTimeout(() => {
      searchUsers(v).then((r) => { const filtered = r.filter((u) => !selected.some((s) => s.id === u.id)); setOptions(filtered); setOpen(filtered.length > 0); setActiveIndex(-1); });
    }, 250);
  }

  function add(u: UserOption) {
    setSelected((prev) => [...prev, { id: u.id, name: u.name }]);
    setQuery("");
    setOptions([]);
    setOpen(false);
    setActiveIndex(-1);
  }

  function remove(id: number) {
    setSelected((prev) => prev.filter((u) => u.id !== id));
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || !options.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIndex((i) => Math.min(i + 1, options.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIndex((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && activeIndex >= 0) { e.preventDefault(); add(options[activeIndex]); }
    else if (e.key === "Escape") { setOpen(false); }
  }

  return (
    <div className="autocomplete-wrap" role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-owns={listId}>
      {selected.length > 0 && (
        <div className="notify-chips" role="list">
          {selected.map((u) => (
            <span key={u.id} className="notify-chip" role="listitem">
              {u.name}
              <button type="button" onClick={() => remove(u.id)} aria-label={`Remover ${u.name}`}>×</button>
            </span>
          ))}
        </div>
      )}
      <input
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => { if (options.length) setOpen(true); }}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onKeyDown={handleKeyDown}
        placeholder="Buscar participante..."
        autoComplete="off"
        aria-autocomplete="list"
        aria-controls={listId}
        aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
      />
      {open && (
        <ul id={listId} className="autocomplete-list" role="listbox">
          {options.map((u, i) => (
            <li key={u.id} id={`${listId}-${i}`} role="option" aria-selected={i === activeIndex} className={i === activeIndex ? "active" : undefined} onMouseDown={() => add(u)}>
              <strong>{u.name}</strong><small>{u.email}</small>
            </li>
          ))}
        </ul>
      )}
      <input type="hidden" name={name} value={JSON.stringify(selected.map((u) => u.id))} />
    </div>
  );
}

export function KanbanBoard({
  definition,
  user,
}: {
  definition: ModuleDefinition;
  user: TenantUser;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"kanban" | "list">("kanban");
  const [showCreate, setShowCreate] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ModuleRecord | null>(null);
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const dragSourceCol = useRef<string | null>(null);

  const records = definition.records;
  const canCreate = user.permissions.includes("*") || user.permissions.includes("work_order.create");
  const canEdit = user.permissions.includes("*") || user.permissions.includes("work_order.edit");
  const canDelete = user.permissions.includes("*") || user.permissions.includes("work_order.delete");

  const filtered = query
    ? records.filter(
        (r) =>
          r.title.toLowerCase().includes(query.toLowerCase()) ||
          r.owner.toLowerCase().includes(query.toLowerCase()),
      )
    : records;

  const grouped = new Map<string, ModuleRecord[]>();
  for (const col of KANBAN_COLUMNS) {
    grouped.set(col.key, []);
  }
  for (const record of filtered) {
    const list = grouped.get(record.status);
    if (list) list.push(record);
  }

  const handleDragStart = useCallback((e: React.DragEvent, recordId: number, sourceStatus: string) => {
    setDraggedId(recordId);
    dragSourceCol.current = sourceStatus;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(recordId));
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, colKey: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverColumn(colKey);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverColumn(null);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, targetStatus: string) => {
    e.preventDefault();
    setDragOverColumn(null);
    const recordId = parseInt(e.dataTransfer.getData("text/plain"), 10);
    setDraggedId(null);

    if (!recordId || dragSourceCol.current === targetStatus) return;

    setError(null);
    startTransition(async () => {
      const result = await transitionWorkOrderAction(recordId, targetStatus);
      if (!result.ok) {
        setError(result.error ?? "Transição não permitida.");
        setTimeout(() => setError(null), 4000);
      }
      router.refresh();
    });
  }, [router]);

  const handleDelete = useCallback((id: number, title: string) => {
    if (!confirm(`Excluir a OS "${title}"?`)) return;
    setError(null);
    startTransition(async () => {
      const result = await deleteWorkOrderAction(id);
      if (!result.ok) {
        setError(result.error ?? "Erro ao excluir.");
      }
      router.refresh();
    });
  }, [router]);

  return (
    <>
      <header className="module-heading">
        <div>
          <h1>{definition.title}</h1>
          <p>{definition.description}</p>
        </div>
        <div style={{ display: "flex", gap: "var(--sp-2)" }}>
          <a className="secondary-button" href="/api/work-orders/export">
            <Download size={16} /> Exportar XLSX
          </a>
          {canCreate && (
            <button className="btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={18} />
              Nova OS
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="kanban-error">
          {error}
          <button onClick={() => setError(null)} aria-label="Fechar"><X size={14} /></button>
        </div>
      )}

      <div className="kanban-toolbar">
        <label className="kanban-search">
          <Search size={18} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar ordens de serviço…"
          />
        </label>
        <div className="segmented">
          <button className={view === "kanban" ? "selected" : ""} onClick={() => setView("kanban")} aria-label="Visão Kanban">
            <LayoutGrid size={16} /> Kanban
          </button>
          <button className={view === "list" ? "selected" : ""} onClick={() => setView("list")} aria-label="Visão em lista">
            <List size={16} /> Lista
          </button>
        </div>
        <span className="kanban-count">{filtered.length} ordem(ns)</span>
      </div>

      {view === "kanban" ? (
        <div className="kanban-container">
          {KANBAN_COLUMNS.map((col) => {
            const items = grouped.get(col.key) ?? [];
            const isOver = dragOverColumn === col.key && dragSourceCol.current !== col.key;
            return (
              <div
                key={col.key}
                className={`kanban-column${isOver ? " kanban-column-dragover" : ""}`}
                onDragOver={(e) => handleDragOver(e, col.key)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, col.key)}
              >
                <div className="kanban-column-header" style={{ "--col-color": col.color } as React.CSSProperties}>
                  <span className="kanban-column-title">{col.label}</span>
                  <span className="kanban-column-count">{items.length}</span>
                </div>
                <div className="kanban-column-body">
                  {items.map((record) => (
                    <article
                      key={record.id}
                      className={`kanban-card${draggedId === record.id ? " kanban-card-dragging" : ""}`}
                      draggable={canEdit}
                      onDragStart={(e) => handleDragStart(e, record.id, col.key)}
                      onDragEnd={() => { setDraggedId(null); setDragOverColumn(null); }}
                      onClick={() => canEdit ? setEditingRecord(record) : undefined}
                    >
                      <div className="kanban-card-header">
                        <span className="kanban-card-id">
                          {canEdit && <GripVertical size={12} className="kanban-grip" />}
                          #{record.id}
                        </span>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {priorityBadge(record.priority)}
                          {canDelete && (
                            <button
                              className="kanban-card-delete"
                              onClick={(e) => { e.stopPropagation(); handleDelete(record.id, record.title); }}
                              aria-label="Excluir"
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      </div>
                      <h3 className="kanban-card-title">{record.title}</h3>
                      {record.category && record.category !== "Geral" && (
                        <span className="kanban-card-category">{record.category}</span>
                      )}
                      <footer className="kanban-card-footer">
                        <span>{record.owner}</span>
                        <span>{record.updatedAt}</span>
                      </footer>
                      {record.slaDeadline && (
                        <div className="kanban-card-sla">
                          SLA: {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(record.slaDeadline))}
                        </div>
                      )}
                    </article>
                  ))}
                  {items.length === 0 && (
                    <div className="kanban-empty">Nenhuma OS</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Título</th>
                <th>Categoria</th>
                <th>Responsável</th>
                <th>Prioridade</th>
                <th>Status</th>
                <th>Prazo</th>
                <th>Atualização</th>
                {(canEdit || canDelete) && <th>Ações</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((record) => (
                <tr key={record.id} onClick={() => canEdit ? setEditingRecord(record) : undefined}>
                  <td className="protocol">#{record.id}</td>
                  <td><strong>{record.title}</strong></td>
                  <td>{record.category ?? "—"}</td>
                  <td>{record.owner}</td>
                  <td>{priorityBadge(record.priority) ?? "—"}</td>
                  <td>{statusBadge(record.status)}</td>
                  <td className="muted">
                    {record.deadline
                      ? new Intl.DateTimeFormat("pt-BR").format(new Date(record.deadline))
                      : record.slaDeadline
                        ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(record.slaDeadline))
                        : "—"}
                  </td>
                  <td className="muted">{record.updatedAt}</td>
                  {(canEdit || canDelete) && (
                    <td>
                      <div className="row-actions">
                        {canEdit && (
                          <button onClick={(e) => { e.stopPropagation(); setEditingRecord(record); }} aria-label="Editar">
                            <Pencil size={16} />
                          </button>
                        )}
                        {canDelete && (
                          <button onClick={(e) => { e.stopPropagation(); handleDelete(record.id, record.title); }} aria-label="Excluir">
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={9} className="module-state">Nenhuma OS encontrada.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {isPending && <div className="kanban-loading">Salvando…</div>}

      {showCreate && (
        <CreateWorkOrderModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); router.refresh(); }}
        />
      )}

      {editingRecord && (
        <EditWorkOrderModal
          record={editingRecord}
          onClose={() => setEditingRecord(null)}
          onSaved={() => { setEditingRecord(null); router.refresh(); }}
        />
      )}
    </>
  );
}

function useCategoryOptions() {
  const [categories, setCategories] = useState<string[]>([]);
  useEffect(() => {
    fetchWorkOrderCategories().then(setCategories);
  }, []);
  return categories;
}

function useSectorOptions() {
  const [sectors, setSectors] = useState<RegistryOption[]>([]);
  useEffect(() => {
    fetchRegistryOptions("Setor").then(setSectors);
  }, []);
  return sectors;
}

function CategorySelect({ value, onChange, categories }: {
  value: string;
  onChange: (v: string) => void;
  categories: string[];
}) {
  const [custom, setCustom] = useState(false);

  if (custom) {
    return (
      <div style={{ display: "flex", gap: "var(--sp-2)" }}>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Nova categoria..."
          autoFocus
          style={{ flex: 1 }}
        />
        <button type="button" onClick={() => { setCustom(false); onChange(""); }}
          style={{ fontSize: "var(--font-sm)", color: "var(--blue)", background: "none", border: "none", cursor: "pointer", whiteSpace: "nowrap" }}>
          Voltar
        </button>
      </div>
    );
  }

  return (
    <select value={value} onChange={(e) => {
      if (e.target.value === "__new__") { setCustom(true); onChange(""); }
      else onChange(e.target.value);
    }}>
      <option value="">Sem categoria</option>
      {categories.map((c) => <option key={c} value={c}>{c}</option>)}
      <option value="__new__">+ Nova categoria</option>
    </select>
  );
}

function CreateWorkOrderModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [slaHours, setSlaHours] = useState("");
  const [sectorId, setSectorId] = useState("");
  const [unit, setUnit] = useState("");
  const [deadline, setDeadline] = useState("");
  const [comments, setComments] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const categories = useCategoryOptions();
  const sectors = useSectorOptions();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!title.trim()) return;

    const formData = new FormData(e.currentTarget);
    let participantIds: number[] = [];
    try { participantIds = JSON.parse(String(formData.get("participant_ids") ?? "[]")); } catch { /* empty */ }

    startTransition(async () => {
      const result = await createWorkOrderAction({
        title: title.trim(),
        description: description.trim() || undefined,
        priority: priority || undefined,
        category: category.trim() || undefined,
        sla_hours: slaHours ? parseInt(slaHours, 10) : undefined,
        sector_id: sectorId ? Number(sectorId) : undefined,
        unit: unit.trim() || undefined,
        deadline: deadline || undefined,
        comments: comments.trim() || undefined,
        participant_ids: participantIds.length ? participantIds : undefined,
      });
      if (!result.ok) {
        setError(result.error ?? "Erro ao criar OS.");
        return;
      }
      onCreated();
    });
  };

  return (
    <div className="modal-layer" role="presentation" onClick={onClose}>
      <section className="record-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <header>
          <div>
            <span>Ordens de Serviço</span>
            <h2>Nova Ordem de Serviço</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fechar"><X size={20} /></button>
        </header>
        <form onSubmit={handleSubmit}>
          {error && <div className="kanban-form-error">{error}</div>}
          <label>
            Título *
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Descreva a ordem de serviço"
              required
              autoFocus
            />
          </label>
          <label>
            Descrição
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detalhes adicionais (opcional)"
              rows={3}
            />
          </label>
          <div className="form-grid">
            <label>
              Prioridade
              <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option value="">Sem prioridade</option>
                {PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </label>
            <label>
              Categoria
              <CategorySelect value={category} onChange={setCategory} categories={categories} />
            </label>
            <label>
              SLA (horas)
              <input
                type="number"
                value={slaHours}
                onChange={(e) => setSlaHours(e.target.value)}
                placeholder="Ex: 24"
                min={1}
              />
            </label>
          </div>
          <div className="form-grid">
            <label>
              Setor
              <select value={sectorId} onChange={(e) => setSectorId(e.target.value)}>
                <option value="">Sem setor</option>
                {sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>
              Unidade/Apartamento
              <input type="text" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Ex: 302" />
            </label>
            <label>
              Prazo
              <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </label>
          </div>
          <label>
            Participantes
            <UserMultiSelect name="participant_ids" />
          </label>
          <label>
            Comentários
            <textarea
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Observações adicionais (opcional)"
              rows={3}
            />
          </label>
          <footer>
            <button type="button" onClick={onClose}>Cancelar</button>
            <button type="submit" disabled={isPending || !title.trim()}>
              {isPending ? "Criando…" : "Criar OS"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function EditWorkOrderModal({
  record,
  onClose,
  onSaved,
}: {
  record: ModuleRecord;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(record.title);
  const [description, setDescription] = useState(record.description ?? "");
  const [priority, setPriority] = useState(record.priority ?? "");
  const [category, setCategory] = useState(record.category === "Geral" ? "" : record.category);
  const [sectorId, setSectorId] = useState(record.sectorId ? String(record.sectorId) : "");
  const [unit, setUnit] = useState(record.unit ?? "");
  const [deadline, setDeadline] = useState(record.deadline ?? "");
  const [comments, setComments] = useState(record.comments ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [cloning, startCloneTransition] = useTransition();
  const categories = useCategoryOptions();
  const sectors = useSectorOptions();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!title.trim()) return;

    const formData = new FormData(e.currentTarget);
    let participantIds: number[] = [];
    try { participantIds = JSON.parse(String(formData.get("participant_ids") ?? "[]")); } catch { /* empty */ }

    startTransition(async () => {
      const result = await updateWorkOrderAction(record.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        priority: priority || undefined,
        category: category.trim() || undefined,
        sector_id: sectorId ? Number(sectorId) : undefined,
        unit: unit.trim() || undefined,
        deadline: deadline || undefined,
        comments: comments.trim() || undefined,
        participant_ids: participantIds.length ? participantIds : undefined,
      });
      if (!result.ok) {
        setError(result.error ?? "Erro ao atualizar OS.");
        return;
      }
      onSaved();
    });
  };

  function handleClone() {
    setError(null);
    startCloneTransition(async () => {
      const result = await cloneWorkOrderAction(record.id);
      if (!result.ok) {
        setError(result.error ?? "Erro ao duplicar OS.");
        return;
      }
      onSaved();
    });
  }

  return (
    <div className="modal-layer" role="presentation" onClick={onClose}>
      <section className="record-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <header>
          <div>
            <span>Ordens de Serviço</span>
            <h2>Editar OS #{record.id}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fechar"><X size={20} /></button>
        </header>
        <form onSubmit={handleSubmit}>
          {error && <div className="kanban-form-error">{error}</div>}
          <label>
            Título *
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              autoFocus
            />
          </label>
          <label>
            Descrição
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </label>
          <div className="form-grid">
            <label>
              Prioridade
              <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option value="">Sem prioridade</option>
                {PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </label>
            <label>
              Categoria
              <CategorySelect value={category} onChange={setCategory} categories={categories} />
            </label>
          </div>
          <div className="form-grid">
            <label>
              Setor
              <select value={sectorId} onChange={(e) => setSectorId(e.target.value)}>
                <option value="">Sem setor</option>
                {sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>
              Unidade/Apartamento
              <input type="text" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Ex: 302" />
            </label>
            <label>
              Prazo
              <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </label>
          </div>
          <label>
            Participantes
            <UserMultiSelect name="participant_ids" defaultValues={record.participants} />
          </label>
          <label>
            Comentários
            <textarea
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              rows={3}
            />
          </label>
          <div style={{ display: "flex", gap: "var(--sp-2)", flexWrap: "wrap" }}>
            <a className="secondary-button" href={`/api/work-orders/${record.id}/pdf`} target="_blank" rel="noopener noreferrer">
              <FileText size={16} /> Exportar PDF
            </a>
            <button type="button" className="secondary-button" onClick={handleClone} disabled={cloning}>
              <Copy size={16} /> {cloning ? "Duplicando…" : "Clonar"}
            </button>
          </div>
          <footer>
            <button type="button" onClick={onClose}>Cancelar</button>
            <button type="submit" disabled={isPending || !title.trim()}>
              {isPending ? "Salvando…" : "Salvar"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
