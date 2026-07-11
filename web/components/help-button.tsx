"use client";

import { HelpCircle, Send, X } from "lucide-react";
import { useRef, useState } from "react";
import { createSupportRequestAction } from "@/app/actions";

export function HelpButton() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  function close() {
    setOpen(false);
    setError("");
    setSent(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fd = new FormData(formRef.current!);
    setLoading(true);
    setError("");
    try {
      const result = await createSupportRequestAction({
        contact_name: String(fd.get("contact_name") ?? ""),
        contact_whatsapp: String(fd.get("contact_whatsapp") ?? ""),
        message: String(fd.get("message") ?? "") || undefined,
      });
      if (!result.ok) throw new Error(result.error);
      setSent(true);
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
                <h2>Falar com o suporte</h2>
              </div>
              <button className="icon-button" onClick={close}>
                <X />
              </button>
            </header>

            {sent ? (
              <div style={{ padding: "0 var(--sp-5) var(--sp-5)" }}>
                <p>Pedido enviado! Nossa equipe entrará em contato pelo WhatsApp informado.</p>
                <footer>
                  <button type="button" onClick={close}>Fechar</button>
                </footer>
              </div>
            ) : (
              <form ref={formRef} onSubmit={handleSubmit}>
                {error && <div className="kanban-form-error">{error}</div>}

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
