import { z } from "zod";

export const TenantUserSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string(),
  phone: z.string().nullable(),
  company_id: z.number(),
  role_name: z.string().nullable(),
  permissions: z.array(z.string()),
});

export const TokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  expires_in: z.number(),
});

export const PaginatedSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number(),
    page: z.number(),
    page_size: z.number(),
  });

export const NotificationItemSchema = z.object({
  id: z.number(),
  title: z.string(),
  body: z.string().nullable(),
  category: z.string(),
  entity_type: z.string().nullable(),
  entity_id: z.number().nullable(),
  read_at: z.string().nullable(),
  created_at: z.string(),
});

export const NotificationListSchema = z.object({
  items: z.array(NotificationItemSchema),
  total: z.number(),
  unread: z.number(),
  page: z.number(),
  page_size: z.number(),
});

export const TimelineEntrySchema = z.object({
  id: z.number(),
  event_type: z.string(),
  user: z.string(),
  message: z.string().nullable(),
  changes: z.record(z.object({ from: z.string(), to: z.string() })).nullable(),
  created_at: z.string(),
});

export const AttachmentItemSchema = z.object({
  id: z.number(),
  entity_type: z.string(),
  entity_id: z.number(),
  filename: z.string(),
  content_type: z.string(),
  size_bytes: z.number(),
  uploaded_by_user_id: z.number(),
  created_at: z.string(),
});

export const RegistryOptionSchema = z.object({
  id: z.number(),
  name: z.string(),
});

export const UserOptionSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string(),
});

export const EmployeeOptionSchema = z.object({
  id: z.number(),
  name: z.string(),
});

export const EmployeeSummarySchema = z.object({
  id: z.number(),
  name: z.string(),
  cpf: z.string().nullable(),
  personal_email: z.string().nullable(),
  phone: z.string().nullable(),
  status: z.string(),
  user_id: z.number().nullable(),
  avatar_url: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const EmployeeDetailedSchema = EmployeeSummarySchema.extend({
  rg: z.string().nullable(),
  birth_date: z.string().nullable(),
  address_street: z.string().nullable(),
  address_number: z.string().nullable(),
  address_complement: z.string().nullable(),
  address_neighborhood: z.string().nullable(),
  address_city: z.string().nullable(),
  address_state: z.string().nullable(),
  address_zip: z.string().nullable(),
  job_title: z.string().nullable(),
  hire_date: z.string().nullable(),
  termination_date: z.string().nullable(),
  registration_number: z.string().nullable(),
  sector_id: z.number().nullable(),
  sector_name: z.string().nullable(),
  external_ids: z.array(
    z.object({
      id: z.number(),
      employee_id: z.number(),
      system: z.string(),
      external_id: z.string(),
    }),
  ),
});

export const EmployeeImportRowResultSchema = z.object({
  row: z.number(),
  ok: z.boolean(),
  name: z.string().nullable(),
  id: z.number().nullable(),
  error: z.string().nullable(),
});

export const EmployeeImportResultSchema = z.object({
  total: z.number(),
  created: z.number(),
  failed: z.number(),
  results: z.array(EmployeeImportRowResultSchema),
});

export const PayslipImportRowResultSchema = z.object({
  row: z.number(),
  status: z.enum(["created", "updated", "failed"]),
  employee_name: z.string().nullable(),
  reference_month: z.string().nullable(),
  error: z.string().nullable(),
});

export const PayslipImportResponseSchema = z.object({
  total: z.number(),
  created: z.number(),
  updated: z.number(),
  failed: z.number(),
  results: z.array(PayslipImportRowResultSchema),
});

export function safeParse<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    console.error("[API schema mismatch]", result.error.flatten());
    return data as T;
  }
  return result.data;
}
