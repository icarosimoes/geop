"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { TenantUser } from "@/lib/api";
import type { EvolutionSettings, BrevoSettings, CompanyInfo, RegistryOption, TimeclockSettings } from "@/app/actions";
import {
  getEvolutionSettings, saveEvolutionSettings,
  getBrevoSettings, saveBrevoSettings, testBrevoSettings,
  getTimeclockSettings, saveTimeclockSettings,
  fetchRegistryOptions,
} from "@/app/actions";

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

export function CompanySettingsSection() {
  const [info, setInfo] = useState<CompanyInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    import("@/app/actions").then(({ getCompanyInfo }) =>
      getCompanyInfo().then((data) => { setInfo(data); setLoading(false); })
    ).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="settings-form"><section><h2>Estabelecimento</h2><p>Carregando...</p></section></div>;
  if (!info) return null;

  return <div className="settings-form"><form className="settings-evolution" onSubmit={async (e) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);
    const fd = new FormData(e.currentTarget);
    const body: Record<string, string> = {};
    const name = String(fd.get("company_name") ?? "").trim();
    const email = String(fd.get("company_email") ?? "").trim();
    const document = String(fd.get("company_document") ?? "").trim();
    const timezone = String(fd.get("company_timezone") ?? "");
    if (name && name !== info.name) body.name = name;
    if (email !== (info.email ?? "")) body.email = email;
    if (document !== (info.document ?? "")) body.document = document;
    if (timezone && timezone !== info.timezone) body.timezone = timezone;
    if (!Object.keys(body).length) { setFeedback("Nenhum campo alterado."); setSaving(false); return; }
    const { updateCompanyInfo } = await import("@/app/actions");
    const result = await updateCompanyInfo(body);
    setSaving(false);
    if (result.ok) {
      setInfo({ ...info, ...body });
      setFeedback("Dados atualizados com sucesso.");
    } else {
      setFeedback(result.error ?? "Erro ao salvar.");
    }
  }}>
    <section>
      <h2>Estabelecimento</h2>
      <p>Dados cadastrais do seu hotel ou empresa.</p>
      {feedback && <p className={feedback.includes("sucesso") ? "settings-connected" : "settings-error"}>{feedback}</p>}
      <div className="form-grid">
        <label>Nome do estabelecimento<input name="company_name" type="text" required defaultValue={info.name}/></label>
        <label>E-mail corporativo<input name="company_email" type="email" placeholder="contato@hotel.com" defaultValue={info.email ?? ""}/></label>
      </div>
      <div className="form-grid">
        <label>CNPJ / CPF<input name="company_document" type="text" placeholder="00.000.000/0000-00" defaultValue={info.document ?? ""} onChange={(e) => { e.target.value = formatDocument(e.target.value); }}/></label>
        <label>Fuso horário<select name="company_timezone" defaultValue={info.timezone}>
          <option value="America/Sao_Paulo">Brasília (GMT-3)</option>
          <option value="America/Manaus">Manaus (GMT-4)</option>
          <option value="America/Belem">Belém (GMT-3)</option>
          <option value="America/Fortaleza">Fortaleza (GMT-3)</option>
          <option value="America/Recife">Recife (GMT-3)</option>
          <option value="America/Bahia">Salvador (GMT-3)</option>
          <option value="America/Cuiaba">Cuiabá (GMT-4)</option>
          <option value="America/Campo_Grande">Campo Grande (GMT-4)</option>
          <option value="America/Porto_Velho">Porto Velho (GMT-4)</option>
          <option value="America/Rio_Branco">Rio Branco (GMT-5)</option>
          <option value="America/Noronha">Fernando de Noronha (GMT-2)</option>
        </select></label>
      </div>
      <label>Identificador (slug)<input type="text" value={info.slug} readOnly/><small className="field-hint">O slug é gerado automaticamente e não pode ser alterado.</small></label>
    </section>
    <button className="primary-button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar dados"}</button>
  </form></div>;
}

