import { AppLayout } from "@/components/app-layout";
import { OperationalModule } from "@/components/operational-module";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { moduleDefinitions } from "@/lib/module-definitions";
import { notFound, redirect } from "next/navigation";

const CATEGORY_MAP: Record<string, string> = {
  setores: "Setor",
  locais: "Local",
  funcoes: "Função",
};

export default async function CadastrosSubPage({
  params,
  searchParams,
}: {
  params: Promise<{ sub: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { sub } = await params;
  const query = await searchParams;
  const category = CATEGORY_MAP[sub];
  if (!category) notFound();

  const defKey = `cadastros/${sub}` as keyof typeof moduleDefinitions;
  const definition = moduleDefinitions[defKey];
  if (!definition) notFound();

  try {
    const user = await currentTenantUser();
    let hydratedDefinition = definition;

    type RegistryItem = {
      id: number;
      name: string;
      category: string;
      updated_at: string;
      latitude: number | null;
      longitude: number | null;
      geofence_radius_m: number | null;
    };
    type RegistryPage = {
      items: RegistryItem[];
      total: number;
      page: number;
      page_size: number;
    };

    try {
      const pg = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
      const search = query.search ?? "";
      const params = new URLSearchParams({
        page: String(pg),
        page_size: "20",
        category,
      });
      if (search) params.set("search", search);
      const data = await tenantFetch<RegistryPage>(
        `/registries?${params}`,
      );
      hydratedDefinition = {
        ...definition,
        source: "api",
        records: data.items.map((item) => ({
          id: item.id,
          title: item.name,
          category: item.category,
          owner: "Administração",
          status: "Ativo",
          updatedAt: new Intl.DateTimeFormat("pt-BR").format(
            new Date(item.updated_at),
          ),
          latitude: item.latitude,
          longitude: item.longitude,
          geofenceRadiusM: item.geofence_radius_m,
        })),
        serverPagination: {
          total: data.total,
          page: data.page,
          pageSize: data.page_size,
          search,
        },
      };
    } catch (error) {
      if (error instanceof Error && error.message === "unauthorized")
        throw error;
    }

    return (
      <AppLayout user={user}>
        <OperationalModule definition={hydratedDefinition} user={user} />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized")
      redirect("/login");
    throw error;
  }
}
