import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { platformFetch } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

type AuditLog = {
  id: number;
  operator_email: string;
  action: string;
  entity_type: string;
  entity_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

export default async function AuditPage() {
  let logs: AuditLog[] = [];
  try {
    logs = await platformFetch<AuditLog[]>("/platform/audit");
  } catch {
    logs = [];
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Auditoria" description="Ações administrativas na plataforma." />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Data</TableHead>
            <TableHead>Operador</TableHead>
            <TableHead>Ação</TableHead>
            <TableHead>Entidade</TableHead>
            <TableHead>Detalhes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.length === 0 && <TableEmpty colSpan={5}>Nenhum registro de auditoria.</TableEmpty>}
          {logs.map((log) => (
            <TableRow key={log.id}>
              <TableCell className="text-xs text-[var(--muted-foreground)] whitespace-nowrap">
                {fmtDate(log.created_at)}
              </TableCell>
              <TableCell>{log.operator_email}</TableCell>
              <TableCell>
                <Badge variant="brand">{log.action}</Badge>
              </TableCell>
              <TableCell className="text-xs text-[var(--muted-foreground)]">
                {log.entity_type}
                {log.entity_id ? ` #${log.entity_id}` : ""}
              </TableCell>
              <TableCell className="text-xs text-[var(--muted-foreground)] max-w-xs truncate">
                {log.details ? JSON.stringify(log.details) : "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
