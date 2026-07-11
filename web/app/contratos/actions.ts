"use server";

import { getValidToken, tryRefreshToken } from "@/lib/auth";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

async function authFetch(path: string, init?: RequestInit) {
  const token = await getValidToken();
  const res = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (res.status === 401) {
    const newToken = await tryRefreshToken();
    if (!newToken) throw new Error("unauthorized");
    return fetch(`${apiUrl}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${newToken}`, "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  }
  return res;
}

export type ContractSummary = {
  id: number;
  number: string | null;
  title: string;
  contract_type: string;
  supplier_name: string | null;
  responsible_name: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  total_value: string | null;
  monthly_value: string | null;
  alert_days: number;
  days_until_expiry: number | null;
  expiry_alert: boolean;
  updated_at: string;
};

export type ContractAmendment = {
  id: number;
  contract_id: number;
  amendment_type: string;
  description: string;
  new_end_date: string | null;
  new_value: string | null;
  signed_at: string | null;
  created_by_name: string | null;
  created_at: string;
};

export type ContractApprovalStep = {
  id: number;
  step_order: number;
  approver_user_id: number;
  approver_name: string | null;
  status: string;
  comment: string | null;
  decided_at: string | null;
};

export type ContractDetail = {
  id: number;
  number: string | null;
  title: string;
  contract_type: string;
  supplier_id: number | null;
  supplier_name: string | null;
  responsible_user_id: number | null;
  responsible_name: string | null;
  status: string;
  description: string | null;
  conditions: string | null;
  notes: string | null;
  signed_at: string | null;
  start_date: string | null;
  end_date: string | null;
  alert_days: number;
  auto_renew: boolean;
  indexer: string | null;
  total_value: string | null;
  monthly_value: string | null;
  currency: string;
  payment_frequency: string | null;
  payment_day: number | null;
  cost_center_id: number | null;
  cost_center_name: string | null;
  budget_category: string | null;
  amendments: ContractAmendment[];
  approval_steps: ContractApprovalStep[];
  created_at: string;
  updated_at: string;
};

export type SupplierOption = { id: number; name: string; document: string | null };

export type CostCenterOption = { id: number; name: string; code: string | null };

// ---- Contracts ----

export async function listContractsAction(params?: {
  page?: number; search?: string; status?: string; contract_type?: string;
  supplier_id?: number; expiring_in_days?: number;
}): Promise<{ items: ContractSummary[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  q.set("page", String(params?.page ?? 1));
  q.set("page_size", "20");
  if (params?.search) q.set("search", params.search);
  if (params?.status) q.set("status", params.status);
  if (params?.contract_type) q.set("contract_type", params.contract_type);
  if (params?.supplier_id) q.set("supplier_id", String(params.supplier_id));
  if (params?.expiring_in_days != null) q.set("expiring_in_days", String(params.expiring_in_days));
  const res = await authFetch(`/contracts?${q}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function getContractAction(id: number): Promise<ContractDetail> {
  const res = await authFetch(`/contracts/${id}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function createContractAction(data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: ContractDetail }> {
  try {
    const res = await authFetch("/contracts", { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao criar contrato." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateContractAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: ContractDetail }> {
  try {
    const res = await authFetch(`/contracts/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar contrato." };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateContractStatusAction(id: number, status: string, comment?: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/${id}/status`, { method: "PATCH", body: JSON.stringify({ status, comment }) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar status." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function deleteContractAction(id: number): Promise<{ ok: boolean }> {
  const res = await authFetch(`/contracts/${id}`, { method: "DELETE" });
  return { ok: res.ok };
}

export async function createAmendmentAction(contractId: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/${contractId}/amendments`, { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao criar aditivo." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function approveContractAction(contractId: number, approved: boolean, comment?: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/${contractId}/approve`, { method: "POST", body: JSON.stringify({ approved, comment }) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao aprovar contrato." };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

// ---- Suppliers (opções para o formulário de contrato; CRUD fica em cadastros/fornecedores) ----

export async function listSupplierOptionsAction(): Promise<SupplierOption[]> {
  const res = await authFetch("/contracts/suppliers/options");
  if (!res.ok) return [];
  return res.json();
}

// ---- Cost Centers (opções para o formulário de contrato; CRUD fica em cadastros/centros-custo) ----

export async function listCostCenterOptionsAction(): Promise<CostCenterOption[]> {
  const res = await authFetch("/contracts/cost-centers/options");
  if (!res.ok) return [];
  return res.json();
}
