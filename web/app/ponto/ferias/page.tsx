import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { VacationRequestManager } from "./manager";

export default async function FeriasPontoPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <VacationRequestManager user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
