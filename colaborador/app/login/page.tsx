"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { loginAction } from "@/app/actions";

export default function LoginPage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [companySlug, setCompanySlug] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      const result = await loginAction(companySlug.trim(), registrationNumber.trim(), pin);
      if (!result.ok) {
        setError(result.error ?? "Falha no login.");
        return;
      }
      if (result.mustChangePin) {
        router.push("/login/trocar-pin");
        return;
      }
      router.push("/ponto");
    });
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="logo">G</div>
        <h1>Portal do Colaborador</h1>
        <p className="subtitle">Ponto, escala e contracheque</p>

        {error && <div className="error-box">{error}</div>}

        <form onSubmit={handleSubmit}>
          <label>
            Empresa
            <input
              name="company_slug"
              type="text"
              required
              value={companySlug}
              onChange={(e) => setCompanySlug(e.target.value)}
              autoComplete="organization"
              autoCapitalize="none"
            />
            <span className="field-hint">Nome da sua empresa no GEOP (ex.: minha-empresa)</span>
          </label>
          <label>
            Matrícula
            <input
              name="registration_number"
              type="text"
              required
              value={registrationNumber}
              onChange={(e) => setRegistrationNumber(e.target.value)}
              inputMode="numeric"
              autoComplete="username"
            />
          </label>
          <label>
            PIN
            <input
              name="pin"
              type="password"
              required
              maxLength={6}
              inputMode="numeric"
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              autoComplete="current-password"
            />
          </label>
          <button type="submit" className="primary" disabled={isPending}>
            {isPending ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