export function BrevoSettingsSection() {
  const [config, setConfig] = useState<BrevoSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testFeedback, setTestFeedback] = useState<string | null>(null);

  useEffect(() => {
    getBrevoSettings().then(setConfig).catch(() => setConfig({ has_credentials: false }));
  }, []);

  async function sendTest() {
    setTesting(true);
    setTestFeedback(null);
    const result = await testBrevoSettings(testTo);
    setTesting(false);
    setTestFeedback(result.ok ? `E-mail de teste enviado para ${testTo}.` : (result.error ?? "Erro ao enviar teste."));
  }

  return <div className="settings-evolution">
    <form onSubmit={async (e) => {
      e.preventDefault();
      setSaving(true);
      setFeedback(null);
      const fd = new FormData(e.currentTarget);
      const result = await saveBrevoSettings({
        api_key: String(fd.get("brevo_api_key")),
        from_address: String(fd.get("brevo_from_address")),
        from_name: String(fd.get("brevo_from_name")),
      });
      setSaving(false);
      if (result.ok) {
        setConfig({ has_credentials: true, from_address: String(fd.get("brevo_from_address")), from_name: String(fd.get("brevo_from_name")) });
        setFeedback("Configuração salva com sucesso.");
      } else {
        setFeedback(result.error ?? "Erro ao salvar.");
      }
    }}>
      <section>
        <h2>E-mail (Brevo)</h2>
        <p>Configure o envio de e-mails transacionais para notificações de chamados e atualizações.</p>
        {config?.has_credentials && !feedback && <p className="settings-connected">Conectado{config.from_address ? ` — ${config.from_address}` : ""}</p>}
        {feedback && <p className={feedback.includes("sucesso") ? "settings-connected" : "settings-error"}>{feedback}</p>}
        <div className="form-grid">
          <label>E-mail remetente<input name="brevo_from_address" type="email" required placeholder="noreply@suaempresa.com" defaultValue={config?.from_address ?? ""}/></label>
          <label>Nome remetente<input name="brevo_from_name" type="text" required placeholder="Registro" defaultValue={config?.from_name ?? ""}/></label>
        </div>
        <label>API Key<input name="brevo_api_key" type="password" required placeholder={config?.has_credentials ? "Configurada — preencha para trocar" : "xkeysib-..."}/><small className="field-hint">Brevo → SMTP & API → API Keys</small></label>
      </section>
      <button className="primary-button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar e-mail"}</button>
    </form>

    {config?.has_credentials && (
      <section>
        <h2>Testar envio</h2>
        <p>Envia um e-mail de teste com a configuração salva, para confirmar que a API key e o remetente estão válidos na Brevo.</p>
        {testFeedback && <p className={testFeedback.startsWith("E-mail de teste enviado") ? "settings-connected" : "settings-error"}>{testFeedback}</p>}
        <label>Enviar para<input type="email" required placeholder="voce@suaempresa.com" value={testTo} onChange={(e) => setTestTo(e.target.value)}/></label>
        <button type="button" className="secondary-button" disabled={testing || !testTo} onClick={sendTest}>
          {testing ? "Enviando..." : "Enviar teste"}
        </button>
      </section>
    )}
  </div>;
}

export function EvolutionSettingsSection() {
  const [config, setConfig] = useState<EvolutionSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    getEvolutionSettings().then(setConfig).catch(() => setConfig({ has_credentials: false }));
  }, []);

  return <form className="settings-evolution" onSubmit={async (e) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);
    const fd = new FormData(e.currentTarget);
    const result = await saveEvolutionSettings({
      api_url: String(fd.get("evo_api_url")),
      api_key: String(fd.get("evo_api_key")),
      instance: String(fd.get("evo_instance")),
    });
    setSaving(false);
    if (result.ok) {
      setConfig({ has_credentials: true, api_url: String(fd.get("evo_api_url")), instance: String(fd.get("evo_instance")) });
      setFeedback("Configuração salva com sucesso.");
    } else {
      setFeedback(result.error ?? "Erro ao salvar.");
    }
  }}>
    <section>
      <h2>WhatsApp (Evolution API)</h2>
      <p>Configure a conexão com a Evolution API para enviar notificações via WhatsApp.</p>
      {config?.has_credentials && !feedback && <p className="settings-connected">Conectado{config.api_url ? ` — ${config.api_url}` : ""}</p>}
      {feedback && <p className={feedback.includes("sucesso") ? "settings-connected" : "settings-error"}>{feedback}</p>}
      <label>URL da instância<input name="evo_api_url" type="url" required placeholder="https://evo.suaempresa.com" defaultValue={config?.api_url ?? ""}/></label>
      <label>API Key<input name="evo_api_key" type="password" required placeholder="Chave de autenticação"/><small className="field-hint">Evolution → Manager → Global API Key ou API Key da instância</small></label>
      <label>Nome da instância<input name="evo_instance" type="text" required placeholder="aero-default" defaultValue={config?.instance ?? ""}/><small className="field-hint">Nome exato da instância criada no painel da Evolution API</small></label>
    </section>
    <button className="primary-button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar conexão"}</button>
  </form>;
}

