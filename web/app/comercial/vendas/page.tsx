import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { SaleManager } from "./manager";

export default async function VendasPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <SaleManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
