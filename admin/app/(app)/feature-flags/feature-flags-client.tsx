"use client";

import { useState } from "react";
import { Flag, Pencil, Plus, ToggleLeft, ToggleRight, Trash2, X } from "lucide-react";
import type { FeatureFlag } from "./page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

function FlagModal({
  flag,
  onClose,
  onSaved,
}: {
  flag: FeatureFlag | null;
  onClose: () => void;
  onSaved: (f: FeatureFlag) => void;
}) {
  const [form, setForm] = useState({
    key: flag?.key ?? "",
    description: flag?.description ?? "",
    enabled_default: flag?.enabled_default ?? false,
    targeting_rules: flag ? JSON.stringify(flag.targeting_rules, null, 2) : "{}",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      let rules: Record<string, unknown> = {};
      try {
        rules = JSON.parse(form.targeting_rules);
      } catch {
        setError("targeting_rules inválido (JSON)");
        setLoading(false);
        return;
      }
      const saved = flag
        ? await apiFetch<FeatureFlag>(`/feature-flags/${flag.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              description: form.description || null,
              enabled_default: form.enabled_default,
              targeting_rules: rules,
            }),
          })
        : await apiFetch<FeatureFlag>("/feature-flags", {
            method: "POST",
            body: JSON.stringify({
              key: form.key,
              description: form.description || null,
              enabled_default: form.enabled_default,
              targeting_rules: rules,
            }),
          });
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
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
          <h2 className="text-lg font-bold text-white">
            {flag ? "Editar feature flag" : "Nova feature flag"}
          </h2>
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
              <Label>Chave (key) *</Label>
              <Input
                required
                disabled={!!flag}
                value={form.key}
                onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))}
                placeholder="booking_engine_v2"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Descrição</Label>
              <Input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>

            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, enabled_default: !f.enabled_default }))}
              className="flex items-center gap-3 text-sm text-[var(--foreground)]"
            >
              {form.enabled_default ? (
                <ToggleRight className="h-6 w-6 text-[var(--color-brand)]" />
              ) : (
                <ToggleLeft className="h-6 w-6 text-[var(--muted-foreground)]" />
              )}
              Habilitado por padrão: <strong>{form.enabled_default ? "Sim" : "Não"}</strong>
            </button>

            <div className="space-y-1.5">
              <Label>Targeting rules (JSON)</Label>
              <Textarea
                rows={4}
                className="font-mono text-xs"
                value={form.targeting_rules}
                onChange={(e) => setForm((f) => ({ ...f, targeting_rules: e.target.value }))}
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

export function FeatureFlagsClient({ initialFlags }: { initialFlags: FeatureFlag[] }) {
  const [flags, setFlags] = useState(initialFlags);
  const [modal, setModal] = useState<"new" | FeatureFlag | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  async function deleteFlag(flag: FeatureFlag) {
    if (!confirm(`Remover a feature flag "${flag.key}"?`)) return;
    setDeleting(flag.id);
    try {
      await apiFetch(`/feature-flags/${flag.id}`, { method: "DELETE" });
      setFlags((prev) => prev.filter((f) => f.id !== flag.id));
    } finally {
      setDeleting(null);
    }
  }

  function onSaved(saved: FeatureFlag) {
    setFlags((prev) => {
      const idx = prev.findIndex((f) => f.id === saved.id);
      if (idx >= 0) return prev.map((f) => (f.id === saved.id ? saved : f));
      return [saved, ...prev];
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Feature Flags"
        description="Controle gradual de funcionalidades por tenant ou plano."
        actions={
          <Button onClick={() => setModal("new")}>
            <Plus size={16} /> Nova flag
          </Button>
        }
      />

      {flags.length === 0 ? (
        <EmptyState
          icon={<Flag className="h-6 w-6" />}
          title="Nenhuma feature flag cadastrada"
          action={<Button onClick={() => setModal("new")}>Criar primeira flag</Button>}
        />
      ) : (
        <div className="space-y-3">
          {flags.map((flag) => (
            <div
              key={flag.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm p-5 flex items-start gap-4"
            >
              <div className="mt-0.5">
                {flag.enabled_default ? (
                  <ToggleRight className="h-5 w-5 text-[var(--color-brand)]" />
                ) : (
                  <ToggleLeft className="h-5 w-5 text-[var(--muted-foreground)]" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <code className="text-sm font-semibold bg-[var(--accent)] rounded px-2 py-0.5">
                    {flag.key}
                  </code>
                  <Badge variant={flag.enabled_default ? "success" : "default"}>
                    {flag.enabled_default ? "Ativo por padrão" : "Inativo por padrão"}
                  </Badge>
                </div>
                {flag.description && (
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">{flag.description}</p>
                )}
                {Object.keys(flag.targeting_rules).length > 0 && (
                  <code className="text-xs text-[var(--muted-foreground)] mt-1 block truncate max-w-md">
                    rules: {JSON.stringify(flag.targeting_rules)}
                  </code>
                )}
              </div>

              <div className="flex gap-1 shrink-0">
                <Button variant="ghost" size="icon" onClick={() => setModal(flag)} title="Editar flag">
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteFlag(flag)}
                  disabled={deleting === flag.id}
                  title="Remover flag"
                  className="hover:bg-[var(--danger)]/10 hover:text-[var(--danger)]"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal !== null && (
        <FlagModal
          flag={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={(saved) => {
            onSaved(saved);
            setModal(null);
          }}
        />
      )}
    </div>
  );
}