export function TimeclockSettingsSection() {
  const [config, setConfig] = useState<TimeclockSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [functions, setFunctions] = useState<RegistryOption[]>([]);
  const [newCargo, setNewCargo] = useState("");
  const [newCargoSalary, setNewCargoSalary] = useState("");

  useEffect(() => {
    getTimeclockSettings().then(setConfig).catch(() =>
      setConfig({ overtime_paid_in_cash: false, cargo_salaries: {} })
    );
    fetchRegistryOptions("Função").then(setFunctions);
  }, []);

  async function persist(next: TimeclockSettings) {
    setSaving(true);
    setFeedback(null);
    const result = await saveTimeclockSettings(next);
    setSaving(false);
    if (result.ok) {
      setConfig(next);
      setFeedback("Configuração salva com sucesso.");
    } else {
      setFeedback(result.error ?? "Erro ao salvar.");
    }
  }

  if (!config) return null;

  function addCargo() {
    const name = newCargo.trim();
    const salary = Number(newCargoSalary);
    if (!name || !salary || salary <= 0) return;
    const next = { ...config!, cargo_salaries: { ...config!.cargo_salaries, [name]: salary } };
    setNewCargo("");
    setNewCargoSalary("");
    persist(next);
  }

  function removeCargo(name: string) {
    const cargo_salaries = { ...config!.cargo_salaries };
    delete cargo_salaries[name];
    persist({ ...config!, cargo_salaries });
  }

  return (
    <div className="settings-form">
      <section>
        <h2>Ponto e banco de horas</h2>
        <p>Define se hora extra vira saldo de banco de horas (compensação em folga) ou é paga em dinheiro.</p>
        {feedback && <p className={feedback.includes("sucesso") ? "settings-connected" : "settings-error"}>{feedback}</p>}
        <label className="switch-row">
          <span>
            <strong>Pagar hora extra em dinheiro</strong>
            <small>HE 50%/100% deixa de virar saldo de banco de horas e passa a ter valor em R$ no espelho de ponto.</small>
          </span>
          <input
            type="checkbox"
            checked={config.overtime_paid_in_cash}
            disabled={saving}
            onChange={(e) => persist({ ...config, overtime_paid_in_cash: e.target.checked })}
          />
        </label>

        <h3 style={{ marginTop: "var(--sp-4)" }}>Salário-base por cargo</h3>
        <p>
          Usado para calcular o valor da hora extra de funcionários sem salário individual cadastrado
          (ver Cadastros → Funcionários). O salário individual, quando preenchido, tem prioridade.
        </p>
        <table className="module-table">
          <thead>
            <tr>
              <th>Cargo</th>
              <th className="col-num">Salário</th>
              <th aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {Object.entries(config.cargo_salaries).map(([cargo, salary]) => (
              <tr key={cargo}>
                <td>{cargo}</td>
                <td className="col-num">
                  {salary.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                </td>
                <td>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remover ${cargo}`}
                    disabled={saving}
                    onClick={() => removeCargo(cargo)}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {Object.keys(config.cargo_salaries).length === 0 && (
              <tr>
                <td colSpan={3} style={{ color: "var(--label)" }}>Nenhum cargo cadastrado.</td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="report-filter-bar" style={{ marginTop: "var(--sp-3)" }}>
          <div className="report-filter-field">
            <label htmlFor="cargo_salary_function">Cargo</label>
            <select id="cargo_salary_function" value={newCargo} onChange={(e) => setNewCargo(e.target.value)}>
              <option value="">Selecione a função...</option>
              {functions
                .filter((fn) => !(fn.name in config.cargo_salaries))
                .map((fn) => (
                  <option key={fn.id} value={fn.name}>
                    {fn.name}
                  </option>
                ))}
            </select>
          </div>
          <div className="report-filter-field">
            <label>Salário</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={newCargoSalary}
              onChange={(e) => setNewCargoSalary(e.target.value)}
            />
          </div>
          <button type="button" className="secondary-button" disabled={saving} onClick={addCargo}>
            Adicionar
          </button>
        </div>
      </section>
    </div>
  );
}

export function ProfileForm({ user, onSaved }: { user: TenantUser; onSaved: (msg: string) => void }) {
  const [saving, setSaving] = useState(false);
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    const fd = new FormData(e.currentTarget);
    const name = String(fd.get("name") ?? "").trim();
    const phone = String(fd.get("phone") ?? "").replace(/\D/g, "") || undefined;
    const password = String(fd.get("password") ?? "") || undefined;
    const body: Record<string, string | undefined> = {};
    if (name && name !== user.name) body.name = name;
    if (phone) body.phone = phone;
    if (password) body.password = password;
    if (!Object.keys(body).length) { onSaved("Nenhum campo alterado."); setSaving(false); return; }
    const { updateProfileAction } = await import("@/app/actions");
    const result = await updateProfileAction(body);
    setSaving(false);
    if (result.ok) { onSaved("Perfil atualizado com sucesso."); } else { onSaved(result.error ?? "Erro ao salvar."); }
  }
  return <form className="settings-form profile-form" onSubmit={handleSubmit}>
    <section>
      <h2>Dados pessoais</h2>
      <label>Nome completo<input name="name" defaultValue={user.name} required/></label>
      <label>E-mail<input type="email" value={user.email} readOnly/><small className="field-hint">O e-mail não pode ser alterado por aqui.</small></label>
      <label>Telefone<input name="phone" type="tel" placeholder="(00) 00000-0000" defaultValue={user.phone ?? ""} onChange={(e) => { e.target.value = formatPhone(e.target.value); }}/></label>
      <label>Cargo<input value={user.role_name ?? ""} readOnly/></label>
      <label>Nova senha<small className="field-hint"> (deixe vazio para manter a atual)</small><input name="password" type="password" placeholder="••••••••"/></label>
    </section>
    <button className="primary-button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar perfil"}</button>
  </form>;
}
