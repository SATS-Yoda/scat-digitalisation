import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  Clock,
  Eye,
  Info,
  Loader,
  type LucideIcon,
  Pencil,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";

import type { ReviewState, StageState } from "@/lib/api";
import { cn } from "@/lib/format";

type Tone = "info" | "success" | "warning" | "error" | "neutral";

const TONE_VAR: Record<Tone, string> = {
  info: "var(--color-info)",
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  error: "var(--color-error)",
  neutral: "var(--text-muted)",
};

/** Status as icon + text + colour. The text keeps the body colour so contrast holds in
 *  both themes; the status hue is carried by the icon, border and tint. */
export function Pill({ tone, icon: Icon, children }: { tone: Tone; icon: LucideIcon; children: ReactNode }) {
  const hue = TONE_VAR[tone];
  return (
    <span
      className="inline-flex items-center gap-xxs whitespace-nowrap rounded-full border px-xs py-[2px] text-xs font-semibold text-content-primary"
      style={{ borderColor: hue, background: `color-mix(in srgb, ${hue} 12%, transparent)` }}
    >
      <Icon className="size-[14px]" strokeWidth={1.75} style={{ color: hue }} aria-hidden />
      {children}
    </span>
  );
}

const STATE: Record<StageState, { label: string; tone: Tone; icon: LucideIcon }> = {
  NO_DATA: { label: "No data", tone: "neutral", icon: CircleDashed },
  PENDING: { label: "Pending", tone: "info", icon: Clock },
  NOT_RELEASED: { label: "Not released", tone: "neutral", icon: Ban },
  SENDING: { label: "Sending", tone: "info", icon: Loader },
  SENT: { label: "Sent", tone: "success", icon: CheckCircle2 },
  FAILED: { label: "Send failed", tone: "error", icon: XCircle },
};

export function StatePill({ state }: { state: StageState }) {
  const { label, tone, icon } = STATE[state];
  return (
    <Pill tone={tone} icon={icon}>
      {label}
    </Pill>
  );
}

export function ReviewPill({ state }: { state: ReviewState }) {
  if (state === "NOT_REVIEWED") return null;
  return state === "REVIEWED_OK" ? (
    <Pill tone="success" icon={Eye}>
      Reviewed
    </Pill>
  ) : (
    <Pill tone="info" icon={Pencil}>
      Amended
    </Pill>
  );
}

const NOTICE: Record<Exclude<Tone, "neutral">, LucideIcon> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
};

export function Notice({
  tone,
  title,
  children,
  action,
}: {
  tone: Exclude<Tone, "neutral">;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const Icon = NOTICE[tone];
  const hue = TONE_VAR[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className="flex items-start gap-sm rounded-md border p-sm text-sm"
      style={{ borderColor: hue, background: `color-mix(in srgb, ${hue} 8%, transparent)` }}
    >
      <Icon className="mt-[2px] size-4 shrink-0" strokeWidth={1.75} style={{ color: hue }} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-xxs">
        <span className="font-semibold">{title}</span>
        {children ? <div className="text-content-secondary">{children}</div> : null}
      </div>
      {action}
    </div>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section
      className={cn(
        "rounded-xl border border-edge-subtle bg-surface-primary p-lg shadow-elevation-1",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({ title, meta, actions }: { title: string; meta?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-md flex flex-wrap items-center justify-between gap-xs">
      <div className="flex flex-wrap items-baseline gap-xs">
        <h3 className="text-md font-semibold">{title}</h3>
        {meta ? <span className="text-xs text-content-muted">{meta}</span> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-xs">{actions}</div> : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-sm bg-surface-tertiary", className)} aria-hidden />;
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-xs" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-xs px-lg py-xl text-center">
      <Icon className="size-6 text-content-muted" strokeWidth={1.75} aria-hidden />
      <h4 className="text-md font-semibold">{title}</h4>
      <p className="max-w-md text-sm text-content-secondary">{children}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Notice
      tone="error"
      title="Could not load"
      action={
        onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="min-h-[44px] rounded-sm px-sm text-sm font-semibold hover:bg-surface-hover"
          >
            Retry
          </button>
        ) : undefined
      }
    >
      {error instanceof Error ? error.message : "Unknown error"}
    </Notice>
  );
}
