"use client";

import {
  createRoleAction, updateRoleAction, deleteRoleAction,
} from "@/app/actions";
import type { TenantUser } from "@/lib/api";
import { Pencil, Plus, Trash2, X, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

type PermissionItem = { id: number; code: string; name: string; module: string };
type PermissionGroup = { module: string; permissions: PermissionItem[] };
type RoleItem = {
  id: number;
  code: string;
  name: string;
  permission_codes: string[];
  user_count: number;
  updated_at?: string;
};

const MODULE_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  user: "Usuários",
  users: "Usuários",
  admin: "Usuários",
  registry: "Cadastros",
  registries: "Cadastros",
  module: "Módulos",
  modules: "Módulos",
  procedure: "Procedimentos",
  procedures: "Procedimentos",
  meeting: "Reuniões",
  meetings: "Reuniões",
  shift_report: "Relatórios de Turno",
  shift_reports: "Relatórios de Turno",
  bulletin: "Informativos",
  bulletins: "Informativos",
  handoff: "Passagem de Turno",
  handoffs: "Passagem de Turno",
  checklist: "Checklists",
  checklists: "Checklists",
  inspections: "Inspeções",
  maintenance: "Manutenção",
  preventive_plan: "Preventivas",
  stock: "Estoque",
  construction: "Diário de Obra",
  work_orders: "Ordens de Serviço",
  settings: "Configurações",
  system: "Sistema",
};

const MODULE_ORDER = [
  "dashboard",
  "user", "users", "admin", "registry", "registries",
  "module", "modules", "procedure", "procedures",
  "meeting", "meetings", "shift_report", "shift_reports",
  "bulletin", "bulletins", "handoff", "handoffs",
  "checklist", "checklists", "inspections",
  "maintenance", "preventive_plan", "stock",
  "construction", "work_orders", "settings",
];

