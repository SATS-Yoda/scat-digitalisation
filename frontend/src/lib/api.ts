// Types mirror backend/app/schemas.py. Keep the two in step when either changes.

export type Status = "P24H" | "P06H";
export type Plant = "ICC1" | "ICC2";
export type StageState = "NO_DATA" | "PENDING" | "NOT_RELEASED" | "SENDING" | "SENT" | "FAILED";
export type ReviewState = "NOT_REVIEWED" | "REVIEWED_OK" | "REVIEWED_AMENDED";

export interface FlightRef {
  airline: string;
  flt_nbr: string;
  actdate: string;
}

export interface StageSummary {
  status: Status;
  state: StageState;
  sectors: number;
  review_state: ReviewState;
  open_review_items: number;
  blocking_review_items: number;
  sent_at: string | null;
  updated_at: string | null;
  send_error: string | null;
}

export interface FlightSummary extends FlightRef {
  plant: Plant;
  stages: StageSummary[];
  return_flight: (FlightRef & { stages: StageSummary[] }) | null;
}

export interface ClassCount {
  slot: string;
  code: string | null;
  pax: number | null;
}

export interface I033 {
  i033_id: number;
  sector_nbr: number;
  version_no: number;
  is_current: boolean;
  created_source: string;
  created_by: string;
  created_at: string;
  source_email_id: number | null;
  is_ex_sector: boolean;
  sent_to_sap_at: string | null;
  classes: ClassCount[];
}

export interface I034 {
  i034_id: number;
  sector_nbr: number;
  class_code: string;
  meal_type: string | null;
  spml_id: string;
  qnty: number;
  pname: string | null;
  meal_nr: string | null;
  txt: string | null;
}

export interface VersionInfo {
  version_no: number;
  is_current: boolean;
  created_source: string;
  created_by: string;
  created_at: string;
  source_email_id: number | null;
}

export interface SectorDetail {
  sector_nbr: number;
  i033: I033;
  i034: I034[];
  versions: VersionInfo[];
}

export interface ReviewItem {
  review_item_id: number;
  error_code: string;
  severity: string;
  blocks_release: boolean;
  email_id: number | null;
  sector_nbr: number | null;
  field_name: string | null;
  text_snippet: string | null;
  message: string;
  created_at: string;
}

export interface SendInfo {
  send_id: number;
  state: string;
  release_mode: string | null;
  decided_by: string;
  decided_at: string;
  i033_file_name: string | null;
  i034_file_name: string | null;
  sent_at: string | null;
  failure_reason: string | null;
}

export interface StageDetail extends FlightRef {
  status: Status;
  plant: Plant;
  state: StageState;
  locked: boolean;
  review_state: ReviewState;
  return_flight_missing: boolean;
  sent_at: string | null;
  return_of: FlightRef | null;
  return_flight: FlightRef | null;
  send: SendInfo | null;
  sectors: SectorDetail[];
  review_items: ReviewItem[];
}

export interface VersionDetail {
  i033: I033;
  i034: I034[];
}

export interface AmfLine {
  amf_line_id: number;
  line_type: "PAX" | "SPML";
  cabin: string;
  source_class: string;
  meal_type: string | null;
  pax_p06h: number | null;
  spml_id: string | null;
  delta_qty: number | null;
}

export interface Amf {
  amf_id: number;
  sector_nbr: number;
  amf_version: number;
  generated_at: string;
  lines: AmfLine[];
}

export interface Email {
  email_id: number;
  sender: string | null;
  subject: string | null;
  received_at: string;
  detected_status: string | null;
  confidence: string | null;
  pipeline_status: string;
  body_preview: string | null;
}

export interface SectorEdit {
  base_version_no: number;
  classes: ClassCount[];
  i034: Omit<I034, "i034_id" | "sector_nbr">[];
}

export interface SaveResult {
  version_no: number;
  warnings: string[];
}

export interface SendResult {
  state: "SENT" | "FAILED";
  failure_reason: string | null;
  warnings: string[];
}

export interface ReturnFlightMapping {
  airline: string;
  return_flt_nbr: string;
  outbound_flt_nbr: string;
  day_offset: number;
  is_active: boolean;
  updated_by?: string;
  updated_at?: string;
}

export interface AirlineSetting {
  airline: string;
  auto_release: boolean;
  auto_release_hold_min: number;
  updated_by?: string;
  updated_at?: string;
}

export interface FlightFilters {
  date_from?: string;
  date_to?: string;
  airline?: string;
  plant?: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "The console server could not be reached. Check the connection and retry.");
  }
  if (!response.ok) {
    let message = `The server answered ${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = (body.detail as ValidationIssue[])
          .map((d) => `${(d.loc ?? []).slice(1).join(" ")}: ${d.msg}`)
          .join("; ");
      }
    } catch {
      // No JSON body: keep the status line as the message.
    }
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const send = <T>(method: string, path: string, body?: unknown) =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const stagePath = (f: FlightRef, status: Status) =>
  `/api/flights/${f.airline}/${f.flt_nbr}/${f.actdate}/stages/${status}`;

export const api = {
  flights: (filters: FlightFilters) => {
    const params = new URLSearchParams(
      Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    return request<FlightSummary[]>(`/api/flights?${params}`);
  },
  stage: (f: FlightRef, status: Status) => request<StageDetail>(stagePath(f, status)),
  version: (f: FlightRef, status: Status, sector: number, version: number) =>
    request<VersionDetail>(`${stagePath(f, status)}/sectors/${sector}/versions/${version}`),
  amf: (f: FlightRef) => request<Amf[]>(`/api/flights/${f.airline}/${f.flt_nbr}/${f.actdate}/amf`),
  email: (id: number) => request<Email>(`/api/emails/${id}`),

  saveSector: (f: FlightRef, status: Status, sector: number, edit: SectorEdit) =>
    send<SaveResult>("PUT", `${stagePath(f, status)}/sectors/${sector}`, edit),
  markReviewed: (f: FlightRef, status: Status) => send<void>("POST", `${stagePath(f, status)}/review`),
  markNotReleased: (f: FlightRef, status: Status) =>
    send<void>("POST", `${stagePath(f, status)}/not-released`),
  sendToSap: (f: FlightRef, status: Status) => send<SendResult>("POST", `${stagePath(f, status)}/send`),
  resolveReviewItem: (id: number, resolution_type: string, remarks: string | null) =>
    send<void>("POST", `/api/review-items/${id}/resolve`, { resolution_type, remarks }),

  returnFlights: () => request<ReturnFlightMapping[]>("/api/admin/return-flights"),
  saveReturnFlight: (m: ReturnFlightMapping) =>
    send<void>("PUT", `/api/admin/return-flights/${m.airline}/${m.return_flt_nbr}`, {
      outbound_flt_nbr: m.outbound_flt_nbr,
      day_offset: m.day_offset,
      is_active: m.is_active,
    }),
  airlineSettings: () => request<AirlineSetting[]>("/api/admin/airline-settings"),
  saveAirlineSetting: (s: AirlineSetting) =>
    send<void>("PUT", `/api/admin/airline-settings/${s.airline}`, {
      auto_release: s.auto_release,
      auto_release_hold_min: s.auto_release_hold_min,
    }),
};
