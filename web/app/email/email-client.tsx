"use client";

import { useState, useCallback, useTransition } from "react";
import {
  Mail, RefreshCw, Plus, Trash2, Edit2, Bell, BellOff, Check,
  ChevronRight, X, Eye, EyeOff, AlertCircle, Inbox, Settings,
  MessageSquare, Filter, Globe, AtSign, Hash,
} from "lucide-react";

type EmailAccount = {
  id: number;
  name: string;
  provider: string;
  protocol: "imap" | "pop3";
  imap_host: string;
  imap_port: number;
  imap_ssl: boolean;
  username: string;
  active: boolean;
  last_synced_at: string | null;
  created_at: string;
};

type MessageListItem = {
  id: number;
  account_id: number;
  uid: string;
  from_addr: string;
  from_name: string | null;
  subject: string | null;
  received_at: string | null;
  is_read: boolean;
  is_flagged: boolean;
};

type AlertRule = {
  id: number;
  name: string;
  active: boolean;
  filter_type: "subject" | "domain" | "sender";
  filter_value: string;
  whatsapp_targets: { number: string; label?: string | null }[];
  account_ids: number[];
  created_at: string;
  updated_at: string;
};

type MessageDetail = MessageListItem & {
  body_text: string | null;
  to_addr: string | null;
};

type Tab = "inbox" | "alertas" | "contas";

const PROVIDER_PRESETS: Record<string, { host: string; port: number; ssl: boolean; protocol: "imap" | "pop3" }> = {
  gmail:     { host: "imap.gmail.com",          port: 993, ssl: true,  protocol: "imap" },
  microsoft: { host: "outlook.office365.com",   port: 993, ssl: true,  protocol: "imap" },
  imap:      { host: "",                         port: 993, ssl: true,  protocol: "imap" },
  pop3:      { host: "",                         port: 995, ssl: true,  protocol: "pop3" },
};

