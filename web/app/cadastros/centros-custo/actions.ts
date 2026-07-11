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

export type CostCenterOption = {
  id: number;
  name: string;
  code: string | null;
};

export type CostCenterSummary = {
  id: number;
  name: string;
  code: string | null;
  parent_name: string | null;
  active: boolean;
  contract_count: number;
  updated_at: string;
};

export type CostCenterDetail = {
  id: number;
  name: string;
  code: string | null;
  parent_id: number | null;
  parent_name: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export async function listCostCentersAction(params?: { page?: number; search?: string }): Promise<{ items: CostCenterSummary[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  q.set("page", String(params?.page ?? 1));
  q.set("page_size", "20");
  if (params?.search) q.set("search", params.search);
  const res = await authFetch(`/contracts/cost-centers?${q}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function listCostCenterOptionsAction(): Promise<CostCenterOption[]> {
  const res = await authFetch("/contracts/cost-centers/options");
  if (!res.ok) return [];
  return res.json();
}

export async function getCostCenterAction(id: number): Promise<CostCenterDetail> {
  const res = await authFetch(`/contracts/cost-centers/${id}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function createCostCenterAction(data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: CostCenterDetail }> {
  try {
    const res = await authFetch("/contracts/cost-centers", { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao criar centro de custo." };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateCostCenterAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/cost-centers/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar centro de custo." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function deleteCostCenterAction(id: number): Promise<{ ok: boolean }> {
  const res = await authFetch(`/contracts/cost-centers/${id}`, { method: "DELETE" });
  return { ok: res.ok };
}
