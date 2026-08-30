import { getValidToken } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

async function token() {
  return getValidToken();
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  let tk: string;
  try { tk = await token(); } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const body = await request.json();
  const res = await fetch(`${apiUrl}/email-client/accounts/${id}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${tk}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function DELETE(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  let tk: string;
  try { tk = await token(); } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const res = await fetch(`${apiUrl}/email-client/accounts/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${tk}` },
  });
  return new NextResponse(null, { status: res.status });
}
