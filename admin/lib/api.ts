import { cookies } from "next/headers";

const API_URL = process.env.API_URL ?? "http://localhost:8000/api/v1";

export async function getPlatformToken(): Promise<string | null> {
  const store = await cookies();
  return store.get("platform_token")?.value ?? null;
}

export async function tryRefreshToken(): Promise<string | null> {
  const jar = await cookies();
  const refreshToken = jar.get("platform_refresh_token")?.value;
  if (!refreshToken) return null;

  const response = await fetch(`${API_URL}/platform/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!response.ok) return null;

  const data = (await response.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };
  jar.set("platform_token", data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: data.expires_in,
  });
  jar.set("platform_refresh_token", data.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return data.access_token;
}

export async function platformFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await getPlatformToken();
  if (!token) throw new Error("unauthorized");
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401) {
    const newToken = await tryRefreshToken();
    if (!newToken) throw new Error("unauthorized");
    const retry = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${newToken}`,
        ...(init.headers ?? {}),
      },
    });
    if (!retry.ok) throw new Error(`Platform API ${retry.status}`);
    if (retry.status === 204) return undefined as T;
    return retry.json();
  }
  if (!res.ok) throw new Error(`Platform API ${res.status}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}
