"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchStatus, punchAction } from "@/app/actions";
import TabBar from "@/app/components/TabBar";

type ViewState =
  | { kind: "idle" }
  | { kind: "locating" }
  | { kind: "sending" }
  | { kind: "success"; punchedAt: string; status: string | null }
  | { kind: "error"; message: string };

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export default function PontoPage() {
  const router = useRouter();
  const [nextPunchType, setNextPunchType] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [view, setView] = useState<ViewState>({ kind: "idle" });

  useEffect(() => {
    fetchStatus()
      .then((result) => setNextPunchType(result?.nextPunchType ?? "in"))
      .catch(() => router.push("/login"))
      .finally(() => setLoadingStatus(false));
  }, [router]);

  function handlePunch() {
    setView({ kind: "locating" });

    if (!("geolocation" in navigator)) {
      setView({ kind: "error", message: "Geolocalização não é suportada neste navegador." });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setView({ kind: "sending" });
        punchAction(position.coords.latitude, position.coords.longitude)
          .then((result) => {
            if (result.ok && result.punchedAt) {
              setView({ kind: "success", punchedAt: result.punchedAt, status: result.status ?? null });
              fetchStatus().then((s) => setNextPunchType(s?.nextPunchType ?? null));
              return;
            }
            if (result.errorCode === "OUT_OF_RANGE") {
              const distance = result.distanceM != null ? Math.round(result.distanceM) : null;
              setView({
                kind: "error",
                message:
                  distance != null
                    ? `Você está a ${distance}m do estabelecimento. Aproxime-se e tente novamente.`
                    : "Você está fora do raio permitido do estabelecimento.",
              });
              return;
            }
            if (result.errorCode === "LOCATION_NOT_CONFIGURED") {
              setView({
                kind: "error",
                message: "O local de trabalho ainda não foi configurado. Fale com o RH.",
              });
              return;
            }
            setView({ kind: "error", message: result.error ?? "Não foi possível registrar o ponto." });
          })
          .catch(() => router.push("/login"));
      },
      (geoError) => {
        let message = "Não foi possível obter sua localização.";
        if (geoError.code === geoError.PERMISSION_DENIED) {
          message = "Permissão de localização negada. Habilite o acesso à localização para bater o ponto.";
        } else if (geoError.code === geoError.TIMEOUT) {
          message = "Tempo esgotado ao obter localização. Tente novamente.";
        }
        setView({ kind: "error", message });
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  const buttonLabel = nextPunchType === "out" ? "Bater saída" : "Bater entrada";
  const isBusy = view.kind === "locating" || view.kind === "sending";

  return (
    <div className="app-content">
      <header className="app-header">
        <h1>Ponto</h1>
      </header>

      {view.kind === "success" && (
        <div className="success-box">
          {(nextPunchType === "in" ? "Saída" : "Entrada")} registrada às {formatTime(view.punchedAt)}
          {view.status ? ` — ${view.status}` : ""}
        </div>
      )}

      {view.kind === "error" && <div className="error-box">{view.message}</div>}

      <div className="card" style={{ textAlign: "center" }}>
        <button
          type="button"
          className="punch-button"
          onClick={handlePunch}
          disabled={loadingStatus || isBusy}
        >
          {view.kind === "locating"
            ? "Localizando..."
            : view.kind === "sending"
              ? "Enviando..."
              : loadingStatus
                ? "Carregando..."
                : buttonLabel}
        </button>

        {view.kind === "error" && (
          <button type="button" className="secondary" onClick={handlePunch}>
            Tentar novamente
          </button>
        )}
      </div>

      <TabBar />
    </div>
  );
}
