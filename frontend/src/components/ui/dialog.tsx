// shadcn/ui Dialog on Radix: focus trap, Escape to close and labelling come from Radix.
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/format";

export const Dialog = DialogPrimitive.Root;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
}: {
  className?: string;
  children: React.ReactNode;
  title: string;
  description?: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-neutral-900/50" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100vw-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col gap-md overflow-y-auto rounded-xl border bg-surface-primary p-lg shadow-elevation-overlay",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-md">
          <div className="flex flex-col gap-xxs">
            <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="text-sm text-content-secondary">
                {description}
              </DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close
            aria-label="Close"
            className="-mr-xs -mt-xs inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-sm text-content-secondary hover:bg-surface-hover"
          >
            <X className="size-4" strokeWidth={1.75} />
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogFooter({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap justify-end gap-xs">{children}</div>;
}
