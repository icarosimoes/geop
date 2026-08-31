import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

// Prefixo de páginas públicas por natureza (não é "tela de login alternativa" —
// um usuário autenticado do tenant também pode abrir o link, ex.: pra
// conferir o que o cliente vê antes de mandar) — nunca redireciona, em
// nenhum dos dois sentidos. Ver app/orcamento/[token]/ (aceite de orçamento
// pelo cliente, autenticado via token JWT próprio no path, não por cookie).
const PUBLIC_PREFIXES = ["/orcamento/"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return NextResponse.next();
  }

  const token = request.cookies.get("tenant_token")?.value;

  // Authenticated user on login page -> redirect to dashboard
  if (token && PUBLIC_PATHS.includes(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Unauthenticated user on protected page -> redirect to login
  if (!token && !PUBLIC_PATHS.includes(pathname)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico, sitemap.xml, robots.txt
     * - API routes
     * - /impersonate (troca de ticket de impersonação, controla seus próprios redirects)
     * - /sso (troca de token de SSO vindo do erpsolid, controla seus próprios redirects)
     * - Public assets (manifest, service worker, imagens, svgs, etc. — servidos de web/public)
     */
    "/((?!_next/static|_next/image|favicon\\.ico|sitemap\\.xml|robots\\.txt|api/|impersonate|sso|manifest\\.json|sw\\.js|sw-loader\\.js|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
