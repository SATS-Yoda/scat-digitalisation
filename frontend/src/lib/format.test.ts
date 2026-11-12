import { expect, test } from "vitest";

import { formatDate, isoDate, signed, stageRoute } from "./format";

test("formats a date without shifting it across time zones", () => {
  expect(formatDate("2026-11-03")).toBe("03 Nov 2026");
});

test("isoDate crosses month and year ends", () => {
  expect(isoDate(1, new Date(2026, 11, 31, 23, 30))).toBe("2027-01-01");
  expect(isoDate(0, new Date(2026, 1, 9))).toBe("2026-02-09");
});

test("signed uses a plus and a true minus", () => {
  expect(signed(2)).toBe("+2");
  expect(signed(-4)).toBe("−4");
});

test("stage route", () => {
  const flight = { airline: "SQ", flt_nbr: "856", actdate: "2026-11-13" };
  expect(stageRoute(flight, "P06H")).toBe("/flights/SQ/856/2026-11-13/P06H");
});
