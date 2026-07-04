import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { EmployeeManager } from "./manager";

export default async function FuncionariosPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Cadastros</p>
            <h1>Funcionários</h1>
            <p>Cadastro de RH dos funcionários do hotel, separado das contas de login do sistema.</p>
          </div>
        </header>
        <EmployeeManager user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
