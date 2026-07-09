import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { SupplierManager } from "./manager";

export default async function FornecedoresPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Cadastros</p>
            <h1>Fornecedores</h1>
            <p>Cadastro de fornecedores e contatos usados nos contratos.</p>
          </div>
        </header>
        <SupplierManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
