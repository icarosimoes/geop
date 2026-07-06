"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import {
  createDeviceAction,
  deleteDeviceAction,
  fetchDevices,
  fetchRegistryOptions,
  type RegistryOption,
  type TimeClockDevice,
} from "@/app/actions";

const WEBHOOK_PATH = (token: string) => `/api/v1/integrations/control-id/${token}/punches`;

export function DeviceManager() {
  const [devices, setDevices] = useState<TimeClockDevice[]>([]);
  const [locations, setLocations] = useState<RegistryOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [serial, setSerial] = useState("");
  const [locationId, setLocationId] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [newToken, setNewToken] = useState<string | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  function reload() {
    fetchDevices().then(setDevices).finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    fetchRegistryOptions("locais").then(setLocations);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    const result = await createDeviceAction({
      name: name.trim(),
      serial_number: serial.trim() || null,
      location_id: locationId ? Number(locationId) : null,
    });
    setSaving(false);
    if (result.ok) {
      setName("");
      setSerial("");
      setLocationId("");
      setNewToken(String(result.data?.webhook_token ?? ""));
      showToast("Dispositivo criado.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao criar dispositivo.");
    }
  }

  async function handleDelete(device: TimeClockDevice) {
    if (!confirm(`Excluir o dispositivo "${device.name}"?`)) return;
    const result = await deleteDeviceAction(device.id);
    if (result.ok) {
      showToast("Dispositivo excluído.");
      reload();
    } else {
      showToast(result.error ?? "Erro ao excluir.");
    }
  }

  return (
    <section className="module-panel">
      <form
        onSubmit={handleCreate}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--sp-3)",
          padding: "var(--sp-4) var(--sp-5)",
          borderBottom: "1px solid var(--field-border)",
        }}
      >
        <div className="report-filter-field">
          <label htmlFor="device_name">Nome do relógio</label>
          <input
            id="device_name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex.: Recepção"
            required
          />
        </div>
        <div className="report-filter-group">
          <div className="report-filter-field" style={{ flex: "1 1 200px" }}>
            <label htmlFor="device_serial">Número de série</label>
            <input
              id="device_serial"
              value={serial}
              onChange={(e) => setSerial(e.target.value)}
              placeholder="Opcional"
            />
          </div>
          <div className="report-filter-field" style={{ flex: "1 1 200px" }}>
            <label htmlFor="device_location">Local</label>
            <select id="device_location" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Opcional</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>
          <button className="primary-button" type="submit" disabled={saving} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Plus size={16} /> {saving ? "Criando..." : "Adicionar"}
          </button>
        </div>
      </form>

      {newToken && (
        <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--field-border)" }}>
          <strong>Dispositivo criado.</strong> Configure no relógio a URL completa da API do
          Registro (ex.: <code>https://api.SEU-DOMINIO.com.br</code>) seguida do caminho abaixo:
          <div style={{ marginTop: 8 }}>
            <code>{WEBHOOK_PATH(newToken)}</code>
          </div>
          <small className="field-hint">
            Guarde o token — por segurança ele não é exibido novamente aqui além desta tela de
            criação (mas continua visível na lista abaixo).
          </small>
        </div>
      )}

      {loading ? (
        <div className="module-state">Carregando dispositivos...</div>
      ) : devices.length === 0 ? (
        <div className="module-state">
          <strong>Nenhum dispositivo cadastrado</strong>
          <span>Adicione um relógio de ponto para começar a receber batidas.</span>
        </div>
      ) : (
        <div className="module-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Modelo</th>
                <th>Local</th>
                <th>Token do webhook</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id}>
                  <td>
                    <strong>{device.name}</strong>
                  </td>
                  <td>{device.model}</td>
                  <td>{device.location ?? "—"}</td>
                  <td>
                    <code>{device.webhook_token}</code>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button onClick={() => handleDelete(device)} aria-label="Excluir">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="module-pagination">
        <span>{devices.length} dispositivo(s)</span>
      </footer>
      {toast && (
        <div className="module-toast" role="status">
          {toast}
        </div>
      )}
    </section>
  );
}
