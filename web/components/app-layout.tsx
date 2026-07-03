"use client";

import {
  Bell, BookOpen, Building2, CalendarClock, ChevronDown,
  ClipboardCheck, ClipboardList, Clock, Cpu, FileClock, FileText, Home,
  Link2, MapPin, Menu, Package, PanelLeftClose, PanelLeftOpen,
  Receipt, Settings, Shield, ShieldCheck, Timer, UserCog, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { logoutAction } from "@/app/actions";
import type { TenantUser } from "@/lib/api";
import { NotificationPanel, NotificationBadge } from "./notification-panel";

const navOperation = [
  { slug: "dashboard", label: "Dashboard", icon: Home, href: "/dashboard" },
  { slug: "ocorrencias", label: "Ocorrências", icon: FileClock, href: "/ocorrencias" },
  { slug: "ordens-servico", label: "Ordens de Serviço", icon: ClipboardList, href: "/ordens-servico" },
  { slug: "reunioes", label: "Reuniões", icon: Users, href: "/reunioes" },
  { slug: "relatorios-turno", label: "Relatórios de turno", icon: FileText, href: "/relatorios-turno" },
  { slug: "inspecoes", label: "Inspeções", icon: ClipboardCheck, href: "/inspecoes" },
  { slug: "preventivas", label: "Preventivas", icon: Timer, href: "/preventivas" },
  { slug: "solicitacoes-fiscais", label: "Solicitações Fiscais", icon: Receipt, href: "/solicitacoes-fiscais" },
  { slug: "mural", label: "Mural de avisos", icon: Bell, href: "/mural" },
];

const cadastrosSub = [
  { slug: "cadastros-setores", label: "Setores", icon: Building2, href: "/cadastros/setores" },
  { slug: "cadastros-locais", label: "Locais", icon: MapPin, href: "/cadastros/locais" },
  { slug: "cadastros-funcoes", label: "Funções", icon: UserCog, href: "/cadastros/funcoes" },
  { slug: "cadastros-procedimentos", label: "Procedimentos", icon: BookOpen, href: "/cadastros/procedimentos" },
  { slug: "cadastros-categorias-os", label: "Categorias de OS", icon: ClipboardList, href: "/cadastros/categorias-os" },
  { slug: "cadastros-escalas", label: "Escalas de trabalho", icon: CalendarClock, href: "/cadastros/escalas" },
  { slug: "cadastros-usuarios", label: "Usuários", icon: ShieldCheck, href: "/usuarios" },
  { slug: "cadastros-perfis", label: "Perfis de acesso", icon: Shield, href: "/perfis" },
];

const pontoSub = [
  { slug: "ponto-batidas", label: "Batidas", icon: Clock, href: "/ponto" },
  { slug: "ponto-dispositivos", label: "Dispositivos", icon: Cpu, href: "/ponto/dispositivos" },
  { slug: "ponto-vinculos", label: "Vínculos", icon: Link2, href: "/ponto/vinculos" },
];

export function AppLayout({ user, children }: { user: TenantUser; children: ReactNode }) {
  const pathname = usePathname();
  const pathParts = pathname.replace(/^\//, "").split("/");
  const currentSlug = pathname === "/" || pathname === "/dashboard" ? "dashboard" : pathParts[0];
  const isCadastrosPage = currentSlug === "cadastros" || currentSlug === "usuarios" || currentSlug === "perfis";
  const cadastrosSubSlug = currentSlug === "usuarios"
    ? "cadastros-usuarios"
    : currentSlug === "perfis"
    ? "cadastros-perfis"
    : currentSlug === "cadastros" && pathParts[1]
    ? `cadastros-${pathParts[1]}`
    : currentSlug === "cadastros" ? "cadastros" : "";
  const isPontoPage = currentSlug === "ponto";
  const pontoSubSlug = isPontoPage ? `ponto-${pathParts[1] ?? "batidas"}` : "";
  const [collapsed, setCollapsed] = useState(false);
  const [cadastrosOpen, setCadastrosOpen] = useState(isCadastrosPage);
  const [pontoOpen, setPontoOpen] = useState(isPontoPage);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [panel, setPanel] = useState<"notifications" | "profile" | null>(null);

  const displayName = user.name;
  const initials = displayName.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();

  function togglePanel(next: "notifications" | "profile") {
    setPanel((c) => (c === next ? null : next));
  }

  return (
    <div className={`app-shell ${collapsed ? "is-collapsed" : ""}`}>
      <aside className={`sidebar ${mobileMenu ? "is-open" : ""}`} aria-label="Navegação principal">
        <div className="brand-row">
          <div className="brand-mark" aria-hidden="true">R</div>
          {!collapsed && <div><strong>Registro</strong><span>Gestão operacional</span></div>}
          <button className="icon-button collapse-button" onClick={() => setCollapsed((v) => !v)} aria-label={collapsed ? "Expandir menu" : "Recolher menu"}>
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>
        <nav className="nav-list">
          <p className="nav-section">{collapsed ? "" : "Operação"}</p>
          {navOperation.map(({ slug, label, icon: Icon, href }) => (
            <Link key={slug} href={href} className={`nav-item ${currentSlug === slug ? "active" : ""}`} title={collapsed ? label : undefined} onClick={() => setMobileMenu(false)}>
              <Icon size={19} aria-hidden="true" />
              {!collapsed && <span>{label}</span>}
            </Link>
          ))}
          <button
            className={`nav-item ${isCadastrosPage ? "active" : ""}`}
            onClick={() => setCadastrosOpen((v) => !v)}
            title={collapsed ? "Cadastros" : undefined}
          >
            <Building2 size={19} aria-hidden="true" />
            {!collapsed && <><span>Cadastros</span><ChevronDown size={14} className={`nav-chevron ${cadastrosOpen ? "open" : ""}`} /></>}
          </button>
          {cadastrosOpen && !collapsed && cadastrosSub.map(({ slug, label, icon: SubIcon, href }) => (
            <Link key={slug} href={href} className={`nav-item nav-sub-item ${cadastrosSubSlug === slug ? "active" : ""}`} onClick={() => setMobileMenu(false)}>
              {SubIcon ? <SubIcon size={16} aria-hidden="true" /> : <span className="nav-sub-dot" />}
              <span>{label}</span>
            </Link>
          ))}
          <button
            className={`nav-item ${isPontoPage ? "active" : ""}`}
            onClick={() => setPontoOpen((v) => !v)}
            title={collapsed ? "Ponto" : undefined}
          >
            <Clock size={19} aria-hidden="true" />
            {!collapsed && <><span>Ponto</span><ChevronDown size={14} className={`nav-chevron ${pontoOpen ? "open" : ""}`} /></>}
          </button>
          {pontoOpen && !collapsed && pontoSub.map(({ slug, label, icon: SubIcon, href }) => (
            <Link key={slug} href={href} className={`nav-item nav-sub-item ${pontoSubSlug === slug ? "active" : ""}`} onClick={() => setMobileMenu(false)}>
              <SubIcon size={16} aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <Link href="/configuracoes" className={`nav-item ${currentSlug === "configuracoes" ? "active" : ""}`} onClick={() => setMobileMenu(false)}>
            <Settings size={19} />{!collapsed && <span>Configurações</span>}
          </Link>
          {!collapsed && <span className="version">Nova plataforma · prévia</span>}
        </div>
      </aside>

      {mobileMenu && <button className="backdrop" aria-label="Fechar menu" onClick={() => setMobileMenu(false)} />}

      <div className="top-float">
        <button className="icon-button mobile-menu-btn" onClick={() => setMobileMenu(true)} aria-label="Abrir menu"><Menu size={21} /></button>
        <div className="top-float-actions">
          <button className="icon-button notification-button" onClick={() => togglePanel("notifications")} aria-label="Notificações"><Bell size={20} /><NotificationBadge /></button>
          <button className="avatar-button" onClick={() => togglePanel("profile")} aria-label="Menu do usuário">{initials}</button>
        </div>
      </div>

      <main className="main-content">{children}</main>

      {panel && (
        <>
          <button className="panel-backdrop" aria-label="Fechar painel" onClick={() => setPanel(null)} />
          <aside className="context-drawer" aria-label={panel === "notifications" ? "Notificações" : "Perfil"}>
            <div className="drawer-heading">
              <div>
                <span>{panel === "notifications" ? "Central" : "Conta"}</span>
                <h2>{panel === "notifications" ? "Notificações" : displayName}</h2>
              </div>
              <button className="icon-button" onClick={() => setPanel(null)} aria-label="Fechar"><X size={20} /></button>
            </div>
            {panel === "notifications" ? (
              <NotificationPanel />
            ) : (
              <div className="profile-content">
                <div className="profile-card"><div className="profile-avatar">{initials}</div><strong>{displayName}</strong><span>{user.role_name ?? "Demonstração"}</span></div>
                <Link href="/configuracoes?tab=conta" onClick={() => setPanel(null)}><Users /> Minha conta</Link>
                <Link href="/usuarios" onClick={() => setPanel(null)}><ShieldCheck /> Segurança e acesso</Link>
                <Link href="/configuracoes" onClick={() => setPanel(null)}><Settings /> Preferências</Link>
                <form action={logoutAction}><button className="logout-button" type="submit">Sair da conta</button></form>
              </div>
            )}
          </aside>
        </>
      )}
    </div>
  );
}
