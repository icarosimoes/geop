import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { PayslipImportManager } from "./manager";

export default async function ContrachequesPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Ponto</p>
            <h1>Contracheques</h1>
            <p>
              Importe em lote os contracheques recebidos do escritório de contabilidade — não
              depende de nenhum sistema de folha específico, basta um ZIP com os PDFs e um
              manifesto casando cada arquivo ao funcionário por CPF.
            </p>
          </div>
        </header>
        <PayslipImportManager user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
