import { redirect } from "next/navigation";
import { getPlatformToken, platformFetch } from "@/lib/api";
import { TenantsClient } from "./tenants-client";

export type Tenant = {
  id: number;
  name: string;
  slug: string;
  email: string;
  document: string | null;
  trade_name: string | null;
  address_street: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_neighborhood: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  timezone: string;
  status: string;
  users_count: number;
  subscription_status: string | null;
  plan_name: string | null;
  created_at: string | null;
};

export type Plan = { id: number; code: string; name: string; price_cents: number };

export default async function TenantsPage() {
  if (!(await getPlatformToken())) redirect("/login");

  const [tenants, plans] = await Promise.all([
    platformFetch<Tenant[]>("/platform/tenants").catch(() => [] as Tenant[]),
    platformFetch<Plan[]>("/platform/plans").catch(() => [] as Plan[]),
  ]);

  return <TenantsClient initialTenants={tenants} plans={plans} />;
}
