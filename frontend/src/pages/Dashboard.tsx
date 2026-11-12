import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CornerDownRight, PlaneTakeoff, RotateCcw, ShieldAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { Card, EmptyState, ErrorState, ReviewPill, SkeletonRows, StatePill } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/form";
import { api, type FlightFilters, type FlightRef, type StageSummary } from "@/lib/api";
import { flightName, formatDate, isoDate, stageRoute } from "@/lib/format";

/** Filters live in the URL so a link reproduces the screen. With no dates in the URL the
 *  dashboard shows today and tomorrow. */
function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters: FlightFilters = {
    date_from: params.get("date_from") ?? isoDate(0),
    date_to: params.get("date_to") ?? isoDate(1),
    airline: params.get("airline") ?? "",
    plant: params.get("plant") ?? "",
  };
  const set = (key: keyof FlightFilters, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return { filters, set, reset: () => setParams({}, { replace: true }), isDefault: params.size === 0 };
}

function StageCell({ flight, stage }: { flight: FlightRef; stage: StageSummary }) {
  if (stage.state === "NO_DATA" && stage.open_review_items === 0) {
    return <StatePill state="NO_DATA" />;
  }
  return (
    <Link
      to={stageRoute(flight, stage.status)}
      aria-label={`${flightName(flight)} ${stage.status}`}
      className="-mx-xs flex min-h-[44px] flex-wrap items-center gap-xs rounded-sm px-xs hover:bg-surface-hover"
    >
      <StatePill state={stage.state} />
      <ReviewPill state={stage.review_state} />
      {stage.blocking_review_items > 0 ? (
        <span className="inline-flex items-center gap-xxs text-xs font-semibold">
          <ShieldAlert className="size-[14px] text-status-error" strokeWidth={1.75} aria-hidden />
          {stage.blocking_review_items} blocking
        </span>
      ) : stage.open_review_items > 0 ? (
        <span className="inline-flex items-center gap-xxs text-xs">
          <AlertTriangle className="size-[14px] text-status-warning" strokeWidth={1.75} aria-hidden />
          {stage.open_review_items} to check
        </span>
      ) : null}
    </Link>
  );
}

function stageOf(stages: StageSummary[], status: "P24H" | "P06H") {
  return stages.find((s) => s.status === status)!;
}

export function DashboardPage() {
  const { filters, set, reset, isDefault } = useFilters();
  const query = useQuery({ queryKey: ["flights", filters], queryFn: () => api.flights(filters) });
  const flights = query.data ?? [];

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-md">
        <div className="flex flex-col gap-xxs">
          <h1 className="text-2xl font-semibold">Flights</h1>
          <p className="text-sm text-content-muted">
            {query.isSuccess
              ? `${flights.length} outbound ${flights.length === 1 ? "flight" : "flights"}, ` +
                `${formatDate(filters.date_from!)} to ${formatDate(filters.date_to!)}`
              : "Meal requests by flight and stage"}
          </p>
        </div>
      </header>

      <Card className="flex flex-wrap items-end gap-sm p-md">
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="f-from">From</Label>
          <Input
            id="f-from"
            type="date"
            className="w-[160px]"
            value={filters.date_from}
            onChange={(e) => set("date_from", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="f-to">To</Label>
          <Input
            id="f-to"
            type="date"
            className="w-[160px]"
            value={filters.date_to}
            onChange={(e) => set("date_to", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="f-airline">Airline</Label>
          <Input
            id="f-airline"
            className="num w-[96px] uppercase placeholder:normal-case"
            maxLength={3}
            placeholder="All"
            value={filters.airline}
            onChange={(e) => set("airline", e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
          />
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="f-plant">Plant</Label>
          <Select id="f-plant" className="w-[160px]" value={filters.plant} onChange={(e) => set("plant", e.target.value)}>
            <option value="">All plants</option>
            <option value="ICC1">ICC1 (SQ)</option>
            <option value="ICC2">ICC2 (other airlines)</option>
          </Select>
        </div>
        <Button variant="ghost" onClick={reset} disabled={isDefault}>
          <RotateCcw strokeWidth={1.75} /> Reset filters
        </Button>
      </Card>

      <Card className="overflow-hidden p-0">
        {query.isPending ? (
          <div className="p-lg">
            <SkeletonRows rows={6} />
          </div>
        ) : query.isError ? (
          <div className="p-lg">
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : flights.length === 0 ? (
          <EmptyState icon={PlaneTakeoff} title="No flights in this range">
            Flights appear here once a meal request email has been extracted for them. Widen the
            dates or clear the airline and plant filters.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Flight</th>
                  <th scope="col">Plant</th>
                  <th scope="col">P24H</th>
                  <th scope="col">P06H</th>
                </tr>
              </thead>
              <tbody>
                {flights.flatMap((f) => {
                  const rows = [
                    <tr key={`${f.airline}${f.flt_nbr}${f.actdate}`}>
                      <td className="num whitespace-nowrap">{formatDate(f.actdate)}</td>
                      <td className="num whitespace-nowrap font-semibold">{flightName(f)}</td>
                      <td>{f.plant}</td>
                      <td>
                        <StageCell flight={f} stage={stageOf(f.stages, "P24H")} />
                      </td>
                      <td>
                        <StageCell flight={f} stage={stageOf(f.stages, "P06H")} />
                      </td>
                    </tr>,
                  ];
                  const r = f.return_flight;
                  if (r) {
                    rows.push(
                      <tr key={`${r.airline}${r.flt_nbr}${r.actdate}-return`} className="bg-surface-secondary">
                        <td className="num whitespace-nowrap text-content-secondary">{formatDate(r.actdate)}</td>
                        <td className="whitespace-nowrap">
                          <span className="inline-flex items-center gap-xs pl-sm">
                            <CornerDownRight className="size-4 text-content-muted" strokeWidth={1.75} aria-hidden />
                            <span className="num font-semibold">{flightName(r)}</span>
                            <span className="text-xs text-content-muted">Return, sent with {flightName(f)}</span>
                          </span>
                        </td>
                        <td />
                        <td>
                          <StageCell flight={r} stage={stageOf(r.stages, "P24H")} />
                        </td>
                        <td>
                          <StageCell flight={r} stage={stageOf(r.stages, "P06H")} />
                        </td>
                      </tr>,
                    );
                  }
                  return rows;
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
