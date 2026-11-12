// shadcn/ui Input, Label and Textarea, plus a styled native select.
import * as LabelPrimitive from "@radix-ui/react-label";
import * as React from "react";

import { cn } from "@/lib/format";

const field =
  "w-full rounded-sm border border-edge-default bg-surface-primary px-sm text-sm text-content-primary placeholder:text-content-muted disabled:bg-surface-disabled disabled:text-content-disabled aria-[invalid=true]:border-edge-error";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(field, "min-h-[44px]", className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(field, "min-h-[88px] py-xs", className)} {...props} />
));
Textarea.displayName = "Textarea";

// Native <select>: keyboard and screen-reader behaviour for free, no JavaScript needed.
export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, ...props }, ref) => (
  <select ref={ref} className={cn(field, "min-h-[44px]", className)} {...props} />
));
Select.displayName = "Select";

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-xs font-semibold text-content-secondary", className)}
    {...props}
  />
));
Label.displayName = "Label";
