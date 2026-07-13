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

export type SupplierContact = {
  id: number;
  supplier_id: number;
  name: string;
  role: string | null;
  email: string | null;
  phone: string | null;
  whatsapp: string | null;
  is_primary: boolean;
  notes: string | null;
  created_at: string;
};

export type SupplierSummary = {
  id: number;
  name: string;
  document: string | null;
  category: string | null;
  email: string | null;
  phone: string | null;
  active: boolean;
  contact_count: number;
  contract_count: number;
  updated_at: string;
};

export type SupplierDetail = {
  id: number;
  name: string;
  document: string | null;
  document_type: string | null;
  category: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  address_street: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_neighborhood: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  active: boolean;
  notes: string | null;
  contacts: SupplierContact[];
  created_at: string;
  updated_at: string;
};

export async function listSuppliersAction(params?: { page?: number; search?: string }): Promise<{ items: SupplierSummary[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  q.set("page", String(params?.page ?? 1));
  q.set("page_size", "20");
  if (params?.search) q.set("search", params.search);
  const res = await authFetch(`/contracts/suppliers?${q}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function getSupplierAction(id: number): Promise<SupplierDetail> {
  const res = await authFetch(`/contracts/suppliers/${id}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function createSupplierAction(data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: SupplierDetail }> {
  try {
    const res = await authFetch("/contracts/suppliers", { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao criar fornecedor." };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateSupplierAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/suppliers/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar fornecedor." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function deleteSupplierAction(id: number): Promise<{ ok: boolean }> {
  const res = await authFetch(`/contracts/suppliers/${id}`, { method: "DELETE" });
  return { ok: res.ok };
}

export async function createContactAction(supplierId: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/suppliers/${supplierId}/contacts`, { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao criar contato." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateContactAction(contactId: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/contracts/contacts/${contactId}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar contato." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function deleteContactAction(contactId: number): Promise<{ ok: boolean }> {
  const res = await authFetch(`/contracts/contacts/${contactId}`, { method: "DELETE" });
  return { ok: res.ok };
}
