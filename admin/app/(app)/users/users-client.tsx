"use client";

import { useState } from "react";
import { Pencil, Plus, Search, Trash2, UserCog } from "lucide-react";
import { toast } from "sonner";
import type { PlatformUser, PlatformUserRole } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, type ConfirmDialogState } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  open,
  onClose,
  onSaved,
}: {
  user: PlatformUser | null;
  open: boolean;
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
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{user ? "Editar usuário" : "Novo usuário"}</DialogTitle>
          <DialogDescription>{user ? user.email : "Equipe interna da plataforma"}</DialogDescription>
        </DialogHeader>

        {error && (
          <p className="text-sm text-[var(--danger)] mb-3 p-3 bg-[var(--danger)]/10 rounded-lg">{error}</p>
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

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" loading={loading}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function UsersClient({ initialUsers }: { initialUsers: PlatformUser[] }) {
  const [users, setUsers] = useState(initialUsers);
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState<"new" | PlatformUser | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmDialogState | null>(null);

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

  function deleteUser(user: PlatformUser) {
    setConfirmState({
      title: "Remover usuário",
      description: `Remover ${user.name} do painel? Essa ação não pode ser desfeita.`,
      confirmLabel: "Remover",
      variant: "destructive",
      onConfirm: async () => {
        try {
          await apiFetch(`/users/${user.id}`, { method: "DELETE" });
          setUsers((prev) => prev.filter((item) => item.id !== user.id));
        } catch (err) {
          toast.error(err instanceof Error ? err.message : "Erro ao remover usuário");
        }
      },
    });
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

      <UserModal
        user={modal === "new" ? null : modal}
        open={modal !== null}
        onClose={() => setModal(null)}
        onSaved={onSaved}
      />

      <ConfirmDialog state={confirmState} onOpenChange={(o) => !o && setConfirmState(null)} />
    </div>
  );
}
