import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { tryRefreshToken } from "@/lib/api";

const API_URL = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, await params);
}

async function forward(url: string, method: string, body: string | undefined, token: string) {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (body) headers["Content-Type"] = "application/json";
  return fetch(url, { method, headers, body, cache: "no-store" });
}

async function proxy(req: NextRequest, params: { path: string[] }) {
  let token = (await cookies()).get("platform_token")?.value;
  if (!token) return NextResponse.json({ detail: "unauthorized" }, { status: 401 });

  const path = params.path.join("/");
  const url = `${API_URL}/platform/${path}`;

  let body: string | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    try {
      body = await req.text();
    } catch {
      // no body
    }
  }

  let res = await forward(url, req.method, body, token);

  if (res.status === 401) {
    const newToken = await tryRefreshToken();
    if (!newToken) {
      return NextResponse.json(
        { detail: "session_expired" },
        { status: 401 },
      );
    }
    token = newToken;
    res = await forward(url, req.method, body, token);
  }

  if (res.status === 204) return new NextResponse(null, { status: 204 });

  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
