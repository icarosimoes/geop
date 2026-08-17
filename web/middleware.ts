import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
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
     * - Public assets (images, svgs, etc.)
     */
    "/((?!_next/static|_next/image|favicon\\.ico|sitemap\\.xml|robots\\.txt|api/|impersonate|sso|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
