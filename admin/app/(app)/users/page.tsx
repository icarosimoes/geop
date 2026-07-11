import { platformFetch } from "@/lib/api";
import { UsersClient } from "./users-client";

export type PlatformUserRole = "super_admin" | "support" | "billing" | "read_only";

export type PlatformUser = {
  id: number;
  name: string;
  email: string;
  role: PlatformUserRole;
  active: boolean;
  last_login_at: string | null;
  created_at: string;
};

export default async function UsersPage() {
  let users: PlatformUser[] = [];
  try {
    users = await platformFetch<PlatformUser[]>("/platform/users");
  } catch {
    users = [];
  }

  return <UsersClient initialUsers={users} />;
}
