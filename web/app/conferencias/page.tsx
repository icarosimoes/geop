import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { DiscrepancyReportManager } from "./manager";

export default async function ConferenciasPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <DiscrepancyReportManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
