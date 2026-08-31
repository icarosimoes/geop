import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { CustomerManager } from "./manager";

export default async function ClientesPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <CustomerManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