const FILTER_TYPE_LABELS: Record<string, { label: string; icon: React.ElementType; help: string }> = {
  subject: { label: "Assunto", icon: Hash, help: "Contém o texto no assunto do e-mail" },
  domain: { label: "Domínio", icon: Globe, help: "Domínio exato do remetente (ex: empresa.com.br)" },
  sender: { label: "Remetente", icon: AtSign, help: "E-mail ou parte do e-mail do remetente" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86_400_000 && d.getDate() === now.getDate()) {
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function senderInitials(name: string | null, addr: string): string {
  const src = name || addr;
  const parts = src.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`/api/email-client${path}`, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function EmailClient({
  initialAccounts,
  initialMessages,
  initialAlertRules,
}: {
  initialAccounts: EmailAccount[];
  initialMessages: MessageListItem[];
  initialAlertRules: AlertRule[];
}) {
  const [tab, setTab] = useState<Tab>("inbox");
  const [accounts, setAccounts] = useState(initialAccounts);
  const [messages, setMessages] = useState(initialMessages);
  const [alertRules, setAlertRules] = useState(initialAlertRules);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<MessageDetail | null>(null);
  const [syncing, startSync] = useTransition();
  const [showNewAccount, setShowNewAccount] = useState(false);
  const [showNewRule, setShowNewRule] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const visibleMessages = selectedAccountId
    ? messages.filter((m) => m.account_id === selectedAccountId)
    : messages;

  const unreadCount = messages.filter((m) => !m.is_read).length;

  function showFeedback(msg: string) {
    setFeedback(msg);
    setTimeout(() => setFeedback(null), 3000);
  }

  const handleSync = useCallback(() => {
    startSync(async () => {
      try {
        const syncRes = await fetch("/api/email-client/sync", { method: "POST" });
        if (!syncRes.ok) {
          showFeedback("Erro ao sincronizar. Verifique a conexão IMAP.");
          return;
        }
        const results: { account_id: number; error: string | null }[] = await syncRes.json();
        const failed = results.filter((r) => r.error);

        const [messagesRes, accountsRes] = await Promise.all([
          fetch("/api/email-client/messages?page=1&page_size=50"),
          fetch("/api/email-client/accounts"),
        ]);
        if (messagesRes.ok) {
          const data = await messagesRes.json();
          setMessages(data.items);
        }
        if (accountsRes.ok) {
          setAccounts(await accountsRes.json());
        }

        if (failed.length > 0) {
          showFeedback(`Erro ao sincronizar: ${failed[0].error}`);
        } else {
          showFeedback("Caixa de entrada sincronizada.");
        }
      } catch {
        showFeedback("Erro ao sincronizar. Verifique a conexão IMAP.");
      }
    });
  }, []);

  const openMessage = useCallback(async (msg: MessageListItem) => {
    if (!msg.is_read) {
      setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, is_read: true } : m));
    }
    try {
      const res = await fetch(`/api/email-client/messages/${msg.id}`);
      if (res.ok) {
        const detail = await res.json();
        setSelectedMessage(detail);
      } else {
        setSelectedMessage({ ...msg, body_text: null, to_addr: null });
      }
    } catch {
      setSelectedMessage({ ...msg, body_text: null, to_addr: null });
    }
  }, []);

  const deleteRule = useCallback(async (id: number) => {
    try {
      await fetch(`/api/email-client/alert-rules/${id}`, { method: "DELETE" });
      setAlertRules((prev) => prev.filter((r) => r.id !== id));
      showFeedback("Regra removida.");
    } catch {
      showFeedback("Erro ao remover regra.");
    }
  }, []);

  const toggleRule = useCallback(async (rule: AlertRule) => {
    try {
      const res = await fetch(`/api/email-client/alert-rules/${rule.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !rule.active }),
      });
      if (res.ok) {
        const updated = await res.json();
        setAlertRules((prev) => prev.map((r) => r.id === rule.id ? updated : r));
      }
    } catch {
      showFeedback("Erro ao atualizar regra.");
    }
  }, []);

  const deleteAccount = useCallback(async (id: number) => {
    try {
      await fetch(`/api/email-client/accounts/${id}`, { method: "DELETE" });
      setAccounts((prev) => prev.filter((a) => a.id !== id));
      showFeedback("Conta removida.");
    } catch {
      showFeedback("Erro ao remover conta.");
    }
  }, []);

  return (
    <div className="ec-shell">
      {feedback && (
        <div className="ec-feedback" role="status">
          <Check size={14} /> {feedback}
        </div>
      )}

      {/* ── Sidebar ── */}
      <aside className="ec-sidebar">
        <div className="ec-sidebar-header">
          <Mail size={18} />
          <span>E-mail</span>
        </div>

        <nav className="ec-nav">
          <button
            className={`ec-nav-item ${tab === "inbox" ? "active" : ""}`}
            onClick={() => { setTab("inbox"); setSelectedMessage(null); }}
          >
            <Inbox size={16} />
            <span>Caixa de entrada</span>
            {unreadCount > 0 && <span className="ec-badge">{unreadCount}</span>}
          </button>
          <button
            className={`ec-nav-item ${tab === "alertas" ? "active" : ""}`}
            onClick={() => { setTab("alertas"); setSelectedMessage(null); }}
          >
            <MessageSquare size={16} />
            <span>Alertas WhatsApp</span>
            {alertRules.filter((r) => r.active).length > 0 && (
              <span className="ec-badge ec-badge-wa">
                {alertRules.filter((r) => r.active).length}
              </span>
            )}
          </button>
          <button
            className={`ec-nav-item ${tab === "contas" ? "active" : ""}`}
            onClick={() => { setTab("contas"); setSelectedMessage(null); }}
          >
            <Settings size={16} />
            <span>Contas</span>
          </button>
        </nav>

        {accounts.length > 0 && (
          <>
            <p className="ec-sidebar-section">Contas</p>
            <button
              className={`ec-nav-item ${selectedAccountId === null ? "active" : ""}`}
              onClick={() => setSelectedAccountId(null)}
            >
              <span className="ec-account-dot" style={{ background: "#4F6EF7" }} />
              <span>Todas as contas</span>
            </button>
            {accounts.map((a, i) => (
              <button
                key={a.id}
                className={`ec-nav-item ${selectedAccountId === a.id ? "active" : ""}`}
                onClick={() => setSelectedAccountId(a.id)}
              >
                <span className="ec-account-dot" style={{ background: ACCOUNT_COLORS[i % ACCOUNT_COLORS.length] }} />
                <span className="ec-nav-truncate">{a.name}</span>
              </button>
            ))}
          </>
        )}
      </aside>

      {/* ── Main ── */}
      <main className="ec-main">
        {tab === "inbox" && (
          <div className="ec-inbox">
            {/* Message list */}
            <div className="ec-msg-list">
              <div className="ec-msg-list-header">
                <span className="ec-list-title">Caixa de entrada</span>
                <button className="ec-icon-btn" onClick={handleSync} disabled={syncing} title="Sincronizar agora">
                  <RefreshCw size={15} className={syncing ? "spin" : ""} />
                </button>
              </div>
              {visibleMessages.length === 0 ? (
                <div className="ec-empty">
                  <Mail size={32} />
                  <p>Nenhuma mensagem</p>
                  <span>Adicione uma conta e sincronize para ver os e-mails.</span>
                </div>
              ) : (
                visibleMessages.map((msg) => {
                  const acc = accounts.find((a) => a.id === msg.account_id);
                  const accIdx = acc ? accounts.indexOf(acc) : 0;
                  return (
                    <button
                      key={msg.id}
                      className={`ec-msg-row ${!msg.is_read ? "unread" : ""} ${selectedMessage?.id === msg.id ? "selected" : ""}`}
                      onClick={() => openMessage(msg)}
                    >
                      <div
                        className="ec-avatar"
                        style={{ background: ACCOUNT_COLORS[accIdx % ACCOUNT_COLORS.length] }}
                      >
                        {senderInitials(msg.from_name, msg.from_addr)}
                      </div>
                      <div className="ec-msg-meta">
                        <div className="ec-msg-top">
                          <span className="ec-sender">{msg.from_name || msg.from_addr}</span>
                          <span className="ec-time">{formatDate(msg.received_at)}</span>
                        </div>
                        <div className="ec-subject">{msg.subject || "(sem assunto)"}</div>
                        <div className="ec-from-addr">{msg.from_addr}</div>
                      </div>
                      {!msg.is_read && <span className="ec-unread-dot" />}
                    </button>
                  );
                })
              )}
            </div>

            {/* Detail panel */}
            <div className="ec-detail">
              {selectedMessage ? (
                <>
                  <div className="ec-detail-header">
                    <h2 className="ec-detail-subject">{selectedMessage.subject || "(sem assunto)"}</h2>
                    <button className="ec-icon-btn" onClick={() => setSelectedMessage(null)} title="Fechar">
                      <X size={16} />
                    </button>
                  </div>
                  <div className="ec-detail-meta">
                    <div className="ec-avatar ec-avatar-lg">
                      {senderInitials(selectedMessage.from_name, selectedMessage.from_addr)}
                    </div>
                    <div>
                      <p className="ec-detail-from">{selectedMessage.from_name || selectedMessage.from_addr}</p>
                      <p className="ec-detail-addr">&lt;{selectedMessage.from_addr}&gt;</p>
                      <p className="ec-detail-date">{selectedMessage.received_at ? new Date(selectedMessage.received_at).toLocaleString("pt-BR") : ""}</p>
                    </div>
                  </div>
                  <div className="ec-detail-body">
                    {selectedMessage.body_text
                      ? selectedMessage.body_text.split("\n").map((line, i) => (
                          <p key={i} className="ec-body-line">{line || " "}</p>
                        ))
                      : <p className="ec-empty-body">Corpo do e-mail não disponível.</p>}
                  </div>
                </>
              ) : (
                <div className="ec-detail-placeholder">
                  <Mail size={40} />
                  <p>Selecione um e-mail para ler</p>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "alertas" && (
          <div className="ec-alertas">
            <div className="ec-page-header">
              <div>
                <h2>Alertas WhatsApp</h2>
                <p>Quando um e-mail corresponder ao filtro, a mensagem é enviada automaticamente pelo WhatsApp.</p>
              </div>
              <button className="ec-btn ec-btn-primary" onClick={() => { setEditingRule(null); setShowNewRule(true); }}>
                <Plus size={15} /> Nova regra
              </button>
            </div>

            {alertRules.length === 0 ? (
              <div className="ec-empty ec-empty-full">
                <MessageSquare size={40} />
                <p>Nenhuma regra configurada</p>
                <span>Crie uma regra para receber alertas no WhatsApp quando chegarem e-mails específicos.</span>
                <button className="ec-btn ec-btn-primary" onClick={() => setShowNewRule(true)}>
                  <Plus size={15} /> Criar primeira regra
                </button>
              </div>
            ) : (
              <div className="ec-rules-list">
                {alertRules.map((rule) => {
                  const filterMeta = FILTER_TYPE_LABELS[rule.filter_type];
                  const FilterIcon = filterMeta?.icon ?? Filter;
                  return (
                    <div key={rule.id} className={`ec-rule-card ${!rule.active ? "inactive" : ""}`}>
                      <div className="ec-rule-top">
                        <div className="ec-rule-name-row">
                          <span className="ec-rule-name">{rule.name}</span>
                          <span className={`ec-rule-status ${rule.active ? "on" : "off"}`}>
                            {rule.active ? "Ativo" : "Pausado"}
                          </span>
                        </div>
                        <div className="ec-rule-actions">
                          <button className="ec-icon-btn" onClick={() => toggleRule(rule)} title={rule.active ? "Pausar" : "Ativar"}>
                            {rule.active ? <BellOff size={15} /> : <Bell size={15} />}
                          </button>
                          <button className="ec-icon-btn" onClick={() => { setEditingRule(rule); setShowNewRule(true); }} title="Editar">
                            <Edit2 size={15} />
                          </button>
                          <button className="ec-icon-btn ec-icon-btn-danger" onClick={() => deleteRule(rule.id)} title="Remover">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </div>
                      <div className="ec-rule-filter">
                        <FilterIcon size={13} />
                        <span className="ec-rule-filter-type">{filterMeta?.label}</span>
                        <span className="ec-rule-filter-value">{rule.filter_value}</span>
                      </div>
                      <div className="ec-rule-targets">
                        {rule.whatsapp_targets.map((t, i) => (
                          <span key={i} className="ec-target-chip">
                            <span className="ec-wa-icon">WA</span>
                            {t.label || t.number}
                          </span>
                        ))}
                        {rule.whatsapp_targets.length === 0 && (
                          <span className="ec-no-targets">Sem destinos configurados</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {tab === "contas" && (
          <div className="ec-contas">
            <div className="ec-page-header">
              <div>
                <h2>Contas de e-mail</h2>
                <p>Configure contas Gmail, Microsoft ou IMAP para sincronização.</p>
              </div>
              <button className="ec-btn ec-btn-primary" onClick={() => setShowNewAccount(true)}>
                <Plus size={15} /> Adicionar conta
              </button>
            </div>

            {accounts.length === 0 ? (
              <div className="ec-empty ec-empty-full">
                <Mail size={40} />
                <p>Nenhuma conta configurada</p>
                <span>Adicione uma conta Gmail, Microsoft ou IMAP para começar a receber e-mails.</span>
                <button className="ec-btn ec-btn-primary" onClick={() => setShowNewAccount(true)}>
                  <Plus size={15} /> Adicionar conta
                </button>
              </div>
            ) : (
              <div className="ec-account-list">
                {accounts.map((acc, i) => (
                  <div key={acc.id} className={`ec-account-card ${!acc.active ? "inactive" : ""}`}>
                    <div className="ec-account-icon" style={{ background: ACCOUNT_COLORS[i % ACCOUNT_COLORS.length] }}>
                      <Mail size={18} />
                    </div>
                    <div className="ec-account-info">
                      <p className="ec-account-name">{acc.name}</p>
                      <p className="ec-account-detail">{acc.username} · {acc.imap_host}:{acc.imap_port} <span className="ec-protocol-badge">{(acc.protocol ?? "imap").toUpperCase()}</span></p>
                      <p className="ec-account-sync">
                        {acc.last_synced_at
                          ? `Sincronizado ${formatDate(acc.last_synced_at)}`
                          : "Nunca sincronizado"}
                      </p>
                    </div>
                    <div className="ec-account-actions">
                      <span className={`ec-rule-status ${acc.active ? "on" : "off"}`}>
                        {acc.active ? "Ativa" : "Inativa"}
                      </span>
                      <button
                        className="ec-icon-btn ec-icon-btn-danger"
                        onClick={() => deleteAccount(acc.id)}
                        title="Remover conta"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Modais ── */}
      {showNewAccount && (
        <AccountModal
          onClose={() => setShowNewAccount(false)}
          onSaved={(acc) => { setAccounts((p) => [...p, acc]); setShowNewAccount(false); showFeedback("Conta adicionada com sucesso."); }}
        />
      )}
      {showNewRule && (
        <AlertRuleModal
          accounts={accounts}
          rule={editingRule}
          onClose={() => { setShowNewRule(false); setEditingRule(null); }}
          onSaved={(rule) => {
            if (editingRule) {
              setAlertRules((p) => p.map((r) => r.id === rule.id ? rule : r));
              showFeedback("Regra atualizada.");
            } else {
              setAlertRules((p) => [...p, rule]);
              showFeedback("Regra criada com sucesso.");
            }
            setShowNewRule(false);
            setEditingRule(null);
          }}
        />
      )}

      <style>{styles}</style>
    </div>
  );
}

const ACCOUNT_COLORS = ["#4F6EF7", "#7C5CBF", "#2BA4A0", "#D97706", "#DC2626"];

// ── Account Modal ──

function AccountModal({ onClose, onSaved }: {
  onClose: () => void;
  onSaved: (acc: EmailAccount) => void;
}) {
  const [provider, setProvider] = useState<"gmail" | "microsoft" | "imap" | "pop3">("gmail");
  const preset = PROVIDER_PRESETS[provider];
  const [form, setForm] = useState({
    name: "",
    imap_host: preset.host,
    imap_port: preset.port,
    imap_ssl: preset.ssl,
    protocol: preset.protocol as "imap" | "pop3",
    username: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPass, setShowPass] = useState(false);

  function applyPreset(p: "gmail" | "microsoft" | "imap" | "pop3") {
    setProvider(p);
    const pre = PROVIDER_PRESETS[p];
    setForm((f) => ({ ...f, imap_host: pre.host, imap_port: pre.port, imap_ssl: pre.ssl, protocol: pre.protocol }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const apiProvider = provider === "pop3" ? "imap" : provider; // backend usa "imap" como fallback genérico
    try {
      const res = await fetch("/api/email-client/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, provider: apiProvider }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err?.detail || "Erro ao salvar conta.");
      } else {
        const saved = await res.json();
        onSaved(saved);
      }
    } catch {
      setError("Erro de conexão.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ec-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ec-modal">
        <div className="ec-modal-header">
          <h3>Adicionar conta de e-mail</h3>
          <button className="ec-icon-btn" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="ec-form">
          <div className="ec-provider-tabs">
            {(["gmail", "microsoft", "imap", "pop3"] as const).map((p) => (
              <button key={p} type="button" className={`ec-provider-tab ${provider === p ? "active" : ""}`} onClick={() => applyPreset(p)}>
                {p === "gmail" ? "Gmail" : p === "microsoft" ? "Microsoft" : p === "imap" ? "IMAP" : "POP3"}
              </button>
            ))}
          </div>
          {provider === "gmail" && (
            <div className="ec-info-box">
              Para Gmail, habilite o acesso IMAP nas configurações da conta e use uma <strong>Senha de app</strong> (não a senha normal). Acesse Conta Google → Segurança → Senhas de app.
            </div>
          )}
          {provider === "microsoft" && (
            <div className="ec-info-box">
              Para Outlook/Microsoft 365, certifique-se que o acesso IMAP está habilitado na conta e use a senha da conta ou uma senha de aplicativo se o 2FA estiver ativo.
            </div>
          )}
          {provider === "pop3" && (
            <div className="ec-info-box">
              POP3 baixa os e-mails do servidor (padrão: porta 995 com SSL). Gmail POP3: <code>pop.gmail.com:995</code>. Microsoft: <code>outlook.office365.com:995</code>. Obs: POP3 não mantém pastas — todas as mensagens ficam em Caixa de entrada.
            </div>
          )}
          <div className="ec-field">
            <label>Nome da conta</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ex: Financeiro, Suporte..." />
          </div>
          <div className="ec-field">
            <label>E-mail / usuário</label>
            <input required type="email" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="conta@empresa.com" />
          </div>
          <div className="ec-field">
            <label>Senha {provider === "gmail" ? "(Senha de app)" : ""}</label>
            <div className="ec-input-row">
              <input required type={showPass ? "text" : "password"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="••••••••••••" />
              <button type="button" className="ec-icon-btn" onClick={() => setShowPass((v) => !v)}>
                {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>
          {(provider === "imap" || provider === "pop3") && (
            <div className="ec-field-row">
              <div className="ec-field ec-field-grow">
                <label>Servidor {provider === "pop3" ? "POP3" : "IMAP"}</label>
                <input required value={form.imap_host} onChange={(e) => setForm({ ...form, imap_host: e.target.value })} placeholder={provider === "pop3" ? "pop.exemplo.com" : "imap.exemplo.com"} />
              </div>
              <div className="ec-field ec-field-sm">
                <label>Porta</label>
                <input required type="number" value={form.imap_port} onChange={(e) => setForm({ ...form, imap_port: +e.target.value })} />
              </div>
              <div className="ec-field ec-field-sm">
                <label>SSL</label>
                <select value={form.imap_ssl ? "true" : "false"} onChange={(e) => setForm({ ...form, imap_ssl: e.target.value === "true" })}>
                  <option value="true">Sim</option>
                  <option value="false">Não</option>
                </select>
              </div>
            </div>
          )}
          {error && <div className="ec-error"><AlertCircle size={14} /> {error}</div>}
          <div className="ec-modal-footer">
            <button type="button" className="ec-btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="ec-btn ec-btn-primary" disabled={loading}>
              {loading ? "Salvando..." : "Salvar conta"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Alert Rule Modal ──

function AlertRuleModal({ accounts, rule, onClose, onSaved }: {
  accounts: EmailAccount[];
  rule: AlertRule | null;
  onClose: () => void;
  onSaved: (rule: AlertRule) => void;
}) {
  const [form, setForm] = useState({
    name: rule?.name ?? "",
    filter_type: rule?.filter_type ?? "subject",
    filter_value: rule?.filter_value ?? "",
    account_ids: rule?.account_ids ?? [],
    whatsapp_targets: rule?.whatsapp_targets ?? [],
  });
  const [newTarget, setNewTarget] = useState({ number: "", label: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addTarget() {
    if (!newTarget.number.trim()) return;
    setForm((f) => ({ ...f, whatsapp_targets: [...f.whatsapp_targets, { ...newTarget }] }));
    setNewTarget({ number: "", label: "" });
  }

  function removeTarget(i: number) {
    setForm((f) => ({ ...f, whatsapp_targets: f.whatsapp_targets.filter((_, idx) => idx !== i) }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const url = rule ? `/api/email-client/alert-rules/${rule.id}` : "/api/email-client/alert-rules";
      const method = rule ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err?.detail || "Erro ao salvar regra.");
      } else {
        onSaved(await res.json());
      }
    } catch {
      setError("Erro de conexão.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ec-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ec-modal">
        <div className="ec-modal-header">
          <h3>{rule ? "Editar regra" : "Nova regra de alerta"}</h3>
          <button className="ec-icon-btn" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="ec-form">
          <div className="ec-field">
            <label>Nome da regra</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ex: NF-e recebida, Suporte urgente..." />
          </div>
          <div className="ec-field">
            <label>Tipo de filtro</label>
            <div className="ec-filter-opts">
              {(["subject", "domain", "sender"] as const).map((t) => {
                const meta = FILTER_TYPE_LABELS[t];
                const Icon = meta.icon;
                return (
                  <label key={t} className={`ec-filter-opt ${form.filter_type === t ? "active" : ""}`}>
                    <input type="radio" name="filter_type" value={t} checked={form.filter_type === t} onChange={() => setForm({ ...form, filter_type: t })} />
                    <Icon size={14} />
                    <span>{meta.label}</span>
                  </label>
                );
              })}
            </div>
            <p className="ec-field-help">{FILTER_TYPE_LABELS[form.filter_type]?.help}</p>
          </div>
          <div className="ec-field">
            <label>Valor do filtro</label>
            <input
              required
              value={form.filter_value}
              onChange={(e) => setForm({ ...form, filter_value: e.target.value })}
              placeholder={
                form.filter_type === "subject" ? "Ex: NF-e, fatura, urgente" :
                form.filter_type === "domain" ? "Ex: empresa.com.br" :
                "Ex: notificacao@banco.com"
              }
            />
          </div>
          {accounts.length > 1 && (
            <div className="ec-field">
              <label>Monitorar contas (vazio = todas)</label>
              <div className="ec-checkboxes">
                {accounts.map((a) => (
                  <label key={a.id} className="ec-checkbox-item">
                    <input
                      type="checkbox"
                      checked={form.account_ids.includes(a.id)}
                      onChange={(e) => setForm((f) => ({
                        ...f,
                        account_ids: e.target.checked
                          ? [...f.account_ids, a.id]
                          : f.account_ids.filter((id) => id !== a.id),
                      }))}
                    />
                    {a.name}
                  </label>
                ))}
              </div>
            </div>
          )}
          <div className="ec-field">
            <label>Destinos WhatsApp</label>
            {form.whatsapp_targets.map((t, i) => (
              <div key={i} className="ec-target-row">
                <span className="ec-wa-icon">WA</span>
                <span className="ec-target-text">{t.label || t.number}</span>
                <span className="ec-target-num">{t.label ? t.number : ""}</span>
                <button type="button" className="ec-icon-btn" onClick={() => removeTarget(i)}><X size={13} /></button>
              </div>
            ))}
            <div className="ec-add-target">
              <input
                value={newTarget.number}
                onChange={(e) => setNewTarget({ ...newTarget, number: e.target.value })}
                placeholder="Número ou JID do grupo (5511999...)"
              />
              <input
                value={newTarget.label}
                onChange={(e) => setNewTarget({ ...newTarget, label: e.target.value })}
                placeholder="Rótulo (opcional)"
              />
              <button type="button" className="ec-btn" onClick={addTarget}><Plus size={14} /></button>
            </div>
            <p className="ec-field-help">Para grupos do WhatsApp, use o JID do grupo (ex: 120363...@g.us)</p>
          </div>
          {error && <div className="ec-error"><AlertCircle size={14} /> {error}</div>}
          <div className="ec-modal-footer">
            <button type="button" className="ec-btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="ec-btn ec-btn-primary" disabled={loading}>
              {loading ? "Salvando..." : rule ? "Salvar alterações" : "Criar regra"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Styles ──
const styles = `
.ec-shell {
  display: flex;
  height: 100%;
  min-height: 0;
  background: var(--color-bg, #F0F2F7);
  position: relative;
  flex: 1;
  overflow: hidden;
}

.ec-feedback {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #1A1F2E;
  color: #fff;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 200;
  box-shadow: 0 4px 16px rgba(0,0,0,.25);
}

/* Sidebar */
.ec-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: #1C2333;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #252D42;
  overflow-y: auto;
}

.ec-sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 12px;
  color: #E2E6F0;
  font-family: var(--font-syne), system-ui, sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
  border-bottom: 1px solid #252D42;
}

.ec-sidebar-section {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #4B5563;
  padding: 14px 16px 4px;
  font-family: var(--font-syne), system-ui, sans-serif;
}

.ec-nav { padding: 8px 0; }

.ec-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 16px;
  background: none;
  border: none;
  cursor: pointer;
  color: #8B95B0;
  font-size: 13.5px;
  text-align: left;
  border-radius: 0;
  transition: background .12s, color .12s;
}

.ec-nav-item:hover { background: #232B3E; color: #C8CED8; }
.ec-nav-item.active { background: #2D3752; color: #E2E6F0; }

.ec-nav-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ec-badge {
  margin-left: auto;
  background: #4F6EF7;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.ec-badge-wa { background: #25D366; }

.ec-account-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Main area */
.ec-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

/* Inbox */
.ec-inbox {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.ec-msg-list {
  width: 340px;
  flex-shrink: 0;
  border-right: 1px solid #E2E6EF;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.ec-msg-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 12px;
  border-bottom: 1px solid #E2E6EF;
  flex-shrink: 0;
}

.ec-list-title {
  font-family: var(--font-syne), system-ui, sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: #374151;
}

.ec-msg-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: none;
  border: none;
  border-bottom: 1px solid #F3F4F6;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: background .1s;
  position: relative;
}

.ec-msg-row:hover { background: #F7F8FC; }
.ec-msg-row.selected { background: #EEF2FF; }
.ec-msg-row.unread .ec-sender { font-weight: 600; color: #111827; }
.ec-msg-row.unread .ec-subject { font-weight: 600; }

.ec-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  font-family: var(--font-jetbrains-mono), monospace;
}

.ec-avatar-lg { width: 44px; height: 44px; font-size: 14px; }

.ec-msg-meta { flex: 1; min-width: 0; }

.ec-msg-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.ec-sender {
  font-size: 13.5px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ec-time {
  font-size: 11.5px;
  color: #9CA3AF;
  flex-shrink: 0;
  font-family: var(--font-jetbrains-mono), monospace;
}

.ec-subject {
  font-size: 13px;
  color: #4B5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ec-from-addr {
  font-size: 11.5px;
  color: #9CA3AF;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-jetbrains-mono), monospace;
}

.ec-unread-dot {
  position: absolute;
  top: 50%;
  right: 10px;
  transform: translateY(-50%);
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #4F6EF7;
}

/* Detail */
.ec-detail {
  flex: 1;
  min-width: 0;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.ec-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px 12px;
  border-bottom: 1px solid #F3F4F6;
  gap: 16px;
}

.ec-detail-subject {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  line-height: 1.3;
  text-wrap: balance;
}

.ec-detail-meta {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 24px;
  border-bottom: 1px solid #F3F4F6;
}

.ec-detail-from { font-size: 14px; font-weight: 600; color: #111827; }
.ec-detail-addr { font-size: 12.5px; color: #6B7280; font-family: var(--font-jetbrains-mono), monospace; }
.ec-detail-date { font-size: 12px; color: #9CA3AF; margin-top: 2px; font-family: var(--font-jetbrains-mono), monospace; }

.ec-detail-body {
  padding: 20px 24px;
  flex: 1;
}

.ec-body-line {
  font-size: 14px;
  line-height: 1.7;
  color: #374151;
  margin: 0;
}

.ec-empty-body { color: #9CA3AF; font-size: 14px; }

.ec-detail-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #D1D5DB;
}

.ec-detail-placeholder p { font-size: 15px; color: #9CA3AF; }

/* Pages (alertas/contas) */
.ec-alertas, .ec-contas {
  padding: 28px 32px;
  overflow-y: auto;
  flex: 1;
}

.ec-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.ec-page-header h2 {
  font-family: var(--font-syne), system-ui, sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 4px;
}

.ec-page-header p { font-size: 13.5px; color: #6B7280; margin: 0; }

/* Empty */
.ec-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 20px;
  color: #D1D5DB;
  text-align: center;
}

.ec-empty-full { min-height: 320px; }
.ec-empty p { font-size: 15px; color: #9CA3AF; font-weight: 600; margin: 0; }
.ec-empty span { font-size: 13.5px; color: #C4C9D4; max-width: 360px; }

/* Alert rules */
.ec-rules-list { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }

.ec-rule-card {
  background: #fff;
  border: 1px solid #E2E6EF;
  border-radius: 10px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: opacity .15s;
}

.ec-rule-card.inactive { opacity: .55; }

.ec-rule-top { display: flex; align-items: center; justify-content: space-between; }
.ec-rule-name-row { display: flex; align-items: center; gap: 10px; }
.ec-rule-name { font-size: 14.5px; font-weight: 600; color: #111827; }

.ec-rule-status {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 4px;
}

.ec-rule-status.on { background: #DCFCE7; color: #15803D; }
.ec-rule-status.off { background: #F3F4F6; color: #9CA3AF; }

.ec-rule-actions { display: flex; gap: 4px; }

.ec-rule-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #4B5563;
}

.ec-rule-filter-type {
  background: #EEF2FF;
  color: #4F6EF7;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11.5px;
  font-weight: 600;
}

.ec-rule-filter-value {
  font-family: var(--font-jetbrains-mono), monospace;
  font-size: 12.5px;
  color: #374151;
}

.ec-rule-targets { display: flex; flex-wrap: wrap; gap: 8px; }

.ec-target-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #F0FDF4;
  border: 1px solid #BBF7D0;
  color: #15803D;
  font-size: 12.5px;
  padding: 4px 10px;
  border-radius: 6px;
}

.ec-wa-icon {
  background: #25D366;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: .04em;
}

.ec-no-targets { font-size: 12.5px; color: #D1D5DB; }

/* Accounts */
.ec-account-list { display: flex; flex-direction: column; gap: 12px; max-width: 720px; }

.ec-account-card {
  background: #fff;
  border: 1px solid #E2E6EF;
  border-radius: 10px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: opacity .15s;
}

.ec-account-card.inactive { opacity: .55; }

.ec-account-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.ec-account-info { flex: 1; min-width: 0; }
.ec-account-name { font-size: 14.5px; font-weight: 600; color: #111827; margin: 0 0 2px; }
.ec-account-detail { font-size: 12.5px; color: #6B7280; font-family: var(--font-jetbrains-mono), monospace; margin: 0 0 2px; }
.ec-protocol-badge { display: inline-block; font-size: 10px; font-family: var(--font-jetbrains-mono), monospace; background: var(--ec-border); color: var(--ec-text-muted); border-radius: 3px; padding: 0 4px; margin-left: 4px; vertical-align: middle; }
.ec-account-sync { font-size: 12px; color: #9CA3AF; margin: 0; }
.ec-account-actions { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }

/* Buttons */
.ec-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 7px;
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #E2E6EF;
  background: #fff;
  color: #374151;
  transition: background .1s, border-color .1s;
}

.ec-btn:hover { background: #F7F8FC; border-color: #D1D5DB; }
.ec-btn:disabled { opacity: .5; cursor: not-allowed; }

.ec-btn-primary {
  background: #4F6EF7;
  color: #fff;
  border-color: #4F6EF7;
}

.ec-btn-primary:hover { background: #3B55D9; border-color: #3B55D9; }

.ec-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  color: #6B7280;
  transition: background .1s, color .1s;
}

.ec-icon-btn:hover { background: #F3F4F6; color: #111827; }
.ec-icon-btn-danger:hover { background: #FEF2F2; color: #DC2626; }
.ec-icon-btn:disabled { opacity: .4; cursor: not-allowed; }

.spin { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Modal */
.ec-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.45);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.ec-modal {
  background: #fff;
  border-radius: 12px;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,.2);
}

.ec-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #F3F4F6;
}

.ec-modal-header h3 {
  font-family: var(--font-syne), system-ui, sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}

.ec-form { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }

.ec-provider-tabs {
  display: flex;
  background: #F3F4F6;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}

.ec-provider-tab {
  flex: 1;
  padding: 6px;
  border: none;
  background: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  color: #6B7280;
  transition: all .1s;
}

.ec-provider-tab.active { background: #fff; color: #111827; box-shadow: 0 1px 3px rgba(0,0,0,.1); }

.ec-info-box {
  background: #EEF2FF;
  border: 1px solid #C7D2FE;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 12.5px;
  color: #3730A3;
  line-height: 1.6;
}

.ec-field { display: flex; flex-direction: column; gap: 5px; }
.ec-field label { font-size: 12.5px; font-weight: 600; color: #374151; letter-spacing: .01em; }

.ec-field input, .ec-field select {
  padding: 9px 12px;
  border: 1px solid #E2E6EF;
  border-radius: 7px;
  font-size: 13.5px;
  color: #111827;
  background: #fff;
  outline: none;
  transition: border-color .1s;
}

.ec-field input:focus, .ec-field select:focus { border-color: #4F6EF7; }

.ec-field-row { display: flex; gap: 12px; }
.ec-field-grow { flex: 1; }
.ec-field-sm { width: 90px; }

.ec-field-help { font-size: 11.5px; color: #9CA3AF; margin: 0; }

.ec-input-row { display: flex; gap: 8px; align-items: center; }
.ec-input-row input { flex: 1; }

.ec-filter-opts { display: flex; gap: 8px; }

.ec-filter-opt {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid #E2E6EF;
  border-radius: 7px;
  cursor: pointer;
  font-size: 13px;
  color: #4B5563;
  transition: all .1s;
}

.ec-filter-opt input { display: none; }
.ec-filter-opt.active { border-color: #4F6EF7; background: #EEF2FF; color: #4F6EF7; }

.ec-checkboxes { display: flex; flex-direction: column; gap: 6px; }

.ec-checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  color: #374151;
  cursor: pointer;
}

.ec-target-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #F0FDF4;
  border: 1px solid #BBF7D0;
  border-radius: 7px;
  margin-bottom: 6px;
}

.ec-target-text { flex: 1; font-size: 13px; color: #15803D; font-weight: 500; }
.ec-target-num { font-size: 11.5px; color: #6B7280; font-family: var(--font-jetbrains-mono), monospace; }

.ec-add-target { display: flex; gap: 8px; }
.ec-add-target input { flex: 1; }
.ec-add-target input { padding: 8px 12px; border: 1px solid #E2E6EF; border-radius: 7px; font-size: 13px; outline: none; }
.ec-add-target input:focus { border-color: #4F6EF7; }

.ec-error {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #FEF2F2;
  border: 1px solid #FECACA;
  color: #DC2626;
  border-radius: 7px;
  padding: 10px 12px;
  font-size: 13px;
}

.ec-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
}
`;
