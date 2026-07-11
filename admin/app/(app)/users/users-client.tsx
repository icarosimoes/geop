"use client";

import { useState } from "react";
import { Pencil, Plus, Search, Trash2, UserCog, X } from "lucide-react";
import type { PlatformUser, PlatformUserRole } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fmtDate, pluralize } from "@/lib/utils";

const ROLE_LABEL: Record<PlatformUserRole, string> = {
  super_admin: "Super admin",
  support: "Suporte",
  billing: "Financeiro",
  read_only: "Somente leitura",
};

const ROLE_VARIANT: Record<PlatformUserRole, "brand" | "success" | "warning" | "default"> = {
  super_admin: "brand",
  support: "success",
  billing: "warning",
  read_only: "default",
};

type UserForm = {
  name: string;
  email: string;
  role: PlatformUserRole;
  password: string;
};

const EMPTY_FORM: UserForm = { name: "", email: "", role: "read_only", password: "" };

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

function UserModal({
  user,
  onClose,
  onSaved,
}: {
  user: PlatformUser | null;
  onClose: () => void;
  onSaved: (user: PlatformUser) => void;
}) {
  const [form, setForm] = useState<UserForm>(
    user ? { name: user.name, email: user.email, role: user.role, password: "" } : { ...EMPTY_FORM },
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload: Partial<UserForm> = { name: form.name, email: form.email, role: form.role };
      if (form.password) payload.password = form.password;

      const saved = user
        ? await apiFetch<PlatformUser>(`/users/${user.id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : await apiFetch<PlatformUser>("/users", {
            method: "POST",
            body: JSON.stringify({ ...payload, password: form.password }),
          });
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar usuário");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-[var(--card)] rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in">
        <div
          className="px-6 py-4 flex items-center justify-between"
          style={{ background: "linear-gradient(135deg, #1D3461, #142548)" }}
        >
          <div>
            <h2 className="text-lg font-bold text-white">
              {user ? "Editar usuário" : "Novo usuário"}
            </h2>
            <p className="text-xs text-white/60 mt-0.5">
              {user ? user.email : "Equipe interna da plataforma"}
            </p>
          </div>
          <button onClick={onClose} className="text-white/60 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6">
          {error && (
            <p className="text-sm text-[var(--danger)] mb-3 p-3 bg-[var(--danger)]/10 rounded-lg">
              {error}
            </p>
          )}
          <form onSubmit={submit} className="space-y-3">
            <div className="space-y-1.5">
              <Label>Nome</Label>
              <Input
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label>E-mail</Label>
              <Input
                required
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label>Papel</Label>
              <select
                className="flex h-9 w-full rounded-md border border-[var(--input)] bg-transparent px-3 py-1 text-sm shadow-sm"
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as PlatformUserRole }))}
              >
                {Object.entries(ROLE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label>{user ? "Nova senha (opcional)" : "Senha inicial"}</Label>
              <Input
                required={!user}
                type="password"
                minLength={8}
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button type="submit" loading={loading}>
                Salvar
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export function UsersClient({ initialUsers }: { initialUsers: PlatformUser[] }) {
  const [users, setUsers] = useState(initialUsers);
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState<"new" | PlatformUser | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  const query = search.trim().toLowerCase();
  const filtered = users.filter(
    (user) =>
      !query ||
      user.name.toLowerCase().includes(query) ||
      user.email.toLowerCase().includes(query) ||
      ROLE_LABEL[user.role].toLowerCase().includes(query),
  );

  function onSaved(saved: PlatformUser) {
    setUsers((prev) => {
      const idx = prev.findIndex((user) => user.id === saved.id);
      if (idx >= 0) return prev.map((user) => (user.id === saved.id ? saved : user));
      return [saved, ...prev];
    });
  }

  async function deleteUser(user: PlatformUser) {
    if (!confirm(`Remover ${user.name} do painel?`)) return;
    setDeleting(user.id);
    try {
      await apiFetch(`/users/${user.id}`, { method: "DELETE" });
      setUsers((prev) => prev.filter((item) => item.id !== user.id));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Usuários"
        description={`${users.length} ${pluralize(users.length, "usuário interno", "usuários internos")} da plataforma.`}
        actions={
          <Button onClick={() => setModal("new")}>
            <Plus size={16} /> Novo usuário
          </Button>
        }
      />

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
        <Input
          className="pl-9"
          placeholder="Buscar por nome, e-mail ou papel…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Usuário</TableHead>
            <TableHead>Papel</TableHead>
            <TableHead className="text-right">Último login</TableHead>
            <TableHead className="text-right">Criado em</TableHead>
            <TableHead className="text-right">Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 && (
            <TableEmpty colSpan={5}>
              {users.length === 0 ? "Nenhum usuário cadastrado." : "Nenhum resultado para a busca."}
            </TableEmpty>
          )}
          {filtered.map((user) => (
            <TableRow key={user.id}>
              <TableCell>
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-lg bg-[#1D3461]/10 text-[#1D3461] flex items-center justify-center shrink-0">
                    <UserCog className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium">{user.name}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">{user.email}</p>
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={ROLE_VARIANT[user.role]}>{ROLE_LABEL[user.role]}</Badge>
              </TableCell>
              <TableCell className="text-right text-xs text-[var(--muted-foreground)]">
                {fmtDate(user.last_login_at)}
              </TableCell>
              <TableCell className="text-right text-xs text-[var(--muted-foreground)]">
                {fmtDate(user.created_at)}
              </TableCell>
              <TableCell>
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" size="icon" onClick={() => setModal(user)} title="Editar usuário">
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteUser(user)}
                    disabled={deleting === user.id}
                    title="Remover usuário"
                    className="hover:bg-[var(--danger)]/10 hover:text-[var(--danger)]"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {modal !== null && (
        <UserModal
          user={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={onSaved}
        />
      )}
    </div>
  );
}
