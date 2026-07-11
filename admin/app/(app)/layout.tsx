import { redirect } from "next/navigation";
import { Toaster } from "@/components/ui/toaster";
import { SidebarWrapper } from "@/components/sidebar-wrapper";
import { TopUserMenu } from "@/components/top-user-menu";
import { getPlatformToken, platformFetch } from "@/lib/api";

type PlatformUser = { name: string; email: string; role: string };

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const token = await getPlatformToken();
  if (!token) redirect("/login");

  let me: PlatformUser = { name: "Admin", email: "", role: "super_admin" };
  try {
    me = await platformFetch<PlatformUser>("/platform/auth/me");
  } catch {
    // fallback
  }

  return (
    <>
      <div className="min-h-screen flex bg-[#1D3461]">
        <SidebarWrapper name={me.name} email={me.email} />

        <div className="flex-1 flex flex-col min-w-0 bg-[#F4F6FB] rounded-tl-2xl rounded-bl-2xl overflow-hidden">
          <header className="h-14 bg-white border-b border-gray-100 px-6 flex items-center justify-between gap-2 shrink-0 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-widest text-[#2BC4B4]">Plataforma</span>
              <span className="text-gray-300">·</span>
              <span className="text-xs text-gray-500">Super Admin</span>
            </div>
            <TopUserMenu name={me.name} email={me.email} />
          </header>

          <main className="flex-1 overflow-y-auto p-8">
            {children}
          </main>
        </div>
      </div>
      <Toaster />
    </>
  );
}
