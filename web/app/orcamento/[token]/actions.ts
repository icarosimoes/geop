"use server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export type PublicQuoteItem = {
  id: number;
  item_type: "produto" | "servico";
  description: string;
  unit: string;
  quantity: string;
  unit_price: string;
  discount_percent: string | null;
  line_total: string;
};

export type PublicQuote = {
  number: string | null;
  title: string;
  status: string;
  customer_name: string;
  company_name: string;
  description: string | null;
  conditions: string | null;
  notes: string | null;
  issued_at: string | null;
  valid_until: string | null;
  expired: boolean;
  discount_amount: string;
  subtotal: string;
  total: string;
  decided_at: string | null;
  items: PublicQuoteItem[];
};

export async function getPublicQuoteAction(token: string): Promise<{ ok: boolean; data?: PublicQuote; error?: string }> {
  try {
    const res = await fetch(`${apiUrl}/public/quotes/${token}`, { cache: "no-store" });
    if (!res.ok) return { ok: false, error: res.status === 404 ? "Orçamento não encontrado ou link inválido." : "Erro ao carregar orçamento." };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function decidePublicQuoteAction(
  token: string, approved: boolean, decisionNote?: string
): Promise<{ ok: boolean; data?: PublicQuote; error?: string }> {
  try {
    const res = await fetch(`${apiUrl}/public/quotes/${token}/${approved ? "accept" : "reject"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision_note: decisionNote || undefined }),
      cache: "no-store",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao registrar decisão." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function requestSignatureOtpAction(
  token: string, signerName: string, signerDocument: string
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${apiUrl}/public/quotes/${token}/signature/otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signer_name: signerName, signer_document: signerDocument }),
      cache: "no-store",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao enviar o código." };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}

export async function confirmSignatureOtpAction(
  token: string, code: string
): Promise<{ ok: boolean; data?: PublicQuote; error?: string }> {
  try {
    const res = await fetch(`${apiUrl}/public/quotes/${token}/signature/otp/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
      cache: "no-store",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err?.detail?.message ?? "Erro ao confirmar assinatura." };
    }
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "Erro de conexão." };
  }
}
