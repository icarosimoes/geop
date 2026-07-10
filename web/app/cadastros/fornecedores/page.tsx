import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { SupplierManager } from "./manager";

export default async function FornecedoresPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <SupplierManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
