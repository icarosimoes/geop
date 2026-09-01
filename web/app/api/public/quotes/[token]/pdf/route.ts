import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

// Sem auth de propósito — espelha /public/quotes/{token}/pdf da API, que é
// autenticado só pelo próprio token JWT no path (ver
// app/domain/commercial/public_router.py). Proxy existe porque o browser do
// cliente não resolve o hostname interno do container da API (`api:8000`),
// só o server-side desta rota resolve.
export async function GET(_request: NextRequest, { params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  const response = await fetch(`${apiUrl}/public/quotes/${token}/pdf`, { cache: "no-store" });

  if (!response.ok) {
    return NextResponse.json({ error: "download_failed" }, { status: response.status });
  }

  const buffer = await response.arrayBuffer();
  return new NextResponse(buffer, {
    status: 200,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/pdf",
      "Content-Disposition": response.headers.get("Content-Disposition") ?? "attachment",
    },
  });
}
