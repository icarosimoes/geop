import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { PunchDashboard } from "./dashboard";

export default async function PontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Batidas</h1>
            <p>Acompanhe as batidas recebidas dos relógios e lance ajustes manuais.</p>
          </div>
        </header>
        <PunchDashboard user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
