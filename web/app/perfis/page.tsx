import { redirect } from "next/navigation";

export default function PerfisPage() {
  redirect("/configuracoes?tab=perfis");
}
