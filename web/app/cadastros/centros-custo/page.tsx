import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { CostCenterManager } from "./manager";

export default async function CentrosCustoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <CostCenterManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
