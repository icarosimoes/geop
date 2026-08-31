import { AppLayout } from "@/components/app-layout";
import { ChecklistManager } from "@/components/checklist-manager";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { redirect } from "next/navigation";

export default async function InspecoesPage() {
  try {
    const user = await currentTenantUser();

    type ChecklistItem = {
      id: number; name: string; description: string | null;
      recurrence: string; category: string | null;
      assigned_user_name: string | null; active: boolean;
      next_due: string | null; item_count: number;
      created_at: string; updated_at: string;
    };
    type ChecklistPage = { items: ChecklistItem[]; total: number; page: number; page_size: number };

    let templates: ChecklistItem[] = [];
    try {
      const data = await tenantFetch<ChecklistPage>("/checklists/templates?page=1&page_size=100");
      templates = data.items;
    } catch (error) {
      if (error instanceof Error && error.message === "unauthorized") throw error;
    }

    return (
      <AppLayout user={user}>
        <ChecklistManager templates={templates.map((t) => ({
          id: t.id,
          name: t.name,
          description: t.description,
          recurrence: t.recurrence,
          category: t.category,
          assigned_user_name: t.assigned_user_name,
          active: t.active,
          item_count: t.item_count,
        }))} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized")
      redirect("/login");
    throw error;
  }
}
