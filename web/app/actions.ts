"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { setTokenCookies, tryRefreshToken } from "@/lib/auth";
import {
  AttachmentItemSchema,
  EmployeeDetailedSchema,
  EmployeeImportResultSchema,
  EmployeeOptionSchema,
  EmployeeSummarySchema,
  NotificationItemSchema,
  NotificationListSchema,
  PayslipImportResponseSchema,
  RegistryOptionSchema,
  safeParse,
  TimelineEntrySchema,
  TokenResponseSchema,
  UserOptionSchema,
} from "@/lib/schemas";
import { z } from "zod";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

interface LoginResult {
  ok: boolean;
  error?: string;
  multi_tenant?: boolean;
  tenants?: { id: number; name: string }[];
}

export async function loginAction(
  email: string,
  password: string,
  companyId?: number,
): Promise<LoginResult> {
  const body: Record<string, unknown> = { email, password };
  if (companyId) body.company_id = companyId;

  const response = await fetch(`${apiUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (response.status === 422) {
    const data = await response.json();
    if (data.detail?.code === "multi_tenant") {
      return {
        ok: false,
        multi_tenant: true,
        tenants: data.detail.tenants,
      };
    }
  }

  if (!response.ok) {
    return { ok: false, error: "E-mail ou senha inválidos." };
  }

  const data = safeParse(TokenResponseSchema, await response.json());
  await setTokenCookies(data);
  return { ok: true };
}

interface SsoExchangeResult {
  ok: boolean;
  error?: string;
}

export async function ssoExchangeAction(token: string): Promise<SsoExchangeResult> {
  const response = await fetch(`${apiUrl}/auth/sso/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
    cache: "no-store",
  });

  if (!response.ok) {
    return {
      ok: false,
      error: "Link expirado, peça pra abrir o GEOP de novo a partir do ERP.",
    };
  }

  const data = safeParse(TokenResponseSchema, await response.json());
  await setTokenCookies(data);
  return { ok: true };
}

