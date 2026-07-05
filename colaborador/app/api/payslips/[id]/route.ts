import { NextRequest, NextResponse } from "next/server";

import { getEmployeeToken } from "@/lib/auth";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

// Proxy autenticado do download de contracheque: o <a href> do client não
// consegue anexar o header Authorization, então este route handler injeta o
// Bearer token do cookie httpOnly e repassa o stream binário (PDF) do backend
// direto para o browser, sem nunca expor o token no client.
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await getEmployeeToken();
  if (!token) {
    return NextResponse.json({ detail: { code: "unauthorized" } }, { status: 401 });
  }

  const response = await fetch(`${apiUrl}/timeclock/mobile/payslips/${id}/download`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok || !response.body) {
    return NextResponse.json(
      { detail: { code: "download_failed" } },
      { status: response.status || 502 },
    );
  }

  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  const contentDisposition = response.headers.get("content-disposition");
  if (contentType) headers.set("content-type", contentType);
  headers.set("content-disposition", contentDisposition ?? `attachment; filename="contracheque-${id}.pdf"`);

  return new NextResponse(response.body, { status: 200, headers });
}
