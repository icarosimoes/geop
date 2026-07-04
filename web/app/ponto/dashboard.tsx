"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import {
  createManualPunchAction,
  fetchPunches,
  searchEmployees,
  type EmployeeOption,
  type TimePunch,
} from "@/app/actions";
import type { TenantUser } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  on_time: "No horário",
  late: "Atraso",
  early_leave: "Saída antecipada",
  unscheduled: "Sem escala",
};

function statusClass(status: string | null) {
  if (status === "on_time") return "status status-done";
  if (status === "late" || status === "early_leave") return "status status-waiting";
  return "status status-progress";
}

function hasPermission(user: TenantUser, code: string) {
  return user.permissions.includes("*") || user.permissions.includes(code);
}

export function PunchDashboard({ user }: { user: TenantUser }) {
  const [punches, setPunches] = useState<TimePunch[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formEmployeeId, setFormEmployeeId] = useState("");
  const [formDateTime, setFormDateTime] = useState("");
  const [formType, setFormType] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  const canManage = hasPermission(user, "timeclock.manage");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    fetchPunches({
      page,
      pageSize,
      employeeId: employeeId ? Number(employeeId) : undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      status: status || undefined,
    })
      .then((res) => {
        setPunches(res.items);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    searchEmployees("").then(setEmployees);
  }, []);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, employeeId, dateFrom, dateTo, status]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formEmployeeId || !formDateTime) return;
    setSaving(true);
    const result = await createManualPunchAction({
      employee_id: Number(formEmployeeId),
      punched_at: formDateTime,
      punch_type: formType || undefined,
      notes: formNotes || undefined,
    });
    setSaving(false);
    if (result.ok) {
      setShowForm(false);
      setFormEmployeeId("");
      setFormDateTime("");
      setFormType("");
      setFormNotes("");
      showToast("Batida lançada.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao lançar batida.");
    }
  }

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="module-panel">
      <div
        className="module-toolbar"
        style={{ display: "flex", gap: "var(--sp-3)", flexWrap: "wrap", alignItems: "center" }}
      >
        <select value={employeeId} onChange={(e) => { setEmployeeId(e.target.value); setPage(1); }}>
          <option value="">Todos os funcionários</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.name}
            </option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} />
        <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} />
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Todos os status</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        {canManage && (
          <button
            className="primary-button"
            onClick={() => setShowForm((v) => !v)}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, marginLeft: "auto" }}
          >
            <Plus size={16} /> Lançar manualmente
          </button>
        )}
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          style={{
            display: "flex",
            gap: "var(--sp-3)",
            padding: "var(--sp-4) var(--sp-5)",
            borderBottom: "1px solid var(--field-border)",
            flexWrap: "wrap",
          }}
        >
          <select value={formEmployeeId} onChange={(e) => setFormEmployeeId(e.target.value)} required>
            <option value="">Funcionário...</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name}
              </option>
            ))}
          </select>
          <input
            type="datetime-local"
            value={formDateTime}
            onChange={(e) => setFormDateTime(e.target.value)}
            required
          />
          <select value={formType} onChange={(e) => setFormType(e.target.value)}>
            <option value="">Tipo não informado</option>
            <option value="in">Entrada</option>
            <option value="out">Saída</option>
          </select>
          <input
            value={formNotes}
            onChange={(e) => setFormNotes(e.target.value)}
            placeholder="Observação (opcional)"
            style={{ flex: 1, minWidth: 200 }}
          />
          <button className="primary-button" type="submit" disabled={saving}>
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </form>
      )}

      {loading ? (
        <div className="module-state">Carregando batidas...</div>
      ) : punches.length === 0 ? (
        <div className="module-state">
          <strong>Nenhuma batida encontrada</strong>
          <span>Ajuste os filtros ou aguarde o relógio enviar novas batidas.</span>
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data/hora</th>
                <th>Funcionário</th>
                <th>Origem</th>
                <th>Tipo</th>
                <th>Status</th>
                <th>Observação</th>
              </tr>
            </thead>
            <tbody>
              {punches.map((punch) => (
                <tr key={punch.id}>
                  <td>{new Date(punch.punched_at).toLocaleString("pt-BR")}</td>
                  <td>{punch.employee_name ?? "Sem vínculo"}</td>
                  <td>{punch.source === "manual" ? "Manual" : punch.device_name ?? "Relógio"}</td>
                  <td>{punch.punch_type === "in" ? "Entrada" : punch.punch_type === "out" ? "Saída" : "—"}</td>
                  <td>
                    <span className={statusClass(punch.status)}>
                      {punch.status ? STATUS_LABELS[punch.status] ?? punch.status : "—"}
                    </span>
                  </td>
                  <td className="muted">{punch.notes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <footer className="module-pagination">
        <span>{total} batida(s)</span>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Página anterior">
            <ChevronLeft size={16} />
          </button>
          <span>
            Página {page} de {pages}
          </span>
          <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Próxima página">
            <ChevronRight size={16} />
          </button>
        </div>
      </footer>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
