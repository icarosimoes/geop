import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { ShiftManager } from "./manager";

export default async function TurnosPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Cadastros</p>
            <h1>Turnos de trabalho</h1>
            <p>Defina templates de turnos (Manhã, Tarde, Noite, etc.) para usar na escala.</p>
          </div>
        </header>
        <ShiftManager user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
