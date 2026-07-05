import { redirect } from "next/navigation";

import { getEmployeeToken } from "@/lib/auth";

export default async function HomePage() {
  const token = await getEmployeeToken();
  if (!token) redirect("/login");
  redirect("/ponto");
}
