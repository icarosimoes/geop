import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { DeviceManager } from "./manager";

export default async function DispositivosPontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Dispositivos</h1>
            <p>Cadastre os relógios de ponto Control iD e obtenha a URL de webhook de cada um.</p>
          </div>
        </header>
        <DeviceManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
