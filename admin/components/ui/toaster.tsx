"use client";

import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      position="top-right"
      theme="light"
      toastOptions={{
        classNames: {
          toast:
            "border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] shadow-lg",
          description: "text-[var(--muted-foreground)]",
          actionButton: "bg-[var(--color-brand)] text-[var(--color-brand-foreground)]",
          cancelButton: "bg-[var(--muted)] text-[var(--muted-foreground)]",
        },
      }}
    />
  );
}

export { toast } from "sonner";
