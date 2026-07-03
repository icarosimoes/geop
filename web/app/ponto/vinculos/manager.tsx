"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import {
  createEnrollmentAction,
  deleteEnrollmentAction,
  fetchEnrollments,
  searchUsers,
  type TimeClockEnrollment,
  type UserOption,
} from "@/app/actions";

export function EnrollmentManager() {
  const [enrollments, setEnrollments] = useState<TimeClockEnrollment[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState("");
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
    searchUsers("").then(setUsers);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!userId || !externalId.trim()) return;
    setSaving(true);
    const result = await createEnrollmentAction(Number(userId), externalId.trim());
    setSaving(false);
    if (result.ok) {
      setUserId("");
      setExternalId("");
      showToast("Vínculo criado.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao criar vínculo.");
    }
  }

  async function handleDelete(enrollment: TimeClockEnrollment) {
    if (!confirm(`Remover o vínculo de "${enrollment.user_name}"?`)) return;
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
        }}
      >
        <select value={userId} onChange={(e) => setUserId(e.target.value)} required style={{ flex: 1 }}>
          <option value="">Selecione o funcionário...</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
        <input
          value={externalId}
          onChange={(e) => setExternalId(e.target.value)}
          placeholder="Matrícula cadastrada no relógio"
          required
          style={{ flex: 1 }}
        />
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
                    <strong>{enrollment.user_name}</strong>
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
