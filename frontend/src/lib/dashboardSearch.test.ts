import { afterEach, describe, expect, it, vi } from "vitest";

import { dashboardPath, rememberDashboardSearch } from "./dashboardSearch";

function fakeStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("dashboardPath", () => {
  it("returns the default view before anything is remembered", () => {
    vi.stubGlobal("sessionStorage", fakeStorage());
    expect(dashboardPath()).toBe("/");
  });

  it("returns the remembered filters", () => {
    vi.stubGlobal("sessionStorage", fakeStorage());
    rememberDashboardSearch("?date_from=2026-03-01&airline=SQ");
    expect(dashboardPath()).toBe("/?date_from=2026-03-01&airline=SQ");
  });

  it("goes back to the default view once the filters are reset", () => {
    vi.stubGlobal("sessionStorage", fakeStorage());
    rememberDashboardSearch("?airline=SQ");
    rememberDashboardSearch("");
    expect(dashboardPath()).toBe("/");
  });

  it("still works when storage is unavailable", () => {
    // In Node there is no sessionStorage at all, which is the same failure.
    expect(() => rememberDashboardSearch("?airline=SQ")).not.toThrow();
    expect(dashboardPath()).toBe("/");
  });
});
