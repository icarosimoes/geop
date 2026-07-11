import { Settings } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Configurações" description="Preferências da plataforma." />

      <EmptyState
        icon={<Settings className="h-6 w-6" />}
        title="Configurações da plataforma em breve"
      />
    </div>
  );
}
