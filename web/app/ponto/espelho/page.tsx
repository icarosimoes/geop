import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { EspelhoManager } from "./manager";

export default async function EspelhoPontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Espelho de ponto</h1>
            <p>Batidas, horas trabalhadas, hora extra e adicional noturno por funcionário e período.</p>
          </div>
        </header>
        <EspelhoManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
