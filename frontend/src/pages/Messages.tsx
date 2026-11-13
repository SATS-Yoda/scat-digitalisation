import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Inbox,
  Loader,
  type LucideIcon,
  Mail,
  RotateCcw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { Card, EmptyState, ErrorState, Pill, SkeletonRows } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/form";
import { api, type EmailSummary, type PipelineStatus } from "@/lib/api";
import { flightName, formatDate, formatDateTime, stageRoute } from "@/lib/format";

type Tone = "info" | "success" | "warning" | "error" | "neutral";

const STATUSES: Record<PipelineStatus, { label: string; tone: Tone; icon: LucideIcon }> = {
  RECEIVED: { label: "Received", tone: "info", icon: Inbox },
  PROCESSING: { label: "Processing", tone: "info", icon: Loader },
  PROCESSED_OK: { label: "Processed OK", tone: "success", icon: CheckCircle2 },
  PROCESSED_PARTIAL: { label: "Processed partially", tone: "warning", icon: AlertTriangle },
  PROCESSED_FAILED: { label: "Processing failed", tone: "error", icon: XCircle },
  REJECTED: { label: "Rejected", tone: "neutral", icon: Ban },
};

/** Filters live in the URL so a link reproduces the screen. */
function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters = { status: params.get("status") ?? "", airline: params.get("airline") ?? "" };
  const set = (key: keyof typeof filters, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return { filters, set, reset: () => setParams({}, { replace: true }), isDefault: params.size === 0 };
}

function EmailRow({ email }: { email: EmailSummary }) {
  const { label, tone, icon } = STATUSES[email.pipeline_status];
  return (
    <tr>
      <td className="num align-top">{formatDateTime(email.received_at)}</td>
      <td className="min-w-0 align-top">
        {/* overflow-wrap:anywhere (unlike break-words) also lets long addresses shrink the column. */}
        <div className="font-semibold [overflow-wrap:anywhere]">{email.subject || "(no subject)"}</div>
        <div className="text-xs text-content-muted [overflow-wrap:anywhere]">
          {email.sender || "unknown sender"}
          {email.airline ? <span className="num"> · {email.airline}</span> : null}
          {email.detected_status ? <span className="num"> · {email.detected_status}</span> : null}
        </div>
      </td>
      <td className="align-top">
        <Pill tone={tone} icon={icon}>
          {label}
        </Pill>
        {email.rejection_reason ? (
          <div className="mt-xxs max-w-[28ch] text-xs text-content-secondary [overflow-wrap:anywhere]">
            {email.rejection_reason}
          </div>
        ) : null}
      </td>
      <td className="align-top">
        {email.flights.length ? (
          <ul className="flex flex-col gap-xxs">
            {email.flights.map((f) => (
              <li key={`${f.airline}${f.flt_nbr}${f.actdate}${f.status}`}>
                <Link className="num text-sm font-semibold link [overflow-wrap:anywhere]" to={stageRoute(f, f.status)}>
                  {flightName(f)}, {formatDate(f.actdate)}, {f.status}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-sm text-content-muted">No flight yet</span>
        )}
        {email.blocking_review_items > 0 ? (
          <div className="mt-xxs inline-flex items-center gap-xxs text-xs font-semibold">
            <ShieldAlert className="size-[14px] text-status-error" strokeWidth={1.75} aria-hidden />
            {email.blocking_review_items} blocking
          </div>
        ) : email.open_review_items > 0 ? (
          <div className="mt-xxs inline-flex items-center gap-xxs text-xs">
            <AlertTriangle className="size-[14px] text-status-warning" strokeWidth={1.75} aria-hidden />
            {email.open_review_items} to check
          </div>
        ) : null}
      </td>
    </tr>
  );
}

export function MessagesPage() {
  const { filters, set, reset, isDefault } = useFilters();
  const query = useQuery({ queryKey: ["emails", filters], queryFn: () => api.emails(filters) });
  const emails = query.data ?? [];

  return (
    <>
      <header className="flex flex-col gap-xxs">
        <h1 className="text-2xl font-semibold">Messages</h1>
        <p className="text-sm text-content-muted">
          {query.isSuccess
            ? `${emails.length} ${emails.length === 1 ? "email" : "emails"}, newest first`
            : "Every email received, how far it got, and the flights it produced"}
        </p>
      </header>

      <Card className="flex flex-wrap items-end gap-sm p-md">
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="m-status">Status</Label>
          <Select id="m-status" className="w-[220px]" value={filters.status} onChange={(e) => set("status", e.target.value)}>
            <option value="">All statuses</option>
            {Object.entries(STATUSES).map(([code, { label }]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="m-airline">Airline</Label>
          <Input
            id="m-airline"
            className="num w-[96px] uppercase placeholder:normal-case"
            maxLength={3}
            placeholder="All"
            value={filters.airline}
            onChange={(e) => set("airline", e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
          />
        </div>
        <Button variant="ghost" onClick={reset} disabled={isDefault}>
          <RotateCcw strokeWidth={1.75} /> Reset filters
        </Button>
      </Card>

      <Card className="overflow-hidden p-0">
        {query.isPending ? (
          <div className="p-lg">
            <SkeletonRows rows={8} />
          </div>
        ) : query.isError ? (
          <div className="p-lg">
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : emails.length === 0 ? (
          <EmptyState icon={Mail} title="No emails match">
            Emails appear here as soon as they are received, including rejected and failed ones. Clear the filters
            to see everything.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Received</th>
                  <th scope="col">Message</th>
                  <th scope="col">Status</th>
                  <th scope="col">Flights</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((e) => (
                  <EmailRow key={e.email_id} email={e} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
