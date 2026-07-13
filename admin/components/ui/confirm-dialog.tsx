"use client";

import { useState } from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface ConfirmDialogState {
  title: string;
  description?: string;
  confirmLabel?: string;
  variant?: ButtonProps["variant"];
  onConfirm: () => void | Promise<void>;
}

export function ConfirmDialog({
  state,
  onOpenChange,
}: {
  state: ConfirmDialogState | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    if (!state) return;
    setLoading(true);
    try {
      await state.onConfirm();
      onOpenChange(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={!!state} onOpenChange={(open) => !loading && onOpenChange(open)}>
      <DialogContent className="max-w-sm">
        {state && (
          <>
            <DialogHeader>
              <DialogTitle>{state.title}</DialogTitle>
              {state.description && <DialogDescription>{state.description}</DialogDescription>}
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
                Cancelar
              </Button>
              <Button variant={state.variant ?? "destructive"} loading={loading} onClick={handleConfirm}>
                {state.confirmLabel ?? "Confirmar"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
