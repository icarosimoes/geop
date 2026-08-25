"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTransition } from "react";

import { logoutAction } from "@/app/actions";

const TABS = [
  {
    href: "/ponto",
    label: "Ponto",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 3" />
      </svg>
    ),
  },
  {
    href: "/escala",
    label: "Escala",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="4" width="18" height="17" rx="2" />
        <path d="M3 9h18M8 2v4M16 2v4" />
      </svg>
    ),
  },
  {
    href: "/contracheque",
    label: "Contracheque",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M6 2h9l3 3v17H6z" />
        <path d="M14 2v4h4M9 13h6M9 17h6" />
      </svg>
    ),
  },
  {
    href: "/banco",
    label: "Banco",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="10" width="18" height="10" rx="1" />
        <path d="M3 10l9-6 9 6M9 14v3M15 14v3" />
      </svg>
    ),
  },
  {
    href: "/ferias",
    label: "Férias",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2C7 2 3 7 3 12s4 10 9 10 9-4.5 9-10S17 2 12 2z" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
  },
];

export default function TabBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function handleLogout() {
    startTransition(async () => {
      await logoutAction();
      router.push("/login");
    });
  }

  return (
    <nav className="tab-bar">
      {TABS.map((tab) => (
        <Link key={tab.href} href={tab.href} className={pathname === tab.href ? "active" : ""}>
          {tab.icon}
          {tab.label}
        </Link>
      ))}
      <button type="button" onClick={handleLogout} disabled={isPending}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <path d="M16 17l5-5-5-5M21 12H9" />
        </svg>
        Sair
      </button>
    </nav>
  );
}
