"use client";

import { Loader2, Paperclip, Upload, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ModuleRecord } from "@/lib/module-definitions";
import type { AttachmentItem } from "@/app/actions";
import { useCepLookup } from "@/lib/use-document-lookup";
import { formatCEP } from "@/lib/validators";

const requestTypes = [
  "Dados do tomador incorretos",
  "Nota travada / erro no sistema",
  "Nota solicitada após check-out",
  "Cancelamento de nota emitida",
] as const;

type LocalFile = { file: File; preview: string };

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

export interface FiscalSaveData extends Partial<ModuleRecord> {
  pendingFiles?: File[];
}

export function FiscalRequestForm({
  record,
  userName,
  existingAttachments,
  onSave,
  onCancel,
  onDeleteAttachment,
}: {
  record: ModuleRecord | "new";
  userName: string;
  existingAttachments?: AttachmentItem[];
  onSave: (data: FiscalSaveData) => void;
  onCancel: () => void;
  onDeleteAttachment?: (id: number) => void;
}) {
  const isNew = record === "new";
  const existing = isNew ? null : record;

  const [requestType, setRequestType] = useState(existing?.requestType ?? "");
  const [apartment, setApartment] = useState(existing?.apartment ?? "");
  const [reservationNumber, setReservationNumber] = useState(existing?.reservationNumber ?? "");
  const [invoiceNumber, setInvoiceNumber] = useState(existing?.invoiceNumber ?? "");
  const [checkoutDate, setCheckoutDate] = useState(existing?.checkoutDate ?? "");
  const [taxpayerDoc, setTaxpayerDoc] = useState(existing?.taxpayerDoc ?? "");
  const [taxpayerName, setTaxpayerName] = useState(existing?.taxpayerName ?? "");
  const [taxpayerZip, setTaxpayerZip] = useState("");
  const [taxpayerStreet, setTaxpayerStreet] = useState(existing?.taxpayerAddress ?? "");
  const [taxpayerNumber, setTaxpayerNumber] = useState("");
  const [taxpayerComplement, setTaxpayerComplement] = useState("");
  const [taxpayerNeighborhood, setTaxpayerNeighborhood] = useState("");
  const [taxpayerCity, setTaxpayerCity] = useState("");
  const [taxpayerState, setTaxpayerState] = useState("");
  const [taxpayerEmail, setTaxpayerEmail] = useState(existing?.taxpayerEmail ?? "");

  const taxpayerCep = useCepLookup((fields) => {
    setTaxpayerStreet(fields.address_street ?? taxpayerStreet);
    setTaxpayerNeighborhood(fields.address_neighborhood ?? taxpayerNeighborhood);
    setTaxpayerCity(fields.address_city ?? taxpayerCity);
    setTaxpayerState(fields.address_state ?? taxpayerState);
  });
  const [cancellationReason, setCancellationReason] = useState(existing?.cancellationReason ?? "");
  const [correction, setCorrection] = useState(existing?.correction ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [status, setStatus] = useState(existing?.status ?? "Em andamento");
  const [owner, setOwner] = useState(existing?.owner ?? userName);
  const [title, setTitle] = useState(existing?.title ?? "");
  const [notifyUsersRaw, setNotifyUsersRaw] = useState((existing?.notifyUsers ?? []).join(", "));
  const [localFiles, setLocalFiles] = useState<LocalFile[]>([]);
  const [savedAttachments, setSavedAttachments] = useState<AttachmentItem[]>(
    existingAttachments ?? [],
  );
  const [dragActive, setDragActive] = useState(false);

  const dropRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((files: FileList | File[]) => {
    const MAX_SIZE = 10 * 1024 * 1024;
    const ALLOWED_TYPES = new Set([
      "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
      "application/pdf", "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "text/csv", "text/plain", "application/zip",
    ]);
    const items: { file: File; preview: string }[] = [];
    for (const file of Array.from(files)) {
      if (file.size > MAX_SIZE) {
        alert(`"${file.name}" excede o limite de 10MB.`);
        continue;
      }
      if (file.type && !ALLOWED_TYPES.has(file.type)) {
        alert(`Tipo "${file.type}" não permitido para "${file.name}".`);
        continue;
      }
      items.push({
        file,
        preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
      });
    }
    if (items.length) setLocalFiles((prev) => [...prev, ...items]);
  }, []);

  const removeLocalFile = (index: number) => {
    setLocalFiles((prev) => {
      const item = prev[index];
      if (item.preview) URL.revokeObjectURL(item.preview);
      return prev.filter((_, i) => i !== index);
    });
  };

  const removeSavedAttachment = (id: number) => {
    setSavedAttachments((prev) => prev.filter((a) => a.id !== id));
    onDeleteAttachment?.(id);
  };

  useEffect(() => {
    return () => {
      localFiles.forEach((f) => { if (f.preview) URL.revokeObjectURL(f.preview); });
    };
  }, []);

  useEffect(() => {
    function handlePaste(e: ClipboardEvent) {
      const items = e.clipboardData?.items;
      if (!items) return;
      const files: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === "file") {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      }
      if (files.length > 0) {
        e.preventDefault();
        addFiles(files);
      }
    }
    document.addEventListener("paste", handlePaste);
    return () => document.removeEventListener("paste", handlePaste);
  }, [addFiles]);

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const slaDeadline = isNew
      ? new Date(Date.now() + 24 * 3_600_000).toISOString()
      : existing?.slaDeadline ?? new Date(Date.now() + 24 * 3_600_000).toISOString();

    onSave({
      title,
      category: requestType,
      owner,
      status,
      description,
      requestType,
      apartment,
      reservationNumber,
      invoiceNumber,
      checkoutDate,
      taxpayerDoc,
      taxpayerName,
      taxpayerAddress: [
        taxpayerStreet, taxpayerNumber, taxpayerComplement,
        taxpayerNeighborhood, taxpayerCity, taxpayerState, taxpayerZip,
      ].filter(Boolean).join(", "),
      taxpayerEmail,
      cancellationReason,
      correction,
      slaDeadline,
      notifyUsers: notifyUsersRaw.split(",").map((s) => s.trim()).filter(Boolean),
      pendingFiles: localFiles.map((f) => f.file),
    });
  }

  const showReservation = requestType === "Dados do tomador incorretos" || requestType === "Nota solicitada após check-out";
  const showInvoice = requestType === "Nota travada / erro no sistema" || requestType === "Cancelamento de nota emitida";
  const showTaxpayer = requestType === "Dados do tomador incorretos" || requestType === "Nota solicitada após check-out";
  const showCorrection = requestType === "Dados do tomador incorretos";
  const showCheckout = requestType === "Nota solicitada após check-out";
  const showEmail = requestType === "Nota solicitada após check-out";
  const showCancellation = requestType === "Cancelamento de nota emitida";

  return (
    <form className="fiscal-request-form" onSubmit={handleSubmit}>
      <label>
        Tipo da solicitação
        <select value={requestType} onChange={(e) => setRequestType(e.target.value)} required>
          <option value="" disabled>Selecione o tipo</option>
          {requestTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>

      <label>
        Título
        <input value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="Resumo da solicitação" />
      </label>

      <div className="form-grid">
        <label>
          UH (Apartamento)
          <input value={apartment} onChange={(e) => setApartment(e.target.value)} placeholder="Ex: 412" />
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option>Em andamento</option>
            <option>Em espera</option>
            <option>Aguardando</option>
            <option>Concluído</option>
          </select>
        </label>
      </div>

      <label>
        Responsável
        <input value={owner} onChange={(e) => setOwner(e.target.value)} required />
      </label>

      <label>
        Notificar
        <input value={notifyUsersRaw} onChange={(e) => setNotifyUsersRaw(e.target.value)} placeholder="Nomes separados por vírgula" />
        <small className="field-hint">Pessoas ou grupos que serão notificados sobre atualizações.</small>
      </label>

      {requestType && (
        <div className="fiscal-field-group">
          {showReservation && (
            <label>
              Número da reserva
              <input value={reservationNumber} onChange={(e) => setReservationNumber(e.target.value)} placeholder="Ex: RES-8821" />
            </label>
          )}

          {showInvoice && (
            <label>
              Número da nota fiscal
              <input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} placeholder="Ex: NF-2847" />
            </label>
          )}

          {showTaxpayer && (
            <>
              <label>
                CPF / CNPJ do tomador
                <input value={taxpayerDoc} onChange={(e) => setTaxpayerDoc(e.target.value)} placeholder="Ex: 12.345.678/0001-90" />
              </label>
              <label>
                Nome do tomador
                <input value={taxpayerName} onChange={(e) => setTaxpayerName(e.target.value)} />
              </label>
              <label>
                CEP do tomador
                <span className="field-with-status">
                  <input
                    value={taxpayerZip}
                    onChange={(e) => setTaxpayerZip(formatCEP(e.target.value))}
                    onBlur={(e) => taxpayerCep.handleBlur(e.target.value)}
                    placeholder="00000-000"
                  />
                  {taxpayerCep.loading && <Loader2 size={16} className="field-spinner" />}
                </span>
                {taxpayerCep.notFound && <small className="field-error-hint">CEP não encontrado.</small>}
              </label>
              <label>
                Logradouro do tomador
                <input value={taxpayerStreet} onChange={(e) => setTaxpayerStreet(e.target.value)} />
              </label>
              <label>
                Número
                <input value={taxpayerNumber} onChange={(e) => setTaxpayerNumber(e.target.value)} />
              </label>
              <label>
                Complemento
                <input value={taxpayerComplement} onChange={(e) => setTaxpayerComplement(e.target.value)} />
              </label>
              <label>
                Bairro
                <input value={taxpayerNeighborhood} onChange={(e) => setTaxpayerNeighborhood(e.target.value)} />
              </label>
              <label>
                Cidade
                <input value={taxpayerCity} onChange={(e) => setTaxpayerCity(e.target.value)} />
              </label>
              <label>
                UF
                <input maxLength={2} value={taxpayerState} onChange={(e) => setTaxpayerState(e.target.value.toUpperCase())} placeholder="SP" />
              </label>
            </>
          )}

          {showEmail && (
            <label>
              E-mail do tomador
              <input type="email" value={taxpayerEmail} onChange={(e) => setTaxpayerEmail(e.target.value)} />
            </label>
          )}

          {showCheckout && (
            <label>
              Data do check-out
              <input value={checkoutDate} onChange={(e) => setCheckoutDate(e.target.value)} placeholder="Ex: 18/06/2026" />
            </label>
          )}

          {showCorrection && (
            <label>
              Correção necessária
              <textarea value={correction} onChange={(e) => setCorrection(e.target.value)} rows={3} placeholder="Descreva a correção necessária" />
            </label>
          )}

          {showCancellation && (
            <label>
              Motivo do cancelamento
              <textarea value={cancellationReason} onChange={(e) => setCancellationReason(e.target.value)} rows={3} placeholder="Descreva o motivo do cancelamento" />
            </label>
          )}
        </div>
      )}

      <label>
        Observações
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} placeholder="Observações adicionais" />
      </label>

      <div>
        <label style={{ marginBottom: 8 }}>Anexos</label>
        <div
          ref={dropRef}
          className={`drop-zone${dragActive ? " active" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload size={22} />
          <span>Arraste arquivos aqui, clique para selecionar ou cole (Ctrl+V)</span>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            style={{ display: "none" }}
            onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ""; }}
          />
        </div>

        {(savedAttachments.length > 0 || localFiles.length > 0) && (
          <div className="attachment-grid">
            {savedAttachments.map((att) => (
              <div key={`saved-${att.id}`} className="attachment-preview">
                <button type="button" className="attachment-remove" onClick={() => removeSavedAttachment(att.id)}>
                  <X size={14} />
                </button>
                <div className="attachment-file-icon">
                  <Paperclip size={20} />
                </div>
                <span className="attachment-name">{att.filename}</span>
              </div>
            ))}
            {localFiles.map((lf, i) => (
              <div key={`local-${i}`} className="attachment-preview">
                <button type="button" className="attachment-remove" onClick={() => removeLocalFile(i)}>
                  <X size={14} />
                </button>
                {lf.preview ? (
                  <img src={lf.preview} alt={lf.file.name} />
                ) : (
                  <div className="attachment-file-icon">
                    <Paperclip size={20} />
                  </div>
                )}
                <span className="attachment-name">{lf.file.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <footer>
        <button type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={!requestType}>Salvar</button>
      </footer>
    </form>
  );
}
