"use client";

import { useEffect, useRef, useState } from "react";
import { FileDown, Pencil, Plus, Trash2, X } from "lucide-react";
import {
  createDiscrepancyReportAction,
  deleteDiscrepancyReportAction,
  fetchDiscrepancyReport,
  fetchDiscrepancyReports,
  fetchLocationsAction,
  searchUsers,
  updateDiscrepancyReportAction,
  type DiscrepancyEntryInput,
  type DiscrepancyReportDetail,
  type DiscrepancyReportSummary,
  type DiscrepancyStatus,
  type UserOption,
} from "@/app/actions";

const STATUS_LABELS: Record<DiscrepancyStatus, string> = {
  draft: "Rascunho",
  submitted: "Enviada",
  closed: "Fechada",
};

const PAGE_SIZE = 20;

type EntryRow = DiscrepancyEntryInput & { key: string };

function emptyEntry(): EntryRow {
  return { key: crypto.randomUUID(), location_id: 0, first_code: "", second_code: "", notes: "" };
}

function fmtDate(value: string): string {
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

function statusClass(status: DiscrepancyStatus): string {
  if (status === "closed") return "status status-done";
  if (status === "draft") return "status status-waiting";
  return "status status-progress";
}

function UserPicker({
  value,
  onChange,
  placeholder,
  disabled,
}: {
  value: { id: number; name: string } | null;
  onChange: (user: { id: number; name: string } | null) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState(value?.name ?? "");
  const [options, setOptions] = useState<UserOption[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listId = useRef(`picker-${crypto.randomUUID()}`).current;

  useEffect(() => {
    setQuery(value?.name ?? "");
  }, [value?.id, value?.name]);

  function handleChange(v: string) {
    setQuery(v);
    onChange(null);
    setActiveIndex(-1);
    clearTimeout(timer.current);
    if (v.trim().length < 2) {
      setOptions([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(() => {
      searchUsers(v).then((r) => {
        setOptions(r);
        setOpen(r.length > 0);
        setActiveIndex(-1);
      });
    }, 250);
  }

  function select(u: UserOption) {
    setQuery(u.name);
    onChange({ id: u.id, name: u.name });
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || !options.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      select(options[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="autocomplete-wrap" role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-owns={listId}>
      <input
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => { if (options.length) setOpen(true); }}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        disabled={disabled}
        aria-autocomplete="list"
        aria-controls={listId}
        aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
      />
      {open && (
        <ul id={listId} className="autocomplete-list" role="listbox">
          {options.map((u, i) => (
            <li
              key={u.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              className={i === activeIndex ? "active" : undefined}
              onMouseDown={() => select(u)}
            >
              <strong>{u.name}</strong>
              <small>{u.email}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DiscrepancyReportManager() {
  const [reports, setReports] = useState<DiscrepancyReportSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [toast, setToast] = useState("");

  const [locations, setLocations] = useState<{ id: number; name: string }[]>([]);
  const [editing, setEditing] = useState<DiscrepancyReportDetail | "new" | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [reportDate, setReportDate] = useState("");
  const [status, setStatus] = useState<DiscrepancyStatus>("draft");
  const [observations, setObservations] = useState("");
  const [preparedBy, setPreparedBy] = useState<{ id: number; name: string } | null>(null);
  const [checkedBy, setCheckedBy] = useState<{ id: number; name: string } | null>(null);
  const [receivedBy, setReceivedBy] = useState<{ id: number; name: string } | null>(null);
  const [entries, setEntries] = useState<EntryRow[]>([emptyEntry()]);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    fetchDiscrepancyReports({
      page,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      status: statusFilter || undefined,
    })
      .then((data) => {
        setReports(data.items);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, dateFrom, dateTo, statusFilter]);

  useEffect(() => {
    fetchLocationsAction().then(setLocations);
  }, []);

  function resetForm() {
    setReportDate("");
    setStatus("draft");
    setObservations("");
    setPreparedBy(null);
    setCheckedBy(null);
    setReceivedBy(null);
    setEntries([emptyEntry()]);
    setError("");
  }

  function openCreate() {
    resetForm();
    setEditing("new");
  }

  async function openEdit(summary: DiscrepancyReportSummary) {
    const detail = await fetchDiscrepancyReport(summary.id);
    if (!detail) {
      showToast("Não foi possível carregar a conferência.");
      return;
    }
    setReportDate(detail.report_date);
    setStatus(detail.status);
    setObservations(detail.observations ?? "");
    setPreparedBy(
      detail.prepared_by_user_id && detail.prepared_by_name
        ? { id: detail.prepared_by_user_id, name: detail.prepared_by_name }
        : null,
    );
    setCheckedBy(
      detail.checked_by_user_id && detail.checked_by_name
        ? { id: detail.checked_by_user_id, name: detail.checked_by_name }
        : null,
    );
    setReceivedBy(
      detail.received_by_user_id && detail.received_by_name
        ? { id: detail.received_by_user_id, name: detail.received_by_name }
        : null,
    );
    setEntries(
      detail.entries.length
        ? detail.entries.map((e) => ({
            key: crypto.randomUUID(),
            location_id: e.location_id,
            first_code: e.first_code ?? "",
            second_code: e.second_code ?? "",
            notes: e.notes ?? "",
          }))
        : [emptyEntry()],
    );
    setError("");
    setEditing(detail);
  }

  function closeModal() {
    setEditing(null);
  }

  function addEntryRow() {
    setEntries((rows) => [...rows, emptyEntry()]);
  }

  function removeEntryRow(key: string) {
    setEntries((rows) => (rows.length > 1 ? rows.filter((r) => r.key !== key) : rows));
  }

  function updateEntry(key: string, patch: Partial<EntryRow>) {
    setEntries((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reportDate) return;
    const validEntries = entries.filter((r) => r.location_id > 0);
    if (validEntries.length === 0) {
      setError("Adicione ao menos um local à conferência.");
      return;
    }
    const locationIds = validEntries.map((r) => r.location_id);
    if (new Set(locationIds).size !== locationIds.length) {
      setError("Cada local só pode aparecer uma vez na conferência.");
      return;
    }

    setSaving(true);
    setError("");
    const payload = {
      report_date: reportDate,
      status,
      observations: observations.trim() || null,
      prepared_by_user_id: preparedBy?.id ?? null,
      checked_by_user_id: checkedBy?.id ?? null,
      received_by_user_id: receivedBy?.id ?? null,
      entries: validEntries.map(({ key: _key, ...rest }) => rest),
    };
    const result =
      editing === "new"
        ? await createDiscrepancyReportAction(payload)
        : await updateDiscrepancyReportAction((editing as DiscrepancyReportDetail).id, payload);
    setSaving(false);
    if (result.ok) {
      showToast(editing === "new" ? "Conferência criada." : "Conferência atualizada.");
      closeModal();
      reload();
    } else {
      setError(result.error ?? "Erro ao salvar a conferência.");
    }
  }

  async function handleDelete(summary: DiscrepancyReportSummary) {
    if (!confirm(`Excluir a conferência de ${fmtDate(summary.report_date)}?`)) return;
    const result = await deleteDiscrepancyReportAction(summary.id);
    if (result.ok) {
      showToast("Conferência excluída.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao excluir.");
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const isClosed = editing !== "new" && editing !== null && editing.status === "closed";

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Operação</p>
          <h1>Conferência de Discrepâncias</h1>
          <p>Compare as duas verificações por local e acompanhe divergências, com exportação em PDF.</p>
        </div>
        <button className="primary-button" onClick={openCreate}>
          <Plus size={18} /> Nova conferência
        </button>
      </header>

      <section className="module-panel">
        <form
          className="report-filter-bar"
          onSubmit={(e) => e.preventDefault()}
          style={{ margin: 0, border: 0, borderRadius: 0, boxShadow: "none", padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}
        >
          <div className="report-filter-field">
            <label htmlFor="df_from">De</label>
            <input id="df_from" type="date" value={dateFrom} onChange={(e) => { setPage(1); setDateFrom(e.target.value); }} />
          </div>
          <div className="report-filter-field">
            <label htmlFor="df_to">Até</label>
            <input id="df_to" type="date" value={dateTo} onChange={(e) => { setPage(1); setDateTo(e.target.value); }} />
          </div>
          <div className="report-filter-field">
            <label htmlFor="df_status">Status</label>
            <select id="df_status" value={statusFilter} onChange={(e) => { setPage(1); setStatusFilter(e.target.value); }}>
              <option value="">Todos</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        </form>

        {loading ? (
          <div className="module-state">Carregando conferências...</div>
        ) : reports.length === 0 ? (
          <div className="module-state">
            <strong>Nenhuma conferência encontrada</strong>
            <span>
              {locations.length === 0
                ? "Cadastre locais em Cadastros → Locais antes de criar a primeira conferência."
                : "Ajuste os filtros ou crie uma nova conferência."}
            </span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Preparado por</th>
                  <th className="col-num">Locais</th>
                  <th className="col-num">Divergências</th>
                  <th>Status</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td>{fmtDate(r.report_date)}</td>
                    <td>{r.prepared_by_name ?? "—"}</td>
                    <td className="col-num">{r.entry_count}</td>
                    <td className="col-num">
                      {r.discrepancy_count > 0 ? (
                        <strong style={{ color: "var(--red)" }}>{r.discrepancy_count}</strong>
                      ) : (
                        r.discrepancy_count
                      )}
                    </td>
                    <td>
                      <span className={statusClass(r.status)}>{STATUS_LABELS[r.status]}</span>
                    </td>
                    <td>
                      <div className="row-actions">
                        <a
                          href={`/api/discrepancy-reports/${r.id}/pdf`}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="Exportar PDF"
                        >
                          <FileDown size={16} />
                        </a>
                        <button onClick={() => openEdit(r)} aria-label="Editar">
                          <Pencil size={16} />
                        </button>
                        <button onClick={() => handleDelete(r)} aria-label="Excluir">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="module-pagination">
          <span>{total} conferência(s)</span>
          {totalPages > 1 && (
            <div className="row-actions">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</button>
              <span>Página {page} de {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Próxima</button>
            </div>
          )}
        </footer>
      </section>

      {editing && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Conferência de discrepâncias</span>
                <h2>{editing === "new" ? "Nova conferência" : `#${editing.id}`}</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <form onSubmit={handleSubmit}>
              {error && <div className="kanban-form-error">{error}</div>}
              {isClosed && (
                <p className="muted" style={{ margin: 0 }}>
                  Esta conferência está fechada e não pode ser editada. Reabra o status para alterar.
                </p>
              )}

              <label>Data *
                <input id="conf_report_date" type="date" value={reportDate} onChange={(e) => setReportDate(e.target.value)} required autoFocus disabled={isClosed} />
              </label>

              <label>Status
                <select id="conf_status" value={status} onChange={(e) => setStatus(e.target.value as DiscrepancyStatus)} disabled={isClosed}>
                  {Object.entries(STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>

              <label>Preparado por
                <UserPicker value={preparedBy} onChange={setPreparedBy} placeholder="Buscar usuário..." disabled={isClosed} />
              </label>
              <label>Conferido por
                <UserPicker value={checkedBy} onChange={setCheckedBy} placeholder="Buscar usuário..." disabled={isClosed} />
              </label>
              <label>Recebido por
                <UserPicker value={receivedBy} onChange={setReceivedBy} placeholder="Buscar usuário..." disabled={isClosed} />
              </label>

              <div className="module-table-wrap" style={{ margin: "var(--sp-3) 0" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Local</th>
                      <th>1ª verificação</th>
                      <th>2ª verificação</th>
                      <th>Observações</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((row, idx) => (
                      <tr key={row.key}>
                        <td>
                          <select
                            name={`entries[${idx}].location_id`}
                            value={row.location_id || ""}
                            onChange={(e) => updateEntry(row.key, { location_id: Number(e.target.value) })}
                            disabled={isClosed}
                          >
                            <option value="">Selecione...</option>
                            {locations.map((loc) => (
                              <option key={loc.id} value={loc.id}>{loc.name}</option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <input
                            name={`entries[${idx}].first_code`}
                            value={row.first_code ?? ""}
                            onChange={(e) => updateEntry(row.key, { first_code: e.target.value })}
                            maxLength={40}
                            disabled={isClosed}
                          />
                        </td>
                        <td>
                          <input
                            name={`entries[${idx}].second_code`}
                            value={row.second_code ?? ""}
                            onChange={(e) => updateEntry(row.key, { second_code: e.target.value })}
                            maxLength={40}
                            disabled={isClosed}
                          />
                        </td>
                        <td>
                          <input
                            name={`entries[${idx}].notes`}
                            value={row.notes ?? ""}
                            onChange={(e) => updateEntry(row.key, { notes: e.target.value })}
                            disabled={isClosed}
                          />
                        </td>
                        <td>
                          {!isClosed && (
                            <button type="button" onClick={() => removeEntryRow(row.key)} aria-label="Remover local">
                              <Trash2 size={16} />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!isClosed && (
                <button type="button" className="secondary-button" onClick={addEntryRow}>
                  <Plus size={16} /> Adicionar local
                </button>
              )}

              <label>Observações
                <textarea value={observations} onChange={(e) => setObservations(e.target.value)} rows={3} disabled={isClosed} />
              </label>

              <footer>
                <button type="button" onClick={closeModal}>{isClosed ? "Fechar" : "Cancelar"}</button>
                {!isClosed && (
                  <button type="submit" disabled={saving}>{saving ? "Salvando…" : "Salvar conferência"}</button>
                )}
              </footer>
            </form>
          </section>
        </div>
      )}

      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </>
  );
}
