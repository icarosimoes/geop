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

export type CustomerSummary = {
  id: number;
  name: string;
  document: string | null;
  email: string | null;
  phone: string | null;
  active: boolean;
  quote_count: number;
  updated_at: string;
};

export type CustomerDetail = {
  id: number;
  name: string;
  document: string | null;
  document_type: string | null;
  email: string | null;
  phone: string | null;
  whatsapp: string | null;
  address_street: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_neighborhood: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerOption = { id: number; name: string; document: string | null };

export async function listCustomersAction(params?: {
  page?: number; search?: string;
}): Promise<{ items: CustomerSummary[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  q.set("page", String(params?.page ?? 1));
  q.set("page_size", "20");
  if (params?.search) q.set("search", params.search);
  const res = await authFetch(`/commercial/customers?${q}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function getCustomerAction(id: number): Promise<CustomerDetail> {
  const res = await authFetch(`/commercial/customers/${id}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function createCustomerAction(data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: CustomerDetail }> {
  try {
    const res = await authFetch("/commercial/customers", { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao criar cliente." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateCustomerAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: CustomerDetail }> {
  try {
    const res = await authFetch(`/commercial/customers/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar cliente." };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function deleteCustomerAction(id: number): Promise<{ ok: boolean }> {
  const res = await authFetch(`/commercial/customers/${id}`, { method: "DELETE" });
  return { ok: res.ok };
}

export async function listCustomerOptionsAction(): Promise<CustomerOption[]> {
  const res = await authFetch("/commercial/customers/options");
  if (!res.ok) return [];
  return res.json();
}
