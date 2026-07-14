import { getValidToken } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function GET(request: NextRequest) {
  let token: string;
  try {
    token = await getValidToken();
  } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const qs = request.nextUrl.searchParams.toString();
  const response = await fetch(`${apiUrl}/work-orders/export${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.json({ error: "export_failed" }, { status: response.status });
  }

  const buffer = await response.arrayBuffer();
  return new NextResponse(buffer, {
    status: 200,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition": response.headers.get("Content-Disposition") ?? "attachment; filename=ordens-de-servico.xlsx",
    },
  });
}
