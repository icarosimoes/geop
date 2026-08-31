"use client";

import { HelpCircle, MessageSquare, Send, X } from "lucide-react";
import { useRef, useState } from "react";
import {
  addCommentAction,
  createSupportRequestAction,
  fetchMySupportRequestsAction,
  fetchTimeline,
  type SupportRequestRecord,
  type TimelineEntry,
} from "@/app/actions";

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  contacted: "Contatado",
  resolved: "Resolvido",
};

function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function TicketThread({ requestId }: { requestId: number }) {
  const [timeline, setTimeline] = useState<TimelineEntry[] | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);

  function load() {
    fetchTimeline("support_request", requestId).then(setTimeline).catch(() => setTimeline([]));
  }

  async function sendReply() {
    const text = reply.trim();
    if (!text) return;
    setSending(true);
    try {
      const result = await addCommentAction("support_request", requestId, text);
      if (result.ok) {
        setReply("");
        load();
      }
    } finally {
      setSending(false);
    }
  }

  if (timeline === null) {
    load();
    return <p style={{ margin: "var(--sp-2) 0" }}>Carregando tratativa…</p>;
  }

  return (
    <div style={{ marginTop: "var(--sp-2)" }}>
      {timeline.length > 0 && (
        <div className="timeline-thread">
          {timeline.map((entry) => {
            const initials = entry.user.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
            return (
              <article
                key={entry.id}
                className={`thread-entry thread-${entry.event_type === "comment" ? "comment" : "change"}`}
              >
                <div className="thread-avatar">{initials}</div>
                <div className="thread-body">
                  <div className="thread-header">
                    <strong>{entry.user}</strong>
                    <time>{fmtDateTime(entry.created_at)}</time>
                  </div>
                  {entry.event_type === "comment" && entry.message ? (
                    <p className="thread-message">{entry.message}</p>
                  ) : null}
                  {entry.changes ? (
                    <div className="thread-changes">
                      {Object.entries(entry.changes).map(([k, v]) => {
                        const change = v as { from: string; to: string };
                        return (
                          <span key={k}>
                            {k}: &quot;{change.from}&quot; → &quot;{change.to}&quot;
                          </span>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      )}
      <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-2)" }}>
        <textarea
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder="Responder…"
          rows={2}
          style={{ flex: 1 }}
        />
        <button type="button" disabled={sending || !reply.trim()} onClick={sendReply}>
          Enviar
        </button>
      </div>
    </div>
  );
}

export function HelpButton() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"new" | "mine">("new");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [myRequests, setMyRequests] = useState<SupportRequestRecord[] | null>(null);
  const [loadingMine, setLoadingMine] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  function close() {
    setOpen(false);
    setError("");
    setSent(false);
    setTab("new");
  }

  async function openMine() {
    setTab("mine");
    if (myRequests !== null) return;
    setLoadingMine(true);
    try {
      setMyRequests(await fetchMySupportRequestsAction());
    } catch {
      setMyRequests([]);
    } finally {
      setLoadingMine(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    setLoading(true);
    setError("");
    try {
      const result = await createSupportRequestAction({
        subject: String(fd.get("subject") ?? ""),
        priority: (String(fd.get("priority") ?? "MEDIA") as "BAIXA" | "MEDIA" | "ALTA"),
        contact_name: String(fd.get("contact_name") ?? ""),
        contact_whatsapp: String(fd.get("contact_whatsapp") ?? ""),
        message: String(fd.get("message") ?? "") || undefined,
      });
      if (!result.ok) throw new Error(result.error);
      setSent(true);
      setMyRequests(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar pedido.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className="icon-button" onClick={() => setOpen(true)} aria-label="Ajuda e suporte" title="Ajuda e suporte">
        <HelpCircle size={20} />
      </button>

      {open && (
        <div className="modal-layer" role="presentation" onClick={close}>
          <section
            className="record-modal"
            role="dialog"
            aria-modal="true"
            style={{ maxWidth: 460 }}
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <span>Central de Ajuda</span>
                <h2>{tab === "new" ? "Falar com o suporte" : "Meus chamados"}</h2>
              </div>
              <button className="icon-button" onClick={close}>
                <X />
              </button>
            </header>

            <div style={{ display: "flex", gap: "var(--sp-2)", padding: "0 var(--sp-5)" }}>
              <button type="button" onClick={() => setTab("new")} disabled={tab === "new"}>
                Novo pedido
              </button>
              <button type="button" onClick={openMine} disabled={tab === "mine"}>
                Meus chamados
              </button>
            </div>

            {tab === "mine" ? (
              <div style={{ padding: "var(--sp-4) var(--sp-5) var(--sp-5)" }}>
                {loadingMine && <p>Carregando…</p>}
                {!loadingMine && myRequests?.length === 0 && <p>Você ainda não abriu nenhum chamado.</p>}
                {!loadingMine && myRequests && myRequests.length > 0 && (
                  <ul style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)", listStyle: "none", padding: 0, margin: 0 }}>
                    {myRequests.map((r) => {
                      const isExpanded = expandedId === r.id;
                      return (
                        <li key={r.id} style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "var(--sp-3)" }}>
                          <button
                            type="button"
                            onClick={() => setExpandedId(isExpanded ? null : r.id)}
                            style={{ display: "flex", justifyContent: "space-between", gap: "var(--sp-2)", width: "100%", background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left" }}
                          >
                            <span>
                              <strong>{r.subject ?? "Chamado #" + r.id}</strong>
                              <span style={{ display: "flex", alignItems: "center", gap: "var(--sp-1)", fontSize: "0.85em", color: "var(--muted-foreground)" }}>
                                <MessageSquare size={12} /> {fmtDateTime(r.created_at)}
                              </span>
                            </span>
                            <span>{STATUS_LABEL[r.status] ?? r.status}</span>
                          </button>
                          {r.message && !isExpanded && <p style={{ marginTop: "var(--sp-2)" }}>{r.message}</p>}
                          {isExpanded && <TicketThread requestId={r.id} />}
                        </li>
                      );
                    })}
                  </ul>
                )}
                <footer>
                  <button type="button" onClick={close}>Fechar</button>
                </footer>
              </div>
            ) : sent ? (
              <div style={{ padding: "0 var(--sp-5) var(--sp-5)" }}>
                <p>Pedido enviado! Nossa equipe entrará em contato pelo WhatsApp informado.</p>
                <footer>
                  <button type="button" onClick={close}>Fechar</button>
                </footer>
              </div>
            ) : (
              <form ref={formRef} onSubmit={handleSubmit}>
                {error && <div className="kanban-form-error">{error}</div>}

                <label>Assunto *<input name="subject" required maxLength={160} placeholder="Resumo do problema" /></label>
                <label>
                  Prioridade
                  <select name="priority" defaultValue="MEDIA">
                    <option value="BAIXA">Baixa</option>
                    <option value="MEDIA">Média</option>
                    <option value="ALTA">Alta</option>
                  </select>
                </label>
                <label>Seu nome *<input name="contact_name" required autoComplete="name" /></label>
                <label>WhatsApp *<input name="contact_whatsapp" required autoComplete="tel" placeholder="(11) 99999-9999" /></label>
                <label>Como podemos ajudar?<textarea name="message" rows={3} placeholder="Descreva sua dúvida ou problema…" /></label>

                <footer>
                  <button type="button" onClick={close}>Cancelar</button>
                  <button type="submit" disabled={loading}>
                    <Send size={14} /> {loading ? "Enviando…" : "Enviar pedido"}
                  </button>
                </footer>
              </form>
            )}
          </section>
        </div>
      )}
    </>
  );
}
