"use client";

import { useState } from "react";
import { PanelLeft, PanelLeftClose } from "lucide-react";
import { SidebarNav } from "./sidebar-nav";
import { SidebarUserMenu } from "./sidebar-user-menu";

export function SidebarWrapper({ name, email }: { name: string; email: string }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-60"} shrink-0 flex flex-col transition-all duration-300 ease-in-out`}
      style={{ background: "linear-gradient(180deg, #1D3461 0%, #142548 100%)" }}
    >
      <div className="flex items-center min-h-[68px] px-3 border-b border-white/10 gap-2">
        {collapsed ? (
          <div className="w-9 h-9 flex items-center justify-center shrink-0">
            <span className="text-white font-extrabold text-sm">R</span>
          </div>
        ) : (
          <div className="flex-1 min-w-0 py-3">
            <span className="text-white font-extrabold text-lg tracking-wide">GEOP</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="ml-auto text-white/50 hover:text-white hover:bg-white/10 rounded-md p-1 transition-colors shrink-0"
          title={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-4">
        <SidebarNav collapsed={collapsed} />
      </div>

      <div className="border-t border-white/10">
        <SidebarUserMenu name={name} email={email} collapsed={collapsed} />
      </div>
    </aside>
  );
}
