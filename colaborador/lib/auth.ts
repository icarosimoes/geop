import { cookies } from "next/headers";

const COOKIE_NAME = "employee_token";

const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.COOKIE_SECURE === "true" || process.env.NODE_ENV === "production",
  path: "/",
};

/**
 * Sessão do colaborador não tem refresh token (por design — TTL curto de 60min,
 * re-login por PIN é aceitável). Ao expirar, authedFetch limpa o cookie e
 * o server component de cada página redireciona para /login.
 */
export async function setEmployeeTokenCookie(token: string, expiresIn: number): Promise<void> {
  const jar = await cookies();
  jar.set(COOKIE_NAME, token, {
    ...COOKIE_OPTIONS,
    maxAge: expiresIn,
  });
}

export async function getEmployeeToken(): Promise<string | null> {
  const jar = await cookies();
  return jar.get(COOKIE_NAME)?.value ?? null;
}

export async function clearEmployeeTokenCookie(): Promise<void> {
  const jar = await cookies();
  jar.delete(COOKIE_NAME);
}

export const EMPLOYEE_COOKIE_NAME = COOKIE_NAME;
