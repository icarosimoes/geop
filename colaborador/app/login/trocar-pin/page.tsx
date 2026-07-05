"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { changePinAction } from "@/app/actions";

export default function TrocarPinPage() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (newPin.length < 4) {
      setError("O PIN precisa ter pelo menos 4 dígitos.");
      return;
    }
    if (newPin !== confirmPin) {
      setError("Os PINs não coincidem.");
      return;
    }
    startTransition(async () => {
      // old_pin: null — troca obrigatória logo após login com PIN default,
      // o backend já sabe (via must_change_pin) que não precisa validar o PIN antigo aqui.
      const result = await changePinAction(null, newPin);
      if (!result.ok) {
        setError(result.error ?? "Não foi possível trocar o PIN.");
        return;
      }
      router.push("/ponto");
    });
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="logo">R</div>
        <h1>Defina seu novo PIN</h1>
        <p className="subtitle">Por segurança, troque o PIN padrão antes de continuar.</p>

        {error && <div className="error-box">{error}</div>}

        <form onSubmit={handleSubmit}>
          <label>
            Novo PIN
            <input
              type="password"
              required
              maxLength={6}
              inputMode="numeric"
              value={newPin}
              onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ""))}
              autoComplete="new-password"
            />
          </label>
          <label>
            Confirme o novo PIN
            <input
              type="password"
              required
              maxLength={6}
              inputMode="numeric"
              value={confirmPin}
              onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, ""))}
              autoComplete="new-password"
            />
          </label>
          <button type="submit" className="primary" disabled={isPending}>
            {isPending ? "Salvando..." : "Salvar PIN"}
          </button>
        </form>
      </div>
    </main>
  );
}
