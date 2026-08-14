import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { loginAction } from "@/lib/actions";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return (
    <main
      className="min-h-screen flex items-center justify-center p-6"
      style={{ background: "linear-gradient(180deg, #1D3461 0%, #142548 100%)" }}
    >
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-8">
          <span className="text-white font-extrabold text-3xl tracking-wide">GEOP</span>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8 space-y-5">
          <div className="space-y-1">
            <p className="text-[#2BC4B4] text-xs font-bold tracking-widest uppercase">Painel SaaS</p>
            <h1 className="text-[#1D3461] font-bold text-2xl">Entrar como administrador</h1>
            <p className="text-sm text-gray-500">Gerencie empresas, planos e assinaturas.</p>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
              E-mail ou senha inválidos.
            </p>
          )}

          <form action={loginAction} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-gray-700">E-mail</Label>
              <Input
                id="email"
                name="email"
                type="email"
                required
                placeholder="admin@registro.local"
                className="h-auto rounded-xl border-gray-200 px-4 py-3"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-gray-700">Senha</Label>
              <Input
                id="password"
                name="password"
                type="password"
                required
                placeholder="••••••••"
                className="h-auto rounded-xl border-gray-200 px-4 py-3"
              />
            </div>
            <Button type="submit" size="lg" className="w-full rounded-xl py-3 h-auto">
              Entrar
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-white/30 mt-6">
          © {new Date().getFullYear()} GEOP · Acesso restrito a administradores da plataforma.
        </p>
      </div>
    </main>
  );
}
