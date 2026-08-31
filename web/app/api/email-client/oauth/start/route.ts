import { getValidToken } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function POST(request: NextRequest) {
  let token: string;
  try { token = await getValidToken(); } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const body = await request.json();
  const res = await fetch(`${apiUrl}/email-client/oauth/start`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
