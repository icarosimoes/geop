"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import { logoutAction } from "@/lib/actions";

function initials(name: string) {
  return name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

export function SidebarUserMenu({
  name,
  email,
  collapsed,
}: {
  name: string;
  email: string;
  collapsed?: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative px-2 py-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center rounded-md p-2 hover:bg-white/10 transition-colors ${collapsed ? "justify-center" : "gap-3"}`}
      >
        <div
          className="h-8 w-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
          style={{ background: "linear-gradient(135deg, #2BC4B4, #1D3461)" }}
        >
          {initials(name)}
        </div>
        {!collapsed && (
          <div className="flex-1 text-left min-w-0">
            <p className="text-white text-sm font-medium truncate">{name}</p>
            <p className="text-white/50 text-xs truncate">{email}</p>
          </div>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-2 right-2 mb-1 z-20 bg-white rounded-xl shadow-xl border border-gray-100 py-1 overflow-hidden">
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
