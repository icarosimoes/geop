"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Building,
  Tag,
  CreditCard,
  ShieldAlert,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const items: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tenants", label: "Empresas", icon: Building },
  { href: "/plans", label: "Planos", icon: Tag },
  { href: "/audit", label: "Auditoria", icon: ShieldAlert },
  { href: "/settings", label: "Configurações", icon: Settings },
];

export function SidebarNav({ collapsed }: { collapsed?: boolean }) {
  const pathname = usePathname();

  return (
    <nav className="space-y-0.5">
      {items.map((item) => {
        const Icon = item.icon;
        const active =
          item.href === "/dashboard"
            ? pathname === "/dashboard" || pathname === "/"
            : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            title={collapsed ? item.label : undefined}
            className={cn(
              "flex items-center rounded-md py-2 text-sm transition-colors",
              collapsed ? "justify-center px-2" : "gap-3 px-3",
              active
                ? "bg-[#2BC4B4]/20 text-[#4DD9CB] font-medium"
                : "text-white/70 hover:bg-white/10 hover:text-white",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}
