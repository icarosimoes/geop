"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, Edit2 } from "lucide-react";
import {
  createShiftAction,
  deleteShiftAction,
  fetchShifts,
  updateShiftAction,
  type Shift,
} from "@/app/actions";
import type { TenantUser } from "@/lib/api";

function hasPermission(user: TenantUser, code: string) {
  return user.permissions.includes("*") || user.permissions.includes(code);
}

export function ShiftManager({ user }: { user: TenantUser }) {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<Partial<Shift>>({
    name: "",
    start_time: "08:00",
    end_time: "17:00",
    color: "#2563eb",
    tolerance_minutes: 10,
  });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  const canManage = hasPermission(user, "shift.manage");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    fetchShifts().then(setShifts).finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
  }, []);

  function resetForm() {
    setShowForm(false);
    setEditingId(null);
    setFormData({
      name: "",
      start_time: "08:00",
      end_time: "17:00",
      color: "#2563eb",
      tolerance_minutes: 10,
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.name?.trim() || !formData.start_time || !formData.end_time) return;

    setSaving(true);
    const result = editingId
      ? await updateShiftAction(editingId, formData)
      : await createShiftAction(formData as Parameters<typeof createShiftAction>[0]);
    setSaving(false);

    if (result.ok) {
      showToast(editingId ? "Turno atualizado." : "Turno criado.");
      resetForm();
      reload();
    } else {
      showToast(result.error ?? "Erro ao salvar.");
    }
  }

  function handleEdit(shift: Shift) {
    setEditingId(shift.id);
    setFormData(shift);
    setShowForm(true);
  }

  async function handleDelete(shift: Shift) {
    if (!confirm(`Remover turno "${shift.name}"?`)) return;
    const result = await deleteShiftAction(shift.id);
    if (result.ok) {
      showToast("Turno removido.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao remover.");
    }
  }

  return (
    <section className="module-panel">
      {canManage && (
        <form
          onSubmit={handleSubmit}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: "var(--sp-3)",
            padding: "var(--sp-4) var(--sp-5)",
            borderBottom: "1px solid var(--field-border)",
            alignItems: "end",
          }}
        >
          {showForm && (
            <>
              <div>
                <label>Nome *</label>
                <input
                  type="text"
                  value={formData.name ?? ""}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="ex: Manhã"
                  required
                />
              </div>
              <div>
                <label>Entrada *</label>
                <input
                  type="time"
                  value={formData.start_time ?? ""}
                  onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                  required
                />
              </div>
              <div>
                <label>Saída *</label>
                <input
                  type="time"
                  value={formData.end_time ?? ""}
                  onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                  required
                />
              </div>
              <div>
                <label>Tolerância (min)</label>
                <input
                  type="number"
                  value={formData.tolerance_minutes ?? 10}
                  onChange={(e) => setFormData({ ...formData, tolerance_minutes: Number(e.target.value) })}
                  min="0"
                  max="60"
                />
              </div>
              <div>
                <label>Cor</label>
                <input
                  type="color"
                  value={formData.color ?? "#2563eb"}
                  onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                  style={{ cursor: "pointer", height: "40px" }}
                />
              </div>
              <div style={{ display: "flex", gap: "var(--sp-2)" }}>
                <button className="primary-button" type="submit" disabled={saving}>
                  {saving ? "Salvando..." : editingId ? "Atualizar" : "Criar"}
                </button>
                <button type="button" onClick={resetForm} style={{ backgroundColor: "var(--field-bg)" }}>
                  Cancelar
                </button>
              </div>
            </>
          )}
          {!showForm && (
            <button
              className="primary-button"
              type="button"
              onClick={() => setShowForm(true)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Plus size={16} /> Novo turno
            </button>
          )}
        </form>
      )}

      {loading ? (
        <div className="module-state">Carregando turnos...</div>
      ) : shifts.length === 0 ? (
        <div className="module-state">
          <strong>Nenhum turno cadastrado</strong>
          <span>Crie turnos que serão usados na escala de trabalho.</span>
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Entrada</th>
                <th>Saída</th>
                <th>Tolerância</th>
                <th>Cor</th>
                {canManage && <th>Ações</th>}
              </tr>
            </thead>
            <tbody>
              {shifts.map((shift) => (
                <tr key={shift.id}>
                  <td>
                    <strong>{shift.name}</strong>
                  </td>
                  <td>{shift.start_time}</td>
                  <td>{shift.end_time}</td>
                  <td>{shift.tolerance_minutes}min</td>
                  <td>
                    <span
                      style={{
                        display: "inline-block",
                        width: 24,
                        height: 24,
                        backgroundColor: shift.color,
                        borderRadius: 4,
                        border: "1px solid var(--field-border)",
                      }}
                    />
                  </td>
                  {canManage && (
                    <td>
                      <div className="row-actions">
                        <button onClick={() => handleEdit(shift)} aria-label="Editar">
                          <Edit2 size={16} />
                        </button>
                        <button onClick={() => handleDelete(shift)} aria-label="Remover">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="module-pagination">
        <span>{shifts.length} turno(s)</span>
      </footer>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