export async function logoutAction() {
  const jar = await cookies();
  jar.delete("tenant_token");
  jar.delete("tenant_refresh_token");
  redirect("/login");
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const jar = await cookies();
  let token = jar.get("tenant_token")?.value;
  if (!token) {
    token = await tryRefreshToken() ?? undefined;
    if (!token) throw new Error("unauthorized");
  }
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (response.status === 401) {
    const newToken = await tryRefreshToken();
    if (!newToken) throw new Error("unauthorized");
    return fetch(`${apiUrl}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${newToken}`, "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  }
  return response;
}

interface MutationResult {
  ok: boolean;
  error?: string;
  data?: Record<string, unknown>;
}

// --- Suporte ---

export interface SupportRequestPayload {
  subject: string;
  priority?: "BAIXA" | "MEDIA" | "ALTA";
  contact_name: string;
  contact_whatsapp: string;
  message?: string;
}

export async function createSupportRequestAction(body: SupportRequestPayload): Promise<MutationResult> {
  const response = await authedFetch("/support/request", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao enviar pedido de suporte." };
  }
  return { ok: true, data: await response.json() };
}

export interface SupportRequestRecord {
  id: number;
  subject: string | null;
  priority: string;
  contact_name: string;
  contact_whatsapp: string;
  message: string | null;
  status: string;
  response_message: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchMySupportRequestsAction(): Promise<SupportRequestRecord[]> {
  const response = await authedFetch("/support/requests");
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return [];
  }
  return response.json();
}

export interface FiscalRequestPayload {
  request_type: string;
  title: string;
  apartment?: string;
  requester: string;
  description?: string;
  status?: string;
  payload?: Record<string, unknown>;
}

export async function createFiscalRequestAction(body: FiscalRequestPayload): Promise<MutationResult> {
  const response = await authedFetch("/fiscal-requests", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar solicitação." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateFiscalRequestAction(
  id: number,
  body: Partial<FiscalRequestPayload>,
): Promise<MutationResult> {
  const response = await authedFetch(`/fiscal-requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar solicitação." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteFiscalRequestAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/fiscal-requests/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir solicitacao." };
  }
  return { ok: true };
}

export interface UserPayload {
  name: string;
  email: string;
  phone?: string;
  password?: string;
  role_id?: number | null;
  job_title?: string;
  sector_id?: number | null;
  active?: boolean;
}

export interface InvitePayload {
  name: string;
  email: string;
  phone?: string;
  role_id?: number | null;
  job_title?: string;
  sector_id?: number | null;
}

export async function createUserAction(body: UserPayload): Promise<MutationResult> {
  const response = await authedFetch("/users", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 409) return { ok: false, error: "E-mail já cadastrado." };
    return { ok: false, error: "Erro ao criar usuário." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateUserAction(id: number, body: Partial<UserPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar usuário." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteUserAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/users/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 400) return { ok: false, error: "Não é possível excluir seu próprio usuário." };
    return { ok: false, error: "Erro ao excluir usuário." };
  }
  return { ok: true };
}

export async function inviteUserAction(body: InvitePayload): Promise<MutationResult> {
  const response = await authedFetch("/users/invite", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 409) return { ok: false, error: "E-mail já cadastrado." };
    return { ok: false, error: "Erro ao convidar usuário." };
  }
  return { ok: true, data: await response.json() };
}

export async function setPasswordAction(token: string, password: string): Promise<MutationResult> {
  const response = await fetch(`${apiUrl}/auth/set-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 401) return { ok: false, error: "Token inválido ou expirado." };
    return { ok: false, error: "Erro ao definir senha." };
  }
  return { ok: true };
}

export async function uploadAvatarAction(userId: number, formData: FormData): Promise<MutationResult> {
  const jar = await cookies();
  const token = jar.get("tenant_token")?.value;
  if (!token) throw new Error("unauthorized");
  const response = await fetch(`${apiUrl}/users/${userId}/avatar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao enviar avatar." };
  }
  return { ok: true, data: await response.json() };
}

export interface RegistryPayload {
  name: string;
  category: string;
}

export async function createRegistryAction(body: RegistryPayload): Promise<MutationResult> {
  const response = await authedFetch("/registries", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar cadastro." };
  }
  return { ok: true, data: await response.json() };
}

export interface RegistryUpdatePayload {
  name?: string;
  latitude?: number | null;
  longitude?: number | null;
  geofence_radius_m?: number | null;
}

export async function updateRegistryAction(id: number, body: RegistryUpdatePayload, category: string): Promise<MutationResult> {
  const response = await authedFetch(`/registries/${id}?category=${encodeURIComponent(category)}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar cadastro." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteRegistryAction(id: number, category: string): Promise<MutationResult> {
  const response = await authedFetch(`/registries/${id}?category=${encodeURIComponent(category)}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir cadastro." };
  }
  return { ok: true };
}

export interface ModuleRecordPayload {
  title: string;
  description?: string;
  category?: string;
  status?: string;
  owner_user_id?: number;
  notify_user_ids?: number[];
  payload?: Record<string, unknown>;
}

export async function createModuleRecordAction(moduleSlug: string, body: ModuleRecordPayload): Promise<MutationResult> {
  const response = await authedFetch(`/modules/${moduleSlug}`, { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar registro." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateModuleRecordAction(moduleSlug: string, id: number, body: Partial<ModuleRecordPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/modules/${moduleSlug}/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar registro." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteModuleRecordAction(moduleSlug: string, id: number): Promise<MutationResult> {
  const response = await authedFetch(`/modules/${moduleSlug}/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir registro." };
  }
  return { ok: true };
}

// --- Registry Options ---

export type RegistryOption = z.infer<typeof RegistryOptionSchema>;

export async function fetchRegistryOptions(
  category: string,
): Promise<RegistryOption[]> {
  const response = await authedFetch(
    `/registries/options/${encodeURIComponent(category)}`,
  );
  if (!response.ok) return [];
  return safeParse(z.array(RegistryOptionSchema), await response.json());
}

// --- Procedures ---

export interface ProcedurePayload {
  name: string;
  link?: string | null;
  file?: string | null;
}

export async function createProcedureAction(body: ProcedurePayload): Promise<MutationResult> {
  const response = await authedFetch("/procedures", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar procedimento." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateProcedureAction(id: number, body: Partial<ProcedurePayload>): Promise<MutationResult> {
  const response = await authedFetch(`/procedures/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar procedimento." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteProcedureAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/procedures/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir procedimento." };
  }
  return { ok: true };
}

export type TimelineEntry = z.infer<typeof TimelineEntrySchema>;

export async function fetchTimeline(entityType: string, entityId: number): Promise<TimelineEntry[]> {
  const response = await authedFetch(`/timeline/${entityType}/${entityId}`);
  if (!response.ok) return [];
  const data = await response.json();
  return safeParse(z.array(TimelineEntrySchema), data.items ?? []);
}

export async function addCommentAction(entityType: string, entityId: number, message: string): Promise<MutationResult> {
  const response = await authedFetch(`/timeline/${entityType}/${entityId}/comment`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao adicionar comentário." };
  }
  return { ok: true, data: await response.json() };
}

export type NotificationItem = z.infer<typeof NotificationItemSchema>;

export type NotificationListResult = z.infer<typeof NotificationListSchema>;

export async function fetchNotifications(page = 1, unreadOnly = false): Promise<NotificationListResult> {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (unreadOnly) params.set("unread_only", "true");
  const response = await authedFetch(`/notifications?${params}`);
  if (!response.ok) return { items: [], total: 0, unread: 0, page: 1, page_size: 20 };
  return safeParse(NotificationListSchema, await response.json());
}

export async function markNotificationRead(id: number): Promise<void> {
  await authedFetch(`/notifications/${id}/read`, { method: "PATCH" });
}

export async function markAllNotificationsRead(): Promise<void> {
  await authedFetch("/notifications/read-all", { method: "POST" });
}

export async function updateProfileAction(body: { name?: string; phone?: string; password?: string }): Promise<MutationResult> {
  const response = await authedFetch("/users/me", { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 422) return { ok: false, error: "Nenhum campo alterado." };
    return { ok: false, error: "Erro ao atualizar perfil." };
  }
  return { ok: true, data: await response.json() };
}

// --- Attachments ---

export type AttachmentItem = z.infer<typeof AttachmentItemSchema>;

export async function uploadAttachmentAction(
  entityType: string,
  entityId: number,
  file: File,
): Promise<MutationResult> {
  const jar = await cookies();
  let token = jar.get("tenant_token")?.value;
  if (!token) {
    token = (await tryRefreshToken()) ?? undefined;
    if (!token) throw new Error("unauthorized");
  }

  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({
    entity_type: entityType,
    entity_id: String(entityId),
  });

  let response = await fetch(
    `${apiUrl}/attachments?${params}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
      cache: "no-store",
    },
  );

  if (response.status === 401) {
    const newToken = await tryRefreshToken();
    if (!newToken) throw new Error("unauthorized");
    response = await fetch(`${apiUrl}/attachments?${params}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${newToken}` },
      body: formData,
      cache: "no-store",
    });
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    return {
      ok: false,
      error: data?.detail?.message ?? "Erro ao enviar anexo.",
    };
  }
  return { ok: true, data: await response.json() };
}

export async function fetchAttachments(
  entityType: string,
  entityId: number,
): Promise<AttachmentItem[]> {
  const params = new URLSearchParams({
    entity_type: entityType,
    entity_id: String(entityId),
  });
  const response = await authedFetch(`/attachments?${params}`);
  if (!response.ok) return [];
  const data = await response.json();
  return safeParse(z.array(AttachmentItemSchema), data.items ?? []);
}

export async function deleteAttachmentAction(
  id: number,
): Promise<MutationResult> {
  const response = await authedFetch(`/attachments/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir anexo." };
  }
  return { ok: true };
}

export async function getAttachmentDownloadUrl(id: number): Promise<string> {
  return `${apiUrl}/attachments/${id}/download`;
}

export interface EvolutionSettings {
  has_credentials: boolean;
  api_url?: string | null;
  instance?: string | null;
}

export async function getEvolutionSettings(): Promise<EvolutionSettings> {
  const response = await authedFetch("/settings/evolution");
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { has_credentials: false };
  }
  return response.json();
}

export async function saveEvolutionSettings(body: { api_url: string; api_key: string; instance: string }): Promise<MutationResult> {
  const response = await authedFetch("/settings/evolution", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao salvar configurações da Evolution." };
  }
  return { ok: true, data: await response.json() };
}

export interface TimeclockSettings {
  overtime_paid_in_cash: boolean;
  cargo_salaries: Record<string, number>;
}

export async function getTimeclockSettings(): Promise<TimeclockSettings> {
  const response = await authedFetch("/settings/timeclock");
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { overtime_paid_in_cash: false, cargo_salaries: {} };
  }
  return response.json();
}

export async function saveTimeclockSettings(body: TimeclockSettings): Promise<MutationResult> {
  const response = await authedFetch("/settings/timeclock", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao salvar configurações de ponto." };
  }
  return { ok: true, data: await response.json() };
}

export interface BrevoSettings {
  has_credentials: boolean;
  from_address?: string | null;
  from_name?: string | null;
}

export async function getBrevoSettings(): Promise<BrevoSettings> {
  const response = await authedFetch("/settings/brevo");
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { has_credentials: false };
  }
  return response.json();
}

export async function saveBrevoSettings(body: { api_key: string; from_address: string; from_name: string }): Promise<MutationResult> {
  const response = await authedFetch("/settings/brevo", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao salvar configurações do Brevo." };
  }
  return { ok: true, data: await response.json() };
}

export async function testBrevoSettings(to: string): Promise<MutationResult> {
  const response = await authedFetch("/settings/brevo/test", { method: "POST", body: JSON.stringify({ to }) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 422) return { ok: false, error: "Salve a configuração antes de testar." };
    return { ok: false, error: "Falha ao enviar o e-mail de teste — confira a API key e o remetente." };
  }
  return { ok: true, data: await response.json() };
}

// --- Dados do Estabelecimento ---

export interface CompanyInfo {
  id: number;
  name: string;
  slug: string;
  email: string | null;
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
}

export async function getCompanyInfo(): Promise<CompanyInfo | null> {
  const response = await authedFetch("/settings/company");
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return null;
  }
  return response.json();
}

export async function updateCompanyInfo(
  body: {
    name?: string;
    email?: string;
    document?: string;
    trade_name?: string;
    address_street?: string;
    address_number?: string;
    address_complement?: string;
    address_neighborhood?: string;
    address_city?: string;
    address_state?: string;
    address_zip?: string;
    timezone?: string;
  },
): Promise<MutationResult> {
  const response = await authedFetch("/settings/company", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao salvar dados do estabelecimento." };
  }
  return { ok: true, data: await response.json() };
}

export type UserOption = z.infer<typeof UserOptionSchema>;

export async function searchUsers(q: string): Promise<UserOption[]> {
  const response = await authedFetch(`/users/search?q=${encodeURIComponent(q)}`);
  if (!response.ok) return [];
  return safeParse(z.array(UserOptionSchema), await response.json());
}

// --- Funcionários (cadastro de RH, separado de User/login) ---

export type EmployeeOption = z.infer<typeof EmployeeOptionSchema>;

export type Employee = z.infer<typeof EmployeeSummarySchema>;

export type EmployeeDetailed = z.infer<typeof EmployeeDetailedSchema>;

export interface EmployeeListResponse {
  items: Employee[];
  total: number;
  page: number;
  page_size: number;
}

export interface EmployeePayload {
  name: string;
  cpf: string;
  rg?: string | null;
  birth_date?: string | null;
  phone?: string | null;
  personal_email?: string | null;
  address_street?: string | null;
  address_number?: string | null;
  address_complement?: string | null;
  address_neighborhood?: string | null;
  address_city?: string | null;
  address_state?: string | null;
  address_zip?: string | null;
  status?: string;
  user_id?: number | null;
  job_title?: string | null;
  hire_date?: string | null;
  termination_date?: string | null;
  registration_number?: string | null;
  salary?: number | null;
  sector_id?: number | null;
}

export async function fetchEmployees(params: {
  page?: number;
  pageSize?: number;
  status?: string;
}): Promise<EmployeeListResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page ?? 1));
  qs.set("page_size", String(params.pageSize ?? 20));
  if (params.status) qs.set("status", params.status);
  const response = await authedFetch(`/employees?${qs.toString()}`);
  if (!response.ok) return { items: [], total: 0, page: 1, page_size: 20 };
  const data = await response.json();
  return {
    ...data,
    items: safeParse(z.array(EmployeeSummarySchema), data.items ?? []),
  };
}

export async function fetchEmployee(id: number): Promise<EmployeeDetailed | null> {
  const response = await authedFetch(`/employees/${id}`);
  if (!response.ok) return null;
  return safeParse(EmployeeDetailedSchema, await response.json());
}

export async function searchEmployees(q: string): Promise<EmployeeOption[]> {
  const response = await authedFetch(`/employees/search?q=${encodeURIComponent(q)}`);
  if (!response.ok) return [];
  return safeParse(z.array(EmployeeOptionSchema), await response.json());
}

export interface CepLookupResult {
  ok: boolean;
  address_street?: string;
  address_neighborhood?: string;
  address_city?: string;
  address_state?: string;
}

export async function lookupCepAction(cep: string): Promise<CepLookupResult> {
  const digits = cep.replace(/\D/g, "");
  if (digits.length !== 8) return { ok: false };

  try {
    const response = await fetch(`https://viacep.com.br/ws/${digits}/json/`, {
      cache: "no-store",
    });
    if (!response.ok) return { ok: false };
    const data = await response.json();
    if (data.erro) return { ok: false };
    return {
      ok: true,
      address_street: data.logradouro || undefined,
      address_neighborhood: data.bairro || undefined,
      address_city: data.localidade || undefined,
      address_state: data.uf || undefined,
    };
  } catch {
    return { ok: false };
  }
}

