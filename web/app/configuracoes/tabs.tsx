"use client";

import Link from "next/link";
import { useState } from "react";
import { Clock, Landmark, Plug, Shield, ShieldCheck, User } from "lucide-react";
import type { TenantUser } from "@/lib/api";
import { CompanySettingsSection, BrevoSettingsSection, EvolutionSettingsSection, TimeclockSettingsSection, ProfileForm } from "@/components/settings-sections";
import { OperationalModule } from "@/components/operational-module";
import { RoleManager } from "@/components/role-manager";
import type { ModuleDefinition } from "@/lib/module-definitions";

const tabs = [
  { key: "estabelecimento", label: "Estabelecimento", icon: Landmark },
  { key: "usuarios", label: "Usuários", icon: ShieldCheck },
  { key: "perfis", label: "Perfis de acesso", icon: Shield },
  { key: "ponto", label: "Ponto", icon: Clock },
  { key: "integracoes", label: "Integrações", icon: Plug },
  { key: "conta", label: "Minha conta", icon: User },
] as const;

type RoleItem = {
  id: number;
  code: string;
  name: string;
  permission_codes: string[];
  user_count: number;
  updated_at?: string;
};
type PermissionItem = { id: number; code: string; name: string; module: string };
type PermissionGroup = { module: string; permissions: PermissionItem[] };

export function SettingsTabs({
  activeTab,
  user,
  usersDefinition,
  roles,
  permissionGroups,
}: {
  activeTab: string;
  user: TenantUser;
  usersDefinition?: ModuleDefinition;
  roles?: RoleItem[];
  permissionGroups?: PermissionGroup[];
}) {
  const [toast, setToast] = useState("");

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }

  return (
    <>
      <nav style={{
        display: "flex", gap: "var(--sp-1)", padding: "0 var(--sp-5)",
        borderBottom: "1px solid var(--field-border)", marginBottom: "var(--sp-4)",
      }}>
        {tabs.map(({ key, label, icon: Icon }) => (
          <Link
            key={key}
            href={`/configuracoes?tab=${key}`}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "var(--sp-3) var(--sp-4)", fontSize: "var(--font-base)",
              fontWeight: activeTab === key ? 600 : 400,
              color: activeTab === key ? "var(--blue)" : "var(--label)",
              borderBottom: activeTab === key ? "2px solid var(--blue)" : "2px solid transparent",
              textDecoration: "none", transition: "color var(--transition)",
            }}
          >
            <Icon size={16} /> {label}
          </Link>
        ))}
      </nav>

      <section style={activeTab === "usuarios" || activeTab === "perfis" ? undefined : { padding: "0 var(--sp-5)" }}>
        {activeTab === "estabelecimento" && <CompanySettingsSection />}
        {activeTab === "usuarios" && usersDefinition && (
          <OperationalModule
            definition={usersDefinition}
            user={user}
            basePath="/configuracoes"
            extraParams={{ tab: "usuarios" }}
          />
        )}
        {activeTab === "perfis" && roles && permissionGroups && (
          <RoleManager roles={roles} permissionGroups={permissionGroups} user={user} />
        )}
        {activeTab === "ponto" && <TimeclockSettingsSection />}
        {activeTab === "integracoes" && (
          <div className="settings-form">
            <BrevoSettingsSection />
            <EvolutionSettingsSection />
          </div>
        )}
        {activeTab === "conta" && <ProfileForm user={user} onSaved={showToast} />}
      </section>

      {toast && <div className="module-toast" role="status">{toast}</div>}
    </>
  );
}
