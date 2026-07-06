import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { HourBankManager } from "./manager";

export default async function BancoDeHorasPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <div style={{ display: "flex", alignItems: "baseline", gap: "var(--sp-3)", flexWrap: "wrap" }}>
              <h1 style={{ margin: 0 }}>Banco de horas</h1>
              <p style={{ margin: 0, color: "var(--muted)" }}>Saldo acumulado por funcionário, calculado a partir da escala e das batidas.</p>
            </div>
          </div>
        </header>
        <HourBankManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
