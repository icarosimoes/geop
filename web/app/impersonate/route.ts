import { NextRequest, NextResponse } from "next/server";

import { setTokenCookies } from "@/lib/auth";
import { safeParse, TokenResponseSchema } from "@/lib/schemas";

const apiUrl = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function GET(request: NextRequest) {
  const ticket = request.nextUrl.searchParams.get("ticket");
  if (!ticket) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const response = await fetch(`${apiUrl}/auth/impersonate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticket }),
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.redirect(new URL("/login?error=impersonation", request.url));
  }

  const data = safeParse(TokenResponseSchema, await response.json());
  await setTokenCookies(data);
  return NextResponse.redirect(new URL("/dashboard", request.url));
}
