"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { setTokenCookies, tryRefreshToken } from "@/lib/auth";
import {
  AttachmentItemSchema,
  NotificationItemSchema,
  NotificationListSchema,
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

export interface FiscalRequestPayload {
  request_type: string;
  title: string;
  apartment?: string;
  requester: string;
  description?: string;
  status?: string;
  payload?: Record<string, unknown>;
}

interface MutationResult {
  ok: boolean;
  error?: string;
  data?: Record<string, unknown>;
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

export interface OccurrencePayload {
  title: string;
  description?: string;
  unit?: string;
  deadline?: string;
  status?: number;
  sector_id?: number;
  location_id?: number;
  owner_user_id?: number;
  notify_user_ids?: number[];
  participant_ids?: number[];
}

export async function createOccurrenceAction(body: OccurrencePayload): Promise<MutationResult> {
  const response = await authedFetch("/occurrences", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao criar ocorrencia." };
  }
  return { ok: true, data: await response.json() };
}

export async function updateOccurrenceAction(
  id: number,
  body: Partial<OccurrencePayload>,
): Promise<MutationResult> {
  const response = await authedFetch(`/occurrences/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao atualizar ocorrencia." };
  }
  return { ok: true, data: await response.json() };
}

export async function deleteOccurrenceAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/occurrences/${id}`, { method: "DELETE" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao excluir ocorrencia." };
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

export async function updateRegistryAction(id: number, body: { name: string }, category: string): Promise<MutationResult> {
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

// --- Dados do Estabelecimento ---

export interface CompanyInfo {
  id: number;
  name: string;
  slug: string;
  email: string | null;
  document: string | null;
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
  body: { name?: string; email?: string; document?: string; timezone?: string },
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

// --- Occurrence extras ---

export async function cloneOccurrenceAction(id: number): Promise<MutationResult> {
  const response = await authedFetch(`/occurrences/${id}/clone`, { method: "POST" });
  if (!response.ok) {
    if (response.status === 401) throw new Error("unauthorized");
    return { ok: false, error: "Erro ao duplicar ocorrência." };
  }
  return { ok: true, data: await response.json() };
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
  occurrence_id?: number;
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
  occurrence_id?: number;
  maintenance_id?: number;
  assigned_user_id?: number;
  notify_user_ids?: number[];
  sla_hours?: number;
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
  user_id: number;
  user_name: string;
  external_id: string;
}

export async function fetchEnrollments(): Promise<TimeClockEnrollment[]> {
  const response = await authedFetch("/timeclock/enrollments");
  if (!response.ok) return [];
  return response.json();
}

export async function createEnrollmentAction(
  userId: number,
  externalId: string,
): Promise<MutationResult> {
  const response = await authedFetch("/timeclock/enrollments", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, external_id: externalId }),
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
  user_id: number | null;
  user_name: string | null;
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
  userId?: number;
  dateFrom?: string;
  dateTo?: string;
  status?: string;
}): Promise<TimePunchListResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page ?? 1));
  qs.set("page_size", String(params.pageSize ?? 20));
  if (params.userId) qs.set("user_id", String(params.userId));
  if (params.dateFrom) qs.set("date_from", params.dateFrom);
  if (params.dateTo) qs.set("date_to", params.dateTo);
  if (params.status) qs.set("status", params.status);
  const response = await authedFetch(`/timeclock/punches?${qs.toString()}`);
  if (!response.ok) return { items: [], total: 0, page: 1, page_size: 20 };
  return response.json();
}

export async function createManualPunchAction(body: {
  user_id: number;
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
