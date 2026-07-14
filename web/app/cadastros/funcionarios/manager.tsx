"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Trash2, Edit2, Upload, History, KeyRound, X } from "lucide-react";
import {
  createEmployeeAction,
  deleteEmployeeAction,
  fetchEmployee,
  fetchEmployees,
  fetchRegistryOptions,
  fetchTimeline,
  importEmployeesAction,
  resetEmployeePinAction,
  updateEmployeeAction,
  uploadEmployeeAvatarAction,
  type Employee,
  type EmployeeImportResult,
  type EmployeePayload,
  type RegistryOption,
  type TimelineEntry,
} from "@/app/actions";
import type { TenantUser } from "@/lib/api";
import { formatCEP, formatCPF, isValidBirthDate, isValidCEP, isValidCPF, onlyDigits } from "@/lib/validators";
import { useCepLookup } from "@/lib/use-document-lookup";

function hasPermission(user: TenantUser, code: string) {
  return user.permissions.includes("*") || user.permissions.includes(code);
}

const STATUS_LABELS: Record<string, string> = {
  active: "Ativo",
  inactive: "Inativo",
  terminated: "Desligado",
};

const BR_STATES = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
  "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
  "SP", "SE", "TO",
];

const EMPTY_FORM: EmployeePayload = {
  name: "",
  cpf: "",
  rg: "",
  birth_date: "",
  phone: "",
  personal_email: "",
  address_street: "",
  address_number: "",
  address_complement: "",
  address_neighborhood: "",
  address_city: "",
  address_state: "",
  address_zip: "",
  status: "active",
  job_title: "",
  hire_date: "",
  termination_date: "",
  registration_number: "",
  salary: null,
  sector_id: null,
};

type FormErrors = Partial<Record<keyof EmployeePayload, string>>;

