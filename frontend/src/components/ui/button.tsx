// shadcn/ui Button, themed to the SATS standard: hover darkens, press moves 1 px down,
// 44 px minimum target.
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/format";

const buttonVariants = cva(
  "inline-flex min-h-[44px] items-center justify-center gap-xs whitespace-nowrap rounded-sm border px-md text-sm font-semibold transition-colors active:translate-y-px disabled:pointer-events-none disabled:border-transparent disabled:bg-surface-disabled disabled:text-content-disabled [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-brand-primary text-white hover:bg-brand-primary-dark",
        secondary:
          "border-edge-default bg-surface-primary text-content-primary hover:bg-surface-hover",
        ghost: "border-transparent text-content-primary hover:bg-surface-hover",
      },
      size: { default: "", icon: "min-w-[44px] px-0" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type = "button", ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        type={asChild ? undefined : type}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
