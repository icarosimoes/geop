"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { loginAction } from "@/app/actions";

export default function LoginPage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [tenants, setTenants] = useState<{ id: number; name: string }[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<number | null>(null);

  function resetTenants() {
    setTenants([]);
    setSelectedTenant(null);
    setError("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      const result = await loginAction(email, password, selectedTenant ?? undefined);
      if (result.ok) {
        router.push("/dashboard");
        return;
      }
      if (result.multi_tenant && result.tenants) {
        setTenants(result.tenants);
        setSelectedTenant(null);
        return;
      }
      setError(result.error ?? "Falha no login.");
    });
  }

  return (
    <main className="tenant-login-page">
      <div className="tenant-login-brand">
        <span className="tenant-login-logo">R</span>
        <strong>Registro</strong>
        <span>Gestão operacional hoteleira</span>
      </div>

      <div className="tenant-login-card">
        {tenants.length > 1 ? (
          <button type="button" className="tenant-login-back" onClick={resetTenants}>
            <ArrowLeft size={14} /> Trocar e-mail
          </button>
        ) : (
          <p className="eyebrow">Bem-vindo</p>
        )}
        <h2>{tenants.length > 1 ? "Selecione a empresa" : "Acesse sua conta"}</h2>
        <p>
          {tenants.length > 1
            ? `O e-mail ${email} tem acesso a mais de uma empresa.`
            : "Entre com seu e-mail e senha — a empresa é identificada automaticamente."}
        </p>
        {error && <div className="login-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>
            E-mail
            <input
              name="email"
              type="email"
              required
              value={email}
              onChange={(e) => { setEmail(e.target.value); resetTenants(); }}
              autoComplete="username"
            />
          </label>
          <label>
            Senha
            <input
              name="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {tenants.length > 1 && (
            <fieldset className="tenant-selector">
              <legend>Empresa</legend>
              {tenants.map((t) => (
                <label key={t.id} className={`tenant-option${selectedTenant === t.id ? " selected" : ""}`}>
                  <input
                    type="radio"
                    name="tenant"
                    value={t.id}
                    checked={selectedTenant === t.id}
                    onChange={() => setSelectedTenant(t.id)}
                  />
                  {t.name}
                </label>
              ))}
            </fieldset>
          )}
          <button type="submit" disabled={isPending || (tenants.length > 1 && !selectedTenant)}>
            {isPending ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