export function EmployeeManager({ user }: { user: TenantUser }) {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<EmployeePayload>(EMPTY_FORM);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);
  const cep = useCepLookup((fields) => {
    setFormData((prev) => ({
      ...prev,
      address_street: fields.address_street ?? prev.address_street,
      address_neighborhood: fields.address_neighborhood ?? prev.address_neighborhood,
      address_city: fields.address_city ?? prev.address_city,
      address_state: fields.address_state ?? prev.address_state,
    }));
  });
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [pinResetting, setPinResetting] = useState(false);
  const [resetPin, setResetPin] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [sectors, setSectors] = useState<RegistryOption[]>([]);
  const [functions, setFunctions] = useState<RegistryOption[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<TimelineEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<EmployeeImportResult | null>(null);

  const canManage = hasPermission(user, "employee.manage");
  const canManageTimeclock = hasPermission(user, "timeclock.manage");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    setLoading(true);
    fetchEmployees({ page, pageSize, status: statusFilter || undefined })
      .then((res) => {
        setEmployees(res.items);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter]);

  useEffect(() => {
    fetchRegistryOptions("Setor").then(setSectors);
    fetchRegistryOptions("Função").then(setFunctions);
  }, []);

  function resetForm() {
    setShowForm(false);
    setEditingId(null);
    setFormData(EMPTY_FORM);
    setErrors({});
    setAvatarUrl(null);
    setShowHistory(false);
    setHistory([]);
    setResetPin(null);
  }

  function setField<K extends keyof EmployeePayload>(field: K, value: EmployeePayload[K]) {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  function validate(): FormErrors {
    const next: FormErrors = {};
    if (!formData.name?.trim()) next.name = "Nome é obrigatório.";
    if (!formData.cpf?.trim()) {
      next.cpf = "CPF é obrigatório.";
    } else if (!isValidCPF(formData.cpf)) {
      next.cpf = "CPF inválido.";
    }
    if (formData.birth_date && !isValidBirthDate(formData.birth_date)) {
      next.birth_date = "Data de nascimento inválida.";
    }
    if (formData.hire_date && !isValidBirthDate(formData.hire_date)) {
      next.hire_date = "Data de admissão inválida.";
    }
    if (formData.termination_date && !isValidBirthDate(formData.termination_date)) {
      next.termination_date = "Data de desligamento inválida.";
    }
    if (formData.address_zip && !isValidCEP(formData.address_zip)) {
      next.address_zip = "CEP deve ter 8 dígitos.";
    }
    return next;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setSaving(true);
    const payload: EmployeePayload = { ...formData, cpf: onlyDigits(formData.cpf) };
    const result = editingId
      ? await updateEmployeeAction(editingId, payload)
      : await createEmployeeAction(payload);
    setSaving(false);

    if (result.ok) {
      showToast(editingId ? "Funcionário atualizado." : "Funcionário criado.");
      resetForm();
      reload();
    } else {
      showToast(result.error ?? "Erro ao salvar.");
    }
  }

  async function handleEdit(employee: Employee) {
    setEditingId(employee.id);
    setShowForm(true);
    setErrors({});
    setShowHistory(false);
    setHistory([]);
    setFormData({ ...EMPTY_FORM, name: employee.name, cpf: employee.cpf ?? "", status: employee.status });
    setAvatarUrl(employee.avatar_url);
    setResetPin(null);

    const detail = await fetchEmployee(employee.id);
    if (detail) {
      setFormData({
        name: detail.name,
        cpf: detail.cpf ?? "",
        rg: detail.rg ?? "",
        birth_date: detail.birth_date ?? "",
        phone: detail.phone ?? "",
        personal_email: detail.personal_email ?? "",
        address_street: detail.address_street ?? "",
        address_number: detail.address_number ?? "",
        address_complement: detail.address_complement ?? "",
        address_neighborhood: detail.address_neighborhood ?? "",
        address_city: detail.address_city ?? "",
        address_state: detail.address_state ?? "",
        address_zip: detail.address_zip ?? "",
        status: detail.status,
        job_title: detail.job_title ?? "",
        hire_date: detail.hire_date ?? "",
        termination_date: detail.termination_date ?? "",
        registration_number: detail.registration_number ?? "",
        salary: detail.salary ?? null,
        sector_id: detail.sector_id ?? null,
      });
      setAvatarUrl(detail.avatar_url);
    }
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !editingId) return;

    setAvatarUploading(true);
    const formDataUpload = new FormData();
    formDataUpload.append("file", file);
    const result = await uploadEmployeeAvatarAction(editingId, formDataUpload);
    setAvatarUploading(false);

    if (result.ok) {
      setAvatarUrl((result.data as { avatar_url?: string })?.avatar_url ?? null);
      showToast("Avatar atualizado.");
    } else {
      showToast(result.error ?? "Erro ao enviar avatar.");
    }
  }

  async function handleResetPin() {
    if (!editingId) return;
    if (!confirm(`Resetar o PIN de acesso ao Portal do Colaborador de "${formData.name}"? O PIN atual deixará de funcionar.`)) return;

    setPinResetting(true);
    const result = await resetEmployeePinAction(editingId);
    setPinResetting(false);

    if (result.ok) {
      setResetPin(result.pin);
    } else {
      showToast(result.error);
    }
  }

  async function handleToggleHistory() {
    const next = !showHistory;
    setShowHistory(next);
    if (next && editingId) {
      setHistoryLoading(true);
      const items = await fetchTimeline("employee", editingId);
      setHistory(items);
      setHistoryLoading(false);
    }
  }

  async function handleDelete(employee: Employee) {
    if (!confirm(`Remover funcionário "${employee.name}"?`)) return;
    const result = await deleteEmployeeAction(employee.id);
    if (result.ok) {
      showToast("Funcionário removido.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao remover.");
    }
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setImporting(true);
    setImportResult(null);
    const formDataUpload = new FormData();
    formDataUpload.append("file", file);
    const result = await importEmployeesAction(formDataUpload);
    setImporting(false);

    if (result.ok) {
      setImportResult(result.result);
      showToast(`Importação concluída: ${result.result.created} criado(s), ${result.result.failed} com erro.`);
      reload();
    } else {
      showToast(result.error);
    }
  }

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <>
      <header className="module-heading">
        <div>
          <p className="eyebrow">Cadastros</p>
          <h1>Funcionários</h1>
          <p>Cadastro de RH dos funcionários do hotel, separado das contas de login do sistema.</p>
        </div>
        {canManage && (
          <button className="primary-button" type="button" onClick={() => setShowForm(true)}>
            <Plus size={18} /> Novo funcionário
          </button>
        )}
      </header>

      <section className="module-panel">
        <div className="module-toolbar">
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">Todos os status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {canManage && (
            <button
              type="button"
              onClick={() => { setShowImport((v) => !v); setImportResult(null); }}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Upload size={16} /> Importar CSV
            </button>
          )}
        </div>

      {canManage && showImport && (
        <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
          <p style={{ marginTop: 0 }}>
            Envie um CSV com colunas <code>name,cpf,rg,birth_date,phone,personal_email,address_street,
            address_number,address_complement,address_neighborhood,address_city,address_state,address_zip,
            status,job_title,hire_date,termination_date,registration_number</code>. Apenas <code>name</code> e{" "}
            <code>cpf</code> são obrigatórios.
          </p>
          <input type="file" accept=".csv,text/csv" onChange={handleImportFile} disabled={importing} />
          {importing && <p>Importando...</p>}
          {importResult && (
            <div className="module-table-wrap" style={{ marginTop: "var(--sp-3)" }}>
              <table>
                <thead>
                  <tr>
                    <th>Linha</th>
                    <th>Nome</th>
                    <th>Status</th>
                    <th>Detalhe</th>
                  </tr>
                </thead>
                <tbody>
                  {importResult.results.map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      <td>{row.name ?? "—"}</td>
                      <td>
                        <span className={row.ok ? "status status-done" : "status status-progress"}>
                          {row.ok ? "Criado" : "Erro"}
                        </span>
                      </td>
                      <td>{row.error ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {canManage && showForm && (
        <div className="modal-layer" onClick={resetForm}>
          <div className={`record-modal${showHistory ? " has-timeline" : ""}`} onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <span>Cadastros</span>
                <h2>{editingId ? "Editar funcionário" : "Novo funcionário"}</h2>
              </div>
              <button type="button" className="icon-button" onClick={resetForm} aria-label="Fechar">
                <X />
              </button>
            </header>
            <form onSubmit={handleSubmit}>
              {editingId && (
                <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)" }}>
                  {avatarUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={avatarUrl}
                      alt="Avatar"
                      style={{ width: 48, height: 48, borderRadius: "50%", objectFit: "cover" }}
                    />
                  ) : (
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: "50%",
                        backgroundColor: "var(--field-bg)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {formData.name.slice(0, 1).toUpperCase()}
                    </div>
                  )}
                  <label style={{ cursor: "pointer" }}>
                    <span className="status status-progress" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <Upload size={14} /> {avatarUploading ? "Enviando..." : "Trocar avatar"}
                    </span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleAvatarChange}
                      disabled={avatarUploading}
                      style={{ display: "none" }}
                    />
                  </label>
                  {canManageTimeclock && (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={handleResetPin}
                      disabled={pinResetting}
                      style={{ marginLeft: "auto" }}
                    >
                      <KeyRound size={14} /> {pinResetting ? "Resetando..." : "Resetar PIN"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleToggleHistory}
                    style={{ marginLeft: canManageTimeclock ? 0 : "auto" }}
                  >
                    <History size={14} /> {showHistory ? "Ocultar histórico" : "Ver histórico"}
                  </button>
                </div>
              )}

              {editingId && resetPin && (
                <div
                  style={{
                    padding: "var(--sp-3) var(--sp-4)",
                    borderRadius: "var(--radius-md)",
                    backgroundColor: "var(--field-bg)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "var(--sp-3)",
                  }}
                >
                  <span>
                    Novo PIN gerado: <strong style={{ fontSize: "1.1em", letterSpacing: "2px" }}>{resetPin}</strong> — informe ao
                    funcionário; ele deverá trocá-lo no primeiro acesso ao Portal do Colaborador.
                  </span>
                  <button type="button" className="secondary-button" onClick={() => setResetPin(null)}>Ok</button>
                </div>
              )}

              <div className="form-grid">
          <div>
            <label>Nome *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Nome completo"
              required
            />
            {errors.name && <small style={{ color: "var(--danger, #c0392b)" }}>{errors.name}</small>}
          </div>
          <div>
            <label>CPF *</label>
            <input
              type="text"
              value={formatCPF(formData.cpf)}
              onChange={(e) => setField("cpf", onlyDigits(e.target.value))}
              placeholder="000.000.000-00"
              maxLength={14}
              required
            />
            {errors.cpf && <small style={{ color: "var(--danger, #c0392b)" }}>{errors.cpf}</small>}
          </div>
          <div>
            <label>RG</label>
            <input
              type="text"
              value={formData.rg ?? ""}
              onChange={(e) => setField("rg", e.target.value)}
              placeholder="Número do RG"
            />
          </div>
          <div>
            <label>Data de nascimento</label>
            <input
              type="date"
              value={formData.birth_date ?? ""}
              onChange={(e) => setField("birth_date", e.target.value)}
              max={new Date().toISOString().slice(0, 10)}
            />
            {errors.birth_date && <small style={{ color: "var(--danger, #c0392b)" }}>{errors.birth_date}</small>}
          </div>
          <div>
            <label>Telefone</label>
            <input
              type="text"
              value={formData.phone ?? ""}
              onChange={(e) => setField("phone", e.target.value)}
              placeholder="(11) 99999-9999"
            />
          </div>
          <div>
            <label>E-mail pessoal</label>
            <input
              type="email"
              value={formData.personal_email ?? ""}
              onChange={(e) => setField("personal_email", e.target.value)}
              placeholder="email@exemplo.com"
            />
          </div>
          <div>
            <label>Status</label>
            <select
              value={formData.status ?? "active"}
              onChange={(e) => setField("status", e.target.value)}
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Cargo</label>
            <select
              value={formData.job_title ?? ""}
              onChange={(e) => setField("job_title", e.target.value)}
            >
              <option value="">—</option>
              {functions.map((fn) => (
                <option key={fn.id} value={fn.name}>
                  {fn.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Matrícula</label>
            <input
              type="text"
              value={formData.registration_number ?? ""}
              onChange={(e) => setField("registration_number", e.target.value)}
              placeholder="Número de matrícula"
            />
          </div>
          <div>
            <label>Salário</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={formData.salary ?? ""}
              onChange={(e) => setField("salary", e.target.value ? Number(e.target.value) : null)}
              placeholder="Usado para calcular o valor da hora extra"
            />
          </div>
          <div>
            <label>Setor</label>
            <select
              value={formData.sector_id ?? ""}
              onChange={(e) => setField("sector_id", e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">—</option>
              {sectors.map((sector) => (
                <option key={sector.id} value={sector.id}>
                  {sector.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Data de admissão</label>
            <input
              type="date"
              value={formData.hire_date ?? ""}
              onChange={(e) => setField("hire_date", e.target.value)}
              max={new Date().toISOString().slice(0, 10)}
            />
            {errors.hire_date && <small style={{ color: "var(--danger, #c0392b)" }}>{errors.hire_date}</small>}
          </div>
          <div>
            <label>Data de desligamento</label>
            <input
              type="date"
              value={formData.termination_date ?? ""}
              onChange={(e) => setField("termination_date", e.target.value)}
            />
            {errors.termination_date && <small style={{ color: "var(--danger, #c0392b)" }}>{errors.termination_date}</small>}
          </div>
          <div>
            <label>CEP {cep.loading && "(buscando...)"}</label>
            <input
              type="text"
              value={formatCEP(formData.address_zip ?? "")}
              onChange={(e) => setField("address_zip", onlyDigits(e.target.value))}
              onBlur={(e) => cep.handleBlur(e.target.value)}
              placeholder="00000-000"
              maxLength={9}
            />
            {errors.address_zip && <small style={{ color: "var(--danger, #c0392b)" }}>{errors.address_zip}</small>}
            {!errors.address_zip && cep.notFound && <small style={{ color: "var(--danger, #c0392b)" }}>CEP não encontrado.</small>}
          </div>
          <div>
            <label>Logradouro</label>
            <input
              type="text"
              value={formData.address_street ?? ""}
              onChange={(e) => setField("address_street", e.target.value)}
              placeholder="Rua, avenida..."
            />
          </div>
          <div>
            <label>Número</label>
            <input
              type="text"
              value={formData.address_number ?? ""}
              onChange={(e) => setField("address_number", e.target.value)}
              placeholder="123"
            />
          </div>
          <div>
            <label>Complemento</label>
            <input
              type="text"
              value={formData.address_complement ?? ""}
              onChange={(e) => setField("address_complement", e.target.value)}
              placeholder="Apto, bloco..."
            />
          </div>
          <div>
            <label>Bairro</label>
            <input
              type="text"
              value={formData.address_neighborhood ?? ""}
              onChange={(e) => setField("address_neighborhood", e.target.value)}
              placeholder="Bairro"
            />
          </div>
          <div>
            <label>Cidade</label>
            <input
              type="text"
              value={formData.address_city ?? ""}
              onChange={(e) => setField("address_city", e.target.value)}
              placeholder="Cidade"
            />
          </div>
          <div>
            <label>UF</label>
            <select
              value={formData.address_state ?? ""}
              onChange={(e) => setField("address_state", e.target.value)}
            >
              <option value="">—</option>
              {BR_STATES.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          </div>
              </div>

              <footer>
                <button type="button" onClick={resetForm}>Cancelar</button>
                <button type="submit" disabled={saving}>
                  {saving ? "Salvando..." : editingId ? "Atualizar" : "Criar"}
                </button>
              </footer>
            </form>

            {editingId && showHistory && (
              <div className="module-table-wrap" style={{ borderTop: "1px solid var(--line)" }}>
                {historyLoading ? (
                  <p style={{ padding: "var(--sp-4) var(--sp-5)" }}>Carregando histórico...</p>
                ) : history.length === 0 ? (
                  <p style={{ padding: "var(--sp-4) var(--sp-5)" }}>Nenhum evento registrado.</p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>Data</th>
                        <th>Evento</th>
                        <th>Usuário</th>
                        <th>Alterações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((entry) => (
                        <tr key={entry.id}>
                          <td>{new Date(entry.created_at).toLocaleString("pt-BR")}</td>
                          <td>{entry.event_type}</td>
                          <td>{entry.user}</td>
                          <td>
                            {entry.changes
                              ? Object.entries(entry.changes)
                                  .map(([field, { from, to }]) => `${field}: ${from} → ${to}`)
                                  .join("; ")
                              : entry.message ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="module-state">Carregando funcionários...</div>
      ) : employees.length === 0 ? (
        <div className="module-state">
          <strong>Nenhum funcionário cadastrado</strong>
          <span>Cadastre os funcionários que trabalham no hotel.</span>
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>CPF</th>
                <th>Telefone</th>
                <th>E-mail</th>
                <th>Status</th>
                {canManage && <th>Ações</th>}
              </tr>
            </thead>
            <tbody>
              {employees.map((employee) => (
                <tr key={employee.id}>
                  <td>
                    <strong>{employee.name}</strong>
                  </td>
                  <td>{employee.cpf ? formatCPF(employee.cpf) : "—"}</td>
                  <td>{employee.phone ?? "—"}</td>
                  <td>{employee.personal_email ?? "—"}</td>
                  <td>
                    <span className={employee.status === "active" ? "status status-done" : "status status-progress"}>
                      {STATUS_LABELS[employee.status] ?? employee.status}
                    </span>
                  </td>
                  {canManage && (
                    <td>
                      <div className="row-actions">
                        <button onClick={() => handleEdit(employee)} aria-label="Editar">
                          <Edit2 size={16} />
                        </button>
                        <button onClick={() => handleDelete(employee)} aria-label="Remover">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="module-pagination">
        <span>{total} funcionário(s)</span>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Página anterior">
            <ChevronLeft size={16} />
          </button>
          <span>
            Página {page} de {pages}
          </span>
          <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Próxima página">
            <ChevronRight size={16} />
          </button>
        </div>
      </footer>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
      </section>
    </>
  );
}
