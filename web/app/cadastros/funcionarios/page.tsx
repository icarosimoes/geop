import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { EmployeeManager } from "./manager";

export default async function FuncionariosPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <EmployeeManager user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
