import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { EnrollmentManager } from "./manager";

export default async function VinculosPontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Vínculos</h1>
            <p>Associe a matrícula cadastrada no relógio a um funcionário do Registro.</p>
          </div>
        </header>
        <EnrollmentManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
