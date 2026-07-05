"use server";

import { redirect } from "next/navigation";

import { clearEmployeeTokenCookie, getEmployeeToken, setEmployeeTokenCookie } from "@/lib/auth";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

// --- Login ---

export interface LoginResult {
  ok: boolean;
  error?: string;
  mustChangePin?: boolean;
  employeeName?: string;
}

export async function loginAction(
  companySlug: string,
  registrationNumber: string,
  pin: string,
): Promise<LoginResult> {
  const response = await fetch(`${apiUrl}/timeclock/mobile/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_slug: companySlug,
      registration_number: registrationNumber,
      pin,
    }),
    cache: "no-store",
  });

  if (response.status === 401) {
    return { ok: false, error: "Empresa, matrícula ou PIN inválidos." };
  }
  if (response.status === 423) {
    return { ok: false, error: "PIN bloqueado por excesso de tentativas. Tente novamente mais tarde." };
  }
  if (!response.ok) {
    return { ok: false, error: "Não foi possível entrar. Tente novamente." };
  }

  const data = await response.json();
  await setEmployeeTokenCookie(data.access_token, data.expires_in);
  return { ok: true, mustChangePin: data.must_change_pin, employeeName: data.employee_name };
}

export async function logoutAction() {
  await clearEmployeeTokenCookie();
  redirect("/login");
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await getEmployeeToken();
  if (!token) throw new Error("unauthorized");
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (response.status === 401) {
    // Sessão do colaborador não tem refresh — expira e volta pro login.
    await clearEmployeeTokenCookie();
    throw new Error("unauthorized");
  }
  return response;
}

// --- Troca de PIN ---

export interface ChangePinResult {
  ok: boolean;
  error?: string;
}

export async function changePinAction(oldPin: string | null, newPin: string): Promise<ChangePinResult> {
  try {
    const response = await authedFetch("/timeclock/mobile/pin", {
      method: "POST",
      body: JSON.stringify({ old_pin: oldPin, new_pin: newPin }),
    });
    if (response.status === 204) return { ok: true };
    const data = await response.json().catch(() => ({}));
    return { ok: false, error: data?.detail?.message ?? data?.detail?.code ?? "Não foi possível trocar o PIN." };
  } catch {
    redirect("/login");
  }
}

// --- Ponto ---

export interface PunchStatus {
  nextPunchType: string;
}

export async function fetchStatus(): Promise<PunchStatus | null> {
  try {
    const response = await authedFetch("/timeclock/mobile/status");
    if (!response.ok) return null;
    const data = await response.json();
    return { nextPunchType: data.next_punch_type };
  } catch {
    redirect("/login");
  }
}

export interface PunchResult {
  ok: boolean;
  errorCode?: string;
  error?: string;
  distanceM?: number | null;
  punchedAt?: string;
  status?: string | null;
}

export async function punchAction(latitude: number, longitude: number): Promise<PunchResult> {
  let response: Response;
  try {
    response = await authedFetch("/timeclock/mobile/punch", {
      method: "POST",
      body: JSON.stringify({ latitude, longitude }),
    });
  } catch {
    redirect("/login");
  }

  if (response.status === 201) {
    const data = await response.json();
    return { ok: true, punchedAt: data.punched_at, status: data.status };
  }

  const data = await response.json().catch(() => ({}));
  const code = data?.detail?.code;
  return {
    ok: false,
    errorCode: code,
    error: data?.detail?.message ?? "Não foi possível registrar o ponto.",
    distanceM: data?.detail?.distance_m ?? null,
  };
}

// --- Escala ---

export interface ScheduleEntry {
  date: string;
  employee_id: number;
  employee_name: string;
  shift_id: number | null;
  shift_name: string | null;
  shift_color: string | null;
  start_time: string | null;
  end_time: string | null;
  source: string;
}

export async function fetchSchedule(start: string, end: string): Promise<ScheduleEntry[]> {
  try {
    const response = await authedFetch(
      `/timeclock/mobile/schedule?start=${start}&end=${end}`,
    );
    if (!response.ok) return [];
    return response.json();
  } catch {
    redirect("/login");
  }
}

// --- Contracheque ---

export interface Payslip {
  id: number;
  reference_month: string;
  created_at: string;
}

export async function fetchPayslips(): Promise<Payslip[]> {
  try {
    const response = await authedFetch("/timeclock/mobile/payslips");
    if (!response.ok) return [];
    const data = await response.json();
    return data.items ?? [];
  } catch {
    redirect("/login");
  }
}

// --- Banco de horas ---

export interface HourBankEntry {
  id: number;
  reference_date: string;
  expected_minutes: number;
  worked_minutes: number;
  balance_minutes: number;
  source: string;
  notes: string | null;
}

export interface HourBankSummary {
  balance_minutes: number;
  entries: HourBankEntry[];
}

export async function fetchHourBank(): Promise<HourBankSummary | null> {
  try {
    const response = await authedFetch("/timeclock/mobile/hour-bank");
    if (!response.ok) return null;
    return response.json();
  } catch {
    redirect("/login");
  }
}

// --- Ajuste de ponto ---

export interface AdjustmentRequest {
  id: number;
  punch_id: number | null;
  requested_punched_at: string;
  requested_punch_type: string | null;
  reason: string;
  status: string;
  review_notes: string | null;
  created_at: string;
}

export async function fetchAdjustments(): Promise<AdjustmentRequest[]> {
  try {
    const response = await authedFetch("/timeclock/mobile/adjustments");
    if (!response.ok) return [];
    return response.json();
  } catch {
    redirect("/login");
  }
}

export interface CreateAdjustmentResult {
  ok: boolean;
  error?: string;
}

export async function createAdjustmentAction(body: {
  requestedPunchedAt: string;
  requestedPunchType: string;
  reason: string;
  punchId?: number | null;
}): Promise<CreateAdjustmentResult> {
  let response: Response;
  try {
    response = await authedFetch("/timeclock/mobile/adjustments", {
      method: "POST",
      body: JSON.stringify({
        punch_id: body.punchId ?? null,
        requested_punched_at: body.requestedPunchedAt,
        requested_punch_type: body.requestedPunchType,
        reason: body.reason,
      }),
    });
  } catch {
    redirect("/login");
  }

  if (response.status === 201) return { ok: true };
  const data = await response.json().catch(() => ({}));
  return { ok: false, error: data?.detail?.message ?? "Não foi possível enviar a solicitação." };
}
