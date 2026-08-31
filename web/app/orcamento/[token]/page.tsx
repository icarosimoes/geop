import { getPublicQuoteAction } from "./actions";
import { QuoteView } from "./quote-view";

export default async function OrcamentoPublicoPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const res = await getPublicQuoteAction(token);

  if (!res.ok || !res.data) {
    return (
      <main className="tenant-login-page">
        <div className="tenant-login-card">
          <h2>Link inválido</h2>
          <p>{res.error ?? "Não foi possível carregar este orçamento."}</p>
        </div>
      </main>
    );
  }

  return <QuoteView token={token} initial={res.data} />;
}
