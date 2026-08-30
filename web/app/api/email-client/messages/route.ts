import { getValidToken } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function GET(request: NextRequest) {
  let token: string;
  try { token = await getValidToken(); } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const qs = request.nextUrl.searchParams.toString();
  const res = await fetch(`${apiUrl}/email-client/messages?${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
