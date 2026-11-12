import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, CheckCircle2, Eye, FileX, Info, Lock, Mail, Send, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Notice,
  Pill,
  ReviewPill,
  SkeletonRows,
  StatePill,
} from "@/components/common";
import { SectorCard } from "@/components/SectorCard";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Label, Select, Textarea } from "@/components/ui/form";
import {
  type Amf,
  api,
  ApiError,
  type FlightRef,
  type ReviewItem,
  type SendResult,
  type StageDetail,
  type Status,
} from "@/lib/api";
import { cn, flightName, formatDate, formatDateTime, signed, stageRoute } from "@/lib/format";

const CABINS: [string, string][] = [
  ["P", "First"],
  ["J", "Business"],
  ["YD", "Premium Economy"],
  ["Y", "Economy"],
];

function EmailPanel({ emailId }: { emailId: number | null }) {
  const query = useQuery({
    queryKey: ["email", emailId],
    queryFn: () => api.email(emailId!),
    enabled: emailId !== null,
  });
  return (
    <Card className="xl:sticky xl:top-lg xl:max-h-[calc(100vh-48px)] xl:overflow-y-auto">
      <CardHeader title="Source email" />
      {emailId === null ? (
        <EmptyState icon={Mail} title="No source email">
          This version was not created from an email, so there is nothing to compare against.
        </EmptyState>
      ) : query.isPending ? (
        <SkeletonRows rows={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : (
        <div className="flex flex-col gap-sm text-sm">
          <dl className="grid grid-cols-[auto_1fr] gap-x-sm gap-y-xxs">
            <dt className="text-content-muted">Subject</dt>
            <dd className="num break-words">{query.data.subject}</dd>
            <dt className="text-content-muted">From</dt>
            <dd className="break-words">{query.data.sender}</dd>
            <dt className="text-content-muted">Received</dt>
            <dd className="num">{formatDateTime(query.data.received_at)}</dd>
            {query.data.confidence !== null ? (
              <>
                <dt className="text-content-muted">Extraction confidence</dt>
                <dd className="num">{Math.round(Number(query.data.confidence) * 100)}% (model estimate)</dd>
              </>
            ) : null}
          </dl>
          <pre className="num overflow-x-auto whitespace-pre-wrap rounded-md border bg-surface-secondary p-sm text-xs leading-relaxed">
            {query.data.body_preview ?? "The email has no text preview"}
          </pre>
        </div>
      )}
    </Card>
  );
}

function ResolveDialog({ item, onDone, onClose }: { item: ReviewItem; onDone: () => void; onClose: () => void }) {
  const [type, setType] = useState("AMENDED");
  const [remarks, setRemarks] = useState("");
  const needsRemarks = type === "ACCEPTED" && remarks.trim() === "";
  const resolve = useMutation({
    mutationFn: () => api.resolveReviewItem(item.review_item_id, type, remarks.trim() || null),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title="Resolve review item" description={item.message}>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="resolve-type">Resolution</Label>
          <Select id="resolve-type" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="AMENDED">Amended: the data was corrected</option>
            <option value="ACCEPTED">Accepted: the data is right as extracted</option>
          </Select>
        </div>
        <div className="flex flex-col gap-xxs">
          <Label htmlFor="resolve-remarks">Remarks{type === "ACCEPTED" ? " (required)" : ""}</Label>
          <Textarea
            id="resolve-remarks"
            value={remarks}
            aria-describedby="resolve-remarks-hint"
            onChange={(e) => setRemarks(e.target.value)}
          />
          <p id="resolve-remarks-hint" className="text-xs text-content-muted">
            {type === "ACCEPTED"
              ? "State why the extracted data is correct, for example who confirmed it."
              : "Optional note on what was corrected."}
          </p>
        </div>
        {resolve.isError ? (
          <Notice tone="error" title="Not resolved">
            {resolve.error.message}
          </Notice>
        ) : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button onClick={() => resolve.mutate()} disabled={needsRemarks || resolve.isPending}>
            {resolve.isPending ? "Resolving" : "Resolve item"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReviewItems({ items, onChanged }: { items: ReviewItem[]; onChanged: () => void }) {
  const [resolving, setResolving] = useState<ReviewItem | null>(null);
  return (
    <Card>
      <CardHeader title="Review items" meta={items.length ? `${items.length} open` : undefined} />
      {items.length === 0 ? (
        <p className="flex items-center gap-xs text-sm text-content-secondary">
          <CheckCircle2 className="size-4 text-status-success" strokeWidth={1.75} aria-hidden />
          No open review items for this stage
        </p>
      ) : (
        <ul className="flex flex-col gap-xs">
          {items.map((item) => (
            <li key={item.review_item_id} className="flex flex-wrap items-start gap-sm rounded-md border p-sm">
              <div className="flex min-w-0 flex-1 flex-col gap-xxs text-sm">
                <div className="flex flex-wrap items-center gap-xs">
                  {item.blocks_release ? (
                    <Pill tone="error" icon={ShieldAlert}>
                      Blocks sending
                    </Pill>
                  ) : (
                    <Pill tone="warning" icon={Info}>
                      To check
                    </Pill>
                  )}
                  <span className="num text-xs text-content-muted">{item.error_code}</span>
                  {item.sector_nbr ? <span className="text-xs text-content-muted">Sector {item.sector_nbr}</span> : null}
                </div>
                <span>{item.message}</span>
                {item.text_snippet ? (
                  <code className="w-fit rounded-xs bg-surface-tertiary px-xs py-[2px] text-xs">{item.text_snippet}</code>
                ) : null}
              </div>
              <Button variant="secondary" onClick={() => setResolving(item)}>
                Resolve
              </Button>
            </li>
          ))}
        </ul>
      )}
      {resolving ? <ResolveDialog item={resolving} onDone={onChanged} onClose={() => setResolving(null)} /> : null}
    </Card>
  );
}

function AmfPanel({ flight }: { flight: FlightRef }) {
  const query = useQuery({ queryKey: ["amf", flight], queryFn: () => api.amf(flight) });
  return (
    <Card>
      <CardHeader title="Additional meal form" meta="Read-only, compares P06H with P24H" />
      {query.isPending ? (
        <SkeletonRows rows={3} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : query.data.length === 0 ? (
        <EmptyState icon={FileX} title="No additional meal form yet">
          The form is generated once both P24H and P06H data exist for the flight.
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-md">
          {query.data.map((form) => (
            <AmfTable key={form.amf_id} form={form} showSector={query.data.length > 1} />
          ))}
        </div>
      )}
    </Card>
  );
}

function AmfTable({ form, showSector }: { form: Amf; showSector: boolean }) {
  const pax = (cabin: string) =>
    form.lines.filter((l) => l.line_type === "PAX" && l.cabin === cabin).reduce((n, l) => n + (l.pax_p06h ?? 0), 0);
  const hasCabin = (cabin: string) => form.lines.some((l) => l.cabin === cabin);
  const spml = form.lines.filter((l) => l.line_type === "SPML");
  const mealTypes = [...new Set(spml.map((l) => l.meal_type ?? ""))];
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <caption className="pb-xs text-left text-xs text-content-muted">
          {showSector ? `Sector ${form.sector_nbr}, version` : "Version"} {form.amf_version}, generated{" "}
          {formatDateTime(form.generated_at)}
        </caption>
        <thead>
          <tr>
            <th scope="col">Meal type</th>
            {CABINS.map(([code, name]) => (
              <th key={code} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row" className="!bg-transparent">
              P06H pax
            </th>
            {CABINS.map(([code]) => (
              <td key={code} className="num">
                {hasCabin(code) && form.lines.some((l) => l.line_type === "PAX" && l.cabin === code)
                  ? `${pax(code)} pax`
                  : ""}
              </td>
            ))}
          </tr>
          {mealTypes.length === 0 ? (
            <tr>
              <td colSpan={5} className="text-content-muted">
                No special meal changes between P24H and P06H
              </td>
            </tr>
          ) : (
            mealTypes.map((mealType) => (
              <tr key={mealType}>
                <th scope="row" className="num !bg-transparent">
                  {mealType || "Any"}
                </th>
                {CABINS.map(([code]) => (
                  <td key={code} className="num">
                    {spml
                      .filter((l) => (l.meal_type ?? "") === mealType && l.cabin === code)
                      .map((l) => (
                        <div key={l.amf_line_id}>
                          {signed(l.delta_qty!)} {l.spml_id}
                          {l.source_class !== code ? ` (${l.source_class})` : ""}
                        </div>
                      ))}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function SendDialog({
  stage,
  onClose,
  onResult,
}: {
  stage: StageDetail;
  onClose: () => void;
  onResult: (result: SendResult) => void;
}) {
  const send = useMutation({
    mutationFn: () => api.sendToSap(stage, stage.status),
    onSuccess: (result) => {
      onResult(result);
      onClose();
    },
  });
  const name = `${flightName(stage)}, ${formatDate(stage.actdate)}, ${stage.status}`;
  return (
    <Dialog open onOpenChange={(open) => !open && !send.isPending && onClose()}>
      <DialogContent title={`Send ${name} to SAP`} description="One I033 file and one I034 file are uploaded to SAP.">
        <ul className="flex list-disc flex-col gap-xxs pl-md text-sm">
          <li>Once sent, this stage is locked. Later corrections must be made in SAP.</li>
          {stage.return_flight ? (
            <li>
              Return flight {flightName(stage.return_flight)} on {formatDate(stage.return_flight.actdate)} is sent in
              the same files.
            </li>
          ) : null}
        </ul>
        {stage.return_flight_missing && stage.return_flight ? (
          <Notice tone="warning" title="Return flight has no data">
            {flightName(stage.return_flight)} on {formatDate(stage.return_flight.actdate)} has no {stage.status} data
            and will not be included. It cannot be added after sending.
          </Notice>
        ) : null}
        {send.isError ? (
          <Notice tone="error" title="Not sent">
            {send.error.message}
          </Notice>
        ) : null}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={send.isPending}>
            Cancel
          </Button>
          <Button onClick={() => send.mutate()} disabled={send.isPending}>
            <Send strokeWidth={1.75} /> {send.isPending ? "Sending" : "Send to SAP"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ConfirmNotReleased({ stage, onClose, onDone }: { stage: StageDetail; onClose: () => void; onDone: () => void }) {
  const mutation = useMutation({
    mutationFn: () => api.markNotReleased(stage, stage.status),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={`Do not release ${flightName(stage)}, ${formatDate(stage.actdate)}, ${stage.status}`}
        description="The stage is marked as not released and nothing is sent to SAP. It can still be sent later."
      >
        {mutation.isError ? (
          <Notice tone="error" title="Not recorded">
            {mutation.error.message}
          </Notice>
        ) : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            Mark as not released
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StageTabs({ flight, status }: { flight: FlightRef; status: Status }) {
  return (
    <nav aria-label="Stage" className="flex gap-xxs rounded-md border bg-surface-primary p-xxs">
      {(["P24H", "P06H"] as const).map((s) => (
        <Link
          key={s}
          to={stageRoute(flight, s)}
          aria-current={s === status ? "page" : undefined}
          className={cn(
            "num flex min-h-[44px] items-center rounded-sm px-md text-sm font-semibold hover:bg-surface-hover",
            s === status && "bg-surface-hover",
          )}
        >
          {s}
        </Link>
      ))}
    </nav>
  );
}

export function StagePage() {
  const params = useParams();
  const flight: FlightRef = { airline: params.airline!, flt_nbr: params.fltNbr!, actdate: params.actdate! };
  const status = params.status as Status;
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<"send" | "not-released" | null>(null);
  const [sendResult, setSendResult] = useState<SendResult | null>(null);

  const query = useQuery({ queryKey: ["stage", flight, status], queryFn: () => api.stage(flight, status) });

  // One thing changed on this flight: refresh its stages, its AMF and the dashboard list.
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["stage"] });
    queryClient.invalidateQueries({ queryKey: ["amf", flight] });
    queryClient.invalidateQueries({ queryKey: ["flights"] });
  };

  const review = useMutation({ mutationFn: () => api.markReviewed(flight, status), onSuccess: refresh });

  const heading = (
    <header className="flex flex-col gap-sm">
      <Link to="/" className="flex min-h-[44px] w-fit items-center gap-xs text-sm font-medium link">
        <ArrowLeft className="size-4" strokeWidth={1.75} aria-hidden /> Flights
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-md">
        <div className="flex flex-wrap items-center gap-sm">
          <h1 className="num text-2xl font-semibold">{flightName(flight)}</h1>
          <span className="num text-md text-content-secondary">{formatDate(flight.actdate)}</span>
          {query.data ? (
            <>
              <StatePill state={query.data.state} />
              <ReviewPill state={query.data.review_state} />
            </>
          ) : null}
        </div>
        <StageTabs flight={flight} status={status} />
      </div>
    </header>
  );

  if (query.isPending) {
    return (
      <>
        {heading}
        <Card>
          <SkeletonRows rows={8} />
        </Card>
      </>
    );
  }
  if (query.isError) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <>
        {heading}
        <Card>
          {missing ? (
            <EmptyState icon={FileX} title={`No ${status} data yet`}>
              Nothing has been extracted for {flightName(flight)} on {formatDate(flight.actdate)} at {status}. It
              appears here once the airline's email for this stage has been processed.
            </EmptyState>
          ) : (
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          )}
        </Card>
      </>
    );
  }

  const stage = query.data;
  const blocking = stage.review_items.filter((i) => i.blocks_release).length;
  const emailId = stage.sectors.map((s) => s.i033.source_email_id).find((id) => id !== null) ?? null;
  const isReturn = stage.return_of !== null;
  const failed = stage.state === "FAILED";

  return (
    <>
      {heading}

      <Card className="flex flex-wrap items-center justify-between gap-md p-md">
        <div className="flex min-w-0 flex-1 flex-col gap-xxs text-sm">
          {stage.state === "SENT" ? (
            <span className="flex items-center gap-xs font-semibold">
              <Lock className="size-4" strokeWidth={1.75} aria-hidden />
              Sent to SAP{stage.send?.sent_at ? ` on ${formatDateTime(stage.send.sent_at)}` : ""}. This stage is locked;
              make later corrections in SAP.
            </span>
          ) : isReturn ? (
            <span>
              Return flight. It is sent with{" "}
              <Link className="num font-semibold link" to={stageRoute(stage.return_of!, status)}>
                {flightName(stage.return_of!)} on {formatDate(stage.return_of!.actdate)}
              </Link>{" "}
              and has no send of its own.
            </span>
          ) : blocking > 0 ? (
            <span>
              {blocking} review {blocking === 1 ? "item blocks" : "items block"} sending. Resolve{" "}
              {blocking === 1 ? "it" : "them"} below first.
            </span>
          ) : stage.return_flight ? (
            <span>
              Sent together with return flight{" "}
              <Link
                className="num font-semibold link"
                to={stageRoute(stage.return_flight, status)}
              >
                {flightName(stage.return_flight)} on {formatDate(stage.return_flight.actdate)}
              </Link>
              {stage.return_flight_missing ? ", which has no data for this stage yet" : ""}.
            </span>
          ) : (
            <span className="text-content-secondary">Check the data against the source email, then send.</span>
          )}
        </div>
        {stage.locked ? null : (
          <div className="flex flex-wrap gap-xs">
            <Button
              variant="secondary"
              onClick={() => review.mutate()}
              disabled={stage.review_state !== "NOT_REVIEWED" || review.isPending}
            >
              <Eye strokeWidth={1.75} /> Mark reviewed
            </Button>
            {isReturn ? null : (
              <>
                <Button
                  variant="secondary"
                  onClick={() => setDialog("not-released")}
                  disabled={stage.state === "NOT_RELEASED"}
                >
                  <Ban strokeWidth={1.75} /> Do not release
                </Button>
                <Button onClick={() => setDialog("send")} disabled={blocking > 0}>
                  <Send strokeWidth={1.75} /> {failed ? "Retry send" : "Send to SAP"}
                </Button>
              </>
            )}
          </div>
        )}
      </Card>

      {review.isError ? (
        <Notice tone="error" title="Not marked as reviewed">
          {review.error.message}
        </Notice>
      ) : null}
      {failed && stage.send?.failure_reason ? (
        <Notice tone="error" title="The last send failed">
          <p>{stage.send.failure_reason}</p>
          <p>Nothing is locked. Retry the send when ready.</p>
        </Notice>
      ) : null}
      {sendResult?.state === "SENT" ? (
        <Notice tone="success" title="Sent to SAP">
          {sendResult.warnings.length ? sendResult.warnings.join(" ") : "Both files were uploaded."}
        </Notice>
      ) : null}

      <div className="grid items-start gap-md xl:grid-cols-[minmax(320px,2fr)_3fr]">
        <EmailPanel emailId={emailId} />
        <div className="flex min-w-0 flex-col gap-md">
          {stage.sectors.map((sector) => (
            <SectorCard
              key={sector.sector_nbr}
              flight={flight}
              status={status}
              sector={sector}
              locked={stage.locked}
              showSectorNumber={stage.sectors.length > 1}
              onSaved={refresh}
            />
          ))}
          <ReviewItems items={stage.review_items} onChanged={refresh} />
          {status === "P06H" ? <AmfPanel flight={flight} /> : null}
        </div>
      </div>

      {dialog === "send" ? (
        <SendDialog
          stage={stage}
          onClose={() => setDialog(null)}
          onResult={(result) => {
            setSendResult(result);
            refresh();
          }}
        />
      ) : null}
      {dialog === "not-released" ? (
        <ConfirmNotReleased stage={stage} onClose={() => setDialog(null)} onDone={refresh} />
      ) : null}
    </>
  );
}
