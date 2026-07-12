import { platformFetch } from "@/lib/api";
import { EmailSettingsForm } from "./email-settings-form";

export type EmailConfig = {
  brevo_configured: boolean;
  email_from_address: string | null;
  email_from_name: string | null;
};

export default async function SettingsPage() {
  let email: EmailConfig = { brevo_configured: false, email_from_address: null, email_from_name: null };
  try {
    email = await platformFetch<EmailConfig>("/platform/settings/email");
  } catch {
    // mantém default
  }

  return (
    <div className="space-y-6">
      <EmailSettingsForm initialConfig={email} />
    </div>
  );
}