export function RoleManager({
  roles: initialRoles,
  permissionGroups,
  user,
}: {
  roles: RoleItem[];
  permissionGroups: PermissionGroup[];
  user: TenantUser;
}) {
  const [roles, setRoles] = useState(initialRoles);
  const [editing, setEditing] = useState<RoleItem | "new" | null>(null);
  const [toast, setToast] = useState("");
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function hasPermission(code: string) {
    return user.permissions.includes("*") || user.permissions.includes(code);
  }
  const canEdit = hasPermission("user.edit");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function handleSave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const formData = new FormData(form);
    const name = String(formData.get("name") ?? "").trim();
    const code = String(formData.get("code") ?? "").trim();
    if (!name || !code) return;

    const selectedPerms: string[] = [];
    for (const group of permissionGroups) {
      for (const perm of group.permissions) {
        if (formData.get(`perm_${perm.code}`) === "on") {
          selectedPerms.push(perm.code);
        }
      }
    }

    startTransition(async () => {
      if (editing === "new") {
        const result = await createRoleAction({ code, name, permission_codes: selectedPerms });
        if (result.ok) {
          showToast("Perfil criado com sucesso.");
          setEditing(null);
          router.refresh();
        } else {
          showToast(result.error ?? "Erro ao criar perfil.");
        }
      } else if (editing) {
        const result = await updateRoleAction(editing.id, { name, permission_codes: selectedPerms });
        if (result.ok) {
          showToast("Perfil atualizado com sucesso.");
          setEditing(null);
          router.refresh();
        } else {
          showToast(result.error ?? "Erro ao atualizar perfil.");
        }
      }
    });
  }

  function handleDelete(role: RoleItem) {
    if (role.user_count > 0) {
      showToast(`Não é possível excluir: ${role.user_count} usuário(s) atribuído(s).`);
      return;
    }
    if (!confirm(`Excluir o perfil "${role.name}"?`)) return;
    startTransition(async () => {
      const result = await deleteRoleAction(role.id);
      if (result.ok) {
        setRoles((prev) => prev.filter((r) => r.id !== role.id));
        showToast("Perfil excluído.");
      } else {
        showToast(result.error ?? "Erro ao excluir.");
      }
    });
  }

  const isAdmin = (r: RoleItem) => r.permission_codes.includes("*");

  return (
    <section className="module-panel">
      <div className="module-toolbar">
        <h1 style={{ fontSize: "1.2rem", fontWeight: 600 }}>
          <Shield size={20} style={{ verticalAlign: "middle", marginRight: 6 }} />
          Perfis de acesso
        </h1>
        <div style={{ flex: 1 }} />
        {canEdit && (
          <button onClick={() => setEditing("new")}>
            <Plus size={17} /> Novo perfil
          </button>
        )}
      </div>

      <div className="module-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Código</th>
              <th>Usuários</th>
              <th>Permissões</th>
              {canEdit && <th>Ações</th>}
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <tr key={role.id}>
                <td><strong>{role.name}</strong></td>
                <td className="muted">{role.code}</td>
                <td>{role.user_count}</td>
                <td className="muted">
                  {isAdmin(role) ? "Acesso total" : `${role.permission_codes.length} permissões`}
                </td>
                {canEdit && (
                  <td>
                    <div className="row-actions">
                      {!isAdmin(role) && (
                        <>
                          <button onClick={() => setEditing(role)} aria-label="Editar">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => handleDelete(role)} aria-label="Excluir">
                            <Trash2 size={16} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing ? (
        <div className="modal-layer" role="presentation">
          <section className="record-modal" role="dialog" aria-modal="true">
            <header>
              <div>
                <h2>{editing === "new" ? "Novo perfil" : `Editar: ${editing.name}`}</h2>
              </div>
              <button className="icon-button" onClick={() => setEditing(null)}>
                <X />
              </button>
            </header>
            <form onSubmit={handleSave}>
              <div className="form-grid">
                <label>
                  Nome
                  <input
                    name="name"
                    required
                    defaultValue={editing === "new" ? "" : editing.name}
                  />
                </label>
                <label>
                  Código
                  <input
                    name="code"
                    required
                    pattern="[a-z0-9_]+"
                    title="Apenas letras minúsculas, números e _"
                    defaultValue={editing === "new" ? "" : editing.code}
                    readOnly={editing !== "new"}
                  />
                </label>
              </div>

              <div className="permission-groups">
                <h3>Permissões</h3>
                {[...permissionGroups]
                  .filter((g) => g.module !== "system" && g.module !== "legacy")
                  .sort((a, b) => {
                    const ai = MODULE_ORDER.indexOf(a.module);
                    const bi = MODULE_ORDER.indexOf(b.module);
                    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
                  })
                  .map((group) => {
                    const allCodes = group.permissions.map((p) => p.code);
                    const checkedCodes =
                      editing !== "new"
                        ? allCodes.filter((c) => editing.permission_codes.includes(c))
                        : [];

                    return (
                      <fieldset key={group.module} className="permission-group">
                        <legend>
                          <label className="permission-group-toggle">
                            <span>{MODULE_LABELS[group.module] ?? group.module}</span>
                            <input
                              type="checkbox"
                              className="toggle-switch"
                              onChange={(e) => {
                                const checkboxes =
                                  e.target.closest("fieldset")?.querySelectorAll<HTMLInputElement>(
                                    'input[type="checkbox"][name^="perm_"]'
                                  );
                                checkboxes?.forEach((cb) => {
                                  cb.checked = e.target.checked;
                                });
                              }}
                              defaultChecked={
                                editing !== "new" &&
                                checkedCodes.length === allCodes.length
                              }
                            />
                          </label>
                        </legend>
                        <div className="permission-items">
                          {group.permissions.map((perm) => (
                            <label key={perm.code} className="permission-toggle">
                              <span>{perm.name}</span>
                              <input
                                type="checkbox"
                                className="toggle-switch"
                                name={`perm_${perm.code}`}
                                defaultChecked={
                                  editing !== "new" &&
                                  editing.permission_codes.includes(perm.code)
                                }
                              />
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    );
                  })}
              </div>

              <footer className="modal-footer">
                <button type="button" onClick={() => setEditing(null)}>
                  Cancelar
                </button>
                <button type="submit" disabled={isPending}>
                  {isPending ? "Salvando…" : "Salvar"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}

      {toast ? (
        <div className="module-toast" role="status">
          {toast}
        </div>
      ) : null}
    </section>
  );
}
