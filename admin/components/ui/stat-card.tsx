import * as React from "react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ReactNode;
  trend?: { value: string; positive: boolean };
  className?: string;
}

export function StatCard({ title, value, hint, icon, trend, className }: StatCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm transition-shadow hover:shadow-md",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-[var(--muted-foreground)]">{title}</span>
        {icon && <div className="text-[var(--muted-foreground)]">{icon}</div>}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight">{value}</span>
        {trend && (
          <span
            className={cn(
              "text-xs font-medium",
              trend.positive ? "text-[var(--success)]" : "text-[var(--danger)]",
            )}
          >
            {trend.positive ? "↑" : "↓"} {trend.value}
          </span>
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-[var(--muted-foreground)]">{hint}</p>}
    </div>
  );
}