export interface CnpjLookupResult {
  ok: boolean;
  rateLimited?: boolean;
  name?: string;
  trade_name?: string;
  email?: string;
  phone?: string;
  address_street?: string;
  address_number?: string;
  address_complement?: string;
  address_neighborhood?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
}

export async function lookupCnpjAction(cnpj: string): Promise<CnpjLookupResult> {
  const digits = cnpj.replace(/\D/g, "");
  if (digits.length !== 14) return { ok: false };

  try {
    const response = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${digits}`, {
      cache: "no-store",
    });
    if (response.status === 429) return { ok: false, rateLimited: true };
    if (!response.ok) return { ok: false };
    const data = await response.json();
    return {
      ok: true,
      name: data.razao_social || undefined,
      trade_name: data.nome_fantasia || undefined,
      email: data.email || undefined,
      phone: data.ddd_telefone_1 || undefined,
      address_street: data.logradouro || undefined,
      address_number: data.numero || undefined,
      address_complement: data.complemento || undefined,
      address_neighborhood: data.bairro || undefined,
      address_city: data.municipio || undefined,
      address_state: data.uf || undefined,
      address_zip: data.cep || undefined,
    };
  } catch {
    return { ok: false };
  }
}

export async function createEmployeeAction(body: EmployeePayload): Promise<MutationResult> {
  const response = await authedFetch("/employees", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao criar funcionário." };
  return { ok: true, data: await response.json() };
}

export async function updateEmployeeAction(
  id: number,
  body: Partial<EmployeePayload>,
): Promise<MutationResult> {
  const response = await authedFetch(`/employees/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao atualizar funcionário." };
  return { ok: true, data: await response.json() };
}

export async function deleteEmployeeAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/employees/${id}`, { method: "DELETE" });
  if (!response.ok) return { ok: false, error: "Erro ao excluir funcionário." };
  return { ok: true };
}

export async function uploadEmployeeAvatarAction(
  employeeId: number,
  formData: FormData,
): Promise<MutationResult> {
  const jar = await cookies();
  const token = jar.get("tenant_token")?.value;
  if (!token) throw new Error("unauthorized");
  const response = await fetch(`${apiUrl}/employees/${employeeId}/avatar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao enviar avatar." };
  }
  return { ok: true, data: await response.json() };
}

