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

export type QuoteItem = {
  id: number;
  item_type: "produto" | "servico";
  stock_item_id: number | null;
  description: string;
  unit: string;
  quantity: string;
  unit_price: string;
  discount_percent: string | null;
  line_total: string;
  sort_order: number;
};

export type QuoteSummary = {
  id: number;
  number: string | null;
  customer_id: number;
  customer_name: string | null;
  title: string;
  status: string;
  total: string;
  valid_until: string | null;
  updated_at: string;
};

export type QuoteDetail = {
  id: number;
  number: string | null;
  customer_id: number;
  customer_name: string | null;
  title: string;
  status: string;
  responsible_user_id: number | null;
  responsible_name: string | null;
  description: string | null;
  conditions: string | null;
  notes: string | null;
  issued_at: string | null;
  valid_until: string | null;
  discount_amount: string;
  subtotal: string;
  total: string;
  decided_at: string | null;
  decision_note: string | null;
  items: QuoteItem[];
  acceptance_url: string | null;
  created_at: string;
  updated_at: string;
};

export async function listQuotesAction(params?: {
  page?: number; search?: string; status?: string; customer_id?: number;
}): Promise<{ items: QuoteSummary[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  q.set("page", String(params?.page ?? 1));
  q.set("page_size", "20");
  if (params?.search) q.set("search", params.search);
  if (params?.status) q.set("status", params.status);
  if (params?.customer_id) q.set("customer_id", String(params.customer_id));
  const res = await authFetch(`/commercial/quotes?${q}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function getQuoteAction(id: number): Promise<QuoteDetail> {
  const res = await authFetch(`/commercial/quotes/${id}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function createQuoteAction(data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: QuoteDetail }> {
  try {
    const res = await authFetch("/commercial/quotes", { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao criar orçamento." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateQuoteAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: QuoteDetail }> {
  try {
    const res = await authFetch(`/commercial/quotes/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao atualizar orçamento." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function deleteQuoteAction(id: number): Promise<{ ok: boolean; error?: string }> {
  const res = await authFetch(`/commercial/quotes/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return { ok: false, error: err?.detail?.message ?? "Erro ao excluir orçamento." };
  }
  return { ok: true };
}

export async function sendQuoteAction(id: number): Promise<{ ok: boolean; error?: string; acceptance_url?: string }> {
  try {
    const res = await authFetch(`/commercial/quotes/${id}/send`, { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao enviar orçamento." };
    }
    const data = await res.json();
    return { ok: true, acceptance_url: data.acceptance_url };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function cancelQuoteAction(id: number): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/commercial/quotes/${id}/cancel`, { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao cancelar orçamento." };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}
