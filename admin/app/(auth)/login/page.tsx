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
          <span className="text-white font-extrabold text-3xl tracking-wide">Registro</span>
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
              <label className="block text-sm font-medium text-gray-700">E-mail</label>
              <input
                name="email"
                type="email"
                required
                placeholder="admin@registro.local"
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#2BC4B4]/40 focus:border-[#2BC4B4] transition-colors"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">Senha</label>
              <input
                name="password"
                type="password"
                required
                placeholder="••••••••"
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#2BC4B4]/40 focus:border-[#2BC4B4] transition-colors"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-xl py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: "linear-gradient(135deg, #1D3461, #142548)" }}
            >
              Entrar
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-white/30 mt-6">
          © {new Date().getFullYear()} Registro · Acesso restrito a administradores da plataforma.
        </p>
      </div>
    </main>
  );
}
