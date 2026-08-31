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

export type SaleSummary = {
  id: number;
  number: string | null;
  customer_id: number;
  customer_name: string | null;
  status: string;
  total_value: string;
  installation_status: string;
  delivered_at: string | null;
  invoiced_total: string;
  received_total: string;
  updated_at: string;
};

export type SalesPayment = {
  id: number;
  invoice_id: number;
  amount: string;
  method: string | null;
  paid_at: string;
  reference: string | null;
  notes: string | null;
  created_at: string;
};

export type SalesInvoice = {
  id: number;
  sale_id: number;
  number: string | null;
  nf_number: string | null;
  status: string;
  amount: string;
  issued_at: string | null;
  due_date: string | null;
  notes: string | null;
  paid_total: string;
  payments: SalesPayment[];
  created_at: string;
  updated_at: string;
};

export type SaleDetail = {
  id: number;
  number: string | null;
  quote_id: number;
  customer_id: number;
  customer_name: string | null;
  status: string;
  total_value: string;
  responsible_user_id: number | null;
  responsible_name: string | null;
  delivered_at: string | null;
  installation_status: string;
  installation_scheduled_at: string | null;
  installation_completed_at: string | null;
  installation_notes: string | null;
  notes: string | null;
  invoiced_total: string;
  received_total: string;
  invoices: SalesInvoice[];
  created_at: string;
  updated_at: string;
};

export async function listSalesAction(params?: {
  page?: number; search?: string; status?: string; installation_status?: string;
}): Promise<{ items: SaleSummary[]; total: number; page: number; page_size: number }> {
  const q = new URLSearchParams();
  q.set("page", String(params?.page ?? 1));
  q.set("page_size", "20");
  if (params?.search) q.set("search", params.search);
  if (params?.status) q.set("status", params.status);
  if (params?.installation_status) q.set("installation_status", params.installation_status);
  const res = await authFetch(`/commercial/sales?${q}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function getSaleAction(id: number): Promise<SaleDetail> {
  const res = await authFetch(`/commercial/sales/${id}`);
  if (!res.ok) throw new Error("api_error");
  return res.json();
}

export async function updateSaleAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/commercial/sales/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar venda." };
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function createInvoiceAction(saleId: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: SalesInvoice }> {
  try {
    const res = await authFetch(`/commercial/sales/${saleId}/invoices`, { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao criar fatura." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function updateInvoiceAction(id: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string; data?: SalesInvoice }> {
  try {
    const res = await authFetch(`/commercial/invoices/${id}`, { method: "PATCH", body: JSON.stringify(data) });
    if (!res.ok) return { ok: false, error: "Erro ao atualizar fatura." };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function registerPaymentAction(invoiceId: number, data: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await authFetch(`/commercial/invoices/${invoiceId}/payments`, { method: "POST", body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao registrar recebimento." };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}
