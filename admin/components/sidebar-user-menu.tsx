"use client";

import { LogOut } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { logoutAction } from "@/lib/actions";
import { initials } from "@/lib/utils";

export function SidebarUserMenu({
  name,
  email,
  collapsed,
}: {
  name: string;
  email: string;
  collapsed?: boolean;
}) {
  return (
    <div className="px-2 py-3">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
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
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-56">
          <DropdownMenuLabel className="font-normal">
            <p className="text-sm font-medium text-[var(--foreground)] truncate">{name}</p>
            <p className="text-xs text-[var(--muted-foreground)] truncate">{email}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <form action={logoutAction}>
            <DropdownMenuItem asChild>
              <button type="submit" className="w-full text-[var(--danger)]">
                <LogOut className="h-4 w-4" />
                Sair
              </button>
            </DropdownMenuItem>
          </form>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
