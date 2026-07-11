import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-brand)] text-[var(--color-brand-foreground)] hover:bg-[var(--color-brand-hover)] shadow-sm",
        secondary:
          "bg-[var(--accent)] text-[var(--accent-foreground)] hover:bg-[var(--accent)]/80",
        outline:
          "border border-[var(--border)] bg-transparent hover:bg-[var(--accent)] text-[var(--foreground)]",
        ghost:
          "bg-transparent hover:bg-[var(--accent)] text-[var(--foreground)]",
        destructive:
          "bg-[var(--danger)] text-[var(--danger-foreground)] hover:bg-[var(--danger)]/90 shadow-sm",
        success:
          "bg-[var(--success)] text-[var(--success-foreground)] hover:bg-[var(--success)]/90 shadow-sm",
        link:
          "text-[var(--color-brand)] underline-offset-4 hover:underline p-0 h-auto",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    // Slot exige exatamente 1 child. Se asChild, não renderizamos o loader.
    const content = asChild ? (
      children
    ) : (
      <>
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {children}
      </>
    );
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        {...props}
      >
        {content}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
