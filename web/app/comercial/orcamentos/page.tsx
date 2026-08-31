import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { QuoteManager } from "./manager";

export default async function OrcamentosPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <QuoteManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
