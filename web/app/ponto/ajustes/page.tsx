import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { AdjustmentManager } from "./manager";

export default async function AjustesPontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Ajustes de ponto</h1>
            <p>Solicitações de correção enviadas pelo Portal do Colaborador, aguardando aprovação.</p>
          </div>
        </header>
        <AdjustmentManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
