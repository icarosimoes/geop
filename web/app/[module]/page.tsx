import { AppLayout } from "@/components/app-layout";
import { KanbanBoard } from "@/components/kanban-board";
import { OperationalModule } from "@/components/operational-module";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { moduleDefinitions } from "@/lib/module-definitions";
import { notFound, redirect } from "next/navigation";

const GENERIC_MODULES = new Set(["inspecoes", "diarios-obra", "manutencao"]);

export default async function ModulePage({ params, searchParams }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { module } = await params;
  const query = await searchParams;
  const definition = moduleDefinitions[module];
  if (!definition) notFound();

  try {
    const user = await currentTenantUser();
    let hydratedDefinition = definition;

    if (module === "solicitacoes-fiscais") {
      type FiscalRequestItem = {
        id: number;
        protocol: string;
        request_type: string;
        title?: string | null;
        apartment: string | null;
        requester: string;
        description?: string | null;
        reservation_number?: string | null;
        sla_deadline?: string | null;
        sla_status?: string | null;
        status: string;
        payload: Record<string, unknown>;
        created_at: string;
        updated_at: string;
      };
      type FiscalRequestPage = { items: FiscalRequestItem[]; total: number; page: number; page_size: number };
      try {
        const page = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const pageSize = 20;
        const search = query.search ?? "";
        const params = new URLSearchParams();
        params.set("page", String(page));
        params.set("page_size", String(pageSize));
        if (search) params.set("search", search);
        const response = await tenantFetch<FiscalRequestPage>(`/fiscal-requests?${params}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: response.items.map((item) => ({
            ...item.payload,
            id: item.id,
            title: item.title || `${item.request_type}${item.apartment ? ` · UH ${item.apartment}` : ""}`,
            category: item.request_type,
            owner: item.requester,
            status: item.status,
            requestType: item.request_type,
            apartment: item.apartment ?? undefined,
            reservationNumber: item.reservation_number ?? (item.payload.reservationNumber as string | undefined),
            slaDeadline: item.sla_deadline ?? undefined,
            slaStatus: item.sla_status ?? undefined,
            description: item.description || String(item.payload.observations ?? item.payload.description ?? ""),
            updatedAt: new Intl.DateTimeFormat("pt-BR", {
              dateStyle: "short",
              timeStyle: "short",
            }).format(new Date(item.updated_at)),
          })),
          serverPagination: { total: response.total, page: response.page, pageSize: response.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "usuarios") {
      type UserItem = {
        id: number;
        name: string;
        email: string;
        phone: string | null;
        role_id: number | null;
        role_name: string | null;
        job_title: string | null;
        sector_name: string | null;
        avatar_url: string | null;
        active: boolean;
        updated_at: string;
      };
      type UserPage = { items: UserItem[]; total: number; page: number; page_size: number };
      type RoleItem = { id: number; code: string; name: string; permission_codes: string[]; user_count: number };
      type RolePage = { items: RoleItem[]; total: number };
      type SectorItem = { id: number; name: string; category: string };
      type SectorPage = { items: SectorItem[]; total: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const [data, rolesData, sectorsData] = await Promise.all([
          tenantFetch<UserPage>(`/users?page=${pg}&page_size=20${searchParam}`),
          tenantFetch<RolePage>("/roles?page=1&page_size=100"),
          tenantFetch<SectorPage>("/registries?category=setor&page=1&page_size=100"),
        ]);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.name,
            category: item.role_name ?? "Sem perfil",
            owner: item.email,
            phone: item.phone ?? undefined,
            status: item.active ? "Ativo" : "Inativo",
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
            roleId: item.role_id ?? undefined,
            jobTitle: item.job_title ?? undefined,
            sectorName: item.sector_name ?? undefined,
            avatarUrl: item.avatar_url ?? undefined,
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
          extraData: {
            roles: rolesData.items.map((r) => ({ id: r.id, name: r.name })),
            sectors: sectorsData.items.map((s) => ({ id: s.id, name: s.name })),
          },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "cadastros") {
      type RegistryItem = { id: number; name: string; category: string; updated_at: string };
      type RegistryPage = { items: RegistryItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<RegistryPage>(`/registries?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.name,
            category: item.category,
            owner: "Administração",
            status: "Ativo",
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "procedimentos") {
      type ProcedureItem = { id: number; name: string; link: string | null; file: string | null; updated_at: string };
      type ProcedurePage = { items: ProcedureItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<ProcedurePage>(`/procedures?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.name,
            category: "Procedimento",
            owner: "Administração",
            status: "Ativo",
            description: item.link ?? undefined,
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "reunioes") {
      type MeetingItem = {
        id: number; title: string; description: string | null;
        scheduled_at: string | null; location: string | null;
        status: string; owner: string; participant_count: number;
        subject_count: number; updated_at: string;
      };
      type MeetingPage = { items: MeetingItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<MeetingPage>(`/meetings?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.title,
            description: item.description ?? undefined,
            category: item.location ?? "Geral",
            owner: item.owner,
            status: item.status,
            scheduledAt: item.scheduled_at ?? undefined,
            updatedAt: item.scheduled_at
              ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.scheduled_at))
              : new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "relatorios-turno") {
      type ShiftReportItem = {
        id: number; title: string; description: string | null;
        shift_date: string | null; shift_type: string | null;
        shift_label: string | null; status: string; owner: string;
        updated_at: string;
      };
      type ShiftReportPage = { items: ShiftReportItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<ShiftReportPage>(`/shift-reports?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.title,
            description: item.description ?? undefined,
            category: item.shift_label ?? item.shift_type ?? "Geral",
            owner: item.owner,
            status: item.status,
            shiftDate: item.shift_date ?? undefined,
            shiftType: item.shift_type ?? undefined,
            updatedAt: item.shift_date
              ? new Intl.DateTimeFormat("pt-BR").format(new Date(item.shift_date))
              : new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "mural") {
      type BulletinItem = {
        id: number; title: string; body: string | null;
        pinned: boolean; author_name: string | null;
        created_at: string; updated_at: string;
      };
      type BulletinPage = { items: BulletinItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<BulletinPage>(`/bulletin?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.title,
            description: item.body ?? undefined,
            category: item.pinned ? "Fixado" : "Normal",
            owner: item.author_name ?? "Sistema",
            status: "Publicado",
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.created_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "preventivas") {
      type PreventivePlanItem = {
        id: number; name: string; description: string | null;
        recurrence: string; category: string | null; priority: string;
        sla_hours: number | null; assigned_user_name: string | null;
        location_name: string | null; active: boolean;
        next_due: string | null; last_generated_at: string | null;
        created_at: string; updated_at: string;
      };
      type PreventivePlanPage = { items: PreventivePlanItem[]; total: number; page: number; page_size: number };
      const recurrenceLabels: Record<string, string> = {
        daily: "Diário", weekly: "Semanal", biweekly: "Quinzenal",
        monthly: "Mensal", quarterly: "Trimestral", semiannual: "Semestral", annual: "Anual",
      };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<PreventivePlanPage>(`/preventive-plans?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.name,
            description: item.description ?? undefined,
            category: recurrenceLabels[item.recurrence] ?? item.recurrence,
            owner: item.assigned_user_name ?? "Não atribuído",
            status: item.active ? "Ativo" : "Inativo",
            priority: item.priority,
            location: item.location_name ?? undefined,
            deadline: item.next_due ?? undefined,
            updatedAt: item.next_due
              ? `Próxima: ${new Intl.DateTimeFormat("pt-BR").format(new Date(item.next_due))}`
              : new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "checklists") {
      type ChecklistItem = {
        id: number; name: string; description: string | null;
        recurrence: string; category: string | null;
        assigned_user_name: string | null; active: boolean;
        next_due: string | null; item_count: number;
        created_at: string; updated_at: string;
      };
      type ChecklistPage = { items: ChecklistItem[]; total: number; page: number; page_size: number };
      const recurrenceLabels: Record<string, string> = {
        daily: "Diário", weekly: "Semanal", biweekly: "Quinzenal", monthly: "Mensal",
      };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<ChecklistPage>(`/checklists/templates?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.name,
            description: item.description ?? undefined,
            category: recurrenceLabels[item.recurrence] ?? item.recurrence,
            owner: item.assigned_user_name ?? "Não atribuído",
            status: item.active ? "Ativo" : "Inativo",
            deadline: item.next_due ?? undefined,
            updatedAt: item.item_count > 0
              ? `${item.item_count} itens`
              : new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "estoque") {
      type StockItem = {
        id: number; name: string; category: string | null;
        unit: string; min_quantity: number; current_quantity: number;
        location_name: string | null; below_min: boolean;
        created_at: string; updated_at: string;
      };
      type StockPage = { items: StockItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<StockPage>(`/stock/items?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.name,
            category: item.category ?? "Geral",
            owner: `${item.current_quantity} ${item.unit}`,
            status: item.below_min ? "Abaixo do mínimo" : "OK",
            location: item.location_name ?? undefined,
            description: item.min_quantity > 0 ? `Mín: ${item.min_quantity} ${item.unit}` : undefined,
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "pendencias") {
      type HandoffItem = {
        id: number; title: string; description: string | null;
        priority: string; category: string | null;
        target_shift: string | null; target_date: string;
        status: string; created_by_name: string | null;
        read_at: string | null; resolved_at: string | null;
        created_at: string; updated_at: string;
      };
      type HandoffPage = { items: HandoffItem[]; total: number; page: number; page_size: number };
      const shiftLabels: Record<string, string> = {
        morning: "Manhã", afternoon: "Tarde", night: "Noite",
      };
      const statusLabels: Record<string, string> = {
        pendente: "Pendente", lido: "Lido", resolvido: "Resolvido",
      };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<HandoffPage>(`/handoffs?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.title,
            description: item.description ?? undefined,
            category: item.target_shift ? shiftLabels[item.target_shift] ?? item.target_shift : "Todos",
            owner: item.created_by_name ?? "Sistema",
            status: statusLabels[item.status] ?? item.status,
            priority: item.priority,
            deadline: item.target_date,
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.target_date)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (module === "ordens-servico") {
      type WorkOrderItem = {
        id: number; title: string; description: string | null;
        status: string; priority: string | null; category: string | null;
        assigned_user_name: string | null; sla_deadline: string | null;
        sector_id: number | null; sector_name: string | null;
        unit: string | null; comments: string | null; deadline: string | null;
        participants: { id: number; name: string }[] | null;
        created_at: string; updated_at: string;
      };
      type WorkOrderPage = { items: WorkOrderItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const status = query.status ?? "";
        const params = new URLSearchParams();
        params.set("page", String(pg));
        params.set("page_size", "100");
        if (search) params.set("search", search);
        if (status) params.set("status", status);
        const data = await tenantFetch<WorkOrderPage>(`/work-orders?${params}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.title,
            description: item.description ?? undefined,
            category: item.category ?? "Geral",
            owner: item.assigned_user_name ?? "Não atribuído",
            status: item.status,
            priority: item.priority ?? undefined,
            slaDeadline: item.sla_deadline ?? undefined,
            sectorId: item.sector_id ?? undefined,
            sectorName: item.sector_name ?? undefined,
            unit: item.unit ?? undefined,
            comments: item.comments ?? undefined,
            deadline: item.deadline ?? undefined,
            participants: item.participants ?? undefined,
            updatedAt: new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    } else if (GENERIC_MODULES.has(module)) {
      type ModuleRecordItem = {
        id: number;
        title: string;
        description: string | null;
        category: string | null;
        owner: string;
        status: string;
        updated_at: string;
      };
      type ModuleRecordPage = { items: ModuleRecordItem[]; total: number; page: number; page_size: number };
      try {
        const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
        const search = query.search ?? "";
        const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
        const data = await tenantFetch<ModuleRecordPage>(`/modules/${module}?page=${pg}&page_size=20${searchParam}`);
        hydratedDefinition = {
          ...definition,
          source: "api",
          records: data.items.map((item) => ({
            id: item.id,
            title: item.title,
            description: item.description ?? undefined,
            category: item.category ?? "Geral",
            owner: item.owner,
            status: item.status,
            updatedAt: new Intl.DateTimeFormat("pt-BR").format(new Date(item.updated_at)),
          })),
          serverPagination: { total: data.total, page: data.page, pageSize: data.page_size, search },
        };
      } catch (error) {
        if (error instanceof Error && error.message === "unauthorized") throw error;
      }
    }

    const content = hydratedDefinition.layout === "kanban"
      ? <KanbanBoard definition={hydratedDefinition} user={user} />
      : <OperationalModule definition={hydratedDefinition} user={user} />;
    return <AppLayout user={user}>{content}</AppLayout>;
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
