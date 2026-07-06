"use client";

import { useState } from "react";
import { Upload, Download } from "lucide-react";
import { importPayslipsAction, type PayslipImportResponse } from "@/app/actions";
import type { TenantUser } from "@/lib/api";

const MANIFEST_TEMPLATE = "cpf,matricula,competencia,arquivo\n12345678900,,2026-06,fulano.pdf\n";

function statusLabel(status: string) {
  if (status === "created") return "Criado";
  if (status === "updated") return "Atualizado";
  return "Erro";
}

function statusClass(status: string) {
  if (status === "failed") return "status status-waiting";
  return "status status-done";
}

export function PayslipImportManager({ user }: { user: TenantUser }) {
  const [manifest, setManifest] = useState<File | null>(null);
  const [archive, setArchive] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<PayslipImportResponse | null>(null);
  const [toast, setToast] = useState("");

  const canManage = user.permissions.includes("*") || user.permissions.includes("timeclock.manage");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function downloadTemplate() {
    const blob = new Blob([MANIFEST_TEMPLATE], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "modelo-manifesto-contracheques.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport() {
    if (!manifest || !archive) return;
    setImporting(true);
    setResult(null);
    const formData = new FormData();
    formData.append("manifest", manifest);
    formData.append("archive", archive);
    const response = await importPayslipsAction(formData);
    setImporting(false);

    if (response.ok) {
      setResult(response.result);
      showToast(
        `Importação concluída: ${response.result.created} criado(s), ${response.result.updated} atualizado(s), ${response.result.failed} com erro.`,
      );
    } else {
      showToast(response.error);
    }
  }

  if (!canManage) {
    return (
      <section className="module-panel">
        <div className="module-state">
          <strong>Sem permissão</strong>
          <span>Você não tem permissão para importar contracheques.</span>
        </div>
      </section>
    );
  }

  return (
    <section className="module-panel">
      <div style={{ padding: "var(--sp-4) var(--sp-5)" }}>
        <p style={{ marginTop: 0 }}>
          Suba um <strong>manifesto CSV</strong> (colunas <code>cpf</code>, <code>matricula</code>,{" "}
          <code>competencia</code> no formato <code>AAAA-MM</code>, e <code>arquivo</code> com o
          nome exato do PDF dentro do ZIP) e um <strong>ZIP</strong> com os PDFs de contracheque.
          Basta informar <code>cpf</code> <em>ou</em> <code>matricula</code> por linha.
        </p>
        <button
          type="button"
          className="secondary-button"
          onClick={downloadTemplate}
          style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: "var(--sp-4)" }}
        >
          <Download size={16} /> Baixar modelo de manifesto
        </button>

        <div className="report-filter-bar" style={{ margin: 0, boxShadow: "none" }}>
          <div className="report-filter-field">
            <label htmlFor="manifest_file">Manifesto (.csv)</label>
            <input
              id="manifest_file"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setManifest(e.target.files?.[0] ?? null)}
              disabled={importing}
            />
          </div>
          <div className="report-filter-field">
            <label htmlFor="archive_file">Arquivo com os PDFs (.zip)</label>
            <input
              id="archive_file"
              type="file"
              accept=".zip,application/zip"
              onChange={(e) => setArchive(e.target.files?.[0] ?? null)}
              disabled={importing}
            />
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={handleImport}
            disabled={!manifest || !archive || importing}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Upload size={16} /> {importing ? "Importando..." : "Importar contracheques"}
          </button>
        </div>

        {result && (
          <div className="module-table-wrap" style={{ marginTop: "var(--sp-4)" }}>
            <table>
              <thead>
                <tr>
                  <th>Linha</th>
                  <th>Funcionário</th>
                  <th>Competência</th>
                  <th>Status</th>
                  <th>Detalhe</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((row) => (
                  <tr key={row.row}>
                    <td>{row.row}</td>
                    <td>{row.employee_name ?? "—"}</td>
                    <td>{row.reference_month ?? "—"}</td>
                    <td>
                      <span className={statusClass(row.status)}>{statusLabel(row.status)}</span>
                    </td>
                    <td>{row.error ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
