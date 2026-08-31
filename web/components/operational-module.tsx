"use client";

import {
  createUserAction, updateUserAction, deleteUserAction, inviteUserAction,
  createRegistryAction, updateRegistryAction, deleteRegistryAction,
  createModuleRecordAction, updateModuleRecordAction, deleteModuleRecordAction,
  createProcedureAction, updateProcedureAction, deleteProcedureAction,
  getEvolutionSettings, saveEvolutionSettings,
  getBrevoSettings, saveBrevoSettings, searchUsers,
  fetchTimeline, addCommentAction,
  uploadAttachmentAction, fetchAttachments, deleteAttachmentAction,
} from "@/app/actions";
import type { EvolutionSettings, BrevoSettings, UserOption, TimelineEntry, AttachmentItem, RegistryUpdatePayload } from "@/app/actions";
import type { TenantUser } from "@/lib/api";
import { type HistoryEntry, type ModuleDefinition, type ModuleRecord } from "@/lib/module-definitions";
import {
  ChevronLeft, ChevronRight, Download, FileClock,
  MessageSquare, Paperclip, Pencil, Plus, RefreshCw, Search,
  Send, Trash2, Upload, X,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { HandoffSection } from "./handoff-section";
import { CompanySettingsSection, BrevoSettingsSection, EvolutionSettingsSection, ProfileForm } from "./settings-sections";

const pageSize = 5;

function formatPhone(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d.length ? `(${d}` : "";
  if (d.length <= 7) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

function formatDocument(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 14);
  if (d.length <= 3) return d;
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`;
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`;
  if (d.length <= 11) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`;
  if (d.length <= 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

function UserAutocomplete({ name, defaultValue, placeholder, required }: { name: string; defaultValue?: string; placeholder?: string; required?: boolean }) {
  const [query, setQuery] = useState(defaultValue ?? "");
  const [options, setOptions] = useState<UserOption[]>([]);
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listId = `${name}-listbox`;

  function handleChange(v: string) {
    setQuery(v);
    setSelectedId(null);
    setActiveIndex(-1);
    clearTimeout(timer.current);
    if (v.trim().length < 2) { setOptions([]); setOpen(false); return; }
    timer.current = setTimeout(() => {
      searchUsers(v).then((r) => { setOptions(r); setOpen(r.length > 0); setActiveIndex(-1); });
    }, 250);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || !options.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIndex((i) => Math.min(i + 1, options.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIndex((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && activeIndex >= 0) { e.preventDefault(); const u = options[activeIndex]; setQuery(u.name); setSelectedId(u.id); setOpen(false); }
    else if (e.key === "Escape") { setOpen(false); }
  }

  return <div className="autocomplete-wrap" role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-owns={listId}>
    <input name={`${name}_display`} value={query} onChange={(e) => handleChange(e.target.value)} onFocus={() => { if (options.length) setOpen(true); }} onBlur={() => setTimeout(() => setOpen(false), 200)} onKeyDown={handleKeyDown} placeholder={placeholder} required={required} autoComplete="off" aria-autocomplete="list" aria-controls={listId} aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}/>
    <input type="hidden" name={name} value={selectedId ?? query}/>
    {open && <ul id={listId} className="autocomplete-list" role="listbox">{options.map((u, i) => <li key={u.id} id={`${listId}-${i}`} role="option" aria-selected={i === activeIndex} className={i === activeIndex ? "active" : undefined} onMouseDown={() => { setQuery(u.name); setSelectedId(u.id); setOpen(false); }}><strong>{u.name}</strong><small>{u.email}</small></li>)}</ul>}
  </div>;
}

function UserMultiSelect({ name, defaultValues }: { name: string; defaultValues?: { id: number; name: string }[] }) {
  const [selected, setSelected] = useState<{ id: number; name: string }[]>(defaultValues ?? []);
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<UserOption[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listId = `${name}-multi-listbox`;

  function handleChange(v: string) {
    setQuery(v);
    setActiveIndex(-1);
    clearTimeout(timer.current);
    if (v.trim().length < 2) { setOptions([]); setOpen(false); return; }
    timer.current = setTimeout(() => {
      searchUsers(v).then((r) => { const filtered = r.filter((u) => !selected.some((s) => s.id === u.id)); setOptions(filtered); setOpen(filtered.length > 0); setActiveIndex(-1); });
    }, 250);
  }

  function add(u: UserOption) {
    setSelected((prev) => [...prev, { id: u.id, name: u.name }]);
    setQuery("");
    setOptions([]);
    setOpen(false);
    setActiveIndex(-1);
  }

  function remove(id: number) {
    setSelected((prev) => prev.filter((u) => u.id !== id));
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || !options.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIndex((i) => Math.min(i + 1, options.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIndex((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && activeIndex >= 0) { e.preventDefault(); add(options[activeIndex]); }
    else if (e.key === "Escape") { setOpen(false); }
  }

  return <div className="autocomplete-wrap" role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-owns={listId}>
    <input type="hidden" name={name} value={JSON.stringify(selected.map((u) => u.id))}/>
    {selected.length > 0 && <div className="notify-chips" role="list">{selected.map((u) => <span key={u.id} className="notify-chip" role="listitem">{u.name}<button type="button" onClick={() => remove(u.id)} aria-label={`Remover ${u.name}`}>×</button></span>)}</div>}
    <input value={query} onChange={(e) => handleChange(e.target.value)} onFocus={() => { if (options.length) setOpen(true); }} onBlur={() => setTimeout(() => setOpen(false), 200)} onKeyDown={handleKeyDown} placeholder="Buscar usuário..." autoComplete="off" aria-autocomplete="list" aria-controls={listId} aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}/>
    {open && <ul id={listId} className="autocomplete-list" role="listbox">{options.map((u, i) => <li key={u.id} id={`${listId}-${i}`} role="option" aria-selected={i === activeIndex} className={i === activeIndex ? "active" : undefined} onMouseDown={() => add(u)}><strong>{u.name}</strong><small>{u.email}</small></li>)}</ul>}
  </div>;
}

function statusClass(status: string) {
  if (["Concluído", "Ativo", "Publicado"].includes(status)) return "status status-done";
  if (["Aguardando", "Pendente", "Rascunho"].includes(status)) return "status status-waiting";
  return "status status-progress";
}

const SLUG_TO_ENTITY_TYPE: Record<string, string> = {
  "procedimentos": "procedure",
  "reunioes": "meeting",
  "relatorios-turno": "shift_report",
  "inspecoes": "inspecoes",
  "diarios-obra": "diarios-obra",
  "manutencao": "manutencao",
  "mural": "bulletin",
};

export function OperationalModule({
  definition,
  user,
  basePath,
  extraParams,
}: {
  definition: ModuleDefinition;
  user: TenantUser;
  basePath?: string;
  extraParams?: Record<string, string>;
}) {
  const effectiveBasePath = basePath ?? `/${definition.slug}`;
  const storageKey = `registro:${user.company_id}:${definition.slug}`;
  const isUsers = definition.slug === "usuarios";
  const isCadastros = (definition.slug === "cadastros" || definition.slug.startsWith("cadastros/")) && !definition.slug.includes("procedimentos");
  const cadastroCategory: Record<string, string> = {
    "cadastros/setores": "Setor", "cadastros/locais": "Local", "cadastros/funcoes": "Função",
  };
  const fixedCategory = cadastroCategory[definition.slug] ?? null;
  const isProcedimentos = definition.slug === "procedimentos" || definition.slug === "cadastros/procedimentos";
  const isGenericModule = ["inspecoes", "diarios-obra", "manutencao"].includes(definition.slug);
  const isMeetings = definition.slug === "reunioes";
  const isShiftReports = definition.slug === "relatorios-turno";
  const hasAttachments = isProcedimentos;
  const isApiBacked = definition.source === "api";
  const entityType = SLUG_TO_ENTITY_TYPE[definition.slug];
  function hasPermission(code: string) {
    return user.permissions.includes("*") || user.permissions.includes(code);
  }
  const permModule = isUsers ? "user" : isCadastros ? "registry" : isProcedimentos ? "procedure" : isMeetings ? "meeting" : isShiftReports ? "shift_report" : isGenericModule ? "module" : "module";
  const canView = hasPermission(`${permModule}.view`);
  const canCreate = hasPermission(`${permModule}.create`);
  const canEdit = hasPermission(`${permModule}.edit`);
  const canDelete = hasPermission(`${permModule}.delete`);
  const canMutate = canCreate || canEdit;
  const searchParams = useSearchParams();
  const router = useRouter();
  const sp = definition.serverPagination;
  const [records, setRecords] = useState<ModuleRecord[]>(definition.records);
  const [ready, setReady] = useState(false);
  const [query, setQuery] = useState(sp?.search ?? "");
  const [status, setStatus] = useState("Todos");
  const [page, setPage] = useState(sp?.page ?? 1);
  const [editing, setEditing] = useState<ModuleRecord | "new" | null>(null);
  const [selected, setSelected] = useState<ModuleRecord | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [selectedAttachments, setSelectedAttachments] = useState<AttachmentItem[]>([]);
  const [toast, setToast] = useState("");

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (editing) setEditing(null);
        else if (selected) setSelected(null);
      }
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [editing, selected]);

  useEffect(() => {
    if (isApiBacked) {
      setRecords(definition.records);
    } else {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) setRecords(JSON.parse(saved) as ModuleRecord[]);
    }
    setReady(true);
  }, [definition.records, isApiBacked, storageKey]);

  useEffect(() => {
    if (canMutate && searchParams.get("new") === "1") setEditing("new");
  }, [canMutate, searchParams]);

  useEffect(() => {
    if (!selected || !isApiBacked || !entityType) { setTimeline([]); setSelectedAttachments([]); return; }
    fetchTimeline(entityType, selected.id).then(setTimeline).catch(() => setTimeline([]));
    if (hasAttachments && entityType) {
      fetchAttachments(entityType, selected.id).then(setSelectedAttachments).catch(() => setSelectedAttachments([]));
    }
  }, [selected, isApiBacked, entityType, hasAttachments]);

  useEffect(() => {
    if (!editing || editing === "new" || !hasAttachments || !isApiBacked || !entityType) return;
    fetchAttachments(entityType, editing.id).then(setSelectedAttachments).catch(() => setSelectedAttachments([]));
  }, [editing, hasAttachments, isApiBacked, entityType]);

  const [shiftDetailLoaded, setShiftDetailLoaded] = useState<number | null>(null);
  useEffect(() => {
    if (!editing || editing === "new" || !isShiftReports) return;
    if (shiftDetailLoaded === editing.id) return;
    setShiftDetailLoaded(editing.id);
    import("@/app/actions").then(({ fetchShiftReportDetail }) =>
      fetchShiftReportDetail(editing.id).then((detail) => {
        if (detail) setEditing((prev) => prev && prev !== "new" ? { ...prev, ...detail } : prev);
      })
    );
  }, [editing, isShiftReports, shiftDetailLoaded]);

  useEffect(() => {
    if (!isApiBacked) return;

    const refresh = () => router.refresh();
    const interval = window.setInterval(refresh, 15_000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [isApiBacked, router]);

  function persist(next: ModuleRecord[], message: string) {
    setRecords(next);
    window.localStorage.setItem(storageKey, JSON.stringify(next));
    setToast(message);
    window.setTimeout(() => setToast(""), 2600);
  }

  const statuses = useMemo(() => ["Todos", ...new Set(records.map((record) => record.status))], [records]);
  const filtered = useMemo(() => {
    if (sp) return records;
    return records.filter((record) => {
      const text = `${record.id} ${record.title} ${record.category} ${record.owner} ${record.status}`.toLocaleLowerCase("pt-BR");
      return (!query || text.includes(query.toLocaleLowerCase("pt-BR"))) && (status === "Todos" || record.status === status);
    });
  }, [query, records, status, sp]);
  const totalItems = sp ? sp.total : filtered.length;
  const effectivePageSize = sp ? sp.pageSize : pageSize;
  const pages = Math.max(1, Math.ceil(totalItems / effectivePageSize));
  const visible = sp ? filtered : filtered.slice((Math.min(page, pages) - 1) * pageSize, Math.min(page, pages) * pageSize);

  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  function handleServerSearch(value: string) {
    setQuery(value);
    if (!sp) { setPage(1); return; }
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => {
      const params = new URLSearchParams(extraParams);
      if (value) params.set("search", value);
      router.push(`${effectiveBasePath}?${params.toString()}`);
    }, 400);
  }
  function handleServerPage(newPage: number) {
    setPage(newPage);
    if (!sp) return;
    const params = new URLSearchParams(extraParams);
    params.set("page", String(newPage));
    if (query) params.set("search", query);
    router.push(`${effectiveBasePath}?${params.toString()}`);
  }

  function formatNow() {
    return new Date().toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function diffChanges(before: ModuleRecord, after: { title: string; category: string; owner: string; status: string; description: string }): string {
    const labels: Record<string, string> = { title: "Título", category: "Categoria", owner: "Responsável", status: "Status", description: "Descrição" };
    const parts: string[] = [];
    for (const key of Object.keys(labels) as (keyof typeof labels)[]) {
      const old = (before as Record<string, unknown>)[key] ?? "";
      const cur = (after as Record<string, unknown>)[key] ?? "";
      if (String(old) !== String(cur)) parts.push(`${labels[key]}: "${old}" → "${cur}"`);
    }
    return parts.join("; ");
  }

  function parseNotifyUsers(raw: string): string[] {
    return raw.split(",").map((s) => s.trim()).filter(Boolean);
  }

  async function saveRecord(formData: FormData) {
    const current = editing === "new" ? null : editing;
    const now = formatNow();
    const fields = {
      title: String(formData.get("title")), category: String(formData.get("category")),
      owner: String(formData.get("owner")), status: String(formData.get("status")),
      description: String(formData.get("description") ?? ""),
    };

    if (isApiBacked) {
      let result: { ok: boolean; error?: string; data?: Record<string, unknown> };

      const notifyRaw = String(formData.get("notifyUsers") ?? "[]");
      let notifyIds: number[] = [];
      try { notifyIds = JSON.parse(notifyRaw); } catch { /* empty */ }

      if (isUsers) {
        const password = String(formData.get("password") ?? "");
        const phone = String(formData.get("phone") ?? "").replace(/\D/g, "") || undefined;
        const roleId = formData.get("role_id") ? Number(formData.get("role_id")) : undefined;
        const jobTitle = String(formData.get("job_title") ?? "") || undefined;
        const sectorId = formData.get("sector_id") ? Number(formData.get("sector_id")) : undefined;
        const invite = formData.get("invite") === "on";
        if (current) {
          const body: Record<string, unknown> = { name: fields.title, email: fields.owner, phone, active: fields.status === "Ativo", role_id: roleId, job_title: jobTitle, sector_id: sectorId };
          if (password) body.password = password;
          result = await updateUserAction(current.id, body);
        } else if (invite) {
          result = await inviteUserAction({ name: fields.title, email: fields.owner, phone, role_id: roleId, job_title: jobTitle, sector_id: sectorId });
        } else {
          if (!password) { setToast("Senha é obrigatória para novos usuários."); return; }
          result = await createUserAction({ name: fields.title, email: fields.owner, phone, password, active: fields.status === "Ativo", role_id: roleId, job_title: jobTitle, sector_id: sectorId });
        }
      } else if (isCadastros) {
        const cat = fixedCategory ?? fields.category;
        if (current) {
          const updateBody: RegistryUpdatePayload = { name: fields.title };
          if (cat === "Local") {
            const latRaw = String(formData.get("latitude") ?? "");
            const lngRaw = String(formData.get("longitude") ?? "");
            const radiusRaw = String(formData.get("geofence_radius_m") ?? "");
            if (latRaw) updateBody.latitude = Number(latRaw);
            if (lngRaw) updateBody.longitude = Number(lngRaw);
            if (radiusRaw) updateBody.geofence_radius_m = Number(radiusRaw);
          }
          result = await updateRegistryAction(current.id, updateBody, cat);
        } else {
          result = await createRegistryAction({ name: fields.title, category: cat });
        }
      } else if (isProcedimentos) {
        const link = String(formData.get("link") ?? "") || undefined;
        const pendingFiles: File[] = [];
        const fileInput = formData.getAll("attachmentFiles");
        for (const f of fileInput) {
          if (f instanceof File && f.size > 0) pendingFiles.push(f);
        }
        if (current) {
          result = await updateProcedureAction(current.id, { name: fields.title, link });
        } else {
          result = await createProcedureAction({ name: fields.title, link });
        }
        if (result.ok && pendingFiles.length > 0) {
          const entityId = current?.id ?? (result.data as Record<string, number>)?.id;
          if (entityId) {
            for (const file of pendingFiles) {
              await uploadAttachmentAction("procedure", entityId, file);
            }
          }
        }
      } else if (isMeetings) {
        const ownerRaw = String(formData.get("owner") ?? "");
        const ownerId = /^\d+$/.test(ownerRaw) ? Number(ownerRaw) : undefined;
        const scheduledAt = String(formData.get("scheduled_at") ?? "") || undefined;
        const location = String(formData.get("location") ?? "") || undefined;
        const { createMeetingAction, updateMeetingAction } = await import("@/app/actions");
        const apiBody = {
          title: fields.title,
          description: fields.description || undefined,
          scheduled_at: scheduledAt,
          location,
          status: fields.status,
          owner_user_id: ownerId,
          notify_user_ids: notifyIds.length ? notifyIds : undefined,
        };
        result = current
          ? await updateMeetingAction(current.id, apiBody)
          : await createMeetingAction(apiBody);
      } else if (isShiftReports) {
        const ownerRaw = String(formData.get("owner") ?? "");
        const ownerId = /^\d+$/.test(ownerRaw) ? Number(ownerRaw) : undefined;
        const shiftDate = String(formData.get("shift_date") ?? "") || undefined;
        const shiftType = String(formData.get("shift_type") ?? "") || undefined;
        const intOrNull = (name: string) => { const v = String(formData.get(name) ?? ""); return v ? Number(v) : undefined; };
        const strOrNull = (name: string) => String(formData.get(name) ?? "") || undefined;
        const { createShiftReportAction, updateShiftReportAction } = await import("@/app/actions");
        const apiBody = {
          title: fields.title,
          description: fields.description || undefined,
          shift_date: shiftDate,
          shift_type: shiftType,
          status: fields.status,
          supervisor: strOrNull("supervisor"),
          occupation: strOrNull("occupation"),
          average_daily: strOrNull("average_daily"),
          guests: intOrNull("guests"),
          uhs: intOrNull("uhs"),
          maintenance_count: intOrNull("maintenance_count"),
          cleaning: intOrNull("cleaning"),
          walk_in: intOrNull("walk_in"),
          input_quantity: intOrNull("input_quantity"),
          output_quantity: intOrNull("output_quantity"),
          return_of_customers: intOrNull("return_of_customers"),
          observations: strOrNull("observations"),
          notes_ab: strOrNull("notes_ab"),
          notes_reception: strOrNull("notes_reception"),
          notes_reservations: strOrNull("notes_reservations"),
          notes_governance: strOrNull("notes_governance"),
          notes_maintenance: strOrNull("notes_maintenance"),
          notes_ti: strOrNull("notes_ti"),
          notes_security: strOrNull("notes_security"),
          owner_user_id: ownerId,
          notify_user_ids: notifyIds.length ? notifyIds : undefined,
        };
        result = current
          ? await updateShiftReportAction(current.id, apiBody)
          : await createShiftReportAction(apiBody);
      } else if (isGenericModule) {
        const ownerRaw = String(formData.get("owner") ?? "");
        const ownerId = /^\d+$/.test(ownerRaw) ? Number(ownerRaw) : undefined;
        const apiBody = {
          title: fields.title,
          description: fields.description || undefined,
          category: fields.category || undefined,
          status: fields.status,
          owner_user_id: ownerId,
          notify_user_ids: notifyIds.length ? notifyIds : undefined,
        };
        result = current
          ? await updateModuleRecordAction(definition.slug, current.id, apiBody)
          : await createModuleRecordAction(definition.slug, apiBody);
      } else {
        result = { ok: false, error: "Módulo não suportado." };
      }

      if (!result.ok) { setToast(result.error ?? "Erro ao salvar."); window.setTimeout(() => setToast(""), 2600); return; }
      setEditing(null);
      setToast(`${definition.singular} ${current ? "atualizado" : "criado"} com sucesso.`);
      window.setTimeout(() => setToast(""), 2600);
      router.refresh();
      return;
    }

    const entry: HistoryEntry = current
      ? { type: "change", user: user.name, date: now, changes: diffChanges(current, fields) }
      : { type: "create", user: user.name, date: now, message: `Criou ${definition.singular}` };

    const notifyUsers = parseNotifyUsers(String(formData.get("notifyUsers") ?? ""));
    const prevHistory = current?.history ?? [];
    const record: ModuleRecord = {
      id: current?.id ?? Math.max(0, ...records.map((item) => item.id)) + 1,
      ...fields, notifyUsers, updatedAt: now, history: [...prevHistory, entry],
    };
    const next = current ? records.map((item) => item.id === current.id ? record : item) : [record, ...records];
    persist(next, `${definition.singular} ${current ? "atualizado" : "criado"} com sucesso.`);
    setEditing(null);
  }

  async function addComment(record: ModuleRecord, message: string) {
    if (!message.trim()) return;
    if (isApiBacked && entityType) {
      const result = await addCommentAction(entityType, record.id, message.trim());
      if (!result.ok) { setToast(result.error ?? "Erro ao comentar."); return; }
      setToast("Comentário adicionado.");
      window.setTimeout(() => setToast(""), 2600);
      fetchTimeline(entityType, record.id).then(setTimeline);
      return;
    }
    const now = formatNow();
    const entry: HistoryEntry = { type: "comment", user: user.name, date: now, message: message.trim() };
    const updated = { ...record, updatedAt: now, history: [...(record.history ?? []), entry] };
    const next = records.map((item) => item.id === record.id ? updated : item);
    persist(next, "Comentário adicionado.");
    setSelected(updated);
  }

  async function remove(record: ModuleRecord) {
    if (!window.confirm(`Excluir "${record.title}"? Esta ação não pode ser desfeita.`)) return;
    if (isApiBacked) {
      let result: { ok: boolean; error?: string };
      if (isUsers) result = await deleteUserAction(record.id);
      else if (isCadastros) result = await deleteRegistryAction(record.id, fixedCategory ?? record.category);
      else if (isProcedimentos) result = await deleteProcedureAction(record.id);
      else if (isMeetings) { const { deleteMeetingAction } = await import("@/app/actions"); result = await deleteMeetingAction(record.id); }
      else if (isShiftReports) { const { deleteShiftReportAction } = await import("@/app/actions"); result = await deleteShiftReportAction(record.id); }
      else if (isGenericModule) result = await deleteModuleRecordAction(definition.slug, record.id);
      else result = { ok: false, error: "Módulo não suportado." };
      if (!result.ok) { setToast(result.error ?? "Erro ao excluir."); window.setTimeout(() => setToast(""), 2600); return; }
      setSelected(null);
      setToast(`${definition.singular} excluído.`);
      window.setTimeout(() => setToast(""), 2600);
      router.refresh();
      return;
    }
    persist(records.filter((item) => item.id !== record.id), `${definition.singular} excluído.`);
    setSelected(null);
  }

  function exportCsv() {
    const rows = [["ID", "Título", "Categoria", "Responsável", "Status", "Atualização"], ...filtered.map((item) => [item.id, item.title, item.category, item.owner, item.status, item.updatedAt])];
    const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${definition.slug}.csv`; anchor.click(); URL.revokeObjectURL(url);
    setToast("Arquivo CSV gerado.");
  }

  return <>
      <header className="module-heading"><div><h1>{definition.title}</h1><p>{definition.description}</p></div>{canCreate && definition.layout !== "settings" && definition.layout !== "profile" && definition.layout !== "company" ? <button className="primary-button" onClick={() => setEditing("new")}><Plus size={18}/>{definition.action}</button> : null}</header>

      {definition.layout === "company" ? <CompanySettingsSection/> : definition.layout === "settings" ? <SettingsForm storageKey={storageKey} onSaved={() => setToast("Configurações salvas com sucesso.")}/> : definition.layout === "profile" ? <ProfileForm user={user} onSaved={(msg) => { setToast(msg); window.setTimeout(() => setToast(""), 2600); }}/> : <section className="module-panel">
        <div className="module-toolbar"><label><Search size={18}/><input value={query} onChange={(event) => handleServerSearch(event.target.value)} placeholder={`Buscar em ${definition.title.toLocaleLowerCase("pt-BR")}`}/></label>{!sp ? <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>{statuses.map((item) => <option key={item}>{item}</option>)}</select> : null}{!isApiBacked && !sp ? <button onClick={() => { setRecords(definition.records); localStorage.removeItem(storageKey); setToast("Dados fictícios restaurados."); }} title="Restaurar dados"><RefreshCw size={17}/></button> : null}<button onClick={exportCsv}><Download size={17}/> Exportar</button></div>
        {!ready ? <div className="module-state">Carregando registros…</div> : !visible.length ? <div className="module-state"><Search size={30}/><strong>Nenhum resultado</strong><span>Ajuste os filtros ou crie um novo registro.</span></div> : definition.layout === "cards" ? <div className="notice-grid">{visible.map((record) => <article key={record.id} onClick={() => (isUsers || isCadastros) ? setEditing(record) : setSelected(record)}><span>{record.category}</span><h2>{record.title}</h2><p>{record.description}</p><footer><small>{record.owner} · {record.updatedAt}</small><i className={statusClass(record.status)}>{record.status}</i></footer></article>)}</div> : <div className="module-table-wrap"><table><thead><tr><th>ID</th><th>{definition.singular}</th>{!fixedCategory && <th>Categoria</th>}<th>Responsável</th><th>Status</th><th>Atualização</th>{canMutate ? <th>Ações</th> : null}</tr></thead><tbody>{visible.map((record) => <tr key={record.id} onClick={() => (isUsers || isCadastros) ? setEditing(record) : setSelected(record)}><td className="protocol">#{record.id}</td><td><strong>{record.title}</strong></td>{!fixedCategory && <td>{record.category}</td>}<td>{record.owner}</td><td><span className={statusClass(record.status)}>{record.status}</span></td><td className="muted">{record.updatedAt}</td>{canMutate ? <td><div className="row-actions">{canEdit ? <button onClick={(event) => { event.stopPropagation(); setEditing(record); }} aria-label="Editar"><Pencil size={16}/></button> : null}{canDelete ? <button onClick={(event) => { event.stopPropagation(); remove(record); }} aria-label="Excluir"><Trash2 size={16}/></button> : null}</div></td> : null}</tr>)}</tbody></table></div>}
        <footer className="module-pagination"><span>{totalItems} registro(s)</span><div><button disabled={page <= 1} onClick={() => handleServerPage(page - 1)}><ChevronLeft/></button><span>Pagina {Math.min(page, pages)} de {pages}</span><button disabled={page >= pages} onClick={() => handleServerPage(page + 1)}><ChevronRight/></button></div></footer>
      </section>}

    {editing ? <div className="modal-layer" role="presentation"><section className={`record-modal${editing !== "new" && editing.history?.length ? " has-timeline" : ""}`} role="dialog" aria-modal="true"><header><div><span>{editing === "new" ? "Novo registro" : `#${editing.id}`}</span><h2>{editing === "new" ? definition.action : `Editar ${definition.singular}`}</h2></div><button className="icon-button" onClick={() => setEditing(null)}><X/></button></header>
      <form action={saveRecord}>
      {isUsers ? <>
        <label>Nome<input name="title" required defaultValue={editing === "new" ? "" : editing.title}/></label>
        <label>E-mail<input name="owner" type="email" required defaultValue={editing === "new" ? "" : editing.owner}/></label>
        <label>Telefone<input name="phone" type="tel" placeholder="(00) 00000-0000" defaultValue={editing === "new" ? "" : formatPhone(editing.phone ?? "")} onChange={(e) => { e.target.value = formatPhone(e.target.value); }}/></label>
        <div className="form-grid">
          <label>Cargo / Função<input name="job_title" placeholder="Ex: Recepcionista" defaultValue={editing === "new" ? "" : editing.jobTitle ?? ""}/></label>
          <label>Perfil de acesso<select name="role_id" defaultValue={editing === "new" ? "" : String(editing.roleId ?? "")}><option value="">Sem perfil</option>{definition.extraData?.roles?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
        </div>
        <div className="form-grid">
          <label>Setor<select name="sector_id" defaultValue={editing === "new" ? "" : String(editing.sectorId ?? "")}><option value="">Nenhum</option>{definition.extraData?.sectors?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          <label>Status<select name="status" defaultValue={editing === "new" ? "Ativo" : editing.status}><option>Ativo</option><option>Inativo</option></select></label>
        </div>
        {editing === "new" && <label className="invite-toggle"><input name="invite" type="checkbox" onChange={(e) => { const pwField = e.target.form?.querySelector<HTMLInputElement>('[name="password"]'); if (pwField) { pwField.closest("label")!.style.display = e.target.checked ? "none" : ""; pwField.required = !e.target.checked; } }}/> Convidar por e-mail (o usuário definirá a própria senha)</label>}
        <label>Senha{editing !== "new" && <small className="field-hint"> (deixe vazio para manter a atual)</small>}<input name="password" type="password" {...(editing === "new" ? { required: true } : {})} placeholder={editing === "new" ? "" : "••••••••"}/></label>
      </> : isCadastros ? <>
        <label>Nome<input name="title" required defaultValue={editing === "new" ? "" : editing.title}/></label>
        {fixedCategory ? (
          <input type="hidden" name="category" value={fixedCategory} />
        ) : (
          <label>Tipo<select name="category" defaultValue={editing === "new" ? "Setor" : editing.category}><option>Setor</option><option>Local</option><option>Função</option></select></label>
        )}
        {fixedCategory === "Local" && <>
          <div className="form-grid">
            <label>Latitude<input name="latitude" type="number" step="any" placeholder="-23.550520" defaultValue={editing === "new" ? "" : editing.latitude ?? ""}/></label>
            <label>Longitude<input name="longitude" type="number" step="any" placeholder="-46.633308" defaultValue={editing === "new" ? "" : editing.longitude ?? ""}/></label>
          </div>
          <label>Raio de geofencing (metros)<input name="geofence_radius_m" type="number" min="1" placeholder="100" defaultValue={editing === "new" ? "" : editing.geofenceRadiusM ?? ""}/><small className="field-hint">Distância máxima aceita entre o funcionário e este local para registrar o ponto pelo Portal do Colaborador.</small></label>
        </>}
        <input type="hidden" name="status" value="Ativo" />
        <input type="hidden" name="owner" value="Administração" />
        <input type="hidden" name="description" value="" />
      </> : isProcedimentos ? <>
        <label>Nome<input name="title" required defaultValue={editing === "new" ? "" : editing.title}/></label>
        <label>Link externo<input name="link" type="url" placeholder="https://..." defaultValue={editing === "new" ? "" : editing.description ?? ""}/></label>
        <input type="hidden" name="category" value="Procedimento"/>
        <input type="hidden" name="owner" value="Administração"/>
        <input type="hidden" name="status" value="Ativo"/>
        <input type="hidden" name="description" value=""/>
        <div>
          <label style={{ marginBottom: 8 }}>Anexos</label>
          <div className="drop-zone" onClick={() => { const inp = document.getElementById("proc-file-input") as HTMLInputElement; inp?.click(); }}>
            <Upload size={22}/>
            <span>Arraste arquivos ou clique para selecionar</span>
            <input id="proc-file-input" name="attachmentFiles" type="file" multiple style={{ display: "none" }} onChange={(e) => { if (e.target.files) { const dt = new DataTransfer(); for (const f of Array.from(e.target.files)) dt.items.add(f); e.target.files = dt.files; } }}/>
          </div>
          {editing !== "new" && selectedAttachments.length > 0 && <div className="attachment-grid">{selectedAttachments.map((att) => <div key={att.id} className="attachment-preview"><button type="button" className="attachment-remove" onClick={() => { deleteAttachmentAction(att.id); setSelectedAttachments((prev) => prev.filter((a) => a.id !== att.id)); }}><X size={14}/></button><div className="attachment-file-icon"><Paperclip size={20}/></div><span className="attachment-name">{att.filename}</span></div>)}</div>}
        </div>
      </> : isMeetings ? <>
        <label>Título<input name="title" required defaultValue={editing === "new" ? "" : editing.title}/></label>
        <div className="form-grid">
          <label>Data e hora<input name="scheduled_at" type="datetime-local" defaultValue={editing !== "new" && editing.scheduledAt ? editing.scheduledAt : ""}/></label>
          <label>Status<select name="status" defaultValue={editing === "new" ? "Agendada" : editing.status}><option>Agendada</option><option>Em andamento</option><option>Concluída</option><option>Cancelada</option></select></label>
        </div>
        <label>Local<input name="location" defaultValue={editing !== "new" && editing.location ? editing.location : ""}/></label>
        <label>Responsável<UserAutocomplete name="owner" required defaultValue={editing === "new" ? user.name : editing.owner} placeholder="Buscar responsável..."/></label>
        <label>Notificar<UserMultiSelect name="notifyUsers" defaultValues={editing !== "new" && editing.notifyUserObjects ? editing.notifyUserObjects : []}/></label>
        <label>Descrição<textarea name="description" rows={4} defaultValue={editing === "new" ? "" : editing.description}/></label>
      </> : isShiftReports ? <>
        <label>Título<input name="title" required defaultValue={editing === "new" ? "" : editing.title}/></label>
        <div className="form-grid">
          <label>Data do turno<input name="shift_date" type="date" defaultValue={editing !== "new" && editing.shiftDate ? editing.shiftDate : ""}/></label>
          <label>Turno<select name="shift_type" defaultValue={editing !== "new" && editing.shiftType ? editing.shiftType : "morning"}><option value="morning">Manhã</option><option value="afternoon">Tarde</option><option value="night">Noite</option><option value="diurno">Diurno</option><option value="noturno">Noturno</option></select></label>
          <label>Status<select name="status" defaultValue={editing === "new" ? "Em andamento" : editing.status}><option>Em andamento</option><option>Aguardando</option><option>Concluído</option></select></label>
        </div>
        <label>Responsável<UserAutocomplete name="owner" required defaultValue={editing === "new" ? user.name : editing.owner} placeholder="Buscar responsável..."/></label>
        <label>Supervisor<input name="supervisor" defaultValue={editing !== "new" ? editing.supervisor ?? "" : ""}/></label>
        <fieldset className="form-section"><legend>Indicadores</legend>
          <div className="form-grid">
            <label>Ocupação<input name="occupation" defaultValue={editing !== "new" ? editing.occupation ?? "" : ""}/></label>
            <label>Diária média<input name="average_daily" defaultValue={editing !== "new" ? editing.average_daily ?? "" : ""}/></label>
            <label>Hóspedes<input name="guests" type="number" defaultValue={editing !== "new" ? editing.guests ?? "" : ""}/></label>
            <label>UH&apos;s<input name="uhs" type="number" defaultValue={editing !== "new" ? editing.uhs ?? "" : ""}/></label>
            <label>Manutenção<input name="maintenance_count" type="number" defaultValue={editing !== "new" ? editing.maintenance_count ?? "" : ""}/></label>
            <label>Limpeza<input name="cleaning" type="number" defaultValue={editing !== "new" ? editing.cleaning ?? "" : ""}/></label>
          </div>
          <div className="form-grid">
            <label>Walk-in<input name="walk_in" type="number" defaultValue={editing !== "new" ? editing.walk_in ?? "" : ""}/></label>
            <label>Entradas<input name="input_quantity" type="number" defaultValue={editing !== "new" ? editing.input_quantity ?? "" : ""}/></label>
            <label>Saídas<input name="output_quantity" type="number" defaultValue={editing !== "new" ? editing.output_quantity ?? "" : ""}/></label>
            <label>Retorno de clientes<input name="return_of_customers" type="number" defaultValue={editing !== "new" ? editing.return_of_customers ?? "" : ""}/></label>
          </div>
        </fieldset>
        <fieldset className="form-section"><legend>Observações por setor</legend>
          <label>Observação geral<textarea name="observations" rows={3} defaultValue={editing !== "new" ? editing.observations ?? "" : ""}/></label>
          <div className="form-grid">
            <label>A&amp;B<textarea name="notes_ab" rows={2} defaultValue={editing !== "new" ? editing.notes_ab ?? "" : ""}/></label>
            <label>Recepção<textarea name="notes_reception" rows={2} defaultValue={editing !== "new" ? editing.notes_reception ?? "" : ""}/></label>
          </div>
          <div className="form-grid">
            <label>Reservas<textarea name="notes_reservations" rows={2} defaultValue={editing !== "new" ? editing.notes_reservations ?? "" : ""}/></label>
            <label>Governança<textarea name="notes_governance" rows={2} defaultValue={editing !== "new" ? editing.notes_governance ?? "" : ""}/></label>
          </div>
          <div className="form-grid">
            <label>Manutenção<textarea name="notes_maintenance" rows={2} defaultValue={editing !== "new" ? editing.notes_maintenance ?? "" : ""}/></label>
            <label>TI<textarea name="notes_ti" rows={2} defaultValue={editing !== "new" ? editing.notes_ti ?? "" : ""}/></label>
          </div>
          <label>Segurança<textarea name="notes_security" rows={2} defaultValue={editing !== "new" ? editing.notes_security ?? "" : ""}/></label>
        </fieldset>
        <label>Notificar<UserMultiSelect name="notifyUsers" defaultValues={editing !== "new" && editing.notifyUserObjects ? editing.notifyUserObjects : []}/></label>
        <label>Descrição<textarea name="description" rows={3} defaultValue={editing === "new" ? "" : editing.description}/></label>
        {editing !== "new" && <HandoffSection shiftReportId={editing.id} shiftDate={editing.shiftDate} shiftType={editing.shiftType} />}
      </> : <>
        <label>Título<input name="title" required defaultValue={editing === "new" ? "" : editing.title}/></label>
        <div className="form-grid">
          <label>Categoria<input name="category" required defaultValue={editing === "new" ? "Geral" : editing.category}/></label>
          <label>Status<select name="status" defaultValue={editing === "new" ? "Em andamento" : editing.status}><option>Em andamento</option><option>Aguardando</option><option>Agendada</option><option>Ativo</option><option>Publicado</option><option>Rascunho</option><option>Concluído</option></select></label>
        </div>
        <label>Responsável<UserAutocomplete name="owner" required defaultValue={editing === "new" ? user.name : editing.owner} placeholder="Buscar responsável..."/></label>
        <label>Notificar<UserMultiSelect name="notifyUsers" defaultValues={editing !== "new" && editing.notifyUserObjects ? editing.notifyUserObjects : []}/><small className="field-hint">Pessoas que serão notificadas sobre atualizações.</small></label>
        <label>Descrição<textarea name="description" rows={4} defaultValue={editing === "new" ? "" : editing.description}/></label>
      </>}
      <footer><button type="button" onClick={() => setEditing(null)}>Cancelar</button><button type="submit">Salvar</button></footer>
    </form>
      {!isUsers && editing !== "new" && editing.history?.length ? <div className="modal-timeline"><h3><MessageSquare size={15}/>Tratativa</h3><div className="timeline-thread">{editing.history.map((entry, i) => {
        const entryInitials = entry.user.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
        return <article key={i} className={`thread-entry thread-${entry.type}`}>
          <div className="thread-avatar">{entryInitials}</div>
          <div className="thread-body">
            <div className="thread-header"><strong>{entry.user}</strong><time>{entry.date}</time></div>
            {entry.type === "comment" && entry.message ? <p className="thread-message">{entry.message}</p> : null}
            {entry.type === "create" ? <p className="thread-system">{entry.message}</p> : null}
            {entry.type === "change" && entry.changes ? <div className="thread-changes">{entry.changes.split("; ").map((c, j) => <span key={j}>{c}</span>)}</div> : null}
          </div>
        </article>;
      })}</div></div> : null}
    </section></div> : null}
    {selected && !editing ? <><button className="panel-backdrop" onClick={() => setSelected(null)} aria-label="Fechar detalhes"/><aside className="record-drawer">
      <header><div><span>#{selected.id} · {selected.category}</span><h2>{selected.title}</h2></div><button className="icon-button" onClick={() => setSelected(null)}><X/></button></header>
      <dl>
        <div><dt>Status</dt><dd><span className={statusClass(selected.status)}>{selected.status}</span></dd></div>
        <div><dt>Responsável</dt><dd>{selected.owner}</dd></div>
        {selected.notifyUsers && selected.notifyUsers.length > 0 && <div><dt>Notificar</dt><dd><div className="notify-chips">{selected.notifyUsers.map((name, i) => <span key={i} className="notify-chip">{name}</span>)}</div></dd></div>}
        <div><dt>Atualização</dt><dd>{selected.updatedAt}</dd></div>
        {isProcedimentos && selected.description && <div><dt>Link</dt><dd><a href={selected.description} target="_blank" rel="noopener noreferrer">{selected.description}</a></dd></div>}
        {!isProcedimentos && <div><dt>Descrição</dt><dd>{selected.description || "Nenhuma descrição informada."}</dd></div>}
        {hasAttachments && selectedAttachments.length > 0 && <div><dt>Anexos</dt><dd><div className="attachment-grid drawer-attachments">{selectedAttachments.map((att) => <a key={att.id} href={`/api/attachments/${att.id}/download`} target="_blank" rel="noopener noreferrer" className="attachment-preview"><div className="attachment-file-icon"><Paperclip size={20}/></div><span className="attachment-name">{att.filename}</span></a>)}</div></dd></div>}
      </dl>
      {!isUsers && <div className="record-timeline">
        <h3><MessageSquare size={15}/>Tratativa</h3>
        {isApiBacked && timeline.length > 0 ? <div className="timeline-thread">
          {timeline.map((entry) => {
            const entryInitials = entry.user.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
            const dateStr = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(entry.created_at));
            return <article key={entry.id} className={`thread-entry thread-${entry.event_type === "comment" || entry.event_type.startsWith("attachment") ? "comment" : entry.event_type.startsWith("create") ? "create" : "change"}`}>
              <div className="thread-avatar">{entryInitials}</div>
              <div className="thread-body">
                <div className="thread-header"><strong>{entry.user}</strong><time>{dateStr}</time></div>
                {entry.event_type === "comment" && entry.message ? <p className="thread-message">{entry.message}</p> : null}
                {entry.event_type.startsWith("attachment") && entry.message ? <p className="thread-system">{entry.message}</p> : null}
                {entry.event_type.startsWith("create") ? <p className="thread-system">Criou o registro</p> : null}
                {entry.event_type === "delete" ? <p className="thread-system">Excluiu o registro</p> : null}
                {entry.changes ? <div className="thread-changes">{Object.entries(entry.changes).map(([k, v]) => <span key={k}>{k}: &quot;{(v as {from: string}).from}&quot; → &quot;{(v as {to: string}).to}&quot;</span>)}</div> : null}
              </div>
            </article>;
          })}
        </div> : !isApiBacked && selected.history && selected.history.length > 0 ? <div className="timeline-thread">
          {selected.history.map((entry, i) => {
            const entryInitials = entry.user.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
            return <article key={i} className={`thread-entry thread-${entry.type}`}>
              <div className="thread-avatar">{entryInitials}</div>
              <div className="thread-body">
                <div className="thread-header"><strong>{entry.user}</strong><time>{entry.date}</time></div>
                {entry.type === "comment" && entry.message ? <p className="thread-message">{entry.message}</p> : null}
                {entry.type === "create" ? <p className="thread-system">{entry.message}</p> : null}
                {entry.type === "change" && entry.changes ? <div className="thread-changes">{entry.changes.split("; ").map((c, j) => <span key={j}>{c}</span>)}</div> : null}
              </div>
            </article>;
          })}
        </div> : <p className="thread-empty">Nenhuma interação registrada.</p>}
        {canMutate ? <CommentInput onSend={(msg) => addComment(selected, msg)}/> : <p className="thread-empty">Comentários serão liberados com a API de mutações.</p>}
      </div>}
      <footer>
        {canEdit ? <button onClick={() => setEditing(selected)}><Pencil size={16}/>Editar</button> : null}
        {canDelete ? <button onClick={() => remove(selected)}><Trash2 size={16}/>Excluir</button> : null}
      </footer>
    </aside></> : null}
    {toast ? <div className="module-toast" role="status">{toast}</div> : null}
  </>;
}

function CommentInput({ onSend }: { onSend: (message: string) => void }) {
  const [value, setValue] = useState("");
  return <form className="comment-form" onSubmit={(e) => { e.preventDefault(); onSend(value); setValue(""); }}>
    <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Escreva um comentário..." />
    <button type="submit" disabled={!value.trim()} aria-label="Enviar"><Send size={16}/></button>
  </form>;
}

function SettingsForm({ storageKey, onSaved }: { storageKey: string; onSaved: () => void }) {
  return <div className="settings-form">
    <form action={(data) => { localStorage.setItem(`${storageKey}:preferences`, JSON.stringify(Object.fromEntries(data))); onSaved(); }}>
      <section><h2>Notificações</h2><p>Escolha como deseja acompanhar as atualizações.</p><label className="switch-row"><span><strong>Notificações no sistema</strong><small>Alertas de atividades e menções.</small></span><input name="in_app" type="checkbox" defaultChecked/></label><label className="switch-row"><span><strong>Resumo por e-mail</strong><small>Resumo diário das pendências.</small></span><input name="email_digest" type="checkbox" defaultChecked/></label></section>
      <section><h2>Experiência</h2><p>Preferências aplicadas a este navegador.</p><label>Idioma<select name="language" defaultValue="pt-BR"><option value="pt-BR">Português (Brasil)</option><option value="en">English</option></select></label><label>Página inicial<select name="home" defaultValue="dashboard"><option value="dashboard">Dashboard</option><option value="ordens-servico">Ordens de Serviço</option></select></label></section>
      <button className="primary-button" type="submit">Salvar alterações</button>
    </form>
    <BrevoSettingsSection/>
    <EvolutionSettingsSection/>
  </div>;
}
