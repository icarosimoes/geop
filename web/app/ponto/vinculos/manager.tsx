"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
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
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);

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

  function closeModal() {
    setShowForm(false);
    setEmployeeId("");
    setExternalId("");
    setError("");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!employeeId || !externalId.trim()) return;
    setSaving(true);
    setError("");
    const result = await createEnrollmentAction(Number(employeeId), externalId.trim());
    setSaving(false);
    if (result.ok) {
      closeModal();
      showToast("Vínculo criado.");
      reload();
    } else {
      setError(result.error ?? "Erro ao criar vínculo.");
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
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Ponto</p>
          <h1>Vínculos</h1>
          <p>Associe a matrícula cadastrada no relógio a um funcionário do GEOP.</p>
        </div>
        <button className="primary-button" onClick={() => setShowForm(true)}>
          <Plus size={18} /> Novo vínculo
        </button>
      </header>

      <section className="module-panel">
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
      </section>

      {showForm && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Ponto</span>
                <h2>Novo vínculo</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <form onSubmit={handleCreate}>
              {error && <div className="kanban-form-error">{error}</div>}
              <label>Funcionário *
                <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required autoFocus>
                  <option value="">Selecione o funcionário...</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>Matrícula no relógio *
                <input
                  value={externalId}
                  onChange={(e) => setExternalId(e.target.value)}
                  placeholder="Ex.: 1001"
                  required
                />
              </label>
              <footer>
                <button type="button" onClick={closeModal}>Cancelar</button>
                <button type="submit" disabled={saving}>{saving ? "Vinculando…" : "Criar vínculo"}</button>
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
