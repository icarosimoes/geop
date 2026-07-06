import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { HolidayManager } from "./manager";

export default async function FeriadosPontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Feriados</h1>
            <p>Cadastre os feriados considerados no cálculo de hora extra 100% do espelho de ponto.</p>
          </div>
        </header>
        <HolidayManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
