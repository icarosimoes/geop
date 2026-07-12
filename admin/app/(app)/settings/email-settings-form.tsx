"use client";

import { useState } from "react";
import { CheckCircle2, Mail } from "lucide-react";
import type { EmailConfig } from "./page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function EmailSettingsForm({ initialConfig }: { initialConfig: EmailConfig }) {
  const [config, setConfig] = useState(initialConfig);
  const [form, setForm] = useState({
    brevo_api_key: "",
    email_from_address: initialConfig.email_from_address ?? "",
    email_from_name: initialConfig.email_from_name ?? "",
  });
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setSaved(false);
    setError("");
    try {
      const updated = await apiFetch<EmailConfig>("/settings/email", {
        method: "POST",
        body: JSON.stringify({
          brevo_api_key: form.brevo_api_key || undefined,
          email_from_address: form.email_from_address || undefined,
          email_from_name: form.email_from_name || undefined,
        }),
      });
      setConfig(updated);
      setForm((f) => ({ ...f, brevo_api_key: "" }));
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Configurações"
        description="E-mail transacional usado para convites e avisos do sistema (via Brevo)."
      />

      <Card className="max-w-xl">
        <CardHeader className="flex flex-row items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-[#1D3461]/10 text-[#1D3461] flex items-center justify-center shrink-0">
            <Mail className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold">E-mail (Brevo)</h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Sobrepõe as variáveis de ambiente da API para convites de usuário e demais e-mails
              transacionais da plataforma.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {config.brevo_configured && !saved && (
            <div className="flex items-center gap-2 rounded-lg bg-[var(--success)]/10 px-3 py-2 text-sm text-[var(--success)]">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              Brevo configurada. Deixe a API key em branco para manter a atual.
            </div>
          )}
          {saved && (
            <div className="flex items-center gap-2 rounded-lg bg-[var(--success)]/10 px-3 py-2 text-sm text-[var(--success)]">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              Configuração salva com sucesso.
            </div>
          )}
          {error && (
            <p className="rounded-lg bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">{error}</p>
          )}

          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>E-mail remetente</Label>
                <Input
                  type="email"
                  value={form.email_from_address}
                  onChange={(e) => setForm((f) => ({ ...f, email_from_address: e.target.value }))}
                  placeholder="noreply@registro.app"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Nome remetente</Label>
                <Input
                  value={form.email_from_name}
                  onChange={(e) => setForm((f) => ({ ...f, email_from_name: e.target.value }))}
                  placeholder="Registro"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Brevo API key</Label>
              <Input
                type="password"
                value={form.brevo_api_key}
                onChange={(e) => setForm((f) => ({ ...f, brevo_api_key: e.target.value }))}
                placeholder={config.brevo_configured ? "Configurada — preencha para trocar" : "xkeysib-..."}
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" loading={loading}>
                Salvar e-mail transacional
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
