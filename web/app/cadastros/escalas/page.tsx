import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { ScheduleManager } from "./manager";

export default async function EscalasPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Cadastros</p>
            <h1>Escalas de trabalho</h1>
            <p>Defina o horário previsto de cada funcionário por dia da semana.</p>
          </div>
        </header>
        <ScheduleManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
