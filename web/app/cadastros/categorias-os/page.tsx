import { AppLayout } from "@/components/app-layout";
import { currentTenantUser } from "@/lib/api";
import { redirect } from "next/navigation";
import { CategoryManager } from "./manager";

export default async function CategoriasOSPage() {
  try {
    const user = await currentTenantUser();
    return (
      <AppLayout user={user}>
        <CategoryManager />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized")
      redirect("/login");
    throw error;
  }
}
