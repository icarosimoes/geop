"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import { logoutAction } from "@/lib/actions";

function initials(name: string) {
  return name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

export function TopUserMenu({ name, email }: { name: string; email: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="h-9 w-9 rounded-full flex items-center justify-center text-white text-xs font-bold hover:opacity-90 transition-opacity"
        style={{ background: "linear-gradient(135deg, #2BC4B4, #1D3461)" }}
        title={name}
      >
        {initials(name)}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-11 z-20 w-56 bg-white rounded-xl shadow-xl border border-gray-100 py-1 overflow-hidden">
            <div className="px-3 py-2 border-b border-gray-50">
              <p className="text-sm font-medium text-gray-800 truncate">{name}</p>
              <p className="text-xs text-gray-500 truncate">{email}</p>
            </div>
            <form action={logoutAction}>
              <button
                type="submit"
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Sair
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