export async function resetEmployeePinAction(
  employeeId: number,
): Promise<{ ok: true; pin: string } | { ok: false; error: string }> {
  const response = await authedFetch(`/timeclock/employees/${employeeId}/pin/reset`, {
    method: "POST",
  });
  if (!response.ok) return { ok: false, error: "Erro ao resetar PIN." };
  const data = (await response.json()) as { pin: string };
  return { ok: true, pin: data.pin };
}

export type EmployeeImportResult = z.infer<typeof EmployeeImportResultSchema>;

export async function importEmployeesAction(formData: FormData): Promise<
  { ok: true; result: EmployeeImportResult } | { ok: false; error: string }
> {
  const jar = await cookies();
  const token = jar.get("tenant_token")?.value;
  if (!token) throw new Error("unauthorized");
  const response = await fetch(`${apiUrl}/employees/import`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao importar funcionários." };
  }
  return { ok: true, result: safeParse(EmployeeImportResultSchema, await response.json()) };
}

export type PayslipImportResponse = z.infer<typeof PayslipImportResponseSchema>;

export async function importPayslipsAction(formData: FormData): Promise<
  { ok: true; result: PayslipImportResponse } | { ok: false; error: string }
> {
  const jar = await cookies();
  const token = jar.get("tenant_token")?.value;
  if (!token) throw new Error("unauthorized");
  const response = await fetch(`${apiUrl}/timeclock/employees/payslips/import`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    const detail = await response.json().catch(() => null);
    const code = detail?.detail?.code;
    const messages: Record<string, string> = {
      invalid_manifest_type: "O manifesto precisa ser um arquivo .csv.",
      invalid_archive_type: "O arquivo precisa ser um .zip.",
      invalid_archive: "Não foi possível ler o arquivo .zip.",
      invalid_archive_entry: "O .zip contém um caminho de arquivo inválido.",
      empty_manifest: "O manifesto está vazio.",
      invalid_encoding: "Não foi possível ler a codificação do manifesto.",
    };
    return { ok: false, error: messages[code] ?? "Erro ao importar contracheques." };
  }
  return { ok: true, result: safeParse(PayslipImportResponseSchema, await response.json()) };
}

export async function createEmployeeExternalIdAction(
  employeeId: number,
  system: string,
  externalId: string,
): Promise<MutationResult> {
  const response = await authedFetch(`/employees/${employeeId}/external-ids`, {
    method: "POST",
    body: JSON.stringify({ system, external_id: externalId }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao criar identificador externo." };
  return { ok: true, data: await response.json() };
}

export async function deleteEmployeeExternalIdAction(
  employeeId: number,
  externalIdId: number,
): Promise<MutationResult> {
  const response = await authedFetch(`/employees/${employeeId}/external-ids/${externalIdId}`, {
    method: "DELETE",
  });
  if (!response.ok) return { ok: false, error: "Erro ao excluir identificador externo." };
  return { ok: true };
}

// --- Meetings ---

export interface MeetingPayload {
  title: string;
  description?: string;
  scheduled_at?: string;
  location?: string;
  status?: string;
  owner_user_id?: number;
  participants?: { user_id: number; role: string }[];
  subjects?: { title: string; description?: string; sort_order?: number }[];
  notify_user_ids?: number[];
}

export async function createMeetingAction(body: MeetingPayload): Promise<MutationResult> {
  const response = await authedFetch("/meetings", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar reunião." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateMeetingAction(id: number, body: Partial<MeetingPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/meetings/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar reunião." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteMeetingAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/meetings/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir reunião." };
  }
  return { ok: true };
}

export async function cloneMeetingAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/meetings/${id}/clone`, { method: "POST" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao duplicar reunião." };
  }
  return { ok: true, data: await response.json() };
}

// --- Shift Reports ---

export interface ShiftReportPayload {
  title: string;
  description?: string;
  shift_date?: string;
  shift_type?: string;
  started_at?: string;
  ended_at?: string;
  status?: string;
  supervisor?: string;
  occupation?: string;
  average_daily?: string;
  guests?: number;
  uhs?: number;
  maintenance_count?: number;
  cleaning?: number;
  walk_in?: number;
  input_quantity?: number;
  output_quantity?: number;
  return_of_customers?: number;
  observations?: string;
  notes_ab?: string;
  notes_reception?: string;
  notes_reservations?: string;
  notes_governance?: string;
  notes_maintenance?: string;
  notes_ti?: string;
  notes_security?: string;
  owner_user_id?: number;
  notify_user_ids?: number[];
}

export async function createShiftReportAction(body: ShiftReportPayload): Promise<MutationResult> {
  const response = await authedFetch("/shift-reports", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar relatório." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateShiftReportAction(id: number, body: Partial<ShiftReportPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/shift-reports/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar relatório." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteShiftReportAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/shift-reports/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir relatório." };
  }
  return { ok: true };
}

export async function fetchShiftReportDetail(id: number) {
  const response = await authedFetch(`/shift-reports/${id}`);
  if (!response.ok) return null;
  return response.json();
}

// --- Roles ---

export interface RolePayload {
  code: string;
  name: string;
  permission_codes: string[];
}

export async function listRolesAction(): Promise<{ items: { id: number; code: string; name: string; permission_codes: string[]; user_count: number }[]; total: number }> {
  const response = await authedFetch("/roles?page=1&page_size=100");
  if (!response.ok) return { items: [], total: 0 };
  return response.json();
}

export async function createRoleAction(body: RolePayload): Promise<MutationResult> {
  const response = await authedFetch("/roles", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar cargo." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateRoleAction(id: number, body: Partial<RolePayload>): Promise<MutationResult> {
  const response = await authedFetch(`/roles/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar cargo." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteRoleAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/roles/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    if (response.status === 409) return { ok: false, error: "Cargo possui usuários atribuídos." };
    return { ok: false, error: "Erro ao excluir cargo." };
  }
  return { ok: true };
}

export async function listPermissionsAction(): Promise<{ module: string; permissions: { id: number; code: string; name: string }[] }[]> {
  const response = await authedFetch("/roles/permissions");
  if (!response.ok) return [];
  return response.json();
}

// --- Preventive Plans ---

export interface PreventivePlanPayload {
  name: string;
  description?: string;
  recurrence: string;
  category?: string;
  priority?: string;
  sla_hours?: number;
  location_id?: number;
  assigned_user_id?: number;
  next_due?: string;
}

export async function createPreventivePlanAction(body: PreventivePlanPayload): Promise<MutationResult> {
  const response = await authedFetch("/preventive-plans", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar plano preventivo." };
  }
  return { ok: true, data: await response.json() };
}

export async function updatePreventivePlanAction(id: number, body: Partial<PreventivePlanPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/preventive-plans/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar plano preventivo." };
  }
  return { ok: true, data: await response.json() };
}

