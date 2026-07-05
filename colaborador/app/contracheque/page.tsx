import { fetchPayslips } from "@/app/actions";
import TabBar from "@/app/components/TabBar";

function formatMonth(iso: string): string {
  const [year, month] = iso.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

export default async function ContrachequePage() {
  const payslips = await fetchPayslips();
  const sorted = [...payslips].sort((a, b) => (a.reference_month < b.reference_month ? 1 : -1));

  return (
    <div className="app-content">
      <header className="app-header">
        <h1>Contracheque</h1>
      </header>

      <div className="card">
        {sorted.length === 0 && <p className="center-message">Nenhum contracheque disponível ainda.</p>}
        {sorted.map((payslip) => (
          <div className="list-item" key={payslip.id}>
            <div>
              <div className="title" style={{ textTransform: "capitalize" }}>
                {formatMonth(payslip.reference_month)}
              </div>
            </div>
            <a className="link-button" href={`/api/payslips/${payslip.id}`} download>
              Baixar
            </a>
          </div>
        ))}
      </div>

      <TabBar />
    </div>
  );
}
