"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ssoExchangeAction } from "@/app/actions";

function SsoExchangeScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setError("Link inválido — nenhum token de acesso foi informado.");
      return;
    }
    ssoExchangeAction(token).then((result) => {
      if (result.ok) {
        router.push("/dashboard");
        return;
      }
      setError(result.error ?? "Não foi possível concluir o acesso.");
    });
  }, [searchParams, router]);

  return (
    <main className="tenant-login-page">
      <div className="tenant-login-brand">
        <span className="tenant-login-logo">G</span>
        <strong>GEOP</strong>
        <span>Gestão operacional</span>
      </div>

      <div className="tenant-login-card">
        {error ? (
          <>
            <p className="eyebrow">Acesso via Solid ERP</p>
            <h2>Não foi possível entrar</h2>
            <div className="login-error">{error}</div>
          </>
        ) : (
          <>
            <p className="eyebrow">Acesso via Solid ERP</p>
            <h2>Entrando no GEOP...</h2>
            <p>Aguarde só um instante, estamos validando seu acesso.</p>
          </>
        )}
      </div>
    </main>
  );
}

export default function SsoPage() {
  return (
    <Suspense fallback={null}>
      <SsoExchangeScreen />
    </Suspense>
  );
}
