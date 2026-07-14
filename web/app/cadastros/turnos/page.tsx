import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { ShiftManager } from "./manager";

export default async function TurnosPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <ShiftManager user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
