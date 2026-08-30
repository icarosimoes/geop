import { getValidToken } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function GET(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  let token: string;
  try { token = await getValidToken(); } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const res = await fetch(`${apiUrl}/email-client/messages/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  let token: string;
  try { token = await getValidToken(); } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const qs = request.nextUrl.searchParams.toString();
  const res = await fetch(`${apiUrl}/email-client/messages/${id}/read?${qs}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
