"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import {
  createEnrollmentAction,
  deleteEnrollmentAction,
  fetchEnrollments,
  searchEmployees,
  type EmployeeOption,
  type TimeClockEnrollment,
} from "@/app/actions";

export function EnrollmentManager() {
  const [enrollments, setEnrollments] = useState<TimeClockEnrollment[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [employeeId, setEmployeeId] = useState("");
  const [externalId, setExternalId] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    fetchEnrollments().then(setEnrollments).finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    searchEmployees("").then(setEmployees);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!employeeId || !externalId.trim()) return;
    setSaving(true);
    const result = await createEnrollmentAction(Number(employeeId), externalId.trim());
    setSaving(false);
    if (result.ok) {
      setEmployeeId("");
      setExternalId("");
      showToast("Vínculo criado.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao criar vínculo.");
    }
  }

  async function handleDelete(enrollment: TimeClockEnrollment) {
    if (!confirm(`Remover o vínculo de "${enrollment.employee_name}"?`)) return;
    const result = await deleteEnrollmentAction(enrollment.id);
    if (result.ok) {
      showToast("Vínculo removido.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao remover.");
    }
  }

  return (
    <section className="module-panel">
      <form
        onSubmit={handleCreate}
        style={{
          display: "flex",
          gap: "var(--sp-3)",
          padding: "var(--sp-4) var(--sp-5)",
          borderBottom: "1px solid var(--field-border)",
          flexWrap: "wrap",
          alignItems: "flex-end",
        }}
      >
        <div className="report-filter-field" style={{ flex: "1 1 220px" }}>
          <label htmlFor="enrollment_employee">Funcionário</label>
          <select id="enrollment_employee" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required>
            <option value="">Selecione o funcionário...</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name}
              </option>
            ))}
          </select>
        </div>
        <div className="report-filter-field" style={{ flex: "1 1 220px" }}>
          <label htmlFor="enrollment_external_id">Matrícula no relógio</label>
          <input
            id="enrollment_external_id"
            value={externalId}
            onChange={(e) => setExternalId(e.target.value)}
            placeholder="Ex.: 1001"
            required
          />
        </div>
        <button className="primary-button" type="submit" disabled={saving} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Plus size={16} /> {saving ? "Vinculando..." : "Vincular"}
        </button>
      </form>

      {loading ? (
        <div className="module-state">Carregando vínculos...</div>
      ) : enrollments.length === 0 ? (
        <div className="module-state">
          <strong>Nenhum vínculo cadastrado</strong>
          <span>Vincule a matrícula do relógio a um funcionário para que as batidas sejam identificadas.</span>
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Funcionário</th>
                <th>Matrícula no relógio</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {enrollments.map((enrollment) => (
                <tr key={enrollment.id}>
                  <td>
                    <strong>{enrollment.employee_name}</strong>
                  </td>
                  <td>{enrollment.external_id}</td>
                  <td>
                    <div className="row-actions">
                      <button onClick={() => handleDelete(enrollment)} aria-label="Remover">
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
        <span>{enrollments.length} vínculo(s)</span>
      </footer>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