export async function deletePreventivePlanAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/preventive-plans/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir plano preventivo." };
  }
  return { ok: true };
}

export async function generatePreventiveOrdersAction(): Promise<MutationResult> {
  const response = await authedFetch("/preventive-plans/generate", { method: "POST" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao gerar OS preventivas." };
  }
  return { ok: true, data: await response.json() };
}

// --- Checklists ---

export interface ChecklistTemplatePayload {
  name: string;
  description?: string;
  recurrence: string;
  category?: string;
  assigned_user_id?: number;
  next_due?: string;
  items?: { label: string; sort_order: number }[];
}

export interface ChecklistTemplateDetail {
  id: number;
  name: string;
  description: string | null;
  recurrence: string;
  category: string | null;
  assigned_user_id: number | null;
  assigned_user_name: string | null;
  active: boolean;
  next_due: string | null;
  item_count: number;
  items: { id: number; label: string; sort_order: number }[];
}

export async function fetchChecklistTemplateAction(id: number): Promise<ChecklistTemplateDetail | null> {
  const response = await authedFetch(`/checklists/templates/${id}`);
  if (!response.ok) return null;
  return response.json();
}

export async function createChecklistTemplateAction(body: ChecklistTemplatePayload): Promise<MutationResult> {
  const response = await authedFetch("/checklists/templates", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar template de checklist." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateChecklistTemplateAction(id: number, body: Partial<ChecklistTemplatePayload>): Promise<MutationResult> {
  const response = await authedFetch(`/checklists/templates/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar template." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteChecklistTemplateAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/checklists/templates/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir template." };
  }
  return { ok: true };
}

export async function toggleChecklistItemAction(executionId: number, itemId: number, checked: boolean): Promise<MutationResult> {
  const response = await authedFetch(`/checklists/executions/${executionId}/toggle`, {
    method: "POST", body: JSON.stringify({ item_id: itemId, checked }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar item." };
  }
  return { ok: true, data: await response.json() };
}

export async function completeChecklistAction(executionId: number, notes?: string): Promise<MutationResult> {
  const response = await authedFetch(`/checklists/executions/${executionId}/complete`, {
    method: "POST", body: JSON.stringify({ notes: notes ?? null }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao concluir checklist." };
  }
  return { ok: true, data: await response.json() };
}

export async function generateChecklistExecutionsAction(): Promise<MutationResult> {
  const response = await authedFetch("/checklists/generate", { method: "POST" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao gerar execuções." };
  }
  return { ok: true, data: await response.json() };
}

// --- Stock ---

export interface StockItemPayload {
  name: string;
  category?: string;
  unit?: string;
  min_quantity?: number;
  current_quantity?: number;
  location_id?: number;
}

export async function createStockItemAction(body: StockItemPayload): Promise<MutationResult> {
  const response = await authedFetch("/stock/items", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar item." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateStockItemAction(id: number, body: Partial<StockItemPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/stock/items/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar item." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteStockItemAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/stock/items/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir item." };
  }
  return { ok: true };
}

export interface StockMovementPayload {
  item_id: number;
  movement_type: string;
  quantity: number;
  reason?: string;
  work_order_id?: number;
}

export async function createStockMovementAction(body: StockMovementPayload): Promise<MutationResult> {
  const response = await authedFetch("/stock/movements", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    const data = await response.json().catch(() => ({}));
    return { ok: false, error: data?.detail ?? "Erro ao registrar movimentação." };
  }
  return { ok: true, data: await response.json() };
}

// --- Handoffs ---

export interface HandoffPayload {
  title: string;
  description?: string;
  priority?: string;
  category?: string;
  target_shift?: string;
  target_date?: string;
  shift_report_id?: number;
}

export async function createHandoffAction(body: HandoffPayload): Promise<MutationResult> {
  const response = await authedFetch("/handoffs", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar pendência." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateHandoffAction(id: number, body: Partial<HandoffPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/handoffs/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar pendência." };
  }
  return { ok: true, data: await response.json() };
}

export async function markHandoffReadAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/handoffs/${id}/read`, { method: "POST" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao marcar como lida." };
  }
  return { ok: true, data: await response.json() };
}

export async function resolveHandoffAction(id: number, notes?: string): Promise<MutationResult> {
  const response = await authedFetch(`/handoffs/${id}/resolve`, {
    method: "POST", body: JSON.stringify({ resolution_notes: notes ?? null }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao resolver pendência." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteHandoffAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/handoffs/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir pendência." };
  }
  return { ok: true };
}

export interface HandoffItem {
  id: number;
  title: string;
  description: string | null;
  priority: string;
  category: string | null;
  target_shift: string | null;
  target_date: string;
  status: string;
  created_by_name: string | null;
  read_at: string | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  created_at: string;
}

export async function fetchHandoffsForReportAction(shiftReportId: number): Promise<HandoffItem[]> {
  const response = await authedFetch(`/handoffs?shift_report_id=${shiftReportId}&page_size=50`);
  if (!response.ok) return [];
  const data = await response.json();
  return data.items ?? [];
}

// --- Work Orders ---

export interface WorkOrderPayload {
  title: string;
  description?: string;
  priority?: string;
  category?: string;
  location_id?: number;
  maintenance_id?: number;
  assigned_user_id?: number;
  notify_user_ids?: number[];
  sla_hours?: number;
  sector_id?: number;
  unit?: string;
  comments?: string;
  deadline?: string;
  participant_ids?: number[];
}

export async function createWorkOrderAction(body: WorkOrderPayload): Promise<MutationResult> {
  const response = await authedFetch("/work-orders", { method: "POST", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar ordem de serviço." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateWorkOrderAction(id: number, body: Partial<WorkOrderPayload>): Promise<MutationResult> {
  const response = await authedFetch(`/work-orders/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar ordem de serviço." };
  }
  return { ok: true, data: await response.json() };
}

export async function transitionWorkOrderAction(id: number, targetStatus: string, notes?: string): Promise<MutationResult> {
  const response = await authedFetch(`/work-orders/${id}/transition/${targetStatus}`, {
    method: "POST",
    body: JSON.stringify({ notes: notes ?? null }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    const data = await response.json().catch(() => ({}));
    return { ok: false, error: data?.detail?.message ?? "Transição não permitida." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteWorkOrderAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/work-orders/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir ordem de serviço." };
  }
  return { ok: true };
}

export async function cloneWorkOrderAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/work-orders/${id}/clone`, { method: "POST" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao duplicar ordem de serviço." };
  }
  return { ok: true, data: await response.json() };
}

export async function fetchLocationsAction(): Promise<{ id: number; name: string }[]> {
  const response = await authedFetch("/registries?category=Local&page=1&page_size=100");
  if (!response.ok) return [];
  const data = await response.json();
  return (data.items ?? []).map((i: { id: number; name: string }) => ({ id: i.id, name: i.name }));
}

export async function fetchWorkOrderCategories(): Promise<string[]> {
  const response = await authedFetch("/work-orders/categories");
  if (!response.ok) return [];
  return response.json();
}

export async function fetchConfiguredCategories(): Promise<string[]> {
  const response = await authedFetch("/settings/work-order-categories");
  if (!response.ok) return [];
  const data = await response.json();
  return data.items ?? [];
}

export async function addCategoryAction(name: string): Promise<MutationResult> {
  const response = await authedFetch("/settings/work-order-categories", {
    method: "POST", body: JSON.stringify({ name }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao criar categoria." };
  return { ok: true, data: await response.json() };
}

export async function deleteCategoryAction(name: string): Promise<MutationResult> {
  const response = await authedFetch(`/settings/work-order-categories/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!response.ok) return { ok: false, error: "Erro ao excluir categoria." };
  return { ok: true };
}

// --- Ponto eletrônico / Escala de trabalho ---

export interface WorkScheduleEntry {
  weekday: number;
  start_time: string;
  end_time: string;
  break_start?: string | null;
  break_end?: string | null;
  tolerance_minutes: number;
}

export interface WorkScheduleWeek {
  user_id: number;
  entries: WorkScheduleEntry[];
}

export async function fetchWorkSchedule(userId: number): Promise<WorkScheduleWeek | null> {
  const response = await authedFetch(`/timeclock/schedules/${userId}`);
  if (!response.ok) return null;
  return response.json();
}

export async function saveWorkScheduleAction(
  userId: number,
  entries: WorkScheduleEntry[],
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/schedules/${userId}`, {
    method: "PUT",
    body: JSON.stringify({ entries }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao salvar escala." };
  return { ok: true, data: await response.json() };
}

export interface TimeClockDevice {
  id: number;
  name: string;
  model: string;
  serial_number: string | null;
  location_id: number | null;
  location: string | null;
  webhook_token: string;
  active: boolean;
}

export interface DevicePayload {
  name: string;
  model?: string;
  serial_number?: string | null;
  location_id?: number | null;
}

export async function fetchDevices(): Promise<TimeClockDevice[]> {
  const response = await authedFetch("/timeclock/devices");
  if (!response.ok) return [];
  return response.json();
}

export async function createDeviceAction(body: DevicePayload): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/devices", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao criar dispositivo." };
  return { ok: true, data: await response.json() };
}

export async function updateDeviceAction(
  id: number,
  body: Partial<DevicePayload> & { active?: boolean },
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/devices/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao atualizar dispositivo." };
  return { ok: true, data: await response.json() };
}

export async function deleteDeviceAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/devices/${id}`, { method: "DELETE" });
  if (!response.ok) return { ok: false, error: "Erro ao excluir dispositivo." };
  return { ok: true };
}

export interface TimeClockEnrollment {
  id: number;
  employee_id: number;
  employee_name: string;
  external_id: string;
}

export async function fetchEnrollments(): Promise<TimeClockEnrollment[]> {
  const response = await authedFetch("/timeclock/enrollments");
  if (!response.ok) return [];
  return response.json();
}

export async function createEnrollmentAction(
  employeeId: number,
  externalId: string,
): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/enrollments", {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId, external_id: externalId }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao criar vínculo." };
  return { ok: true, data: await response.json() };
}

export async function deleteEnrollmentAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/enrollments/${id}`, { method: "DELETE" });
  if (!response.ok) return { ok: false, error: "Erro ao excluir vínculo." };
  return { ok: true };
}

export interface TimePunch {
  id: number;
  employee_id: number | null;
  employee_name: string | null;
  device_id: number | null;
  device_name: string | null;
  punched_at: string;
  punch_type: string | null;
  source: string;
  status: string | null;
  notes: string | null;
}

export interface TimePunchListResponse {
  items: TimePunch[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchPunches(params: {
  page?: number;
  pageSize?: number;
  employeeId?: number;
  dateFrom?: string;
  dateTo?: string;
  status?: string;
}): Promise<TimePunchListResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page ?? 1));
  qs.set("page_size", String(params.pageSize ?? 20));
  if (params.employeeId) qs.set("employee_id", String(params.employeeId));
  if (params.dateFrom) qs.set("date_from", params.dateFrom);
  if (params.dateTo) qs.set("date_to", params.dateTo);
  if (params.status) qs.set("status", params.status);
  const response = await authedFetch(`/timeclock/punches?${qs.toString()}`);
  if (!response.ok) return { items: [], total: 0, page: 1, page_size: 20 };
  return response.json();
}

export async function createManualPunchAction(body: {
  employee_id: number;
  punched_at: string;
  punch_type?: string;
  notes?: string;
}): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/punches", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao lançar batida." };
  return { ok: true, data: await response.json() };
}

export async function updatePunchAction(
  id: number,
  body: { punched_at?: string; punch_type?: string; notes?: string },
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/punches/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao corrigir batida." };
  return { ok: true, data: await response.json() };
}

// ── Turnos e Calendário de Escala ──

export interface Shift {
  id: number;
  name: string;
  start_time: string;
  end_time: string;
  break_start: string | null;
  break_end: string | null;
  tolerance_minutes: number;
  color: string;
  active: boolean;
}

export interface CalendarEntry {
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

export async function fetchShifts(): Promise<Shift[]> {
  const response = await authedFetch("/timeclock/shifts");
  if (!response.ok) return [];
  return response.json();
}

export async function createShiftAction(body: {
  name: string;
  start_time: string;
  end_time: string;
  break_start?: string | null;
  break_end?: string | null;
  tolerance_minutes?: number;
  color?: string;
}): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/shifts", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao criar turno." };
  return { ok: true, data: await response.json() };
}

export async function updateShiftAction(
  id: number,
  body: Partial<{
    name: string;
    start_time: string;
    end_time: string;
    break_start: string | null;
    break_end: string | null;
    tolerance_minutes: number;
    color: string;
    active: boolean;
  }>,
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/shifts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao atualizar turno." };
  return { ok: true, data: await response.json() };
}

export async function deleteShiftAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/shifts/${id}`, { method: "DELETE" });
  if (!response.ok) return { ok: false, error: "Erro ao excluir turno." };
  return { ok: true };
}

export async function fetchCalendar(params: {
  start: string;
  end: string;
  employeeId?: number;
  shiftId?: number;
}): Promise<CalendarEntry[]> {
  const qs = new URLSearchParams();
  qs.set("start", params.start);
  qs.set("end", params.end);
  if (params.employeeId) qs.set("employee_id", String(params.employeeId));
  if (params.shiftId) qs.set("shift_id", String(params.shiftId));
  const response = await authedFetch(`/timeclock/schedule?${qs.toString()}`);
  if (!response.ok) return [];
  return response.json();
}

export async function setScheduleDayAction(
  employeeId: number,
  date: string,
  body: { shift_id?: number | null; notes?: string },
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/schedule/${employeeId}/${date}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao atualizar dia." };
  return { ok: true, data: await response.json() };
}

export async function generateScheduleAction(body: {
  employee_ids: number[];
  shift_id: number;
  start_date: string;
  end_date: string;
  pattern: { type: "weekly"; weekdays: number[] } | { type: "rotating"; work_days: number; off_days: number };
}): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/schedule/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao gerar escala." };
  return { ok: true, data: await response.json() };
}

// ---------------------------------------------------------------------------
// Banco de horas
// ---------------------------------------------------------------------------

export interface HourBankEntry {
  id: number;
  reference_date: string;
  expected_minutes: number;
  worked_minutes: number;
  balance_minutes: number;
  source: "calculated" | "initial_balance";
  notes: string | null;
}

export interface HourBankSummary {
  employee_id: number;
  balance_minutes: number;
  entries: HourBankEntry[];
}

export async function fetchHourBankSummary(employeeId: number): Promise<HourBankSummary | null> {
  const response = await authedFetch(`/timeclock/hour-bank/${employeeId}`);
  if (!response.ok) return null;
  return response.json();
}

export async function recalculateHourBankAction(
  employeeId: number,
  startDate: string,
  endDate: string,
): Promise<{ ok: true; affected: number } | { ok: false; error: string }> {
  const response = await authedFetch(`/timeclock/hour-bank/${employeeId}/recalculate`, {
    method: "POST",
    body: JSON.stringify({ start_date: startDate, end_date: endDate }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao recalcular banco de horas." };
  const data = (await response.json()) as { affected: number };
  return { ok: true, affected: data.affected };
}

export async function setHourBankInitialBalanceAction(
  employeeId: number,
  body: { effective_date: string; balance_minutes: number; notes?: string },
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/hour-bank/${employeeId}/initial-balance`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao lançar saldo inicial." };
  return { ok: true, data: await response.json() };
}

// ---------------------------------------------------------------------------
// Ajuste de ponto (aprovação pelo RH/gestor)
// ---------------------------------------------------------------------------

export interface PunchAdjustment {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_avatar_url: string | null;
  punch_id: number | null;
  requested_punched_at: string;
  requested_punch_type: string | null;
  reason: string;
  status: "pending" | "approved" | "rejected";
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  review_notes: string | null;
  resulting_punch_id: number | null;
  created_at: string;
}

export interface PunchAdjustmentListResponse {
  items: PunchAdjustment[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchPunchAdjustments(params: {
  page?: number;
  pageSize?: number;
  status?: string;
}): Promise<PunchAdjustmentListResponse> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.status) query.set("status", params.status);
  const response = await authedFetch(`/timeclock/adjustments?${query}`);
  if (!response.ok) return { items: [], total: 0, page: 1, page_size: 20 };
  return response.json();
}

export async function reviewPunchAdjustmentAction(
  requestId: number,
  approve: boolean,
  reviewNotes?: string,
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/adjustments/${requestId}/review`, {
    method: "POST",
    body: JSON.stringify({ approve, review_notes: reviewNotes }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao revisar solicitação." };
  return { ok: true, data: await response.json() };
}

export interface RequesterStat {
  employee_id: number;
  name: string;
  avatar_url: string | null;
  count: number;
}

export interface AdjustmentStats {
  monthly_trend: Array<{ month: string; count: number }>;
  top_requesters: RequesterStat[];
  least_requesters: RequesterStat[];
}

export async function fetchAdjustmentStats(): Promise<AdjustmentStats | null> {
  const response = await authedFetch("/timeclock/adjustments/stats");
  if (!response.ok) return null;
  return response.json();
}

export interface PunchExcusal {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_avatar_url: string | null;
  reference_date: string;
  minutes: number | null;
  reason: string;
  created_by_user_id: number | null;
  created_at: string;
}

export interface PunchExcusalListResponse {
  items: PunchExcusal[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchPunchExcusals(params: {
  page?: number;
  pageSize?: number;
}): Promise<PunchExcusalListResponse> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  const response = await authedFetch(`/timeclock/excusals?${query}`);
  if (!response.ok) return { items: [], total: 0, page: 1, page_size: 20 };
  return response.json();
}

export async function createPunchExcusalAction(body: {
  employee_id: number;
  reference_date: string;
  minutes?: number;
  reason: string;
}): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/excusals", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return { ok: false, error: "Erro ao abonar ponto." };
  return { ok: true, data: await response.json() };
}

// ---------------------------------------------------------------------------
// Espelho de ponto
// ---------------------------------------------------------------------------

export interface MirrorDay {
  date: string;
  first_in: string | null;
  first_out: string | null;
  second_in: string | null;
  second_out: string | null;
  credit_minutes: number;
  debit_minutes: number;
  break_minutes: number;
  worked_minutes: number;
  overtime_50_minutes: number;
  overtime_100_minutes: number;
  overtime_50_value: number | null;
  overtime_100_value: number | null;
  night_differential_minutes: number;
  balance_minutes: number;
  notes: string;
}

export interface MirrorTotals {
  credit_minutes: number;
  debit_minutes: number;
  break_minutes: number;
  worked_minutes: number;
  overtime_50_minutes: number;
  overtime_100_minutes: number;
  overtime_50_value: number | null;
  overtime_100_value: number | null;
  night_differential_minutes: number;
  balance_minutes: number;
}

export interface EmployeeMirror {
  employee_id: number;
  employee_name: string;
  employee_avatar_url: string | null;
  sector_name: string | null;
  days: MirrorDay[];
  totals: MirrorTotals;
}

export async function fetchTimeclockMirror(params: {
  employeeId: number;
  dateFrom: string;
  dateTo: string;
}): Promise<{ ok: true; data: EmployeeMirror } | { ok: false; error: string }> {
  const query = new URLSearchParams({
    employee_id: String(params.employeeId),
    date_from: params.dateFrom,
    date_to: params.dateTo,
  });
  const response = await authedFetch(`/timeclock/mirror?${query}`);
  if (!response.ok) {
    return {
      ok: false,
      error: response.status === 404 ? "Funcionário não encontrado." : "Erro ao gerar o espelho.",
    };
  }
  return { ok: true, data: await response.json() };
}

export async function fetchSectorMirror(params: {
  sectorId: number;
  dateFrom: string;
  dateTo: string;
}): Promise<{ ok: true; data: EmployeeMirror[] } | { ok: false; error: string }> {
  const query = new URLSearchParams({
    sector_id: String(params.sectorId),
    date_from: params.dateFrom,
    date_to: params.dateTo,
  });
  const response = await authedFetch(`/timeclock/mirror/by-sector?${query}`);
  if (!response.ok) return { ok: false, error: "Erro ao gerar o espelho do setor." };
  const body = await response.json();
  return { ok: true, data: body.mirrors };
}

export interface Holiday {
  id: number;
  date: string;
  name: string;
}

export async function fetchHolidays(): Promise<Holiday[]> {
  const response = await authedFetch("/timeclock/holidays");
  if (!response.ok) return [];
  return response.json();
}

export async function createHolidayAction(body: { date: string; name: string }): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/holidays", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message =
      payload?.detail?.code === "duplicate_date"
        ? "Já existe um feriado cadastrado nesta data."
        : "Erro ao criar feriado.";
    return { ok: false, error: message };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteHolidayAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/holidays/${id}`, { method: "DELETE" });
  if (!response.ok) return { ok: false, error: "Erro ao excluir feriado." };
  return { ok: true };
}

// --- Requisições de Férias ---

export interface VacationRequestItem {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_avatar_url: string | null;
  employee_sector_name: string | null;
  start_date: string;
  end_date: string;
  days: number;
  working_days: number | null;
  notes: string | null;
  status: string;
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
}

export interface VacationRequestListResponse {
  items: VacationRequestItem[];
  total: number;
  page: number;
  page_size: number;
}

// --- Conferência de discrepâncias ---

export interface DiscrepancyEntryInput {
  location_id: number;
  first_code?: string | null;
  second_code?: string | null;
  notes?: string | null;
}

export interface DiscrepancyEntry extends DiscrepancyEntryInput {
  id: number;
  location_name: string;
}

export type DiscrepancyStatus = "draft" | "submitted" | "closed";

export interface DiscrepancyReportSummary {
  id: number;
  report_date: string;
  status: DiscrepancyStatus;
  prepared_by_user_id: number | null;
  prepared_by_name: string | null;
  entry_count: number;
  discrepancy_count: number;
  updated_at: string;
}

export interface DiscrepancyReportDetail extends DiscrepancyReportSummary {
  checked_by_user_id: number | null;
  checked_by_name: string | null;
  received_by_user_id: number | null;
  received_by_name: string | null;
  observations: string | null;
  entries: DiscrepancyEntry[];
  code_summary: { code: string; count: number }[];
  created_at: string;
}

export interface DiscrepancyReportPage {
  items: DiscrepancyReportSummary[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchVacationRequests(params: {
  page?: number;
  pageSize?: number;
  status?: string;
  employeeId?: number;
  sectorId?: number;
}): Promise<VacationRequestListResponse> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.status) query.set("status", params.status);
  if (params.employeeId) query.set("employee_id", String(params.employeeId));
  if (params.sectorId) query.set("sector_id", String(params.sectorId));
  const response = await authedFetch(`/timeclock/vacation-requests?${query}`);
  if (!response.ok) return { items: [], total: 0, page: 1, page_size: 20 };
  return response.json();
}

export async function reviewVacationRequestAction(
  requestId: number,
  approve: boolean,
  reviewNotes?: string,
): Promise<MutationResult> {
  const response = await authedFetch(`/timeclock/vacation-requests/${requestId}/review`, {
    method: "POST",
    body: JSON.stringify({ approve, review_notes: reviewNotes ?? null }),
  });
  if (!response.ok) return { ok: false, error: "Erro ao revisar solicitação." };
  return { ok: true, data: await response.json() };
}

export interface VacationRequestStats {
  monthly_trend: Array<{ month: string; count: number }>;
  pending: number;
  approved_total: number;
  upcoming_60d: number;
}

export async function fetchVacationRequestStats(): Promise<VacationRequestStats | null> {
  const response = await authedFetch("/timeclock/vacation-requests/stats");
  if (!response.ok) return null;
  return response.json();
}

export async function createVacationRequestAdminAction(body: {
  employee_id: number;
  start_date: string;
  end_date: string;
  notes?: string;
}): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/vacation-requests", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (response.status === 201) return { ok: true, data: await response.json() };
  const data = await response.json().catch(() => ({}));
  return { ok: false, error: data?.detail?.message ?? "Erro ao registrar férias." };
}

export interface DiscrepancyReportPayload {
  report_date: string;
  prepared_by_user_id?: number | null;
  checked_by_user_id?: number | null;
  received_by_user_id?: number | null;
  status?: DiscrepancyStatus;
  observations?: string | null;
  entries: DiscrepancyEntryInput[];
}

function apiErrorMessage(payload: unknown, fallback: string): string {
  const detail = (payload as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export async function fetchDiscrepancyReports(
  params: { page?: number; date_from?: string; date_to?: string; status?: string } = {},
): Promise<DiscrepancyReportPage> {
  const query = new URLSearchParams();
  query.set("page", String(params.page ?? 1));
  query.set("page_size", "20");
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  if (params.status) query.set("status", params.status);
  const response = await authedFetch(`/discrepancy-reports?${query}`);
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { items: [], total: 0, page: 1, page_size: 20 };
  }
  return response.json();
}

export async function fetchDiscrepancyReport(id: number): Promise<DiscrepancyReportDetail | null> {
  const response = await authedFetch(`/discrepancy-reports/${id}`);
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return null;
  }
  return response.json();
}

export async function createDiscrepancyReportAction(
  body: DiscrepancyReportPayload,
): Promise<MutationResult> {
  const response = await authedFetch("/discrepancy-reports", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    const payload = await response.json().catch(() => null);
    return { ok: false, error: apiErrorMessage(payload, "Erro ao criar conferência.") };
  }
  return { ok: true, data: await response.json() };
}

export async function updateDiscrepancyReportAction(
  id: number,
  body: Partial<DiscrepancyReportPayload>,
): Promise<MutationResult> {
  const response = await authedFetch(`/discrepancy-reports/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    const payload = await response.json().catch(() => null);
    return { ok: false, error: apiErrorMessage(payload, "Erro ao salvar conferência.") };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteDiscrepancyReportAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/discrepancy-reports/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir conferência." };
  }
  return { ok: true };
}
