import { useQuery } from "@tanstack/react-query";
import {
  Ban,
  CheckCircle2,
  Eye,
  History,
  Inbox,
  Loader,
  type LucideIcon,
  Pencil,
  RotateCcw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { Card, EmptyState, ErrorState, Pill, SkeletonRows } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/form";
import { api, type AuditAction, type AuditEvent } from "@/lib/api";
import { flightName, formatDate, formatDateTime, stageRoute } from "@/lib/format";

type Tone = "info" | "success" | "warning" | "error" | "neutral";

const ACTIONS: Record<AuditAction, { label: string; tone: Tone; icon: LucideIcon }> = {
  EXTRACTED: { label: "Extracted from email", tone: "neutral", icon: Inbox },
  EDITED: { label: "Edited", tone: "info", icon: Pencil },
  REVIEWED_OK: { label: "Reviewed OK", tone: "success", icon: Eye },
  REVIEW_ITEM_RESOLVED: { label: "Review item resolved", tone: "success", icon: ShieldCheck },
  NOT_RELEASED: { label: "Not released", tone: "neutral", icon: Ban },
  SENDING: { label: "Send started", tone: "info", icon: Loader },
  SENT: { label: "Sent to SAP", tone: "success", icon: CheckCircle2 },
  FAILED: { label: "Send failed", tone: "error", icon: XCircle },
};

/** Filters live in the URL so a link reproduces the screen. The server returns the latest
 *  200 events; the action filter narrows what was loaded. */
function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters = {
    date_from: params.get("date_from") ?? "",
    date_to: params.get("date_to") ?? "",
    airline: params.get("airline") ?? "",
    action: params.get("action") ?? "",
  };
  const set = (key: keyof typeof filters, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return { filters, set, reset: () => setParams({}, { replace: true }), isDefault: params.size === 0 };
}

function EventRow({ event }: { event: AuditEvent }) {
  const { label, tone, icon } = ACTIONS[event.action];
  return (
    <tr>
      <td className="num whitespace-nowrap">{formatDateTime(event.at)}</td>
      <td className="num whitespace-nowrap">{event.actor}</td>
      <td>
        <Pill tone={tone} icon={icon}>
          {label}
        </Pill>
      </td>
      <td className="num whitespace-nowrap">
        {event.status ? (
          <Link className="font-semibold link" to={stageRoute(event, event.status)}>
            {flightName(event)}, {formatDate(event.actdate)}, {event.status}
          </Link>
        ) : (
          <>
            {flightName(event)}, {formatDate(event.actdate)}
          </>
        )}
        {event.sector_nbr ? <span className="text-content-muted">, sector {event.sector_nbr}</span> : null}
      </td>
      <td className="break-words text-sm text-content-secondary">{event.detail}</td>
    </tr>
  );
}

export function AuditPage() {
  const { filters, set, reset, isDefault } = useFilters();
  const { action, ...serverFilters } = filters;
  const query = useQuery({ queryKey: ["audit", serverFilters], queryFn: () => api.audit(serverFilters) });
  const events = (query.data ?? []).filter((e) => !action || e.action === action);

  return (
    <>
      <header className="flex flex-col gap-xxs">
        <h1 className="text-2xl font-semibold">Audit trail</h1>
        <p className="text-sm text-content-muted">
          {query.isSuccess
            ? `${events.length} ${events.length === 1 ? "event" : "events"}, newest first, for flights of your plants`
            : "Who extracted, edited, reviewed and sent what"}
        </p>
      </header>

      <Card className="flex flex-wrap items-end gap-sm p-md">
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="a-from">Flight date from</Label>
          <Input
            id="a-from"
            type="date"
            className="w-[160px]"
            value={filters.date_from}
            onChange={(e) => set("date_from", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="a-to">Flight date to</Label>
          <Input
            id="a-to"
            type="date"
            className="w-[160px]"
            value={filters.date_to}
            onChange={(e) => set("date_to", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="a-airline">Airline</Label>
          <Input
            id="a-airline"
            className="num w-[96px] uppercase placeholder:normal-case"
            maxLength={3}
            placeholder="All"
            value={filters.airline}
            onChange={(e) => set("airline", e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
          />
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="a-action">Action</Label>
          <Select id="a-action" className="w-[220px]" value={action} onChange={(e) => set("action", e.target.value)}>
            <option value="">All actions</option>
            {Object.entries(ACTIONS).map(([code, { label }]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </Select>
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
        ) : events.length === 0 ? (
          <EmptyState icon={History} title="No events match">
            Events appear here as emails are extracted and users edit, review and send. Clear the filters or widen
            the dates.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">User</th>
                  <th scope="col">Action</th>
                  <th scope="col">Flight</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e, i) => (
                  <EventRow key={`${e.at}-${e.action}-${e.airline}${e.flt_nbr}-${i}`} event={e} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
