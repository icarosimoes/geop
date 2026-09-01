import { getValidToken } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let token: string;
  try {
    token = await getValidToken();
  } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const response = await fetch(`${apiUrl}/commercial/quotes/${id}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

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
