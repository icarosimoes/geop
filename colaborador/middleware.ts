import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/login/trocar-pin"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("employee_token")?.value;

  const isPublic = PUBLIC_PATHS.includes(pathname);

  if (token && pathname === "/login") {
    return NextResponse.redirect(new URL("/ponto", request.url));
  }

  if (!token && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|sitemap\\.xml|robots\\.txt|api/|manifest\\.json|sw\\.js|sw-loader\\.js|icons/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
