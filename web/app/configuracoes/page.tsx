import { AppLayout } from "@/components/app-layout";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { moduleDefinitions, type ModuleDefinition } from "@/lib/module-definitions";
import { redirect } from "next/navigation";
import { SettingsTabs } from "./tabs";

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
type RoleItem = {
  id: number;
  code: string;
  name: string;
  permission_codes: string[];
  user_count: number;
  updated_at: string;
};
type RolePage = { items: RoleItem[]; total: number; page: number; page_size: number };
type SectorItem = { id: number; name: string; category: string };
type SectorPage = { items: SectorItem[]; total: number };
type PermissionItem = { id: number; code: string; name: string; module: string };
type PermissionGroup = { module: string; permissions: PermissionItem[] };

export default async function ConfiguracoesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const query = await searchParams;
  const tab = query.tab ?? "estabelecimento";

  try {
    const user = await currentTenantUser();
    let usersDefinition: ModuleDefinition | undefined;
    let rolesData: RolePage | undefined;
    let permissionsData: PermissionGroup[] | undefined;

    if (tab === "usuarios") {
      const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
      const search = query.search ?? "";
      const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
      const [data, roles, sectors] = await Promise.all([
        tenantFetch<UserPage>(`/users?page=${pg}&page_size=20${searchParam}`),
        tenantFetch<RolePage>("/roles?page=1&page_size=100"),
        tenantFetch<SectorPage>("/registries?category=setor&page=1&page_size=100"),
      ]);
      usersDefinition = {
        ...moduleDefinitions.usuarios,
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
          roles: roles.items.map((r) => ({ id: r.id, name: r.name })),
          sectors: sectors.items.map((s) => ({ id: s.id, name: s.name })),
        },
      };
    } else if (tab === "perfis") {
      [rolesData, permissionsData] = await Promise.all([
        tenantFetch<RolePage>("/roles?page=1&page_size=100"),
        tenantFetch<PermissionGroup[]>("/roles/permissions"),
      ]);
    }

    return (
      <AppLayout user={user}>
        <header className="module-heading">
          <div>
            <p className="eyebrow">Configurações</p>
            <h1>Configurações</h1>
            <p>Gerencie os dados do estabelecimento, integrações e sua conta pessoal.</p>
          </div>
        </header>
        <SettingsTabs
          activeTab={tab}
          user={user}
          usersDefinition={usersDefinition}
          roles={rolesData?.items}
          permissionGroups={permissionsData}
        />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized")
      redirect("/login");
    throw error;
  }
}
