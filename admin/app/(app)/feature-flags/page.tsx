import { platformFetch } from "@/lib/api";
import { FeatureFlagsClient } from "./feature-flags-client";

export type FeatureFlag = {
  id: number;
  key: string;
  description: string | null;
  enabled_default: boolean;
  targeting_rules: Record<string, unknown>;
  created_at: string;
};

export default async function FeatureFlagsPage() {
  let flags: FeatureFlag[] = [];
  try {
    flags = await platformFetch<FeatureFlag[]>("/platform/feature-flags");
  } catch {
    flags = [];
  }

  return <FeatureFlagsClient initialFlags={flags} />;
}
