"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import {
  fetchWorkOrderCategories,
  addCategoryAction,
  deleteCategoryAction,
} from "@/app/actions";

export function CategoryManager() {
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    fetchWorkOrderCategories().then(setCategories).finally(() => setLoading(false));
  }

  useEffect(() => { reload(); }, []);

  function closeModal() {
    setShowForm(false);
    setNewName("");
    setError("");
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    if (categories.includes(name)) { setError("Categoria já existe."); return; }
    setSaving(true);
    setError("");
    const result = await addCategoryAction(name);
    setSaving(false);
    if (result.ok) {
      closeModal();
      showToast("Categoria criada.");
      reload();
    } else {
      setError(result.error ?? "Erro ao criar.");
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`Excluir a categoria "${name}"? OS existentes com esta categoria não serão afetadas.`)) return;
    const result = await deleteCategoryAction(name);
    if (result.ok) {
      showToast("Categoria excluída.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao excluir.");
    }
  }

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Cadastros</p>
          <h1>Categorias de OS</h1>
          <p>Gerencie as categorias disponíveis para Ordens de Serviço.</p>
        </div>
        <button className="primary-button" onClick={() => setShowForm(true)}>
          <Plus size={18} /> Nova categoria
        </button>
      </header>

      <section className="module-panel">
        {loading ? (
          <div className="module-state">Carregando categorias...</div>
        ) : categories.length === 0 ? (
          <div className="module-state">
            <strong>Nenhuma categoria cadastrada</strong>
            <span>Adicione categorias para organizar suas Ordens de Serviço.</span>
          </div>
        ) : (
          <div className="module-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Categoria</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((cat, i) => (
                  <tr key={cat}>
                    <td className="protocol">#{i + 1}</td>
                    <td><strong>{cat}</strong></td>
                    <td>
                      <div className="row-actions">
                        <button onClick={() => handleDelete(cat)} aria-label="Excluir">
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
          <span>{categories.length} categoria(s)</span>
        </footer>
      </section>

      {showForm && (
        <div className="modal-layer" role="presentation" onClick={closeModal}>
          <section className="record-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Cadastros</span>
                <h2>Nova categoria</h2>
              </div>
              <button className="icon-button" onClick={closeModal}><X /></button>
            </header>
            <form onSubmit={handleAdd}>
              {error && <div className="kanban-form-error">{error}</div>}
              <label>Nome *
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Ex: Elétrica, Hidráulica, HVAC..."
                  required
                  autoFocus
                />
              </label>
              <footer>
                <button type="button" onClick={closeModal}>Cancelar</button>
                <button type="submit" disabled={saving}>{saving ? "Criando…" : "Criar categoria"}</button>
              </footer>
            </form>
          </section>
        </div>
      )}

      {toast && <div className="module-toast" role="status">{toast}</div>}
    </>
  );
}
