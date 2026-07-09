import { AppLayout } from "@/components/app-layout";
import { currentTenantUser, tenantFetch } from "@/lib/api";
import { redirect } from "next/navigation";
import { ContractsManager } from "./contracts-manager";
import type { ContractSummary } from "./actions";

export default async function ContratosPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const query = await searchParams;

  try {
    const user = await currentTenantUser();

    let contracts: ContractSummary[] = [];
    let contractsTotal = 0;

    const page = Math.max(1, parseInt(query.page ?? "1", 10) || 1);
    const search = query.search ?? "";
    const status = query.status ?? "";
    const contractType = query.contract_type ?? "";

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");
      if (search) params.set("search", search);
      if (status) params.set("status", status);
      if (contractType) params.set("contract_type", contractType);
      const data = await tenantFetch<{ items: ContractSummary[]; total: number; page: number; page_size: number }>(
        `/contracts?${params}`
      );
      contracts = data.items;
      contractsTotal = data.total;
    } catch (error) {
      if (error instanceof Error && error.message === "unauthorized") throw error;
    }

    return (
      <AppLayout user={user}>
        <ContractsManager
          user={user}
          initialContracts={contracts}
          contractsTotal={contractsTotal}
          initialPage={page}
          initialSearch={search}
          initialStatus={status}
          initialContractType={contractType}
        />
      </AppLayout>
    );
  } catch (error) {
    if (error instanceof Error && error.message === "unauthorized") redirect("/login");
    throw error;
  }
}
