import { fetchSchedule } from "@/app/actions";
import TabBar from "@/app/components/TabBar";

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

function weekdayLabel(iso: string): string {
  const date = new Date(`${iso}T12:00:00`);
  return date.toLocaleDateString("pt-BR", { weekday: "short" });
}

export default async function EscalaPage() {
  const today = new Date();
  const end = new Date(today);
  end.setDate(end.getDate() + 14);

  const entries = await fetchSchedule(toISODate(today), toISODate(end));

  return (
    <div className="app-content">
      <header className="app-header">
        <h1>Escala</h1>
      </header>

      <div className="card">
        {entries.length === 0 && <p className="center-message">Nenhuma escala encontrada para os próximos dias.</p>}
        {entries.map((entry) => (
          <div className="list-item" key={entry.date}>
            <div>
              <div className="title">
                {formatDate(entry.date)} · {weekdayLabel(entry.date)}
              </div>
              <div className="subtitle">
                {entry.shift_id === null
                  ? "Folga"
                  : `${entry.shift_name ?? "Turno"} · ${entry.start_time ?? "--"}–${entry.end_time ?? "--"}`}
              </div>
            </div>
            {entry.shift_id === null ? (
              <span className="badge" style={{ background: "#f3f6fa", color: "#6c778c" }}>
                Folga
              </span>
            ) : (
              <span className="badge" style={entry.shift_color ? { background: `${entry.shift_color}22`, color: entry.shift_color } : undefined}>
                {entry.shift_name}
              </span>
            )}
          </div>
        ))}
      </div>

      <TabBar />
    </div>
  );
}
