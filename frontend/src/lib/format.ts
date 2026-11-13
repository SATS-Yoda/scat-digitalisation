import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { FlightRef, Status } from "./api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-13" -> "13 Nov 2026". Parsed by hand: a date has no time zone to shift it. */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]} ${y}`;
}

/** Timestamp in the viewer's local time, 24-hour. A value without a zone is UTC. */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${pad(date.getDate())} ${MONTHS[date.getMonth()]} ${date.getFullYear()} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** Local date and time from epoch milliseconds, 24-hour with seconds: "12 Nov 2026 15:51:10". */
export function formatTimestamp(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${pad(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

/** Local calendar date as "YYYY-MM-DD", `offsetDays` from today. */
export function isoDate(offsetDays = 0, now = new Date()): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const flightName = (f: FlightRef) => `${f.airline} ${f.flt_nbr}`;

export const stageRoute = (f: FlightRef, status: Status) =>
  `/flights/${f.airline}/${f.flt_nbr}/${f.actdate}/${status}`;

/** "+2" / "−1" with a true minus sign, for AMF changes. */
export const signed = (n: number) => (n > 0 ? `+${n}` : `−${Math.abs(n)}`);
